export interface A2AMessage {
  id: string;
  from: string;
  to: string;
  timestamp: string;
  type: 'request' | 'response' | 'event' | 'heartbeat' | 'discovery';
  payload: unknown;
  correlationId?: string;
  ttl?: number;
}

export interface VesselInfo {
  id: string;
  name: string;
  version: string;
  capabilities: string[];
  lastSeen: string;
  endpoint?: string;
}

export interface ProtocolSpec {
  version: string;
  messageFormats: {
    request: string[];
    response: string[];
    event: string[];
  };
  endpoints: {
    message: string;
    protocol: string;
    spec: string;
    health: string;
  };
  heartbeatInterval: number;
  discoveryInterval: number;
}

export interface Subscription {
  id: string;
  vesselId: string;
  eventTypes: string[];
  expiresAt: string;
}

class A2AProtocol {
  private vessels: Map<string, VesselInfo> = new Map();
  private subscriptions: Map<string, Subscription> = new Map();
  private messageQueue: A2AMessage[] = [];
  
  readonly spec: ProtocolSpec = {
    version: "1.0.0",
    messageFormats: {
      request: ["id", "from", "to", "timestamp", "type", "payload"],
      response: ["id", "from", "to", "timestamp", "type", "payload", "correlationId"],
      event: ["id", "from", "to", "timestamp", "type", "payload"]
    },
    endpoints: {
      message: "/api/message",
      protocol: "/api/protocol",
      spec: "/api/spec",
      health: "/health"
    },
    heartbeatInterval: 30000,
    discoveryInterval: 60000
  };

  processMessage(message: A2AMessage): A2AMessage | null {
    if (!this.validateMessage(message)) {
      return null;
    }

    this.updateVesselPresence(message.from);

    switch (message.type) {
      case 'heartbeat':
        return this.handleHeartbeat(message);
      case 'discovery':
        return this.handleDiscovery(message);
      case 'request':
        return this.handleRequest(message);
      case 'event':
        this.broadcastEvent(message);
        return null;
      default:
        return null;
    }
  }

  private validateMessage(message: A2AMessage): boolean {
    const required = ['id', 'from', 'to', 'timestamp', 'type', 'payload'];
    return required.every(field => field in message);
  }

  private updateVesselPresence(vesselId: string): void {
    const existing = this.vessels.get(vesselId);
    if (existing) {
      existing.lastSeen = new Date().toISOString();
    }
  }

  private handleHeartbeat(message: A2AMessage): A2AMessage {
    return {
      id: crypto.randomUUID(),
      from: 'coordinator',
      to: message.from,
      timestamp: new Date().toISOString(),
      type: 'response',
      payload: { status: 'ack', vessels: Array.from(this.vessels.values()) },
      correlationId: message.id
    };
  }

  private handleDiscovery(message: A2AMessage): A2AMessage {
    const vesselInfo = message.payload as Partial<VesselInfo>;
    if (vesselInfo.id && vesselInfo.name) {
      this.vessels.set(vesselInfo.id, {
        id: vesselInfo.id,
        name: vesselInfo.name,
        version: vesselInfo.version || '1.0.0',
        capabilities: vesselInfo.capabilities || [],
        lastSeen: new Date().toISOString(),
        endpoint: vesselInfo.endpoint
      });
    }

    return {
      id: crypto.randomUUID(),
      from: 'coordinator',
      to: message.from,
      timestamp: new Date().toISOString(),
      type: 'response',
      payload: { registered: true, fleetSize: this.vessels.size },
      correlationId: message.id
    };
  }

  private handleRequest(message: A2AMessage): A2AMessage {
    return {
      id: crypto.randomUUID(),
      from: 'coordinator',
      to: message.from,
      timestamp: new Date().toISOString(),
      type: 'response',
      payload: { processed: true, requestId: message.id },
      correlationId: message.id
    };
  }

  private broadcastEvent(message: A2AMessage): void {
    for (const sub of this.subscriptions.values()) {
      if (sub.eventTypes.includes(message.type)) {
        this.messageQueue.push({
          ...message,
          to: sub.vesselId
        });
      }
    }
  }

  getFleetStatus(): { total: number; active: number } {
    const now = Date.now();
    const activeThreshold = now - this.spec.heartbeatInterval * 2;
    
    let active = 0;
    for (const vessel of this.vessels.values()) {
      if (new Date(vessel.lastSeen).getTime() > activeThreshold) {
        active++;
      }
    }

    return { total: this.vessels.size, active };
  }
}

const protocol = new A2AProtocol();

const htmlResponse = (content: string): Response => {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A2A Protocol - Agent-to-Agent Communication</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root { --dark: #0a0a0f; --accent: #0891b2; --light: #f8fafc; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Inter', sans-serif; 
      background: var(--dark); 
      color: var(--light); 
      line-height: 1.6; 
      min-height: 100vh;
      padding: 20px;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header { text-align: center; padding: 3rem 1rem; border-bottom: 1px solid #1e293b; }
    h1 { font-size: 3.5rem; font-weight: 700; margin-bottom: 1rem; background: linear-gradient(135deg, var(--accent), #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .tagline { font-size: 1.25rem; color: #94a3b8; max-width: 600px; margin: 0 auto 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; padding: 3rem 0; }
    .card { background: #1e1e2f; border-radius: 12px; padding: 2rem; border: 1px solid #334155; transition: transform 0.2s; }
    .card:hover { transform: translateY(-4px); border-color: var(--accent); }
    .card h3 { color: var(--accent); margin-bottom: 1rem; font-size: 1.5rem; }
    .card p { color: #cbd5e1; margin-bottom: 1.5rem; }
    .endpoint { background: #0f172a; padding: 1rem; border-radius: 8px; font-family: monospace; margin: 1rem 0; border-left: 4px solid var(--accent); }
    .status { display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 1.5rem; border-radius: 12px; margin: 2rem 0; }
    .status-item { text-align: center; }
    .status-value { font-size: 2.5rem; font-weight: 700; color: var(--accent); }
    .status-label { color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
    footer { text-align: center; padding: 3rem 1rem; border-top: 1px solid #1e293b; color: #64748b; font-size: 0.9rem; }
    .fleet { color: var(--accent); font-weight: 600; }
    code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; color: #7dd3fc; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>A2A Protocol</h1>
      <p class="tagline">Standardized agent-to-agent communication for distributed vessel networks</p>
    </header>
    
    <div class="status">
      <div class="status-item">
        <div class="status-value" id="fleetTotal">0</div>
        <div class="status-label">Total Vessels</div>
      </div>
      <div class="status-item">
        <div class="status-value" id="fleetActive">0</div>
        <div class="status-label">Active Now</div>
      </div>
      <div class="status-item">
        <div class="status-value">v1.0.0</div>
        <div class="status-label">Protocol Version</div>
      </div>
    </div>
    
    <div class="grid">
      <div class="card">
        <h3>Message Format</h3>
        <p>Structured JSON messages with required fields: <code>id</code>, <code>from</code>, <code>to</code>, <code>timestamp</code>, <code>type</code>, and <code>payload</code>.</p>
        <div class="endpoint">POST /api/message</div>
      </div>
      
      <div class="card">
        <h3>Request/Response</h3>
        <p>Synchronous communication pattern with correlation IDs for tracking request-response pairs across the fleet.</p>
        <div class="endpoint">Type: "request" | "response"</div>
      </div>
      
      <div class="card">
        <h3>Event Subscription</h3>
        <p>Publish-subscribe model for broadcasting events to interested vessels without direct addressing.</p>
        <div class="endpoint">Type: "event"</div>
      </div>
      
      <div class="card">
        <h3>Heartbeat Protocol</h3>
        <p>Regular status updates to maintain vessel presence and detect failures with configurable intervals.</p>
        <div class="endpoint">Type: "heartbeat"</div>
      </div>
      
      <div class="card">
        <h3>Vessel Discovery</h3>
        <p>Automatic registration and discovery of vessels in the network with capability announcements.</p>
        <div class="endpoint">Type: "discovery"</div>
      </div>
      
      <div class="card">
        <h3>API Endpoints</h3>
        <p>RESTful endpoints for protocol interaction, specification, and health monitoring.</p>
        <div class="endpoint">GET /api/protocol</div>
        <div class="endpoint">GET /api/spec</div>
        <div class="endpoint">GET /health</div>
      </div>
    </div>
    
    <footer>
      <p><span class="fleet">A2A Protocol</span> — How vessels talk to each other. Part of the distributed fleet network.</p>
      <p style="margin-top: 0.5rem;">All vessels communicate securely using standardized message formats and patterns.</p>
    </footer>
  </div>
  
  <script>
    async function updateFleetStatus() {
      try {
        const response = await fetch('/api/protocol');
        const data = await response.json();
        document.getElementById('fleetTotal').textContent = data.fleet.total;
        document.getElementById('fleetActive').textContent = data.fleet.active;
      } catch (error) {
        console.log('Status update failed:', error);
      }
    }
    updateFleetStatus();
    setInterval(updateFleetStatus, 10000);
  </script>
</body>
</html>`;
  
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html;charset=UTF-8',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'"
    }
  });
};

const handleRequest = async (request: Request): Promise<Response> => {
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === '/' || path === '/index.html') {
    return htmlResponse('');
  }

  if (path === '/health') {
    return new Response(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/protocol') {
    const fleetStatus = protocol.getFleetStatus();
    return new Response(JSON.stringify({
      protocol: protocol.spec,
      fleet: fleetStatus,
      timestamp: new Date().toISOString()
    }, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/spec') {
    return new Response(JSON.stringify(protocol.spec, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/message' && request.method === 'POST') {
    try {
      const message = await request.json() as A2AMessage;
      const response = protocol.processMessage(message);
      
      if (response) {
        return new Response(JSON.stringify(response), {
          headers: { 'Content-Type': 'application/json' }
        });
      }
      
      return new Response(JSON.stringify({ status: 'processed' }), {
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Invalid message format' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }

  return new Response(JSON.stringify({ error: 'Not found' }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' }
  });
};

export default {
  async fetch(request: Request): Promise<Response> {
    const response = await handleRequest(request);
    
    response.headers.set('X-Frame-Options', 'DENY');
    response.headers.set(
      'Content-Security-Policy',
      "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'"
    );
    
    return response;
  }
};

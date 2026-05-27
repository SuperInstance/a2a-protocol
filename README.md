# A2A Protocol — Agent-to-Agent Communication

Agent-to-agent protocol specification with a **Python library** and **Cloudflare Workers** reference implementation. Enables type-safe, room-based messaging between fleet agents.

## Overview

The A2A protocol provides a message format and routing layer for agents in the SuperInstance fleet. It handles:

- **Message routing** — agents send to specific vessels by ID
- **Discovery** — heartbeat-based vessel registration and last-seen tracking
- **Subscriptions** — agents subscribe to event types on other agents
- **Queue management** — in-memory message queue with TTL support

## Message Format

```typescript
interface A2AMessage {
  id: string;           // Unique message ID
  from: string;        // Source vessel ID
  to: string;          // Target vessel ID (or "broadcast")
  timestamp: string;   // ISO 8601
  type: 'request' | 'response' | 'event' | 'heartbeat' | 'discovery';
  payload: unknown;
  correlationId?: string;  // For correlating request/response
  ttl?: number;           // Time-to-live in seconds
}
```

## Vessel Registry

```typescript
interface VesselInfo {
  id: string;
  name: string;
  version: string;
  capabilities: string[];
  lastSeen: string;
  endpoint?: string;
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/message` | POST | Send a message to a vessel |
| `/api/protocol` | GET | Get protocol version info |
| `/api/spec` | GET | Get full protocol specification |
| `/api/health` | GET | Health check |
| `/api/vessels` | GET | List registered vessels |
| `/api/vessels/:id` | GET | Get vessel info |
| `/api/vessels/:id/subscribe` | POST | Subscribe to vessel events |
| `/api/subscriptions` | GET | List active subscriptions |

## Reference Implementation

The Cloudflare Workers implementation (`src/worker.ts`) provides:

- TypeScript interfaces for all protocol types
- In-memory vessel registry
- Subscription management with expiry
- TTL-based message expiration
- JSON message validation
- CORS and security headers

```typescript
import A2AProtocol from './src/worker';

// Messages are handled via the fetch handler
// POST /api/message — route to specific vessel
// GET /api/vessels — list registered vessels
```

## Usage Example

```typescript
// Send a message via the protocol
const msg: A2AMessage = {
  id: crypto.randomUUID(),
  from: 'oracle1',
  to: 'jetsonclaw1',
  timestamp: new Date().toISOString(),
  type: 'request',
  payload: { action: 'sensor_reading', sensor: 'gps' }
};

// POST to /api/message with JSON body
// Response: { status: 'queued' } or { error: 'Invalid vessel' }
```

## Part of the SuperInstance Fleet

This protocol is used by all SuperInstance agents to communicate. See also:

- [a2a-r-protocol](https://github.com/SuperInstance/a2a-r-protocol) — A2A-R adds QoS, safety-critical coordination, and sensor streaming for real-time robotics
- [fleet-coordinate](https://github.com/SuperInstance/fleet-coordinate) — Laman rigidity + H1 cohomology for fleet structure
- [PLATO](https://github.com/SuperInstance/SuperInstance) — shared knowledge graph for fleet memory

## Python Library

A pure-Python implementation lives under `a2a_protocol/` with zero external dependencies (only `pytest` for dev):

```python
from a2a_protocol import A2AMessage, MessageType, HandshakeManager, Capability, CapabilitySet, AgentRegistry, AgentRecord

# Create a message
msg = A2AMessage.request("agent-a", "agent-b", {"action": "query"})
print(msg.to_dict())

# Declare capabilities
caps = CapabilitySet([Capability("sensor.gps"), Capability("sensor.camera")])

# Handshake between two agents
alice = HandshakeManager(agent_id="alice", local_capabilities=CapabilitySet([Capability("compute.ml")]))
bob   = HandshakeManager(agent_id="bob",   local_capabilities=CapabilitySet([Capability("sensor.gps")]))

hello = alice.hello()            # step 1: alice says hello
hello.recipient = "bob"
caps_msg = bob.handle_hello(hello)  # step 2: bob replies with capabilities
caps_msg.recipient = "alice"
alice.receive_capabilities(caps_msg)  # step 3: alice processes bob's caps
accept = alice.accept()           # step 4: alice accepts
print(alice.result())

# Agent registry
registry = AgentRegistry()
registry.register(AgentRecord(id="bob", name="Bob", capabilities=CapabilitySet([Capability("sensor.gps")])))
results = registry.find_by_capability("sensor.gps")
print([r.id for r in results])  # ['bob']
```

### Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
```

---

*SuperInstance fleet · [Cocapn](https://github.com/SuperInstance/cocapn-ai)*

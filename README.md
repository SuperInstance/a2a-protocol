# a2a-protocol

**Agent-to-Agent communication protocol** — message format, routing, discovery, and subscriptions for fleet agents. Python library with Cloudflare Workers reference implementation.

## What This Gives You

- **Message routing** — send to specific vessels by ID or broadcast
- **Vessel discovery** — heartbeat-based registration and last-seen tracking
- **Subscriptions** — agents subscribe to event types on other agents
- **Queue management** — in-memory message queue with TTL
- **Cloudflare Workers** — reference implementation for edge deployment

## Message Format

```typescript
interface A2AMessage {
  id: string;           // Unique message ID
  from: string;         // Source vessel ID
  to: string;           // Target vessel ID (or "broadcast")
  timestamp: string;    // ISO 8601
  type: 'request' | 'response' | 'event' | 'heartbeat' | 'discovery';
  payload: unknown;
  correlationId?: string;
  ttl?: number;
}
```

## Installation

```bash
pip install a2a-protocol
```

## Quick Start

```python
from a2a_protocol import A2AProtocol, A2AMessage

protocol = A2AProtocol(vessel_id="my-agent")

# Send a message
msg = A2AMessage(
    to="other-agent",
    type="request",
    payload={"action": "analyze", "data": [1, 2, 3]},
)
protocol.send(msg)

# Receive and handle
@protocol.on_message
def handle(msg: A2AMessage):
    print(f"From {msg.from_}: {msg.payload}")
```

## API Endpoints (Cloudflare Workers)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/message` | POST | Send a message |
| `/api/vessels` | GET | List registered vessels |
| `/api/protocol` | GET | Protocol version |
| `/api/health` | GET | Health check |

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## How It Fits

The core messaging layer for the SuperInstance fleet. Extended by `a2a-r-protocol` (reliability), `a2a-adapter` (Google A2A bridge), and `a2a-constraint-protocol` (math exchange).

## License

MIT

"""A2A message types and message data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class MessageType(str, Enum):
    """Supported message types in the A2A protocol."""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    DISCOVERY = "discovery"
    HANDSHAKE = "handshake"
    CAPABILITY = "capability"


@dataclass
class A2AMessage:
    """A single Agent-to-Agent protocol message.

    Attributes:
        id: Unique message identifier (UUID v4).
        sender: Identifier of the sending agent.
        recipient: Identifier of the receiving agent, or ``"broadcast"``.
        type: The message type.
        payload: Arbitrary JSON-serialisable data.
        correlation_id: Optional ID linking a response to its originating request.
        timestamp: ISO 8601 timestamp (UTC).
        ttl: Optional time-to-live in seconds.
    """

    sender: str
    recipient: str
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ttl: Optional[int] = None

    # -- convenience constructors -------------------------------------------

    @classmethod
    def request(
        cls,
        sender: str,
        recipient: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> A2AMessage:
        return cls(
            sender=sender,
            recipient=recipient,
            type=MessageType.REQUEST,
            payload=payload,
            correlation_id=correlation_id,
            ttl=ttl,
        )

    @classmethod
    def response(
        cls,
        sender: str,
        recipient: str,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> A2AMessage:
        return cls(
            sender=sender,
            recipient=recipient,
            type=MessageType.RESPONSE,
            payload=payload,
            correlation_id=correlation_id,
        )

    @classmethod
    def event(
        cls,
        sender: str,
        payload: Dict[str, Any],
        recipient: str = "broadcast",
    ) -> A2AMessage:
        return cls(
            sender=sender,
            recipient=recipient,
            type=MessageType.EVENT,
            payload=payload,
        )

    @classmethod
    def heartbeat(cls, sender: str, recipient: str = "coordinator") -> A2AMessage:
        return cls(
            sender=sender,
            recipient=recipient,
            type=MessageType.HEARTBEAT,
            payload={"status": "alive"},
        )

    @classmethod
    def discovery(
        cls,
        sender: str,
        agent_info: Dict[str, Any],
        recipient: str = "coordinator",
    ) -> A2AMessage:
        return cls(
            sender=sender,
            recipient=recipient,
            type=MessageType.DISCOVERY,
            payload=agent_info,
        )

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
        if self.correlation_id is not None:
            d["correlationId"] = self.correlation_id
        if self.ttl is not None:
            d["ttl"] = self.ttl
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> A2AMessage:
        return cls(
            id=data["id"],
            sender=data["sender"],
            recipient=data["recipient"],
            type=MessageType(data["type"]),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlationId"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            ttl=data.get("ttl"),
        )

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Return True if the message's TTL has elapsed."""
        if self.ttl is None:
            return False
        ts = datetime.fromisoformat(self.timestamp)
        reference = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        elapsed = (reference - ts).total_seconds()
        return elapsed > self.ttl

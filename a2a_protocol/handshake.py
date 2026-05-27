"""Handshake sequence for establishing agent connections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .capability import Capability, CapabilitySet
from .message import A2AMessage, MessageType
from .protocol import ProtocolInfo, ProtocolVersion


class HandshakeState(str, Enum):
    IDLE = "idle"
    HELLO_SENT = "hello_sent"
    CAPABILITIES_EXCHANGED = "capabilities_exchanged"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass
class HandshakeResult:
    """Outcome of a completed handshake."""

    success: bool
    state: HandshakeState
    negotiated_version: Optional[ProtocolVersion] = None
    local_caps: Optional[CapabilitySet] = None
    remote_caps: Optional[CapabilitySet] = None
    rejection_reason: Optional[str] = None


@dataclass
class HandshakeManager:
    """Manages one side of an A2A handshake.

    Typical flow (initiator):
        1. ``hello()`` → send to peer
        2. Receive peer capabilities → ``receive_capabilities()``
        3. ``accept()`` or ``reject()``
    """

    agent_id: str
    protocol_info: ProtocolInfo = field(default_factory=ProtocolInfo)
    local_capabilities: CapabilitySet = field(default_factory=CapabilitySet)
    state: HandshakeState = HandshakeState.IDLE
    remote_capabilities: Optional[CapabilitySet] = None
    negotiated_version: Optional[ProtocolVersion] = None
    _correlation_id: Optional[str] = field(default=None, repr=False)

    # -- initiator side ----------------------------------------------------

    def hello(self) -> A2AMessage:
        """Build and return a hello message to start a handshake."""
        if self.state != HandshakeState.IDLE:
            raise RuntimeError(f"Cannot send hello from state {self.state.value}")

        self._correlation_id = str(uuid.uuid4())
        self.state = HandshakeState.HELLO_SENT
        return A2AMessage(
            sender=self.agent_id,
            recipient="",
            type=MessageType.HANDSHAKE,
            payload={
                "phase": "hello",
                "version": str(self.protocol_info.version),
                "supportedVersions": [
                    str(v) for v in self.protocol_info.supported_versions
                ],
            },
            correlation_id=self._correlation_id,
        )

    def receive_capabilities(self, message: A2AMessage) -> None:
        """Process the peer's capability advertisement."""
        if message.type != MessageType.HANDSHAKE:
            raise ValueError("Expected a HANDSHAKE message")
        phase = message.payload.get("phase")
        if phase != "capabilities":
            raise ValueError(f"Expected phase=capabilities, got {phase!r}")

        caps_data: List[Dict[str, Any]] = message.payload.get("capabilities", [])
        self.remote_capabilities = CapabilitySet(
            [Capability(**c) for c in caps_data]
        )

        ver_str = message.payload.get("version")
        if ver_str:
            self.negotiated_version = ProtocolVersion.parse(ver_str)

        self.state = HandshakeState.CAPABILITIES_EXCHANGED

    def accept(self) -> A2AMessage:
        """Accept the handshake and return a confirmation message."""
        if self.state != HandshakeState.CAPABILITIES_EXCHANGED:
            raise RuntimeError("Cannot accept before capabilities are exchanged")
        self.state = HandshakeState.ACCEPTED
        return A2AMessage(
            sender=self.agent_id,
            recipient="",
            type=MessageType.HANDSHAKE,
            payload={
                "phase": "accept",
                "version": str(
                    self.negotiated_version or self.protocol_info.version
                ),
            },
            correlation_id=self._correlation_id,
        )

    def reject(self, reason: str = "") -> A2AMessage:
        """Reject the handshake."""
        self.state = HandshakeState.REJECTED
        return A2AMessage(
            sender=self.agent_id,
            recipient="",
            type=MessageType.HANDSHAKE,
            payload={"phase": "reject", "reason": reason},
            correlation_id=self._correlation_id,
        )

    # -- responder side ----------------------------------------------------

    def handle_hello(self, message: A2AMessage) -> A2AMessage:
        """Handle an incoming hello; return a capabilities advertisement."""
        if message.payload.get("phase") != "hello":
            raise ValueError("Expected phase=hello")

        self._correlation_id = message.correlation_id

        client_versions: List[str] = message.payload.get("supportedVersions", [])
        result = self.protocol_info.negotiate(client_versions)
        if result is None:
            self.state = HandshakeState.REJECTED
            return A2AMessage(
                sender=self.agent_id,
                recipient=message.sender,
                type=MessageType.HANDSHAKE,
                payload={"phase": "reject", "reason": "no compatible version"},
                correlation_id=self._correlation_id,
            )

        self.negotiated_version = result[0]
        self.state = HandshakeState.HELLO_SENT

        return A2AMessage(
            sender=self.agent_id,
            recipient=message.sender,
            type=MessageType.HANDSHAKE,
            payload={
                "phase": "capabilities",
                "version": str(self.negotiated_version),
                "capabilities": [c.to_dict() for c in self.local_capabilities],
            },
            correlation_id=self._correlation_id,
        )

    # -- result ------------------------------------------------------------

    def result(self) -> HandshakeResult:
        return HandshakeResult(
            success=self.state == HandshakeState.ACCEPTED,
            state=self.state,
            negotiated_version=self.negotiated_version,
            local_caps=self.local_capabilities,
            remote_caps=self.remote_capabilities,
        )

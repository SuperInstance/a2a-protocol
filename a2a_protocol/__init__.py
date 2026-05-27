"""A2A Protocol — Agent-to-Agent communication library.

Provides message formatting, handshake negotiation, capability exchange,
and agent discovery for distributed agent networks.
"""

from .message import A2AMessage, MessageType
from .protocol import ProtocolVersion, ProtocolInfo
from .handshake import HandshakeState, HandshakeResult, HandshakeManager
from .capability import Capability, CapabilitySet, CompatibilityReport
from .registry import AgentRegistry, AgentRecord

__version__ = "1.0.0"

__all__ = [
    "A2AMessage",
    "MessageType",
    "ProtocolVersion",
    "ProtocolInfo",
    "HandshakeState",
    "HandshakeResult",
    "HandshakeManager",
    "Capability",
    "CapabilitySet",
    "CompatibilityReport",
    "AgentRegistry",
    "AgentRecord",
]

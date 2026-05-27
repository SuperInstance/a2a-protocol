"""Protocol version negotiation and specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ProtocolVersion:
    """Semantic version with comparison support."""

    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, version_str: str) -> ProtocolVersion:
        parts = version_str.strip().lstrip("v").split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid version string: {version_str}")
        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2]) if len(parts) > 2 else 0,
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ProtocolVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: object) -> bool:
        return self == other or self < other

    def is_compatible_with(self, other: ProtocolVersion) -> bool:
        """Two versions are compatible if they share the same major version."""
        return self.major == other.major


DEFAULT_PROTOCOL_VERSION = ProtocolVersion(1, 0, 0)

SUPPORTED_VERSIONS: List[ProtocolVersion] = [
    ProtocolVersion(1, 0, 0),
]


@dataclass
class ProtocolInfo:
    """Full protocol specification and metadata."""

    version: ProtocolVersion = field(default_factory=lambda: DEFAULT_PROTOCOL_VERSION)
    supported_versions: List[ProtocolVersion] = field(
        default_factory=lambda: list(SUPPORTED_VERSIONS)
    )
    message_formats: dict[str, list[str]] = field(default_factory=lambda: {
        "request": ["id", "sender", "recipient", "timestamp", "type", "payload"],
        "response": [
            "id",
            "sender",
            "recipient",
            "timestamp",
            "type",
            "payload",
            "correlationId",
        ],
        "event": ["id", "sender", "recipient", "timestamp", "type", "payload"],
    })
    heartbeat_interval: int = 30_000  # ms
    discovery_interval: int = 60_000  # ms

    def negotiate(
        self, client_versions: List[str]
    ) -> Optional[Tuple[ProtocolVersion, str]]:
        """Negotiate the highest mutually-supported version.

        Returns a ``(version, status)`` tuple where *status* is ``"matched"``
        or ``"fallback"`` (a lower compatible version was chosen).  Returns
        ``None`` when no compatible version exists.
        """
        parsed = []
        for v in client_versions:
            try:
                parsed.append(ProtocolVersion.parse(v))
            except ValueError:
                continue

        # Find highest mutually-supported version
        supported_set = {(v.major, v.minor, v.patch): v for v in self.supported_versions}
        best: Optional[ProtocolVersion] = None
        for pv in parsed:
            key = (pv.major, pv.minor, pv.patch)
            if key in supported_set:
                if best is None or pv > best:
                    best = pv

        if best is not None:
            return (best, "matched")

        # Fallback: same major, highest minor
        for pv in sorted(parsed, reverse=True):
            for sv in sorted(self.supported_versions, reverse=True):
                if pv.is_compatible_with(sv):
                    return (sv, "fallback")

        return None

    def to_dict(self) -> dict:
        return {
            "version": str(self.version),
            "supportedVersions": [str(v) for v in self.supported_versions],
            "messageFormats": self.message_formats,
            "heartbeatInterval": self.heartbeat_interval,
            "discoveryInterval": self.discovery_interval,
        }

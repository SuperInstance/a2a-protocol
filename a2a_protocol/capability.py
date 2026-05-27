"""Capability declaration, matching, and compatibility checking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class Capability:
    """A single capability offered by an agent.

    Attributes:
        name: Dotted identifier, e.g. ``"sensor.gps"``.
        version: Semantic version string for this capability.
        params: Optional parameters describing the capability's limits/config.
    """

    name: str
    version: str = "1.0.0"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name, "version": self.version}
        if self.params:
            d["params"] = self.params
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Capability:
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            params=data.get("params", {}),
        )

    def __hash__(self) -> int:
        return hash((self.name, self.version))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Capability):
            return NotImplemented
        return self.name == other.name and self.version == other.version


@dataclass
class CapabilitySet:
    """A collection of capabilities belonging to an agent."""

    capabilities: List[Capability] = field(default_factory=list)

    def __iter__(self):
        return iter(self.capabilities)

    def __len__(self) -> int:
        return len(self.capabilities)

    def __contains__(self, item: str) -> bool:
        return any(c.name == item for c in self.capabilities)

    def add(self, cap: Capability) -> None:
        if cap.name not in self:
            self.capabilities.append(cap)
        else:
            # update existing
            self.capabilities = [
                cap if c.name == cap.name else c for c in self.capabilities
            ]

    def remove(self, name: str) -> None:
        self.capabilities = [c for c in self.capabilities if c.name != name]

    def get(self, name: str) -> Optional[Capability]:
        for c in self.capabilities:
            if c.name == name:
                return c
        return None

    def names(self) -> Set[str]:
        return {c.name for c in self.capabilities}

    def to_list(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.capabilities]


@dataclass(frozen=True)
class CompatibilityReport:
    """Result of comparing two capability sets."""

    local_only: Set[str]
    remote_only: Set[str]
    shared: Set[str]
    compatible: bool

    @property
    def overlap_ratio(self) -> float:
        total = len(self.local_only) + len(self.remote_only) + len(self.shared)
        if total == 0:
            return 1.0
        return len(self.shared) / total


def check_compatibility(
    local: CapabilitySet,
    remote: CapabilitySet,
    required: Optional[Set[str]] = None,
) -> CompatibilityReport:
    """Compare two capability sets.

    If *required* is given, ``compatible`` is ``True`` only when every required
    capability name appears in both sets.
    """
    local_names = local.names()
    remote_names = remote.names()
    shared = local_names & remote_names

    if required is not None:
        compatible = required.issubset(shared)
    else:
        compatible = True

    return CompatibilityReport(
        local_only=local_names - remote_names,
        remote_only=remote_names - local_names,
        shared=shared,
        compatible=compatible,
    )

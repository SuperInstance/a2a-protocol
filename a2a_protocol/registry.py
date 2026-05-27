"""Agent registry for discovering agents and their capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from .capability import Capability, CapabilitySet


@dataclass
class AgentRecord:
    """Stored information about a registered agent."""

    id: str
    name: str
    version: str = "1.0.0"
    capabilities: CapabilitySet = field(default_factory=CapabilitySet)
    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_active(self, timeout_seconds: int = 60) -> bool:
        """Return True if last_seen is within *timeout_seconds* of now."""
        last = datetime.fromisoformat(self.last_seen)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed <= timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities.to_list(),
            "registeredAt": self.registered_at,
            "lastSeen": self.last_seen,
        }
        if self.endpoint:
            d["endpoint"] = self.endpoint
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class AgentRegistry:
    """In-memory registry for tracking known agents."""

    _agents: Dict[str, AgentRecord] = field(default_factory=dict)
    _on_register: Optional[Callable[[AgentRecord], None]] = field(
        default=None, repr=False
    )
    _on_expire: Optional[Callable[[str], None]] = field(default=None, repr=False)

    def register(self, record: AgentRecord) -> AgentRecord:
        """Register or update an agent."""
        if record.id in self._agents:
            # update last_seen
            existing = self._agents[record.id]
            existing.name = record.name
            existing.version = record.version
            existing.capabilities = record.capabilities
            existing.endpoint = record.endpoint or existing.endpoint
            existing.metadata = {**existing.metadata, **record.metadata}
            existing.last_seen = datetime.now(timezone.utc).isoformat()
        else:
            self._agents[record.id] = record
            if self._on_register:
                self._on_register(record)
        return self._agents[record.id]

    def unregister(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.get(agent_id)

    def all_agents(self) -> List[AgentRecord]:
        return list(self._agents.values())

    def active_agents(self, timeout_seconds: int = 60) -> List[AgentRecord]:
        return [a for a in self._agents.values() if a.is_active(timeout_seconds)]

    def find_by_capability(self, capability_name: str) -> List[AgentRecord]:
        return [
            a for a in self._agents.values() if capability_name in a.capabilities
        ]

    def find_by_capabilities(
        self, required: Set[str], match_all: bool = True
    ) -> List[AgentRecord]:
        results: List[AgentRecord] = []
        for a in self._agents.values():
            names = a.capabilities.names()
            if match_all and required.issubset(names):
                results.append(a)
            elif not match_all and required.intersection(names):
                results.append(a)
        return results

    def touch(self, agent_id: str) -> None:
        """Update last_seen timestamp for an agent."""
        rec = self._agents.get(agent_id)
        if rec:
            rec.last_seen = datetime.now(timezone.utc).isoformat()

    def expire(self, timeout_seconds: int = 60) -> List[str]:
        """Remove agents that haven't been seen within *timeout_seconds*.

        Returns list of expired agent IDs.
        """
        expired: List[str] = []
        for aid, rec in list(self._agents.items()):
            if not rec.is_active(timeout_seconds):
                expired.append(aid)
                del self._agents[aid]
                if self._on_expire:
                    self._on_expire(aid)
        return expired

    def size(self) -> int:
        return len(self._agents)

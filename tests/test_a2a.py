"""Tests for the A2A protocol library."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from a2a_protocol import (
    A2AMessage,
    AgentRecord,
    AgentRegistry,
    Capability,
    CapabilitySet,
    CompatibilityReport,
    HandshakeManager,
    HandshakeResult,
    HandshakeState,
    MessageType,
    ProtocolInfo,
    ProtocolVersion,
)
from a2a_protocol.capability import check_compatibility


# ---------------------------------------------------------------------------
# Message tests
# ---------------------------------------------------------------------------


class TestA2AMessage:
    def test_basic_construction(self):
        msg = A2AMessage(
            sender="agent-a",
            recipient="agent-b",
            type=MessageType.REQUEST,
            payload={"action": "ping"},
        )
        assert msg.sender == "agent-a"
        assert msg.recipient == "agent-b"
        assert msg.type == MessageType.REQUEST
        assert msg.payload == {"action": "ping"}
        assert msg.id  # auto-generated UUID
        assert msg.correlation_id is None

    def test_request_factory(self):
        msg = A2AMessage.request("a", "b", {"action": "query"})
        assert msg.type == MessageType.REQUEST
        assert msg.sender == "a"

    def test_response_factory(self):
        msg = A2AMessage.response("b", "a", {"result": 42}, correlation_id="corr-1")
        assert msg.type == MessageType.RESPONSE
        assert msg.correlation_id == "corr-1"

    def test_event_factory(self):
        msg = A2AMessage.event("a", {"temperature": 72.5})
        assert msg.type == MessageType.EVENT
        assert msg.recipient == "broadcast"

    def test_heartbeat_factory(self):
        msg = A2AMessage.heartbeat("agent-x")
        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload == {"status": "alive"}

    def test_discovery_factory(self):
        msg = A2AMessage.discovery(
            "agent-x", {"name": "TestAgent", "capabilities": ["sensor.gps"]}
        )
        assert msg.type == MessageType.DISCOVERY

    def test_to_dict_roundtrip(self):
        original = A2AMessage.request("a", "b", {"key": "val"}, ttl=30)
        d = original.to_dict()
        assert d["type"] == "request"
        assert d["ttl"] == 30
        restored = A2AMessage.from_dict(d)
        assert restored.id == original.id
        assert restored.sender == original.sender
        assert restored.type == MessageType.REQUEST
        assert restored.ttl == 30

    def test_to_dict_optional_fields(self):
        msg = A2AMessage.request("a", "b", {})
        d = msg.to_dict()
        assert "correlationId" not in d
        assert "ttl" not in d

    def test_is_expired_no_ttl(self):
        msg = A2AMessage.request("a", "b", {})
        assert not msg.is_expired()

    def test_is_expired_within_ttl(self):
        msg = A2AMessage.request("a", "b", {}, ttl=60)
        assert not msg.is_expired()

    def test_is_expired_past_ttl(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=120)
        msg = A2AMessage(
            sender="a",
            recipient="b",
            type=MessageType.REQUEST,
            payload={},
            ttl=60,
            timestamp=past.isoformat(),
        )
        assert msg.is_expired()


# ---------------------------------------------------------------------------
# Protocol version tests
# ---------------------------------------------------------------------------


class TestProtocolVersion:
    def test_parse(self):
        v = ProtocolVersion.parse("1.2.3")
        assert v.major == 1 and v.minor == 2 and v.patch == 3

    def test_parse_no_patch(self):
        v = ProtocolVersion.parse("2.1")
        assert v.patch == 0

    def test_parse_v_prefix(self):
        v = ProtocolVersion.parse("v1.0.0")
        assert v.major == 1

    def test_str(self):
        assert str(ProtocolVersion(1, 2, 3)) == "1.2.3"

    def test_comparison(self):
        assert ProtocolVersion(1, 0, 0) < ProtocolVersion(1, 1, 0)
        assert ProtocolVersion(2, 0, 0) > ProtocolVersion(1, 9, 9)
        assert ProtocolVersion(1, 0, 0) <= ProtocolVersion(1, 0, 0)

    def test_compatibility(self):
        assert ProtocolVersion(1, 0, 0).is_compatible_with(ProtocolVersion(1, 5, 0))
        assert not ProtocolVersion(1, 0, 0).is_compatible_with(
            ProtocolVersion(2, 0, 0)
        )

    def test_invalid_version(self):
        with pytest.raises(ValueError):
            ProtocolVersion.parse("invalid")


class TestProtocolInfo:
    def test_negotiate_exact_match(self):
        info = ProtocolInfo()
        result = info.negotiate(["1.0.0"])
        assert result is not None
        assert result[0] == ProtocolVersion(1, 0, 0)
        assert result[1] == "matched"

    def test_negotiate_fallback(self):
        info = ProtocolInfo()
        result = info.negotiate(["1.5.0"])
        assert result is not None
        assert result[1] == "fallback"

    def test_negotiate_incompatible(self):
        info = ProtocolInfo()
        result = info.negotiate(["2.0.0"])
        assert result is None

    def test_negotiate_ignores_invalid(self):
        info = ProtocolInfo()
        result = info.negotiate(["garbage", "1.0.0"])
        assert result is not None

    def test_to_dict(self):
        info = ProtocolInfo()
        d = info.to_dict()
        assert "version" in d
        assert "supportedVersions" in d


# ---------------------------------------------------------------------------
# Capability tests
# ---------------------------------------------------------------------------


class TestCapability:
    def test_basic(self):
        cap = Capability(name="sensor.gps", version="1.0.0")
        assert cap.name == "sensor.gps"

    def test_to_dict_roundtrip(self):
        cap = Capability(name="sensor.lidar", version="2.1.0", params={"hz": 10})
        d = cap.to_dict()
        restored = Capability.from_dict(d)
        assert restored == cap

    def test_equality(self):
        a = Capability("x", "1.0.0")
        b = Capability("x", "1.0.0")
        assert a == b

    def test_hash_set_membership(self):
        a = Capability("x", "1.0.0")
        s = {a}
        assert a in s


class TestCapabilitySet:
    def test_add_and_contains(self):
        cs = CapabilitySet()
        cs.add(Capability("a"))
        assert "a" in cs
        assert "b" not in cs

    def test_add_updates_existing(self):
        cs = CapabilitySet([Capability("a", "1.0.0")])
        cs.add(Capability("a", "2.0.0"))
        assert cs.get("a").version == "2.0.0"
        assert len(cs) == 1

    def test_remove(self):
        cs = CapabilitySet([Capability("a"), Capability("b")])
        cs.remove("a")
        assert "a" not in cs
        assert len(cs) == 1

    def test_names(self):
        cs = CapabilitySet([Capability("a"), Capability("b")])
        assert cs.names() == {"a", "b"}

    def test_to_list(self):
        cs = CapabilitySet([Capability("x", "1.0.0")])
        lst = cs.to_list()
        assert len(lst) == 1
        assert lst[0]["name"] == "x"


class TestCheckCompatibility:
    def test_full_overlap(self):
        local = CapabilitySet([Capability("a"), Capability("b")])
        remote = CapabilitySet([Capability("a"), Capability("b")])
        report = check_compatibility(local, remote)
        assert report.compatible
        assert report.shared == {"a", "b"}
        assert not report.local_only
        assert not report.remote_only

    def test_partial_overlap(self):
        local = CapabilitySet([Capability("a"), Capability("b")])
        remote = CapabilitySet([Capability("b"), Capability("c")])
        report = check_compatibility(local, remote)
        assert report.shared == {"b"}
        assert report.local_only == {"a"}
        assert report.remote_only == {"c"}

    def test_required_unmet(self):
        local = CapabilitySet([Capability("a")])
        remote = CapabilitySet([Capability("a")])
        report = check_compatibility(local, remote, required={"a", "b"})
        assert not report.compatible

    def test_overlap_ratio(self):
        local = CapabilitySet([Capability("a"), Capability("b")])
        remote = CapabilitySet([Capability("a")])
        report = check_compatibility(local, remote)
        assert report.overlap_ratio == 0.5


# ---------------------------------------------------------------------------
# Handshake tests
# ---------------------------------------------------------------------------


class TestHandshakeManager:
    def _make_pair(self):
        alice = HandshakeManager(
            agent_id="alice",
            local_capabilities=CapabilitySet(
                [Capability("compute.ml"), Capability("sensor.camera")]
            ),
        )
        bob = HandshakeManager(
            agent_id="bob",
            local_capabilities=CapabilitySet(
                [Capability("sensor.gps"), Capability("sensor.camera")]
            ),
        )
        return alice, bob

    def test_full_handshake(self):
        alice, bob = self._make_pair()

        # Alice initiates
        hello = alice.hello()
        assert alice.state == HandshakeState.HELLO_SENT

        # Bob responds with capabilities
        hello.recipient = "bob"
        caps_msg = bob.handle_hello(hello)
        assert caps_msg.payload["phase"] == "capabilities"
        assert bob.negotiated_version is not None

        # Alice receives Bob's capabilities
        caps_msg.recipient = "alice"
        alice.receive_capabilities(caps_msg)
        assert alice.state == HandshakeState.CAPABILITIES_EXCHANGED

        # Alice accepts
        accept = alice.accept()
        assert alice.state == HandshakeState.ACCEPTED
        assert accept.payload["phase"] == "accept"

        result = alice.result()
        assert result.success
        assert result.remote_caps is not None
        assert "sensor.gps" in result.remote_caps

    def test_reject_no_version(self):
        info = ProtocolInfo(supported_versions=[])
        bob = HandshakeManager(agent_id="bob", protocol_info=info)
        alice = HandshakeManager(agent_id="alice")
        hello = alice.hello()
        hello.recipient = "bob"
        resp = bob.handle_hello(hello)
        assert resp.payload["phase"] == "reject"

    def test_initiator_reject(self):
        alice = HandshakeManager(agent_id="alice")
        alice.hello()
        # Simulate receiving capabilities
        alice.state = HandshakeState.CAPABILITIES_EXCHANGED
        alice.remote_capabilities = CapabilitySet([Capability("bad")])
        msg = alice.reject("incompatible")
        assert alice.state == HandshakeState.REJECTED
        assert msg.payload["phase"] == "reject"

    def test_cannot_hello_twice(self):
        alice = HandshakeManager(agent_id="alice")
        alice.hello()
        with pytest.raises(RuntimeError):
            alice.hello()

    def test_cannot_accept_without_caps(self):
        alice = HandshakeManager(agent_id="alice")
        with pytest.raises(RuntimeError):
            alice.accept()


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    def _make_record(self, agent_id: str = "agent-1", **kw) -> AgentRecord:
        return AgentRecord(
            id=agent_id, name=kw.get("name", "Test"), **{
                k: v for k, v in kw.items() if k != "name"
            }
        )

    def test_register_and_get(self):
        reg = AgentRegistry()
        rec = self._make_record()
        reg.register(rec)
        assert reg.get("agent-1") is rec

    def test_register_updates_existing(self):
        reg = AgentRegistry()
        reg.register(self._make_record(name="V1"))
        reg.register(self._make_record(name="V2"))
        assert reg.get("agent-1").name == "V2"
        assert reg.size() == 1

    def test_unregister(self):
        reg = AgentRegistry()
        reg.register(self._make_record())
        removed = reg.unregister("agent-1")
        assert removed is not None
        assert reg.get("agent-1") is None

    def test_find_by_capability(self):
        reg = AgentRegistry()
        reg.register(
            self._make_record(
                agent_id="a",
                capabilities=CapabilitySet([Capability("sensor.gps")]),
            )
        )
        reg.register(
            self._make_record(
                agent_id="b",
                capabilities=CapabilitySet([Capability("sensor.camera")]),
            )
        )
        results = reg.find_by_capability("sensor.gps")
        assert len(results) == 1
        assert results[0].id == "a"

    def test_find_by_capabilities_match_all(self):
        reg = AgentRegistry()
        reg.register(
            self._make_record(
                agent_id="a",
                capabilities=CapabilitySet(
                    [Capability("sensor.gps"), Capability("sensor.camera")]
                ),
            )
        )
        reg.register(
            self._make_record(
                agent_id="b",
                capabilities=CapabilitySet([Capability("sensor.gps")]),
            )
        )
        results = reg.find_by_capabilities({"sensor.gps", "sensor.camera"})
        assert len(results) == 1
        assert results[0].id == "a"

    def test_find_by_capabilities_match_any(self):
        reg = AgentRegistry()
        reg.register(
            self._make_record(
                agent_id="a",
                capabilities=CapabilitySet([Capability("sensor.camera")]),
            )
        )
        results = reg.find_by_capabilities(
            {"sensor.gps", "sensor.camera"}, match_all=False
        )
        assert len(results) == 1

    def test_touch(self):
        reg = AgentRegistry()
        reg.register(self._make_record())
        old = reg.get("agent-1").last_seen
        reg.touch("agent-1")
        assert reg.get("agent-1").last_seen >= old

    def test_expire(self):
        reg = AgentRegistry()
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        rec = AgentRecord(id="stale", name="Stale", last_seen=past)
        reg.register(rec)
        reg.register(self._make_record(agent_id="fresh"))
        expired = reg.expire(timeout_seconds=60)
        assert "stale" in expired
        assert reg.size() == 1

    def test_active_agents(self):
        reg = AgentRegistry()
        reg.register(self._make_record(agent_id="alive"))
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        reg.register(AgentRecord(id="dead", name="Dead", last_seen=past))
        active = reg.active_agents(timeout_seconds=60)
        assert len(active) == 1
        assert active[0].id == "alive"

    def test_callbacks(self):
        registered = []
        expired = []
        reg = AgentRegistry(
            _on_register=lambda r: registered.append(r.id),
            _on_expire=lambda aid: expired.append(aid),
        )
        reg.register(self._make_record(agent_id="a"))
        assert "a" in registered
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        reg.register(AgentRecord(id="b", name="B", last_seen=past))
        reg.expire(timeout_seconds=60)
        assert "b" in expired

    def test_agent_record_to_dict(self):
        rec = AgentRecord(id="x", name="X", endpoint="http://localhost:8080")
        d = rec.to_dict()
        assert d["id"] == "x"
        assert d["endpoint"] == "http://localhost:8080"

"""Tests for LocalTransport — file-based message exchange with frontmatter."""

import json

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    Label,
    Policy,
)
from dbp.transport.local import LocalTransport


@pytest.fixture
def boundary():
    return Boundary()


@pytest.fixture
def base_path(tmp_path):
    return tmp_path / "inbox"


@pytest.fixture
def transport(boundary, base_path):
    return LocalTransport(boundary, str(base_path))


@pytest.fixture
def sender():
    return AgentCard(name="alice", clearance=Clearance({"A", "B"}))


@pytest.fixture
def recipient():
    return AgentCard(name="bob", clearance=Clearance({"A"}))


class TestLocalTransportSend:
    """Sending messages via LocalTransport."""

    def test_send_pass_writes_file(self, transport, sender, recipient):
        msg = DBPMessage(id="m1", label=Label({"A"}), origin="alice", payload={"n": 1})
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.PASS
        path = transport.base_path / "m1.md"
        assert path.exists()

    def test_send_block_does_not_write_file(self, transport, sender, recipient):
        msg = DBPMessage(id="leak", label=Label({"secret"}), origin="alice", payload={})
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.BLOCK
        assert not (transport.base_path / "leak.md").exists()

    def test_send_returns_block_result(self, transport, sender, recipient):
        msg = DBPMessage(id="block-test", label=Label({"Z"}), origin="alice", payload={})
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.BLOCK

    def test_send_returns_pass_result(self, transport, sender, recipient):
        msg = DBPMessage(id="pass-test", label=Label({"A"}), origin="alice", payload={})
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.PASS

    def test_send_multiple_messages_only_pass_written(self, transport, sender, recipient):
        msgs = [
            DBPMessage(id="p1", label=Label({"A"}), origin="alice", payload={}),
            DBPMessage(id="b1", label=Label({"Z"}), origin="alice", payload={}),
            DBPMessage(id="p2", label=Label({"A", "B"}), origin="alice", payload={}),
            DBPMessage(id="b2", label=Label({"C"}), origin="alice", payload={}),
        ]
        for m in msgs:
            transport.send(m, sender, recipient)

        written = sorted(f.name for f in transport.base_path.glob("*.md"))
        assert written == ["p1.md", "p2.md"]


class TestLocalTransportReceive:
    """Receiving messages via LocalTransport."""

    def test_receive_returns_only_passing_messages(self, transport, sender, recipient):
        transport.send(DBPMessage(id="m1", label=Label({"A"}), origin="alice", payload={"x": 1}), sender, recipient)
        transport.send(DBPMessage(id="m2", label=Label({"B"}), origin="alice", payload={"x": 2}), sender, recipient)
        transport.send(DBPMessage(id="m3", label=Label({"A", "B"}), origin="alice", payload={"x": 3}), sender, recipient)

        received = transport.receive(recipient)
        ids = [m.id for m in received]
        assert "m1" in ids
        assert "m2" not in ids  # B not in {A}
        # m3: {A, B} vs {A} — ANY policy: PASS (A matches)
        assert "m3" in ids

    def test_receive_empty_when_no_files(self, transport, recipient):
        assert transport.receive(recipient) == []

    def test_receive_empty_when_nothing_passes(self, transport, sender, recipient):
        transport.send(DBPMessage(id="blocked", label=Label({"secret"}), origin="alice", payload={}), sender, recipient)
        received = transport.receive(recipient)
        assert received == []

    def test_receive_skips_malformed_files(self, transport, recipient):
        bad_file = transport.base_path / "bad.md"
        bad_file.write_text("not frontmatter content")
        received = transport.receive(recipient)
        assert received == []

    def test_receive_skips_malformed_frontmatter(self, transport, recipient):
        bad_file = transport.base_path / "bad.md"
        bad_file.write_text("---\nnot yaml\n---\nbody")
        received = transport.receive(recipient)

    def test_receive_skips_files_with_malformed_json_body(self, transport, sender, recipient):
        transport.send(DBPMessage(id="good", label=Label({"A"}), origin="alice", payload={}), sender, recipient)
        bad = transport.base_path / "bad-body.md"
        transport.write_with_frontmatter(
            path=bad,
            label=Label({"A"}),
            policy=Policy.ANY,
            content="not json at all",
        )
        received = transport.receive(recipient)
        ids = [m.id for m in received]
        assert "good" in ids
        assert "bad-body" not in ids

    def test_receive_respects_all_policy(self, transport, sender):
        all_recipient = AgentCard(name="strict", clearance=Clearance({"A"}))

        transport.send(DBPMessage(id="any-ok", label=Label({"A"}), origin="alice", payload={}), sender, all_recipient)
        transport.send(
            DBPMessage(id="all-block", label=Label({"A", "B"}, policy=Policy.ALL), origin="alice", payload={}, policy=Policy.ALL),
            sender, all_recipient,
        )

        received = transport.receive(all_recipient)
        ids = [m.id for m in received]
        assert "any-ok" in ids
        assert "all-block" not in ids


class TestLocalTransportFrontmatter:
    """YAML frontmatter encoding / decoding."""

    def test_written_file_has_frontmatter(self, transport, sender, recipient):
        msg = DBPMessage(id="fm-test", label=Label({"A", "B"}), origin="alice", payload={"key": "val"})
        transport.send(msg, sender, recipient)

        content = (transport.base_path / "fm-test.md").read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "compartments:" in content
        assert "policy:" in content

    def test_frontmatter_contains_compartments(self, transport, sender, recipient):
        msg = DBPMessage(id="cmp-test", label=Label({"A"}), origin="alice", payload={})
        transport.send(msg, sender, recipient)

        content = (transport.base_path / "cmp-test.md").read_text(encoding="utf-8")
        assert '"A"' in content

    def test_frontmatter_contains_policy(self, transport, sender, recipient):
        msg = DBPMessage(id="pol-test", label=Label({"A"}, policy=Policy.ALL), origin="alice", payload={}, policy=Policy.ALL)
        transport.send(msg, sender, recipient)

        content = (transport.base_path / "pol-test.md").read_text(encoding="utf-8")
        assert "policy: all" in content

    def test_read_frontmatter_parses_correctly(self, transport):
        path = transport.base_path / "parse-me.md"
        transport.write_with_frontmatter(
            path=path,
            label=Label({"eng", "hr"}),
            policy=Policy.ANY,
            content="body text",
        )
        fm = transport.read_frontmatter(path)
        assert fm is not None
        assert set(fm["compartments"]) == {"eng", "hr"}
        assert fm["policy"] == "any"

    def test_read_frontmatter_no_frontmatter(self, transport):
        path = transport.base_path / "no-fm.md"
        path.write_text("just text")
        fm = transport.read_frontmatter(path)
        assert fm is None

    def test_read_frontmatter_empty_file(self, transport):
        path = transport.base_path / "empty.md"
        path.write_text("")
        fm = transport.read_frontmatter(path)
        assert fm is None

    def test_roundtrip_via_transport_preserves_payload(self, transport, sender, recipient):
        original_payload = {"user": "alice", "scores": [1, 2, 3], "active": True}
        msg = DBPMessage(id="rt", label=Label({"A"}), origin="alice", payload=original_payload)
        transport.send(msg, sender, recipient)

        received = transport.receive(recipient)
        assert len(received) == 1
        assert received[0].payload == original_payload


class TestLocalTransportEdgeCases:
    """Edge cases for LocalTransport."""

    def test_base_path_created_on_init(self, tmp_path):
        new_path = tmp_path / "new-dir" / "deep"
        transport = LocalTransport(Boundary(), str(new_path))
        assert new_path.exists()

    def test_send_all_policy_block_written_file_not_created(self, transport, sender, recipient):
        msg = DBPMessage(
            id="all-block",
            label=Label({"A", "B"}, policy=Policy.ALL),
            origin="alice",
            payload={},
            policy=Policy.ALL,
        )
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.BLOCK
        assert not (transport.base_path / "all-block.md").exists()

    def test_send_all_policy_pass(self, transport, sender):
        broad_recipient = AgentCard(name="broad", clearance=Clearance({"A", "B", "C"}))
        msg = DBPMessage(
            id="all-pass",
            label=Label({"A", "B"}, policy=Policy.ALL),
            origin="alice",
            payload={},
            policy=Policy.ALL,
        )
        result = transport.send(msg, sender, broad_recipient)
        assert result == BoundaryResult.PASS
        assert (transport.base_path / "all-pass.md").exists()

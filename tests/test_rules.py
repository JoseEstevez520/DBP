"""Integration tests for the 6 DBP rules working in concert."""

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


class TestRule1ReadIn:
    """R1 — Agent only receives data passing boundary check at startup."""

    class LabelledItem:
        def __init__(self, label, content=""):
            self.label = label
            self.content = content

    def test_r1_read_in_filters_blocked_data(self):
        b = Boundary()
        items = [
            self.LabelledItem(Label({"fitness"}), "workout"),
            self.LabelledItem(Label({"finance"}), "salary"),
            self.LabelledItem(Label(set()), "public"),
        ]
        clearance = Clearance({"fitness"})
        allowed = b.read_in(items, clearance)
        contents = [i.content for i in allowed]
        assert "workout" in contents
        assert "public" in contents
        assert "salary" not in contents

    def test_r1_transport_receive_enforces_boundary(self, tmp_path):
        from dbp.transport.local import LocalTransport

        b = Boundary()
        transport = LocalTransport(b, str(tmp_path / "inbox"))

        sender = AgentCard(name="sender", clearance=Clearance({"X", "Y"}))
        recipient = AgentCard(name="recipient", clearance=Clearance({"Y"}))

        pass_msg = DBPMessage(id="pass-1", label=Label({"Y"}), origin="sender", payload={})
        block_msg = DBPMessage(id="block-1", label=Label({"X"}), origin="sender", payload={})

        transport.send(pass_msg, sender, recipient)
        transport.send(block_msg, sender, recipient)

        received = transport.receive(recipient)
        ids = [m.id for m in received]
        assert "pass-1" in ids
        assert "block-1" not in ids


class TestRule2Write:
    """R2 — Agent can only label data with compartments in its own clearance."""

    def test_r2_can_write_respects_clearance(self):
        b = Boundary()
        clearance = Clearance({"A", "B"})
        assert b.can_write(Label({"A"}), clearance) is True
        assert b.can_write(Label({"A", "B"}), clearance) is True
        assert b.can_write(Label({"A", "B", "C"}), clearance) is False
        assert b.can_write(Label({"C"}), clearance) is False

    def test_r2_empty_label_always_writable(self):
        b = Boundary()
        assert b.can_write(Label(set()), Clearance({"anything"})) is True


class TestRule3Crossing:
    """R3 — Boundary check happens BEFORE sending, not after."""

    def test_r3_transport_block_prevents_file_write(self, tmp_path):
        from dbp.transport.local import LocalTransport

        b = Boundary()
        transport = LocalTransport(b, str(tmp_path / "msgs"))

        sender = AgentCard(name="alice", clearance=Clearance({"A", "B"}))
        recipient = AgentCard(name="bob", clearance=Clearance({"C"}))  # no overlap

        msg = DBPMessage(id="leak-test", label=Label({"A"}), origin="alice", payload={})
        result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.BLOCK
        # No file should exist for this message
        assert not (tmp_path / "msgs" / "leak-test.md").exists()

    def test_r3_transport_pass_writes_file(self, tmp_path):
        from dbp.transport.local import LocalTransport

        b = Boundary()
        transport = LocalTransport(b, str(tmp_path / "msgs"))

        sender = AgentCard(name="alice", clearance=Clearance({"A"}))
        recipient = AgentCard(name="bob", clearance=Clearance({"A"}))

        msg = DBPMessage(id="pass-test", label=Label({"A"}), origin="alice", payload={"data": 1})
        result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.PASS
        assert (tmp_path / "msgs" / "pass-test.md").exists()

    def test_r3_http_block_skips_request(self):
        from unittest.mock import patch
        from dbp.transport.http import HTTPTransport

        b = Boundary()
        transport = HTTPTransport(b)

        sender = AgentCard(name="alice", clearance=Clearance({"A"}))
        recipient = AgentCard(name="bob", clearance=Clearance({"C"}), endpoint="http://localhost:9999")

        msg = DBPMessage(id="http-test", label=Label({"A"}), origin="alice", payload={})

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.BLOCK
        mock_urlopen.assert_not_called()


class TestRule4Heritage:
    """R4 — Derived data inherits the union of source labels."""

    def test_r4_heritage_unions_labels(self):
        b = Boundary()
        source_a = Label({"fitness"})
        source_b = Label({"schedule"})
        derived = b.heritage(source_a, source_b)
        assert derived.compartments == frozenset({"fitness", "schedule"})

    def test_r4_heritage_never_less_restricted(self):
        b = Boundary()
        result = b.heritage(Label({"A", "B"}), Label({"C"}))
        assert "A" in result.compartments
        assert "B" in result.compartments
        assert "C" in result.compartments

    def test_r4_heritage_with_empty_labels(self):
        b = Boundary()
        result = b.heritage(Label({"A"}), Label(set()))
        assert result.compartments == frozenset({"A"})


class TestRule5Traceability:
    """R5 — Every boundary check generates a trace record."""

    def test_r5_every_check_adds_trace(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        b.check(Label({"B"}), Clearance({"C"}))
        assert len(b.trace_log) == 2

    def test_r5_trace_has_required_fields(self):
        b = Boundary()
        b.check(Label({"X"}), Clearance({"X"}), data_id="msg-1", origin="alice", destination="bob")
        rec = b.trace_log[0]
        assert rec.timestamp is not None
        assert rec.data_id == "msg-1"
        assert rec.origin == "alice"
        assert rec.destination == "bob"
        assert rec.label.compartments == frozenset({"X"})
        assert rec.result == BoundaryResult.PASS

    def test_r5_trace_log_is_readonly_copy(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        log = b.trace_log
        original_len = len(log)
        log.append("tamper")
        assert len(b.trace_log) == original_len


class TestRule6Opacity:
    """R6 — Agent cannot modify the boundary engine's internal state."""

    def test_r6_no_public_setters_for_trace(self):
        b = Boundary()
        assert not hasattr(b, "set_trace_log")
        assert not hasattr(b, "clear_log")
        assert not hasattr(b, "reset_log")

    def test_r6_trace_log_is_copy_not_reference(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        log = b.trace_log
        log.clear()
        assert len(b.trace_log) == 1

    def test_r6_cannot_modify_trace_records(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        rec = b.trace_log[0]
        with pytest.raises(AttributeError):
            rec.result = BoundaryResult.BLOCK

    def test_r6_no_method_to_clear_boundary_history(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        assert len(b.trace_log) == 1
        from dbp import EmptyClearanceError
        # Ensure there's no reset method
        methods = [m for m in dir(b) if not m.startswith("_")]
        reset_like = [m for m in methods if "reset" in m.lower() or "clear" in m.lower()]
        assert len(reset_like) == 0


class TestAllRulesScenario:
    """All 6 rules working together in a coherent scenario."""

    def test_full_scenario(self):
        b = Boundary()

        coach_clearance = Clearance({"identity", "fitness", "schedule"})
        developer_clearance = Clearance({"identity", "project", "schedule"})

        # --- R2: can_write ---
        assert b.can_write(Label({"fitness", "schedule"}), coach_clearance) is True
        assert b.can_write(Label({"identity", "fitness"}), coach_clearance) is True
        assert b.can_write(Label({"project"}), coach_clearance) is False  # coach doesn't have project

        # --- R1: read_in ---
        coach_data = [
            type("Item", (), {"label": Label({"identity"})})(),
            type("Item", (), {"label": Label({"fitness"})})(),
            type("Item", (), {"label": Label({"secret"})})(),
        ]
        coach_sees = b.read_in(coach_data, coach_clearance)
        assert len(coach_sees) == 2  # identity + fitness, not secret

        # --- R4: heritage ---
        derived = b.heritage(Label({"fitness"}), Label({"schedule"}))
        assert derived.compartments == frozenset({"fitness", "schedule"})

        # --- R3: crossing ---
        result = b.check(derived, developer_clearance, Policy.ANY)
        assert result == BoundaryResult.PASS  # schedule matches

        result = b.check(derived, developer_clearance, Policy.ALL)
        assert result == BoundaryResult.BLOCK  # missing fitness

        # --- R5: traceability ---
        assert len(b.trace_log) >= 4  # multiple checks above

        # --- R6: opacity ---
        log = b.trace_log
        log.append("spoof")
        assert len(b.trace_log) >= 4  # unchanged

"""Hardening tests for type validation, None handling, and edge cases."""

import pytest

from dbp import (
    Boundary,
    BoundaryResult,
    Clearance,
    DBPError,
    InvalidMessageError,
    Label,
    Policy,
)
from dbp.errors import EmptyClearanceError
from dbp.message import DBPMessage


# ---------------------------------------------------------------------------
# 1. boundary.check() — invalid clearance / label type
# ---------------------------------------------------------------------------

class TestBoundaryCheckTypeValidation:

    def test_check_rejects_none_clearance(self):
        b = Boundary()
        with pytest.raises(TypeError, match="clearance must be a Clearance"):
            b.check(Label({"a"}), None)

    def test_check_rejects_non_clearance_object(self):
        b = Boundary()
        with pytest.raises(TypeError, match="clearance must be a Clearance"):
            b.check(Label({"a"}), "not-a-clearance")

    def test_check_rejects_non_clearance_int(self):
        b = Boundary()
        with pytest.raises(TypeError, match="clearance must be a Clearance"):
            b.check(Label({"a"}), 42)

    def test_check_rejects_non_clearance_list(self):
        b = Boundary()
        with pytest.raises(TypeError, match="clearance must be a Clearance"):
            b.check(Label({"a"}), [1, 2, 3])

    def test_check_rejects_none_label(self):
        b = Boundary()
        clr = Clearance({"x"})
        with pytest.raises(TypeError, match="label must be a Label"):
            b.check(None, clr)

    def test_check_rejects_non_label_object(self):
        b = Boundary()
        clr = Clearance({"x"})
        with pytest.raises(TypeError, match="label must be a Label"):
            b.check("not-a-label", clr)


# ---------------------------------------------------------------------------
# 2. Label — rejection of non-string compartments
# ---------------------------------------------------------------------------

class TestLabelCompartmentTypes:

    def test_label_rejects_none_in_compartments(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label([None, "a"])

    def test_label_rejects_int_in_compartments(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label({"a", 1})

    def test_label_rejects_float_in_compartments(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label(["a", 3.14])

    def test_label_rejects_bool_in_compartments(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label(["a", True])

    def test_label_rejects_bytes_in_compartments(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label([b"bytes"])

    def test_label_rejects_mixed_bad_types(self):
        with pytest.raises(TypeError, match="Compartment values must be strings"):
            Label([None, 42, 3.14, "valid"])

    def test_label_accepts_only_strings(self):
        label = Label(["a", "b", "c"])
        assert label.compartments == frozenset({"a", "b", "c"})

    def test_label_accepts_empty_string_compartment(self):
        label = Label([""])
        assert "" in label.compartments


# ---------------------------------------------------------------------------
# 3. DBPMessage — origin type validation
# ---------------------------------------------------------------------------

class TestMessageOriginType:

    def test_message_rejects_int_origin(self):
        with pytest.raises(InvalidMessageError, match="origin must be a string"):
            DBPMessage(id="x", label=Label({"a"}), origin=123, payload={})

    def test_message_rejects_none_origin(self):
        with pytest.raises(InvalidMessageError, match="origin must be a string"):
            DBPMessage(id="x", label=Label({"a"}), origin=None, payload={})

    def test_message_rejects_list_origin(self):
        with pytest.raises(InvalidMessageError, match="origin must be a string"):
            DBPMessage(id="x", label=Label({"a"}), origin=["a"], payload={})

    def test_message_rejects_empty_string_origin(self):
        with pytest.raises(InvalidMessageError, match="origin is required"):
            DBPMessage(id="x", label=Label({"a"}), origin="", payload={})

    def test_message_rejects_blank_string_origin(self):
        with pytest.raises(InvalidMessageError, match="origin is required"):
            DBPMessage(id="x", label=Label({"a"}), origin="   ", payload={})


# ---------------------------------------------------------------------------
# 4. LocalTransport — empty compartments in frontmatter
# ---------------------------------------------------------------------------

class TestLocalTransportEmptyCompartments:
    """compartments: [] in frontmatter should not break anything."""

    def test_write_and_read_with_empty_compartments(self, tmp_path):
        from dbp import AgentCard
        from dbp.transport.local import LocalTransport

        transport = LocalTransport(Boundary(), tmp_path)
        sender = AgentCard(name="alice", clearance=Clearance({"x"}))
        recipient = AgentCard(name="bob", clearance=Clearance({"x"}))

        label = Label(set())  # empty label
        msg = DBPMessage(
            id="test-001",
            label=label,
            origin="alice",
            payload={"key": "value"},
        )
        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.PASS

        # Now read it back
        received = transport.receive(recipient)
        assert len(received) == 1
        assert received[0].id == "test-001"

    def test_read_frontmatter_with_empty_compartments(self, tmp_path):
        from dbp.transport.local import LocalTransport

        f = tmp_path / "msg.md"
        f.write_text("---\ncompartments: []\npolicy: any\n---\n\n{}", encoding="utf-8")
        fm = LocalTransport.read_frontmatter(f)
        assert fm is not None
        assert fm.get("compartments") == []


# ---------------------------------------------------------------------------
# 5. transport/__init__ exports
# ---------------------------------------------------------------------------

class TestTransportExports:

    def test_transport_base_importable(self):
        from dbp.transport import Transport, HTTPTransport, LocalTransport
        assert Transport is not None
        assert HTTPTransport is not None
        assert LocalTransport is not None

    def test_transport_all_defined(self):
        from dbp.transport import __all__
        assert "Transport" in __all__
        assert "HTTPTransport" in __all__
        assert "LocalTransport" in __all__


# ---------------------------------------------------------------------------
# 6. Boundary.heritage() — zero-arg rejection
# ---------------------------------------------------------------------------

class TestHeritageValidation:

    def test_heritage_zero_args_returns_empty_label(self):
        b = Boundary()
        result = b.heritage()
        assert result.compartments == frozenset()

    def test_heritage_rejects_non_label(self):
        b = Boundary()
        with pytest.raises(TypeError, match="must be a Label"):
            b.heritage("not-a-label")

    def test_heritage_rejects_mixed_valid_and_invalid(self):
        b = Boundary()
        with pytest.raises(TypeError, match="must be a Label"):
            b.heritage(Label({"a"}), "bad", Label({"c"}))

    def test_heritage_rejects_none(self):
        b = Boundary()
        with pytest.raises(TypeError, match="must be a Label"):
            b.heritage(None)

    def test_heritage_one_valid_label_still_works(self):
        b = Boundary()
        result = b.heritage(Label({"a"}))
        assert result.compartments == frozenset({"a"})


# ---------------------------------------------------------------------------
# 7. Escalation GRANT adds a PASS trace record
# ---------------------------------------------------------------------------

class TestEscalationTrace:

    def test_grant_creates_pass_trace(self):
        from dbp import AgentCard, EscalationResult

        b = Boundary()
        agent = AgentCard(name="worker", clearance=Clearance({"x"}))
        parent = AgentCard(name="supervisor", clearance=Clearance({"x", "y", "z"}))
        label = Label({"y", "z"})

        result = b.escalate(agent, label, "need access", parent)
        assert result == EscalationResult.GRANT

        traces = b.trace_log
        assert len(traces) == 2

        # First record = escalation request (BLOCK with __escalation__)
        assert traces[0].result == BoundaryResult.BLOCK
        assert traces[0].clearance.compartments == frozenset({"__escalation__"})

        # Second record = effective override (PASS with parent's real clearance)
        assert traces[1].result == BoundaryResult.PASS
        assert traces[1].clearance is parent.clearance
        assert traces[1].destination == parent.name
        assert traces[1].origin == agent.name

    def test_deny_does_not_create_pass_trace(self):
        from dbp import AgentCard, EscalationResult

        b = Boundary()
        agent = AgentCard(name="worker", clearance=Clearance({"x"}))
        parent = AgentCard(name="supervisor", clearance=Clearance({"a"}))
        label = Label({"y"})

        result = b.escalate(agent, label, "need access", parent)
        assert result == EscalationResult.DENY
        assert len(b.trace_log) == 1

    def test_human_pending_does_not_create_pass_trace(self):
        from dbp import AgentCard, EscalationResult

        b = Boundary()
        agent = AgentCard(name="worker", clearance=Clearance({"x"}))
        label = Label({"y"})

        result = b.escalate(agent, label, "need access")
        assert result == EscalationResult.ESCALATE
        assert len(b.trace_log) == 1


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestAdditionalEdgeCases:

    def test_check_with_non_label_policy_override(self):
        b = Boundary()
        clr = Clearance({"x"})
        with pytest.raises(TypeError, match="label must be a Label"):
            b.check(object(), clr, policy=Policy.ANY)

    def test_can_write_with_empty_clearance_raises_on_construction(self):
        with pytest.raises(EmptyClearanceError):
            Clearance(set())

    def test_read_in_handles_items_without_label_attr(self):
        b = Boundary()
        clr = Clearance({"x"})
        items = [{"not": "a labelled item"}]
        with pytest.raises(AttributeError):
            b.read_in(items, clr)

    def test_escalate_rejects_non_agentcard(self):
        from dbp import AgentCard

        b = Boundary()
        label = Label({"a"})
        with pytest.raises(AttributeError):  # will fail accessing .name / .clearance
            b.escalate("not-an-agent", label, "reason")

    def test_escalate_rejects_non_label(self):
        from dbp import AgentCard

        b = Boundary()
        agent = AgentCard(name="a", clearance=Clearance({"x"}))
        with pytest.raises(AttributeError):  # will fail accessing .compartments
            b.escalate(agent, "not-a-label", "reason")

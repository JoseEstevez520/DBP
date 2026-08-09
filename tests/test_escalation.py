"""Tests for R7 escalation -- EscalationResult, agent card, and Boundary.escalate()."""

import pytest

from dbp import (
    AgentCard,
    Boundary,
    Clearance,
    EscalationError,
    EscalationResult,
    Label,
)


class TestEscalationResult:
    def test_escalation_result_values(self):
        assert EscalationResult.GRANT.value == "grant"
        assert EscalationResult.DENY.value == "deny"
        assert EscalationResult.ESCALATE.value == "escalate"


class TestAgentCardEscalation:
    def test_escalation_parent_default_none(self):
        card = AgentCard(name="a", clearance=Clearance({"x"}))
        assert card.escalation_parent is None

    def test_escalation_parent_explicit(self):
        card = AgentCard(
            name="a",
            clearance=Clearance({"x"}),
            escalation_parent="supervisor",
        )
        assert card.escalation_parent == "supervisor"

    def test_to_dict_includes_escalation_parent(self):
        card = AgentCard(
            name="a",
            clearance=Clearance({"x"}),
            escalation_parent="supervisor",
        )
        d = card.to_dict()
        assert d["escalation_parent"] == "supervisor"

    def test_to_dict_omits_when_none(self):
        card = AgentCard(name="a", clearance=Clearance({"x"}))
        d = card.to_dict()
        assert "escalation_parent" not in d

    def test_from_dict_with_escalation_parent(self):
        data = {
            "name": "a",
            "clearance": ["x"],
            "escalation_parent": "supervisor",
        }
        card = AgentCard.from_dict(data)
        assert card.escalation_parent == "supervisor"

    def test_from_dict_without_escalation_parent(self):
        data = {"name": "a", "clearance": ["x"]}
        card = AgentCard.from_dict(data)
        assert card.escalation_parent is None


class TestBoundaryEscalate:
    def test_escalate_to_parent_with_matching_clearance_grants(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"engineering"}),
        )
        parent = AgentCard(
            name="supervisor",
            clearance=Clearance({"engineering", "hr"}),
        )
        label = Label({"hr"})

        result = boundary.escalate(agent, label, "need hr data for project", parent)
        assert result == EscalationResult.GRANT

    def test_escalate_to_parent_without_clearance_denies(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"engineering"}),
        )
        parent = AgentCard(
            name="supervisor",
            clearance=Clearance({"engineering"}),
        )
        label = Label({"hr"})

        result = boundary.escalate(agent, label, "need hr data", parent)
        assert result == EscalationResult.DENY

    def test_escalate_without_parent_escalates_to_human(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"engineering"}),
        )
        label = Label({"hr"})

        result = boundary.escalate(agent, label, "need help")
        assert result == EscalationResult.ESCALATE

    def test_escalate_with_parent_grant_adds_to_trace_log(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"x"}),
        )
        parent = AgentCard(
            name="supervisor",
            clearance=Clearance({"x", "y"}),
        )
        label = Label({"y"})

        before = len(boundary.trace_log)
        boundary.escalate(agent, label, "please", parent)
        assert len(boundary.trace_log) == before + 2

    def test_escalate_deny_adds_to_trace_log(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"x"}),
        )
        parent = AgentCard(
            name="supervisor",
            clearance=Clearance({"x"}),
        )
        label = Label({"y"})

        before = len(boundary.trace_log)
        boundary.escalate(agent, label, "please", parent)
        assert len(boundary.trace_log) == before + 1

    def test_escalate_to_human_adds_to_trace_log(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"x"}),
        )
        label = Label({"y"})

        before = len(boundary.trace_log)
        boundary.escalate(agent, label, "help")
        assert len(boundary.trace_log) == before + 1

    def test_escalate_only_possible_after_block(self):
        boundary = Boundary()
        agent = AgentCard(
            name="worker",
            clearance=Clearance({"engineering"}),
        )
        parent = AgentCard(
            name="supervisor",
            clearance=Clearance({"engineering", "hr"}),
        )
        label = Label({"hr"})

        # First verify it would be BLOCKed
        block = boundary.check(label, agent.clearance)
        assert block.value == "block"

        # Then escalate
        result = boundary.escalate(agent, label, "need for project", parent)
        assert result == EscalationResult.GRANT


class TestEscalationScenario:
    def test_chain_worker_to_supervisor_to_human(self):
        boundary = Boundary()

        worker = AgentCard(
            name="worker",
            clearance=Clearance({"engineering"}),
            escalation_parent="supervisor",
        )
        supervisor = AgentCard(
            name="supervisor",
            clearance=Clearance({"engineering", "finance"}),
            escalation_parent="human",
        )
        label = Label({"finance"})

        # Worker tries to access finance data
        block = boundary.check(label, worker.clearance)
        assert block.value == "block"

        # Escalate to supervisor
        r1 = boundary.escalate(worker, label, "need budget data", supervisor)
        assert r1 == EscalationResult.GRANT

        # Supervisor has it, so GRANT works
        supervisor_check = boundary.check(label, supervisor.clearance)
        assert supervisor_check.value == "pass"

    def test_chain_longer_buffer(self):
        boundary = Boundary()

        agent = AgentCard(name="agent", clearance=Clearance({"a"}))
        parent = AgentCard(name="parent", clearance=Clearance({"a", "b"}))
        grandparent = AgentCard(name="grandparent", clearance=Clearance({"a", "b", "c"}))
        label = Label({"c"})

        # Agent -> Parent: parent doesn't have 'c'
        r1 = boundary.escalate(agent, label, "need c", parent)
        assert r1 == EscalationResult.DENY

        # Agent -> Grandparent: grandparent has 'c'
        r2 = boundary.escalate(agent, label, "need c", grandparent)
        assert r2 == EscalationResult.GRANT


class TestEscalationChain:
    """R7 hierarchical escalation: escalate_chain walks the parent hierarchy."""

    def _registry(self):
        from dbp import Registry

        reg = Registry()
        # button -> form -> main. Only main is cleared for "pii".
        button = AgentCard(
            name="button",
            clearance=Clearance({"ui"}),
            escalation_parent="form",
        )
        form = AgentCard(
            name="form",
            clearance=Clearance({"ui", "form-state"}),
            escalation_parent="main",
        )
        main = AgentCard(
            name="main",
            clearance=Clearance({"ui", "form-state", "pii"}),
            # no escalation_parent -> human is the final authority
        )
        reg.register(button)
        reg.register(form)
        reg.register(main)
        return reg, button, form, main

    def test_chain_walks_up_to_first_capable_authority(self):
        boundary = Boundary()
        reg, button, form, main = self._registry()
        label = Label({"pii"})

        outcome = boundary.escalate_chain(button, label, "need to know if user can pay", reg)

        assert outcome.result == EscalationResult.GRANT
        assert outcome.authority == "main"          # form could not decide; main could
        assert outcome.chain == ("form", "main")    # walked form first, then main

    def test_derived_answer_never_reveals_raw_data(self):
        boundary = Boundary()
        reg, button, form, main = self._registry()
        label = Label({"pii"})

        # The authority answers with a boundary-safe derivative labelled "derived",
        # which the requester (button, clearance {"ui"}) is NOT blocked from because
        # an empty/derived label passes. Here we hand back a public boolean.
        def derive(authority, blocked_label):
            return ({"can_pay": True}, Label(set()))  # empty label = unrestricted

        outcome = boundary.escalate_chain(
            button, label, "can the user pay?", reg, derive=derive
        )

        assert outcome.result == EscalationResult.GRANT_DERIVED
        assert outcome.authority == "main"
        assert outcome.derived == {"can_pay": True}
        # The raw pii label never crosses; only the derived artifact is returned.
        assert outcome.derived_label is not None and outcome.derived_label.is_empty()

    def test_derived_that_would_still_leak_is_denied(self):
        boundary = Boundary()
        reg, button, form, main = self._registry()
        label = Label({"pii"})

        # A mis-derivation: the authority tries to hand back data still labelled pii,
        # which the requester is not cleared for. This must be refused, not leaked.
        def bad_derive(authority, blocked_label):
            return ({"card": "1234"}, Label({"pii"}))

        outcome = boundary.escalate_chain(
            button, label, "give me everything", reg, derive=bad_derive
        )

        assert outcome.result == EscalationResult.DENY
        assert outcome.authority == "main"

    def test_chain_reaching_top_without_authority_goes_to_human(self):
        boundary = Boundary()
        from dbp import Registry

        reg = Registry()
        # Nobody in the chain is cleared for "secret"; top has no parent -> human.
        a = AgentCard(name="a", clearance=Clearance({"ui"}), escalation_parent="b")
        b = AgentCard(name="b", clearance=Clearance({"ui"}))  # top, no parent
        reg.register(a)
        reg.register(b)

        outcome = boundary.escalate_chain(a, Label({"secret"}), "need secret", reg)

        assert outcome.result == EscalationResult.ESCALATE  # human backstop
        assert outcome.authority is None

    def test_missing_parent_in_registry_raises(self):
        boundary = Boundary()
        from dbp import EscalationError, Registry

        reg = Registry()
        orphan = AgentCard(
            name="orphan", clearance=Clearance({"ui"}), escalation_parent="ghost"
        )
        reg.register(orphan)

        with pytest.raises(EscalationError):
            boundary.escalate_chain(orphan, Label({"pii"}), "help", reg)

    def test_cycle_is_guarded(self):
        boundary = Boundary()
        from dbp import EscalationError, Registry

        reg = Registry()
        a = AgentCard(name="a", clearance=Clearance({"ui"}), escalation_parent="b")
        b = AgentCard(name="b", clearance=Clearance({"ui"}), escalation_parent="a")
        reg.register(a)
        reg.register(b)

        with pytest.raises(EscalationError):
            boundary.escalate_chain(a, Label({"pii"}), "loop", reg, max_hops=8)

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

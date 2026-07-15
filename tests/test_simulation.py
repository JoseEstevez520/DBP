"""Real-world 'day in the life' simulation of DBP in a company with 12 agents."""

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    EscalationResult,
    Label,
    Policy,
)
from dbp.transport.local import LocalTransport


class TestDayInTheLife:
    """A full-day simulation with 12 agents, 5 rounds representing a work day."""

    @pytest.fixture
    def boundary(self):
        return Boundary()

    @pytest.fixture
    def agents(self):
        executive = AgentCard(
            name="executive",
            clearance=Clearance(
                {"engineering", "hr", "finance", "strategy", "infra", "security"}
            ),
            description="Executive with all clearances",
        )
        cto = AgentCard(
            name="cto",
            clearance=Clearance({"engineering", "strategy"}),
            description="Chief Technology Officer",
            escalation_parent="executive",
        )
        eng_manager = AgentCard(
            name="engineering_manager",
            clearance=Clearance({"engineering"}),
            description="Engineering Manager",
            escalation_parent="cto",
        )
        hr_manager = AgentCard(
            name="hr_manager",
            clearance=Clearance({"hr"}),
            description="HR Manager",
            escalation_parent="executive",
        )
        finance_manager = AgentCard(
            name="finance_manager",
            clearance=Clearance({"finance"}),
            description="Finance Manager",
            escalation_parent="cto",
        )
        tech_lead = AgentCard(
            name="tech_lead",
            clearance=Clearance({"engineering", "infra"}),
            description="Tech Lead",
            escalation_parent="cto",
        )
        engineer_1 = AgentCard(
            name="engineer_1",
            clearance=Clearance({"engineering"}),
            description="Software Engineer",
            escalation_parent="engineering_manager",
        )
        engineer_2 = AgentCard(
            name="engineer_2",
            clearance=Clearance({"engineering"}),
            description="Software Engineer",
            escalation_parent="engineering_manager",
        )
        engineer_3 = AgentCard(
            name="engineer_3",
            clearance=Clearance({"engineering"}),
            description="Software Engineer",
            escalation_parent="engineering_manager",
        )
        hr_specialist = AgentCard(
            name="hr_specialist",
            clearance=Clearance({"hr"}),
            description="HR Specialist",
            escalation_parent="hr_manager",
        )
        finance_analyst = AgentCard(
            name="finance_analyst",
            clearance=Clearance({"finance"}),
            description="Finance Analyst",
            escalation_parent="finance_manager",
        )
        devops = AgentCard(
            name="devops",
            clearance=Clearance({"engineering", "infra"}),
            description="DevOps Engineer",
            escalation_parent="tech_lead",
        )
        return {
            "executive": executive,
            "cto": cto,
            "engineering_manager": eng_manager,
            "hr_manager": hr_manager,
            "finance_manager": finance_manager,
            "tech_lead": tech_lead,
            "engineer_1": engineer_1,
            "engineer_2": engineer_2,
            "engineer_3": engineer_3,
            "hr_specialist": hr_specialist,
            "finance_analyst": finance_analyst,
            "devops": devops,
        }

    # ------------------------------------------------------------------
    # Round 1 — Morning standup
    # ------------------------------------------------------------------

    def test_round_1_morning_standup(self, boundary, agents, tmp_path):
        """Morning: engineering standup with engineers reporting to manager."""
        eng_label = Label({"engineering"})
        transport = LocalTransport(boundary, str(tmp_path / "standup"))

        # Engineers send status updates to engineering manager → PASS
        for name in ["engineer_1", "engineer_2", "engineer_3"]:
            msg = DBPMessage(
                id=f"status-{name}",
                label=eng_label,
                origin=name,
                payload={"status": "all good", "tickets": 3},
            )
            result = transport.send(msg, agents[name], agents["engineering_manager"])
            assert result == BoundaryResult.PASS, f"{name} status to manager should PASS"

        # One engineer accidentally sends engineering data to HR → BLOCK
        msg = DBPMessage(
            id="accidental-hr",
            label=eng_label,
            origin="engineer_1",
            payload={"ticket": "SECRET-123", "fix": "patch-456"},
        )
        result = transport.send(msg, agents["engineer_1"], agents["hr_specialist"])
        assert result == BoundaryResult.BLOCK, "engineering data to HR should BLOCK"

        # Engineer escalates to engineering manager → GRANT
        result = boundary.escalate(
            agents["engineer_1"],
            eng_label,
            "accidentally sent engineering data to HR",
            agents["engineering_manager"],
        )
        assert result == EscalationResult.GRANT

        # Verify files: 3 status files exist, accidental not written
        assert (transport.base_path / "status-engineer_1.md").exists()
        assert (transport.base_path / "status-engineer_2.md").exists()
        assert (transport.base_path / "status-engineer_3.md").exists()
        assert not (transport.base_path / "accidental-hr.md").exists()

        # Trace log: 3 sends + 1 block + 2 escalation records
        assert len(boundary.trace_log) >= 6

    # ------------------------------------------------------------------
    # Round 2 — Mid-morning cross-dept
    # ------------------------------------------------------------------

    def test_round_2_mid_morning_cross_dept(self, boundary, agents, tmp_path):
        """Cross-department: HR sends candidate list to Engineering Manager."""
        transport = LocalTransport(boundary, str(tmp_path / "cross-dept"))

        candidate_label = Label({"hr", "engineering"})

        # ANY policy → PASS (engineering in label matches eng manager's clearance)
        msg_any = DBPMessage(
            id="candidates-any",
            label=candidate_label,
            origin="hr_manager",
            payload={"candidates": ["Alice", "Bob"]},
            policy=Policy.ANY,
        )
        result = transport.send(
            msg_any, agents["hr_manager"], agents["engineering_manager"]
        )
        assert result == BoundaryResult.PASS, "ANY policy should PASS"

        # ALL policy → BLOCK (hr compartment missing from engineering manager)
        msg_all = DBPMessage(
            id="candidates-all",
            label=candidate_label,
            origin="hr_manager",
            payload={"candidates": ["Alice", "Bob"]},
            policy=Policy.ALL,
        )
        result = transport.send(
            msg_all, agents["hr_manager"], agents["engineering_manager"]
        )
        assert result == BoundaryResult.BLOCK, "ALL policy should BLOCK (missing hr)"

        assert (transport.base_path / "candidates-any.md").exists()
        assert not (transport.base_path / "candidates-all.md").exists()

    # ------------------------------------------------------------------
    # Round 3 — Pre-lunch budget
    # ------------------------------------------------------------------

    def test_round_3_pre_lunch_budget(self, boundary, agents, tmp_path):
        """Budget report from Finance to CTO, escalated to Executive."""
        transport = LocalTransport(boundary, str(tmp_path / "budget"))

        budget_label = Label({"finance", "engineering"}, policy=Policy.ALL)

        # Finance sends budget to CTO → BLOCK (CTO missing finance)
        msg = DBPMessage(
            id="budget-report",
            label=budget_label,
            origin="finance_analyst",
            payload={"q1": 500000, "q2": 750000},
            policy=Policy.ALL,
        )
        result = transport.send(msg, agents["finance_analyst"], agents["cto"])
        assert result == BoundaryResult.BLOCK, "CTO missing finance → BLOCK"

        # CTO escalates to Executive → GRANT
        result = boundary.escalate(
            agents["cto"],
            budget_label,
            "need budget data for quarterly planning",
            agents["executive"],
        )
        assert result == EscalationResult.GRANT

        assert not (transport.base_path / "budget-report.md").exists()

    # ------------------------------------------------------------------
    # Round 4 — Afternoon incident
    # ------------------------------------------------------------------

    def test_round_4_afternoon_incident(self, boundary, agents, tmp_path):
        """Incident: DevOps needs database credentials, escalates up the chain."""
        transport = LocalTransport(boundary, str(tmp_path / "incident"))

        db_label = Label({"infra", "security"}, policy=Policy.ALL)

        # A vault-like agent sends DB credentials labeled [infra, security]
        vault = AgentCard(
            name="vault",
            clearance=Clearance({"infra", "security", "engineering"}),
        )
        msg = DBPMessage(
            id="db-credentials",
            label=db_label,
            origin="vault",
            payload={"host": "db.internal", "port": 5432},
            policy=Policy.ALL,
        )
        # Devops only has {engineering, infra} — missing security → BLOCK
        result = transport.send(msg, vault, agents["devops"])
        assert result == BoundaryResult.BLOCK, "DevOps missing security → BLOCK"

        # Escalation chain: DevOps → TechLead → CTO → Executive
        r = boundary.escalate(
            agents["devops"], db_label, "need DB access for outage", agents["tech_lead"]
        )
        assert r == EscalationResult.DENY, "TechLead missing security → DENY"

        r = boundary.escalate(
            agents["devops"], db_label, "need DB access for outage", agents["cto"]
        )
        assert r == EscalationResult.DENY, "CTO missing security → DENY"

        r = boundary.escalate(
            agents["devops"], db_label, "need DB access for outage", agents["executive"]
        )
        assert r == EscalationResult.GRANT, "Executive has all → GRANT"

        assert not (transport.base_path / "db-credentials.md").exists()

    # ------------------------------------------------------------------
    # Round 5 — Evening report
    # ------------------------------------------------------------------

    def test_round_5_evening_report(self, boundary, agents, tmp_path):
        """End-of-day: all departments send daily summaries to Executive."""
        transport = LocalTransport(boundary, str(tmp_path / "reports"))

        reports = [
            ("eng-summary", Label({"engineering"}), "engineering_manager"),
            ("hr-summary", Label({"hr"}), "hr_manager"),
            ("fin-summary", Label({"finance"}), "finance_manager"),
        ]

        for msg_id, label, sender_name in reports:
            msg = DBPMessage(
                id=msg_id,
                label=label,
                origin=sender_name,
                payload={"summary": f"{sender_name} done"},
            )
            result = transport.send(msg, agents[sender_name], agents["executive"])
            assert result == BoundaryResult.PASS, f"{sender_name} report → PASS"

        # Executive receives all reports
        received = transport.receive(agents["executive"])
        received_ids = {m.id for m in received}
        for msg_id, _, _ in reports:
            assert msg_id in received_ids, f"{msg_id} should be received"

        assert len(boundary.trace_log) >= 3

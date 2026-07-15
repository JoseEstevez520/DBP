"""Deploy a 15-agent company simulation.

See ``demo/run_company.py`` for the main script.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from dbp import AgentCard, Clearance, DBPMessage, Label, Policy

from .agent_base import BaseAgent

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

_LABEL = Label  # shorthand


def respond(msg: DBPMessage, payload: dict) -> DBPMessage:
    """Build a response to *msg* using the same label."""
    return DBPMessage(
        id="",
        label=msg.label,
        origin=msg.destination,
        destination=msg.origin,
        payload=payload,
        policy=msg.policy,
    )


# ---------------------------------------------------------------------------
# Process handlers (called when an agent receives a message)
# ---------------------------------------------------------------------------

def _executive_process(agent: BaseAgent, msg: DBPMessage) -> Optional[DBPMessage]:
    # Executive acknowledges all reports
    return respond(msg, {"type": "ack", "from": "executive"})


def _manager_process(agent: BaseAgent, msg: DBPMessage) -> Optional[DBPMessage]:
    return respond(msg, {"type": "ack", "from": agent.name})


# ---------------------------------------------------------------------------
# Act handlers  (called every cycle for autonomous behaviour)
# ---------------------------------------------------------------------------

def _backend_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "eng_manager",
        {"type": "status", "ticket": "DBP-42", "status": "in_progress"},
        _LABEL({"engineering"}),
    )


def _frontend_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "eng_manager",
        {"type": "status", "ticket": "DBP-43", "status": "review"},
        _LABEL({"engineering"}),
    )


def _devops_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "eng_manager",
        {"type": "infra", "cpu": "42%", "memory": "67%"},
        _LABEL({"engineering", "infra"}),
    )


def _tech_lead_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "cto",
        {"type": "architecture", "component": "auth", "status": "approved"},
        _LABEL({"engineering", "project", "design"}),
    )


def _eng_manager_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    # Forward aggregated status to CTO
    runtime.send_message(
        agent.name, "cto",
        {"type": "sprint_summary", "completed": 3, "blocked": 1},
        _LABEL({"engineering", "project"}),
    )


def _accountant_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "cfo",
        {"type": "ledger", "period": "Q3", "total": 142_000},
        _LABEL({"finance"}),
    )


def _fin_analyst_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "cfo",
        {"type": "projection", "metric": "revenue", "qty": 1.12},
        _LABEL({"finance", "project"}),
    )


def _cfo_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "executive",
        {"type": "budget_report", "variance": "+3.2%"},
        _LABEL({"finance", "strategy"}),
    )


def _recruiter_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "chro",
        {"type": "candidate", "name": "Jane Doe", "role": "Developer"},
        _LABEL({"hr"}),
    )


def _hr_coordinator_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "chro",
        {"type": "schedule", "event": "onboarding", "date": "2026-08-01"},
        _LABEL({"hr", "schedule"}),
    )


def _chro_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "executive",
        {"type": "headcount", "open": 5, "filled": 2},
        _LABEL({"hr", "strategy"}),
    )


def _ops_manager_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "coo",
        {"type": "resources", "servers": 12, "utilization": "74%"},
        _LABEL({"operations"}),
    )


def _project_manager_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "coo",
        {"type": "timeline", "milestone": "v2.0", "eta": "2026-09-15"},
        _LABEL({"project", "schedule"}),
    )


def _coo_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "executive",
        {"type": "ops_report", "incidents": 0, "uptime": "99.9%"},
        _LABEL({"operations", "schedule", "strategy"}),
    )


def _cto_act(agent: BaseAgent, runtime: "AgentRuntime") -> None:
    runtime.send_message(
        agent.name, "executive",
        {"type": "tech_roadmap", "q4_goals": ["auth-v2", "perf-tuning"]},
        _LABEL({"engineering", "strategy"}),
    )


# ---------------------------------------------------------------------------
# Agent catalogue
# ---------------------------------------------------------------------------

_ALL_COMPARTMENTS = {
    "engineering", "strategy", "project", "design",
    "finance", "hr", "schedule", "operations", "infra",
}


def build_agents() -> List[BaseAgent]:
    """Return all 16 agents for the company simulation.

    Agents are returned bottom-up (leaf agents first) so that parent
    registrations happen after children (ordering is not required by the
    runtime but keeps the log tidy).
    """

    agents: List[BaseAgent] = []

    def add(
        name: str,
        compartments: List[str],
        escalation_parent: Optional[str] = None,
        process=None,
        act=None,
    ) -> None:
        card = AgentCard(
            name=name,
            clearance=Clearance(compartments),
            escalation_parent=escalation_parent,
            description=f"{name} agent",
        )
        agents.append(BaseAgent(card=card, process_msg=process, act=act))

    # -- Level 3: individual contributors  (leaf agents) --------------------

    add("backend_dev", ["engineering"], escalation_parent="eng_manager",
        act=_backend_act)
    add("frontend_dev", ["engineering"], escalation_parent="eng_manager",
        act=_frontend_act)
    add("devops", ["engineering", "infra"], escalation_parent="eng_manager",
        act=_devops_act)
    add("accountant", ["finance"], escalation_parent="cfo",
        act=_accountant_act)
    add("fin_analyst", ["finance", "project"], escalation_parent="cfo",
        act=_fin_analyst_act)
    add("recruiter", ["hr"], escalation_parent="chro",
        act=_recruiter_act)
    add("hr_coordinator", ["hr", "schedule"], escalation_parent="chro",
        act=_hr_coordinator_act)
    add("ops_manager", ["operations"], escalation_parent="coo",
        act=_ops_manager_act)
    add("project_manager", ["project", "schedule"], escalation_parent="coo",
        act=_project_manager_act)

    # -- Level 2: middle management -----------------------------------------

    add("eng_manager", ["engineering", "project"], escalation_parent="cto",
        process=_manager_process, act=_eng_manager_act)
    add("tech_lead", ["engineering", "project", "design"], escalation_parent="cto",
        act=_tech_lead_act)

    # -- Level 2: C-suite ---------------------------------------------------

    add("cfo", ["finance", "strategy"], escalation_parent="executive",
        process=_manager_process, act=_cfo_act)
    add("chro", ["hr", "strategy"], escalation_parent="executive",
        process=_manager_process, act=_chro_act)
    add("coo", ["operations", "schedule", "strategy"], escalation_parent="executive",
        process=_manager_process, act=_coo_act)
    add("cto", ["engineering", "strategy"], escalation_parent="executive",
        process=_manager_process, act=_cto_act)

    # -- Level 1: Executive -------------------------------------------------

    add("executive", sorted(_ALL_COMPARTMENTS),
        process=_executive_process)

    return agents


# ---------------------------------------------------------------------------
# Rogue attempts  (intentional boundary violations for demonstration)
# ---------------------------------------------------------------------------


def build_rogue_attempts() -> List[dict]:
    """Return a list of intentional boundary-violation message attempts.

    All should be **BLOCKED** by the DBP boundary engine.
    """
    return [
        {
            "sender": "backend_dev",
            "recipient": "cfo",
            "payload": {"type": "salary_query", "department": "engineering"},
            "label_compartments": {"finance"},
        },
        {
            "sender": "recruiter",
            "recipient": "cto",
            "payload": {"type": "candidate_eval", "name": "John Smith"},
            "label_compartments": {"hr"},
        },
        {
            "sender": "accountant",
            "recipient": "coo",
            "payload": {"type": "budget_leak", "amount": 50000},
            "label_compartments": {"finance"},
        },
        {
            "sender": "devops",
            "recipient": "chro",
            "payload": {"type": "server_access", "server": "prod-db-01"},
            "label_compartments": {"infra"},
        },
        {
            "sender": "frontend_dev",
            "recipient": "recruiter",
            "payload": {"type": "tech_update", "sprint": "S12"},
            "label_compartments": {"engineering"},
        },
    ]


# ---------------------------------------------------------------------------
# Agent titles
# ---------------------------------------------------------------------------
AGENT_TITLES: Dict[str, str] = {
    "executive":      "Executive",
    "cto":            "CTO",
    "eng_manager":    "Engineering Manager",
    "backend_dev":    "Backend Developer",
    "frontend_dev":   "Frontend Developer",
    "devops":         "DevOps Engineer",
    "tech_lead":      "Tech Lead",
    "cfo":            "CFO",
    "accountant":     "Accountant",
    "fin_analyst":    "Financial Analyst",
    "chro":           "CHRO",
    "recruiter":      "Recruiter",
    "hr_coordinator": "HR Coordinator",
    "coo":            "COO",
    "ops_manager":    "Operations Manager",
    "project_manager":"Project Manager",
}

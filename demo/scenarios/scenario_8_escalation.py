"""Scenario 8: Escalation (R7) -- when BLOCK is not the end.

Demonstrates:
- Agent request escalation to parent after a BLOCK
- Parent GRANTs when it has the clearance
- Parent DENYs when lacking clearance
- Escalation to human when no parent exists
"""

from dbp import AgentCard, Boundary, Clearance, Label


def run():
    boundary = Boundary()

    worker = AgentCard(
        name="worker",
        clearance=Clearance({"engineering"}),
        escalation_parent="supervisor",
    )
    supervisor = AgentCard(
        name="supervisor",
        clearance=Clearance({"engineering", "hr", "finance"}),
        escalation_parent="human",
    )
    hr_label = Label({"hr"})
    finance_label = Label({"finance"})

    print(f"\n{'='*52}")
    print("  [SCENARIO 8]  Escalation (R7)")
    print(f"{'='*52}")

    # 1. Worker tries HR data -> BLOCK
    r1 = boundary.check(hr_label, worker.clearance)
    print(f"\n  Worker -> HR data: {r1.value}")

    # 2. Escalate to supervisor -> GRANT
    r2 = boundary.escalate(worker, hr_label, "Need employee count for server capacity", supervisor)
    print(f"  Worker escalates to Supervisor: {r2.value}")

    # 3. Worker tries finance data -> BLOCK
    r3 = boundary.check(finance_label, worker.clearance)
    print(f"  Worker -> Finance data: {r3.value}")

    # 4. Escalate to supervisor -> GRANT
    r4 = boundary.escalate(worker, finance_label, "Need budget for license renewal", supervisor)
    print(f"  Worker escalates to Supervisor: {r4.value}")

    # 5. Supervisor tries data it doesn't have -> DENY
    secret_label = Label({"classified"})
    r5 = boundary.check(secret_label, supervisor.clearance)
    worker2 = AgentCard(
        name="worker2",
        clearance=Clearance({"engineering"}),
    )
    r6 = boundary.escalate(worker2, secret_label, "Need clearance", supervisor)
    print(f"  Worker2 escalates Classified to Supervisor: {r6.value} (lacks clearance)")

    # 6. Agent without parent -> HUMAN
    lonely = AgentCard(
        name="lonely",
        clearance=Clearance({"engineering"}),
    )
    r7 = boundary.check(hr_label, lonely.clearance)
    r8 = boundary.escalate(lonely, hr_label, "Need access, no parent assigned")
    print(f"  Lonely agent escalates (no parent): {r8.value} -> human must decide")

    # 7. Trace summary
    escalation_traces = [t for t in boundary.trace_log if t.origin in ("worker", "worker2", "lonely")]
    print(f"\n  Escalation trace records: {len(escalation_traces)}")
    for t in escalation_traces:
        print(f"    {t.origin} -> {t.destination or 'human'}: {t.result.value}")

    print()

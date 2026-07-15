from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def run():
    boundary = Boundary()

    coach_clr = Clearance({"identity", "fitness", "schedule"})
    coordinator_clr = Clearance({"identity", "fitness", "schedule", "project"})
    developer_clr = Clearance({"identity", "project", "schedule"})

    fitness_label = Label({"fitness"})

    print("[SCENARIO 4] Chain \u2014 boundaries apply at every hop")
    r1 = boundary.check(fitness_label, coordinator_clr, Policy.ANY, origin="coach", destination="coordinator")
    print(f"  Coach â†’ Coordinator (label: [fitness]): {r1.value}")

    if r1 == BoundaryResult.PASS:
        r2 = boundary.check(fitness_label, developer_clr, Policy.ANY, origin="coordinator", destination="developer")
        print(f"  Coordinator â†’ Developer (label: [fitness]): {r2.value}  (missing: fitness)")

    print("  â†’ Boundaries apply at every hop, not just the first.")
    print()

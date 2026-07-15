from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def run():
    boundary = Boundary()

    coach_clr = Clearance({"identity", "fitness", "schedule"})
    coordinator_clr = Clearance({"identity", "fitness", "schedule", "project"})
    developer_clr = Clearance({"identity", "project", "schedule"})
    assistant_clr = Clearance({"identity", "schedule", "finance"})

    coach_msg = Label({"fitness"})
    dev_msg = Label({"project"})
    combined = boundary.heritage(coach_msg, dev_msg)

    results = {
        "Coachâ†’Coordinator [fitness]": boundary.check(coach_msg, coordinator_clr, Policy.ANY),
        "Coachâ†’Developer [fitness]": boundary.check(coach_msg, developer_clr, Policy.ANY),
        "Developerâ†’Coordinator [project]": boundary.check(dev_msg, coordinator_clr, Policy.ANY),
        "Developerâ†’Assistant [project]": boundary.check(dev_msg, assistant_clr, Policy.ANY),
        "Coordinatorâ†’Assistant [fitness,project]": boundary.check(combined, assistant_clr, Policy.ANY),
    }

    print("[SCENARIO 6] Multi-agent flow")
    for desc, result in results.items():
        icon = "âœ“" if result == BoundaryResult.PASS else "âœ—"
        print(f"  {icon} {desc}: {result.value}")
    print()

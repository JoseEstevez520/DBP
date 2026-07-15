from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def run():
    boundary = Boundary()

    training_plan = Label({"fitness"})
    weekly_schedule = Label({"schedule"})

    combined = boundary.heritage(training_plan, weekly_schedule)
    assert combined.compartments == {"fitness", "schedule"}

    coordinator = Clearance({"identity", "fitness", "schedule", "project"})
    developer = Clearance({"identity", "project", "schedule"})

    r_coord = boundary.check(combined, coordinator, Policy.ANY)
    r_dev = boundary.check(combined, developer, Policy.ANY)

    print("[SCENARIO 2] Heritage â€” label union")
    print(f"  training_plan [fitness] + weekly_schedule [schedule]")
    print(f"  â†’ combined [{', '.join(sorted(combined.compartments))}]")
    print(f"  Coordinator sees combined:  {r_coord.value}")
    dev_suffix = f"  (missing: fitness)" if r_dev == BoundaryResult.BLOCK else ""
    print(f"  Developer  sees combined:  {r_dev.value}{dev_suffix}")
    print()

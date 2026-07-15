from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def run():
    boundary = Boundary()

    A_label = Label({"fitness"})
    B_label = Label({"schedule"})
    C_label = Label({"project"})

    AB_label = boundary.heritage(A_label, B_label)
    ABC_label = boundary.heritage(AB_label, C_label)

    assistant_clr = Clearance({"identity", "schedule", "finance"})
    coordinator_clr = Clearance({"identity", "fitness", "schedule", "project"})

    print("[SCENARIO 7] Chain of derivations")
    print(f"  A [fitness] + B [schedule] â†’ AB [{', '.join(sorted(AB_label.compartments))}]")
    print(f"  AB + C [project] â†’ ABC [{', '.join(sorted(ABC_label.compartments))}]")
    print()
    for name, clr, lbl in [
        ("Assistant", assistant_clr, AB_label),
        ("Assistant", assistant_clr, ABC_label),
        ("Coordinator", coordinator_clr, AB_label),
        ("Coordinator", coordinator_clr, ABC_label),
    ]:
        r = boundary.check(lbl, clr, Policy.ANY)
        icon = "âœ“" if r == BoundaryResult.PASS else "âœ—"
        print(f"  {icon} {name:12s} sees [{', '.join(sorted(lbl.compartments)):20s}]: {r.value}")
    print()

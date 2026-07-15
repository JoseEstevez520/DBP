from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def run():
    boundary = Boundary()

    energy_label = Label({"fitness", "schedule"})

    coach_clr = Clearance({"identity", "fitness", "schedule"})
    assistant_clr = Clearance({"identity", "schedule", "finance"})
    developer_clr = Clearance({"identity", "project", "schedule"})

    print("[SCENARIO 5] ANY vs ALL")
    for name, clr in [("Coach", coach_clr), ("Assistant", assistant_clr), ("Developer", developer_clr)]:
        r_any = boundary.check(energy_label, clr, Policy.ANY)
        r_all = boundary.check(energy_label, clr, Policy.ALL)
        any_icon = "PASS" if r_any == BoundaryResult.PASS else "BLOCK"
        all_icon = "PASS" if r_all == BoundaryResult.PASS else "BLOCK"
        print(f"  {name:10s}  ANY={any_icon}   ALL={all_icon}")
    print()

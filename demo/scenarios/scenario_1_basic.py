from dbp import Boundary, Clearance, Label, Policy


def run():
    boundary = Boundary()

    coordinator = Clearance({"identity", "fitness", "schedule", "project"})
    developer = Clearance({"identity", "project", "schedule"})

    fitness_label = Label({"fitness"})

    r_dev = boundary.check(fitness_label, developer, Policy.ANY)
    r_coord = boundary.check(fitness_label, coordinator, Policy.ANY)

    print("[SCENARIO 1] Basic PASS / BLOCK")
    print(f"  Coach -> Developer    (label: [fitness]): {r_dev.value}" + (" (missing: fitness)" if r_dev.value == "block" else ""))
    print(f"  Coach -> Coordinator  (label: [fitness]): {r_coord.value}")
    print()

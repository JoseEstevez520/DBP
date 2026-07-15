"""Custom policy: only allow data when label compartments match ALL of a seniority set."""
from dbp import Boundary, BoundaryResult, Clearance, Label, Policy


def senior_boundary_check(
    boundary: Boundary,
    label: Label,
    clearance: Clearance,
    required_compartments: set,
) -> BoundaryResult:
    if not required_compartments.issubset(clearance.compartments):
        return BoundaryResult.BLOCK
    if label.compartments & clearance.compartments:
        return BoundaryResult.PASS
    return BoundaryResult.BLOCK


boundary = Boundary()

senior_clr = Clearance({"identity", "fitness", "schedule", "project"})
junior_clr = Clearance({"identity", "schedule"})

fitness_label = Label({"fitness"})

for name, clr in [("Senior", senior_clr), ("Junior", junior_clr)]:
    result = senior_boundary_check(boundary, fitness_label, clr, {"identity", "schedule"})
    print(f"{name:7s} â†’ [fitness] with senior rule: {result.value}")

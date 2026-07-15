from dataclasses import dataclass
from typing import List

from dbp import Boundary, Clearance, Label


@dataclass
class _Item:
    name: str
    content: str
    label: Label


def _load() -> List[_Item]:
    return [
        _Item("weekly_schedule", "Monday: 10am meeting. Tuesday: free. Wednesday: 2pm training.", Label({"schedule"})),
        _Item("energy_status", "Jose has been sleeping <6h for 3 nights. Reduce training load.", Label({"fitness", "schedule"})),
        _Item("sprint_status", "Sprint 3: 80% complete. 2 PRs pending review.", Label({"project"})),
        _Item("user_profile", "Name: Jose. Prefers morning training. Communication style: direct.", Label({"identity"})),
        _Item("training_plan", "Week 3 - Strength. Monday: squat 5x5, bench 4x8.", Label({"fitness"})),
        _Item("personal_records", "Squat: 140kg. Bench: 95kg.", Label({"fitness"})),
        _Item("expenses", "Monthly budget: 2,500 EUR. Spent: 1,800 EUR.", Label({"finance"})),
        _Item("open_prs", "PR #42: Add user auth. PR #43: Fix memory leak.", Label({"project"})),
    ]


def run():
    boundary = Boundary()
    all_data = _load()

    coach_clr = Clearance({"identity", "fitness", "schedule"})
    developer_clr = Clearance({"identity", "project", "schedule"})
    assistant_clr = Clearance({"identity", "schedule", "finance"})

    coach_view = boundary.read_in(all_data, coach_clr)
    dev_view = boundary.read_in(all_data, developer_clr)
    asst_view = boundary.read_in(all_data, assistant_clr)

    print("[SCENARIO 3] Read-in â€” what each agent sees at startup")
    print(f"  Coach ({', '.join(sorted(coach_clr.compartments))}):")
    for item in coach_view:
        print(f"    âœ“ {item.name}  [{', '.join(sorted(item.label.compartments))}]")
    print(f"  Developer ({', '.join(sorted(developer_clr.compartments))}):")
    for item in dev_view:
        print(f"    âœ“ {item.name}  [{', '.join(sorted(item.label.compartments))}]")
    print(f"  Assistant ({', '.join(sorted(assistant_clr.compartments))}):")
    for item in asst_view:
        print(f"    âœ“ {item.name}  [{', '.join(sorted(item.label.compartments))}]")
    print()

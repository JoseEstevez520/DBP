"""DBP multi-agent company simulation - 16 agents, 10 cycles.

Usage::

    python demo/run_company.py
"""

import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dbp import BoundaryResult, Label

from demo.agent_runtime import AgentRuntime
from demo.deploy_company import AGENT_TITLES, build_agents, build_rogue_attempts


def show_roster(runtime: AgentRuntime) -> None:
    print(f"\n{' Agent Roster ':-^64}")
    for name, title in AGENT_TITLES.items():
        card = runtime.registry.get(name)
        comps = ", ".join(sorted(card.clearance.compartments))
        parent = card.escalation_parent or "-"
        print(f"  {title:26s}  [{comps:50s}]  -> {parent}")


def show_trace(runtime: AgentRuntime) -> None:
    print(f"{' Trace Log (boundary checks) ':-^64}")
    log = runtime._repr_messages()
    if not log:
        print("  (no trace records)")
        return

    passed = [r for r in log if r["result"] == "pass"]
    blocked = [r for r in log if r["result"] == "block"]

    print(f"\n  Total checks : {len(log)}")
    print(f"  PASSED       : {len(passed)}")
    print(f"  BLOCKED      : {len(blocked)}")

    print(f"\n{' Detailed trace ':-^64}\n")

    for i, rec in enumerate(log):
        result = rec["result"].upper()
        icon = "+" if result == "PASS" else "-"
        label = ",".join(rec["label"]) if rec["label"] else "(empty)"
        blocked_by = f"  BLOCKED BY: {','.join(rec['blocked_by'])}" if rec["blocked_by"] else ""
        a_from = AGENT_TITLES.get(rec["from"], rec["from"])
        a_to = AGENT_TITLES.get(rec["to"], rec["to"])
        print(f"  {i+1:3d}. {icon} {result:5s}  {a_from:22s} -> {a_to:22s}  [{label:30s}]{blocked_by}")

    print(f"\n{' Traffic matrix (PASS / BLOCK per sender -> recipient) ':-^76}")
    pairs: dict = {}
    for rec in log:
        key = (rec["from"], rec["to"])
        pairs.setdefault(key, {"pass": 0, "block": 0})
        pairs[key][rec["result"]] += 1

    for (src, dst), counts in sorted(pairs.items()):
        s = AGENT_TITLES.get(src, src)
        d = AGENT_TITLES.get(dst, dst)
        total = counts["pass"] + counts["block"]
        pct = counts["pass"] / total * 100 if total else 0
        if counts["block"] > 0:
            print(f"  {s:22s} -> {d:22s}  {counts['pass']:3d} PASS / {counts['block']:3d} BLOCK  ({pct:.0f}% pass) ***")
        else:
            print(f"  {s:22s} -> {d:22s}  {counts['pass']:3d} PASS / {counts['block']:3d} BLOCK  ({pct:.0f}% pass)")


def run_rogue_cycle(runtime: AgentRuntime) -> int:
    """Send intentionally cross-boundary messages. Returns number of blocked."""
    blocked_count = 0
    for attempt in build_rogue_attempts():
        label = Label(attempt["label_compartments"])
        result = runtime.send_message(
            attempt["sender"],
            attempt["recipient"],
            attempt["payload"],
            label,
        )
        if result == BoundaryResult.BLOCK:
            blocked_count += 1
    return blocked_count


def main() -> None:
    print("=" * 64)
    print("  DBP  -  Multi-Agent Company Simulation  (16 agents)")
    print("=" * 64)

    with tempfile.TemporaryDirectory(prefix="dbp_company_") as tmpdir:
        runtime = AgentRuntime(base_path=Path(tmpdir))
        runtime.start()

        for agent in build_agents():
            runtime.add_agent(agent)

        show_roster(runtime)

        print(f"\n{' Running 10 normal cycles ':-^64}\n")
        runtime.run_cycles(10)

        print(f"\n{' Sending 5 rogue (cross-boundary) messages ':-^64}\n")
        blocked_rogue = run_rogue_cycle(runtime)

        print(f"\n{'=' * 64}")
        print(f"  Rogue round: {blocked_rogue} / 5 messages BLOCKED by boundary")
        print(f"{'=' * 64}")

        show_trace(runtime)

        print(f"\n{'=' * 64}")
        log = runtime._repr_messages()
        passed = len([r for r in log if r["result"] == "pass"])
        blocked = len([r for r in log if r["result"] == "block"])
        print(f"  Simulation complete - {len(log)} boundary checks total")
        print(f"  {passed} passed, {blocked} blocked by DBP.")
        print(f"{'=' * 64}")

        runtime.stop()


if __name__ == "__main__":
    main()

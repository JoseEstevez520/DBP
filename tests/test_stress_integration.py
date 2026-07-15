"""Integration and stress tests for the Data Boundary Protocol."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    EscalationResult,
    Label,
    Policy,
)
from dbp.transport.local import LocalTransport


# ---------------------------------------------------------------------------
# Large-scale / stress tests
# ---------------------------------------------------------------------------

class TestLargeScale:
    """Stress and performance tests with large data volumes."""

    def test_boundary_check_50plus_compartments(self):
        b = Boundary()
        label = Label({f"c{i}" for i in range(60)})
        clearance = Clearance({f"c{i}" for i in range(30, 80)})
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.BLOCK

    def test_heritage_100_labels_merged(self):
        b = Boundary()
        labels = [Label({f"c{i}"}) for i in range(100)]
        merged = b.heritage(*labels)
        assert len(merged.compartments) == 100
        for i in range(100):
            assert f"c{i}" in merged.compartments

    def test_1000_boundary_checks_in_sequence(self):
        b = Boundary()
        for i in range(1000):
            label = Label({f"data{i}"})
            clearance = Clearance({f"data{i}"})
            assert b.check(label, clearance) == BoundaryResult.PASS
        assert len(b.trace_log) == 1000

    def test_100_simultaneous_read_in_calls(self):
        b = Boundary()

        class LabelledItem:
            def __init__(self, label, name=""):
                self.label = label
                self.name = name

        items = []
        for i in range(20):
            items.append(LabelledItem(Label({"a"}), f"a-{i}"))
            items.append(LabelledItem(Label({"b"}), f"b-{i}"))

        clearance_a = Clearance({"a"})

        def run_read_in():
            result = b.read_in(items, clearance_a)
            return [x.name for x in result]

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(run_read_in) for _ in range(100)]
            for f in as_completed(futures):
                names = f.result()
                assert len(names) == 20
                assert all(n.startswith("a-") for n in names)

        assert len(b.trace_log) >= 2000


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: unicode, single chars, long strings, special values."""

    def test_label_with_unicode_compartment_names(self):
        b = Boundary()
        label = Label({"español", "日本語"})
        clearance = Clearance({"español", "日本語", "english"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.PASS

        partial = Clearance({"español"})
        assert b.check(label, partial, Policy.ALL) == BoundaryResult.BLOCK
        assert b.check(label, partial, Policy.ANY) == BoundaryResult.PASS

    def test_clearance_with_single_character_compartments(self):
        b = Boundary()
        label = Label({"a", "b", "c"})
        clearance = Clearance({"a", "b"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.BLOCK
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

    def test_label_with_very_long_compartment_name(self):
        b = Boundary()
        long_name = "x" * 500
        label = Label({long_name, "other"})
        clearance = Clearance({long_name, "other", "extra"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.PASS

        missing = Clearance({"other"})
        assert b.check(label, missing, Policy.ALL) == BoundaryResult.BLOCK

    def test_boundary_check_identical_label_and_clearance_100plus(self):
        b = Boundary()
        compartments = {f"c{i}" for i in range(150)}
        label = Label(compartments, policy=Policy.ALL)
        clearance = Clearance(compartments)
        assert b.check(label, clearance) == BoundaryResult.PASS

    def test_empty_string_in_compartments_allowed(self):
        b = Boundary()
        label = Label({"A", ""})
        clearance = Clearance({"A", "B"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.BLOCK
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

        clearance2 = Clearance({"A", "", "B"})
        assert b.check(label, clearance2, Policy.ALL) == BoundaryResult.PASS

    def test_escalation_with_agent_that_has_all_compartments(self):
        b = Boundary()
        agent = AgentCard(
            name="omniscient",
            clearance=Clearance({f"c{i}" for i in range(100)}),
        )
        label = Label({"c42", "c99"})

        result = b.escalate(agent, label, "I already have access")
        assert result == EscalationResult.ESCALATE

        parent = AgentCard(
            name="parent",
            clearance=Clearance({f"c{i}" for i in range(100)}),
        )
        result = b.escalate(agent, label, "I already have access", parent)
        assert result == EscalationResult.GRANT

    def test_escalation_chain_5_levels(self):
        b = Boundary()

        worker = AgentCard(
            name="worker",
            clearance=Clearance({"a"}),
        )
        parent = AgentCard(
            name="parent",
            clearance=Clearance({"a", "b"}),
        )
        grandparent = AgentCard(
            name="grandparent",
            clearance=Clearance({"a", "b", "c"}),
        )
        great_grandparent = AgentCard(
            name="great-grandparent",
            clearance=Clearance({"a", "b", "c", "d"}),
        )
        human_proxy = AgentCard(
            name="human-proxy",
            clearance=Clearance({"a", "b", "c", "d", "e"}),
        )

        label = Label({"e"})

        r1 = b.escalate(worker, label, "need e", parent)
        assert r1 == EscalationResult.DENY

        r2 = b.escalate(worker, label, "need e", grandparent)
        assert r2 == EscalationResult.DENY

        r3 = b.escalate(worker, label, "need e", great_grandparent)
        assert r3 == EscalationResult.DENY

        r4 = b.escalate(worker, label, "need e", human_proxy)
        assert r4 == EscalationResult.GRANT

        assert len(b.trace_log) >= 4


# ---------------------------------------------------------------------------
# Full protocol scenario (R1-R7)
# ---------------------------------------------------------------------------

class TestFullProtocol:
    """Complete R1-R7 scenario with 4 agents, all protocol steps."""

    def test_complete_r1_to_r7_scenario(self):
        b = Boundary()

        worker = AgentCard(
            name="worker",
            clearance=Clearance({"engineering", "docs"}),
            description="Builds and documents code",
            escalation_parent="supervisor",
        )
        supervisor = AgentCard(
            name="supervisor",
            clearance=Clearance({"engineering", "docs", "hr"}),
            description="Oversees engineering team",
            escalation_parent="manager",
        )
        manager = AgentCard(
            name="manager",
            clearance=Clearance({"engineering", "docs", "hr", "finance"}),
            description="Department manager",
            escalation_parent="human-proxy",
        )
        human_proxy = AgentCard(
            name="human-proxy",
            clearance=Clearance({"engineering", "docs", "hr", "finance", "exec"}),
            description="Human delegate with full access",
        )

        assert len(worker.clearance.compartments) == 2
        assert len(supervisor.clearance.compartments) == 3
        assert len(manager.clearance.compartments) == 4
        assert len(human_proxy.clearance.compartments) == 5

        engineering_label = Label({"engineering"}, policy=Policy.ALL)
        assert b.can_write(engineering_label, worker.clearance) is True

        mixed_label = Label({"engineering", "docs"}, policy=Policy.ALL)
        assert b.can_write(mixed_label, worker.clearance) is True

        assert b.can_write(Label({"hr"}), worker.clearance) is False

        class LabelledItem:
            def __init__(self, label, name="", payload=None):
                self.label = label
                self.name = name
                self.payload = payload or {}

        items = [
            LabelledItem(Label({"engineering"}), "design-doc"),
            LabelledItem(Label({"hr"}), "salary-info"),
            LabelledItem(Label({"docs"}), "api-guide"),
            LabelledItem(Label({"finance"}), "budget"),
            LabelledItem(Label(set()), "public-note"),
        ]

        worker_items = b.read_in(items, worker.clearance)
        worker_names = {i.name for i in worker_items}
        assert "design-doc" in worker_names
        assert "api-guide" in worker_names
        assert "public-note" in worker_names
        assert "salary-info" not in worker_names
        assert "budget" not in worker_names

        supervisor_items = b.read_in(items, supervisor.clearance)
        supervisor_names = {i.name for i in supervisor_items}
        assert "design-doc" in supervisor_names
        assert "api-guide" in supervisor_names
        assert "salary-info" in supervisor_names
        assert "public-note" in supervisor_names
        assert "budget" not in supervisor_names

        assert b.check(engineering_label, supervisor.clearance) == BoundaryResult.PASS
        assert b.check(Label({"hr"}, policy=Policy.ALL), worker.clearance) == BoundaryResult.BLOCK
        assert b.check(engineering_label, manager.clearance) == BoundaryResult.PASS

        heritage_label = b.heritage(
            Label({"engineering"}),
            Label({"hr"}),
            policy=Policy.ALL,
        )
        assert "engineering" in heritage_label.compartments
        assert "hr" in heritage_label.compartments

        assert b.check(heritage_label, worker.clearance) == BoundaryResult.BLOCK
        assert b.check(heritage_label, supervisor.clearance) == BoundaryResult.PASS
        assert b.check(heritage_label, manager.clearance) == BoundaryResult.PASS

        exec_label = Label({"exec"})

        assert b.check(exec_label, worker.clearance) == BoundaryResult.BLOCK

        r1 = b.escalate(worker, exec_label, "Need exec data for planning", supervisor)
        assert r1 == EscalationResult.DENY

        r2 = b.escalate(worker, exec_label, "Need exec data", manager)
        assert r2 == EscalationResult.DENY

        r3 = b.escalate(worker, exec_label, "Need exec data", human_proxy)
        assert r3 == EscalationResult.GRANT

        assert len(b.trace_log) >= 10

        results_in_log = [rec.result for rec in b.trace_log]
        assert BoundaryResult.PASS in results_in_log
        assert BoundaryResult.BLOCK in results_in_log


# ---------------------------------------------------------------------------
# Transport stress tests
# ---------------------------------------------------------------------------

class TestTransportStress:
    """Stress tests for LocalTransport."""

    def test_100_simultaneous_sends(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, str(tmp_path / "stress"))
        sender = AgentCard(
            name="sender",
            clearance=Clearance({"a", "b"}),
        )
        recipient = AgentCard(
            name="recipient",
            clearance=Clearance({"a"}),
        )

        n = 100

        def send_msg(i):
            label = Label({"a"}) if i % 2 == 0 else Label({"b"})
            msg = DBPMessage(
                id=f"stress-{i:04d}",
                label=label,
                origin="sender",
                payload={"seq": i},
            )
            return transport.send(msg, sender, recipient)

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(send_msg, i) for i in range(n)]
            results = [f.result() for f in as_completed(futures)]

        pass_count = sum(1 for r in results if r == BoundaryResult.PASS)
        block_count = sum(1 for r in results if r == BoundaryResult.BLOCK)
        assert pass_count == 50
        assert block_count == 50

        md_files = list(transport.base_path.glob("*.md"))
        assert len(md_files) == 50
        for f in md_files:
            seq = int(f.stem.split("-")[1])
            assert seq % 2 == 0

        for f in md_files:
            content = f.read_text(encoding="utf-8")
            assert content.startswith("---")

        assert len(b.trace_log) >= n

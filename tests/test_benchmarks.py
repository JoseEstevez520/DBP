"""Performance benchmarks for DBP with realistic workloads and assertions."""

import statistics
import time

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    Label,
    Policy,
)
from dbp.transport.local import LocalTransport


class TestBenchmarks:
    """Measure DBP performance with realistic workloads."""

    def test_boundary_check_throughput(self):
        """Measure checks per second — should be very fast (set ops)."""
        boundary = Boundary()
        label = Label({"a", "b", "c"})
        clearance = Clearance({"a", "b", "c", "d", "e"})

        start = time.perf_counter()
        n = 10000
        for _ in range(n):
            boundary.check(label, clearance)
        elapsed = time.perf_counter() - start

        checks_per_sec = n / elapsed
        print(f"\n  Boundary checks: {checks_per_sec:,.0f}/sec")
        assert checks_per_sec > 50000

    def test_trace_log_growth(self):
        """Measure trace log append rate with 10K entries."""
        boundary = Boundary()
        label = Label({"a"})
        clearance = Clearance({"a", "b"})

        start = time.perf_counter()
        n = 10000
        for i in range(n):
            boundary.check(label, clearance, data_id=str(i))
        elapsed = time.perf_counter() - start

        log = boundary.trace_log
        append_rate = n / elapsed
        print(f"\n  Trace log entries: {len(log)}, append rate: {append_rate:,.0f}/sec")
        assert len(log) == n
        assert log[0].data_id == "0"
        assert log[-1].data_id == str(n - 1)

    def test_heritage_throughput(self):
        """Measure heritage (label merge) operations per second."""
        boundary = Boundary()
        labels = [Label({f"c{i}"}) for i in range(20)]

        start = time.perf_counter()
        n = 10000
        for _ in range(n):
            boundary.heritage(*labels)
        elapsed = time.perf_counter() - start

        ops_per_sec = n / elapsed
        print(f"\n  Heritage merges (20 labels each): {ops_per_sec:,.0f}/sec")
        assert ops_per_sec > 5000

    def test_read_in_throughput(self):
        """Measure read_in filtering throughput."""

        class LabelledItem:
            def __init__(self, label):
                self.label = label

        boundary = Boundary()
        clearance = Clearance({"a", "b"})
        items = [LabelledItem(Label({"a"})) for _ in range(1000)]

        start = time.perf_counter()
        n = 100
        for _ in range(n):
            boundary.read_in(items, clearance)
        elapsed = time.perf_counter() - start

        items_per_sec = (len(items) * n) / elapsed
        print(f"\n  read_in filtering: {items_per_sec:,.0f} items/sec")
        assert items_per_sec > 100000

    def test_label_serialization_roundtrip(self):
        """Measure DBPMessage → dict → DBPMessage roundtrip speed."""
        label = Label({"a", "b", "c"})
        msg = DBPMessage(
            id="test-serial",
            label=label,
            origin="alice",
            payload={"key": "value", "nested": {"x": [1, 2, 3]}},
        )

        start = time.perf_counter()
        n = 5000
        for _ in range(n):
            d = msg.to_dict()
            _ = DBPMessage.from_dict(d)
        elapsed = time.perf_counter() - start

        ops_per_sec = n / elapsed
        print(f"\n  Serialization roundtrips: {ops_per_sec:,.0f}/sec")
        assert ops_per_sec > 5000

    def test_transport_local_throughput(self, tmp_path):
        """Measure LocalTransport send throughput."""

        class CountingBoundary(Boundary):
            def __init__(self):
                super().__init__()
                self.check_count = 0

            def check(self, label, clearance, policy=None, **kwargs):
                self.check_count += 1
                return super().check(label, clearance, policy, **kwargs)

        boundary = CountingBoundary()
        transport = LocalTransport(boundary, str(tmp_path / "throughput"))
        sender = AgentCard(
            name="sender", clearance=Clearance({"a", "b", "c"})
        )
        recipient = AgentCard(
            name="recipient", clearance=Clearance({"a", "b", "c"})
        )

        msg = DBPMessage(
            id="perf", label=Label({"a"}), origin="sender", payload={"data": "x"}
        )

        start = time.perf_counter()
        n = 500
        for i in range(n):
            msg.id = f"perf-{i}"
            transport.send(msg, sender, recipient)
        elapsed = time.perf_counter() - start

        msgs_per_sec = n / elapsed
        print(f"\n  LocalTransport sends: {msgs_per_sec:,.0f}/sec")
        print(f"  Disk files written: {len(list(transport.base_path.glob('*.md')))}")
        assert msgs_per_sec > 100

    def test_full_pipeline_latency(self, tmp_path):
        """Measure end-to-end: create → check → transport send → receive."""
        latencies = []
        n = 200

        for i in range(n):
            sub_dir = str(tmp_path / f"pipeline-{i}")
            boundary = Boundary()
            transport = LocalTransport(boundary, sub_dir)
            sender = AgentCard(
                name="sender", clearance=Clearance({"a", "b"})
            )
            recipient = AgentCard(
                name="recipient", clearance=Clearance({"a", "b"})
            )

            msg = DBPMessage(
                id=f"pipe-{i}",
                label=Label({"a"}),
                origin="sender",
                payload={"n": i},
            )

            start = time.perf_counter()
            result = transport.send(msg, sender, recipient)
            assert result == BoundaryResult.PASS
            received = transport.receive(recipient)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg = statistics.mean(latencies) * 1000
        p99 = sorted(latencies)[int(n * 0.99)] * 1000
        print(f"\n  Average latency: {avg:.2f}ms")
        print(f"  P99 latency: {p99:.2f}ms")
        assert len(received) == 1
        assert avg < 50

    def test_memory_usage(self):
        """Verify trace log handles 50K checks without issue."""
        boundary = Boundary()
        label = Label({"engineering"})
        clearance = Clearance({"engineering", "hr", "finance"})

        n = 50000
        start = time.perf_counter()
        for i in range(n):
            boundary.check(
                label,
                clearance,
                data_id=f"mem-{i}",
                origin="sender",
                destination="recipient",
            )
        elapsed = time.perf_counter() - start

        log = boundary.trace_log
        checks_per_sec = n / elapsed
        print(f"\n  Trace log entries: {len(log)}")
        print(f"  Check rate under load: {checks_per_sec:,.0f}/sec")
        assert len(log) == n
        assert log[0].data_id == "mem-0"
        assert log[-1].data_id == f"mem-{n - 1}"

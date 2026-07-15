"""Tests for the Boundary engine — core check, trace log, and helpers."""

from datetime import datetime, timezone

import pytest

from dbp import (
    Boundary,
    BoundaryResult,
    Clearance,
    EmptyClearanceError,
    Label,
    Policy,
    TraceRecord,
)


class TestBoundaryCheck:
    """Core boundary check logic (ANY/ALL policies, empty labels, etc.)."""

    def test_any_policy_pass_when_intersection_exists(self):
        b = Boundary()
        label = Label({"A", "B"})
        clearance = Clearance({"B", "C"})
        assert b.check(label, clearance) == BoundaryResult.PASS

    def test_any_policy_block_when_no_intersection(self):
        b = Boundary()
        label = Label({"A", "B"})
        clearance = Clearance({"C", "D"})
        assert b.check(label, clearance) == BoundaryResult.BLOCK

    def test_any_policy_block_single_compartment_no_match(self):
        b = Boundary()
        assert b.check(Label({"X"}), Clearance({"Y"})) == BoundaryResult.BLOCK

    def test_all_policy_pass_when_label_subset_of_clearance(self):
        b = Boundary()
        label = Label({"A", "B"}, policy=Policy.ALL)
        clearance = Clearance({"A", "B", "C"})
        assert b.check(label, clearance) == BoundaryResult.PASS

    def test_all_policy_block_when_label_not_subset(self):
        b = Boundary()
        label = Label({"A", "B", "Z"}, policy=Policy.ALL)
        clearance = Clearance({"A", "B"})
        assert b.check(label, clearance) == BoundaryResult.BLOCK

    def test_all_policy_block_single_missing_compartment(self):
        b = Boundary()
        label = Label({"A", "B"}, policy=Policy.ALL)
        clearance = Clearance({"A"})
        assert b.check(label, clearance) == BoundaryResult.BLOCK

    def test_empty_label_always_passes_any_policy(self):
        b = Boundary()
        label = Label([])
        clearance = Clearance({"secret"})
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

    def test_empty_label_always_passes_all_policy(self):
        b = Boundary()
        label = Label([])
        clearance = Clearance({"secret"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.PASS

    def test_empty_label_passes_regardless_of_clearance(self):
        b = Boundary()
        assert b.check(Label(set()), Clearance({"anything"})) == BoundaryResult.PASS

    def test_empty_clearance_raises_empty_clearance_error(self):
        with pytest.raises(EmptyClearanceError):
            Clearance([])

    def test_empty_clearance_raises_with_frozenset(self):
        with pytest.raises(EmptyClearanceError):
            Clearance(frozenset())

    def test_identical_label_and_clearance_pass_any_policy(self):
        b = Boundary()
        assert b.check(Label({"A"}), Clearance({"A"}), Policy.ANY) == BoundaryResult.PASS

    def test_identical_label_and_clearance_pass_all_policy(self):
        b = Boundary()
        assert b.check(Label({"A", "B"}), Clearance({"A", "B"}), Policy.ALL) == BoundaryResult.PASS

    def test_one_shared_compartment_out_of_many_passes_any(self):
        b = Boundary()
        label = Label({"A", "B", "C"})
        clearance = Clearance({"C", "D", "E"})
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

    def test_one_shared_compartment_out_of_many_blocks_all(self):
        b = Boundary()
        label = Label({"A", "B", "C"})
        clearance = Clearance({"C", "D", "E"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.BLOCK

    def test_policy_override_from_any_to_all(self):
        b = Boundary()
        label = Label({"A", "B"})  # default ANY
        clearance = Clearance({"A"})
        assert b.check(label, clearance, Policy.ALL) == BoundaryResult.BLOCK

    def test_policy_override_from_all_to_any(self):
        b = Boundary()
        label = Label({"A", "B"}, policy=Policy.ALL)
        clearance = Clearance({"B"})
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

    def test_single_matching_compartment(self):
        b = Boundary()
        assert b.check(Label({"X"}), Clearance({"X"}), Policy.ANY) == BoundaryResult.PASS

    def test_single_non_matching_compartment(self):
        b = Boundary()
        assert b.check(Label({"X"}), Clearance({"Y"}), Policy.ANY) == BoundaryResult.BLOCK

    def test_large_disjoint_sets(self):
        b = Boundary()
        label = Label({f"c{i}" for i in range(100)})
        clearance = Clearance({f"d{i}" for i in range(100)})
        assert b.check(label, clearance) == BoundaryResult.BLOCK

    def test_large_overlapping_sets(self):
        b = Boundary()
        label = Label({f"c{i}" for i in range(50)})
        clearance = Clearance({f"c{i}" for i in range(25, 75)})
        assert b.check(label, clearance, Policy.ANY) == BoundaryResult.PASS

    def test_large_subset_sets_all_policy(self):
        b = Boundary()
        label = Label({f"c{i}" for i in range(50)}, policy=Policy.ALL)
        clearance = Clearance({f"c{i}" for i in range(100)})
        assert b.check(label, clearance) == BoundaryResult.PASS


class TestTraceLog:
    """Trace log behaviour — R5 compliance."""

    def test_trace_log_starts_empty(self):
        b = Boundary()
        assert b.trace_log == []

    def test_trace_appended_on_every_check(self):
        b = Boundary()
        assert len(b.trace_log) == 0
        b.check(Label({"A"}), Clearance({"A"}))
        assert len(b.trace_log) == 1
        b.check(Label({"B"}), Clearance({"C"}))
        assert len(b.trace_log) == 2

    def test_trace_log_order_matches_check_order(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}), data_id="first")
        b.check(Label({"B"}), Clearance({"A"}), data_id="second")
        assert b.trace_log[0].data_id == "first"
        assert b.trace_log[1].data_id == "second"

    def test_trace_record_fields_populated_on_pass(self):
        b = Boundary()
        label = Label({"X"})
        clearance = Clearance({"X", "Y"})
        b.check(label, clearance, Policy.ANY, data_id="d1", origin="alice", destination="bob")
        rec = b.trace_log[0]
        assert rec.data_id == "d1"
        assert rec.origin == "alice"
        assert rec.destination == "bob"
        assert rec.label == label
        assert rec.clearance == clearance
        assert rec.policy == Policy.ANY
        assert rec.result == BoundaryResult.PASS
        assert rec.blocked_by == frozenset()
        assert isinstance(rec.timestamp, str)
        # Verify ISO-8601 parseable
        datetime.fromisoformat(rec.timestamp)

    def test_trace_record_fields_populated_on_block_any(self):
        b = Boundary()
        label = Label({"A", "B"})
        clearance = Clearance({"C"})
        b.check(label, clearance)
        rec = b.trace_log[0]
        assert rec.result == BoundaryResult.BLOCK
        assert rec.policy == Policy.ANY
        assert rec.blocked_by == frozenset({"A", "B"})

    def test_trace_record_blocked_by_on_all_policy(self):
        b = Boundary()
        label = Label({"A", "B", "C"}, policy=Policy.ALL)
        clearance = Clearance({"A", "B"})
        b.check(label, clearance)
        rec = b.trace_log[0]
        assert rec.result == BoundaryResult.BLOCK
        assert rec.blocked_by == frozenset({"C"})

    def test_trace_blocked_by_empty_on_pass(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}), data_id="msg")
        rec = b.trace_log[0]
        assert rec.result == BoundaryResult.PASS
        assert rec.blocked_by == frozenset()

    def test_trace_log_is_shallow_copy_not_reference(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        log = b.trace_log
        log.append("tamper")
        assert len(b.trace_log) == 1

    def test_trace_record_is_immutable(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        rec = b.trace_log[0]
        assert isinstance(rec, TraceRecord)

    def test_multiple_checks_preserve_all_traces(self):
        b = Boundary()
        n = 10
        for i in range(n):
            b.check(Label({str(i)}), Clearance({str(i)}), data_id=f"msg-{i}")
        assert len(b.trace_log) == n
        for i, rec in enumerate(b.trace_log):
            assert rec.data_id == f"msg-{i}"

    def test_trace_origin_destination_default_to_none(self):
        b = Boundary()
        b.check(Label({"A"}), Clearance({"A"}))
        rec = b.trace_log[0]
        assert rec.origin is None
        assert rec.destination is None
        assert rec.data_id is None


class TestReadIn:
    """R1 — read_in filters data at startup."""

    class LabelledItem:
        def __init__(self, label, name=""):
            self.label = label
            self.name = name

    def test_read_in_returns_only_passing_items(self):
        b = Boundary()
        items = [
            self.LabelledItem(Label({"A"}), "a"),
            self.LabelledItem(Label({"B"}), "b"),
        ]
        result = b.read_in(items, Clearance({"A"}))
        names = [i.name for i in result]
        assert "a" in names
        assert "b" not in names

    def test_read_in_empty_label_always_included(self):
        b = Boundary()
        items = [
            self.LabelledItem(Label(set()), "unrestricted"),
            self.LabelledItem(Label({"secret"}), "classified"),
        ]
        result = b.read_in(items, Clearance({"harmless"}))
        names = [i.name for i in result]
        assert "unrestricted" in names
        assert "classified" not in names

    def test_read_in_all_policy_respected(self):
        b = Boundary()
        items = [
            self.LabelledItem(Label({"A", "B"}, policy=Policy.ALL), "both"),
            self.LabelledItem(Label({"A"}, policy=Policy.ALL), "just-a"),
        ]
        result = b.read_in(items, Clearance({"A"}))
        names = [i.name for i in result]
        assert "just-a" in names
        assert "both" not in names

    def test_read_in_returns_empty_list_when_none_pass(self):
        b = Boundary()
        items = [self.LabelledItem(Label({"secret"}), "s")]
        result = b.read_in(items, Clearance({"public"}))
        assert result == []

    def test_read_in_empty_items(self):
        b = Boundary()
        assert b.read_in([], Clearance({"A"})) == []


class TestCanWrite:
    """R2 — can_write enforces label ⊆ clearance."""

    def test_can_write_pass_when_label_subset_of_clearance(self):
        b = Boundary()
        assert b.can_write(Label({"A"}), Clearance({"A", "B"})) is True

    def test_can_write_pass_when_label_identical(self):
        b = Boundary()
        assert b.can_write(Label({"A"}), Clearance({"A"})) is True

    def test_can_write_pass_when_label_empty(self):
        b = Boundary()
        assert b.can_write(Label(set()), Clearance({"A"})) is True

    def test_can_write_block_when_label_has_extra_compartment(self):
        b = Boundary()
        assert b.can_write(Label({"A", "Z"}), Clearance({"A", "B"})) is False

    def test_can_write_block_when_label_completely_different(self):
        b = Boundary()
        assert b.can_write(Label({"Z"}), Clearance({"A"})) is False


class TestHeritage:
    """R4 — heritage produces union of compartments."""

    def test_heritage_union_of_two_distinct_labels(self):
        b = Boundary()
        result = b.heritage(Label({"A"}), Label({"B"}))
        assert result.compartments == frozenset({"A", "B"})

    def test_heritage_union_of_three_labels(self):
        b = Boundary()
        result = b.heritage(Label({"A"}), Label({"B"}), Label({"C"}))
        assert result.compartments == frozenset({"A", "B", "C"})

    def test_heritage_deduplicates_overlapping_compartments(self):
        b = Boundary()
        result = b.heritage(Label({"A", "B"}), Label({"B", "C"}))
        assert result.compartments == frozenset({"A", "B", "C"})

    def test_heritage_with_empty_labels(self):
        b = Boundary()
        result = b.heritage()
        assert result.compartments == frozenset()
        assert result.policy == Policy.ANY

    def test_heritage_preserves_custom_policy(self):
        b = Boundary()
        result = b.heritage(Label({"A"}), Label({"B"}), policy=Policy.ALL)
        assert result.policy == Policy.ALL
        assert result.compartments == frozenset({"A", "B"})

    def test_heritage_defaults_to_any_policy(self):
        b = Boundary()
        result = b.heritage(Label({"A"}))
        assert result.policy == Policy.ANY

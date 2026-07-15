"""Focused tests for Heritage — union of labels (R4)."""

import pytest

from dbp import Boundary, Label, Policy


@pytest.fixture
def boundary():
    return Boundary()


class TestHeritageBasic:
    """Basic heritage behaviour: union, dedup, policy."""

    def test_union_of_two_distinct_labels(self, boundary):
        result = boundary.heritage(Label({"engineering"}), Label({"hr"}))
        assert result.compartments == frozenset({"engineering", "hr"})

    def test_union_of_three_plus_labels(self, boundary):
        result = boundary.heritage(
            Label({"a"}), Label({"b"}), Label({"c"}), Label({"d"})
        )
        assert result.compartments == frozenset({"a", "b", "c", "d"})

    def test_heritage_with_overlapping_compartments_dedup(self, boundary):
        result = boundary.heritage(
            Label({"a", "b", "c"}), Label({"b", "c", "d"}), Label({"c", "d", "e"})
        )
        assert result.compartments == frozenset({"a", "b", "c", "d", "e"})

    def test_heritage_preserves_default_policy(self, boundary):
        result = boundary.heritage(Label({"a"}), Label({"b"}))
        assert result.policy == Policy.ANY

    def test_heritage_with_all_policy_on_result(self, boundary):
        result = boundary.heritage(Label({"a"}), Label({"b"}), policy=Policy.ALL)
        assert result.policy == Policy.ALL

    def test_heritage_with_empty_labels(self, boundary):
        result = boundary.heritage()
        assert result.compartments == frozenset()
        assert result.policy == Policy.ANY

    def test_heritage_single_label_returns_copy(self, boundary):
        original = Label({"a"})
        result = boundary.heritage(original)
        assert result.compartments == original.compartments
        assert result is not original

    def test_heritage_with_empty_compartment_labels(self, boundary):
        result = boundary.heritage(Label(set()), Label({"b"}))
        assert result.compartments == frozenset({"b"})


class TestHeritageChain:
    """Heritage chain — A→B→C accumulates all compartments."""

    def test_two_step_chain(self, boundary):
        step1 = boundary.heritage(Label({"a"}), Label({"b"}))
        assert step1.compartments == frozenset({"a", "b"})

        step2 = boundary.heritage(step1, Label({"c"}))
        assert step2.compartments == frozenset({"a", "b", "c"})

    def test_three_step_chain(self, boundary):
        current = Label({"a"})
        current = boundary.heritage(current, Label({"b"}))
        current = boundary.heritage(current, Label({"c"}))
        current = boundary.heritage(current, Label({"d"}))
        assert current.compartments == frozenset({"a", "b", "c", "d"})

    def test_chain_never_loses_compartments(self, boundary):
        combined = Label(set())
        for comp in ["x", "y", "z"]:
            combined = boundary.heritage(combined, Label({comp}))
        assert combined.compartments == frozenset({"x", "y", "z"})

    def test_chain_with_duplicate_labels(self, boundary):
        combined = Label({"a"})
        combined = boundary.heritage(combined, Label({"a"}))
        combined = boundary.heritage(combined, Label({"a"}))
        assert combined.compartments == frozenset({"a"})


class TestHeritageAndBoundaryCheck:
    """Heritage labels should still be subject to boundary checks."""

    def test_heritage_result_passes_boundary_check(self, boundary):
        from dbp import Clearance

        label = boundary.heritage(Label({"a"}), Label({"b"}))
        result = boundary.check(label, clearance=Clearance({"a"}))
        assert result is not None

    def test_heritage_with_clearance(self, boundary):
        from dbp import Clearance, BoundaryResult

        label = boundary.heritage(Label({"engineering"}), Label({"hr"}))
        clearance = Clearance({"engineering"})

        result = boundary.check(label, clearance, Policy.ANY)
        assert result == BoundaryResult.PASS

        result = boundary.check(label, clearance, Policy.ALL)
        assert result == BoundaryResult.BLOCK

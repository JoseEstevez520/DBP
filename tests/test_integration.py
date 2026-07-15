"""End-to-end integration tests for DBP with multiple agents and transports."""

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


# ---------------------------------------------------------------------------
# Fixtures: agents with different clearances
# ---------------------------------------------------------------------------

@pytest.fixture
def boundary():
    return Boundary()


@pytest.fixture
def coach():
    return AgentCard(
        name="coach",
        clearance=Clearance({"identity", "fitness", "schedule"}),
        description="Personal fitness coach",
    )


@pytest.fixture
def coordinator():
    return AgentCard(
        name="coordinator",
        clearance=Clearance({"identity", "schedule"}),
        description="Coordinates tasks (no fitness access)",
    )


@pytest.fixture
def developer():
    return AgentCard(
        name="developer",
        clearance=Clearance({"identity", "project", "schedule"}),
        description="Software developer (no fitness access)",
    )


@pytest.fixture
def coach_to_coordinator(boundary, tmp_path):
    return LocalTransport(boundary, str(tmp_path / "coord-inbox"))


@pytest.fixture
def coach_to_developer(boundary, tmp_path):
    return LocalTransport(boundary, str(tmp_path / "dev-inbox"))


# ---------------------------------------------------------------------------
# Scenario 1: Direct send with boundary enforcement
# ---------------------------------------------------------------------------

class TestDirectSend:
    """Agent A sends labelled data to agent B — boundary either blocks or passes."""

    def test_coach_sends_fitness_to_coordinator_blocked(self, boundary, coach, coordinator):
        """Coach has fitness, coordinator doesn't. ALL policy blocks."""
        label = Label({"fitness", "schedule"}, policy=Policy.ALL)
        result = boundary.check(label, coordinator.clearance)
        assert result == BoundaryResult.BLOCK

    def test_coach_sends_fitness_to_coordinator_passes_any(self, boundary, coach, coordinator):
        """Coach has fitness, coordinator has schedule — ANY passes."""
        label = Label({"fitness", "schedule"})  # default ANY
        result = boundary.check(label, coordinator.clearance)
        assert result == BoundaryResult.PASS

    def test_coach_sends_schedule_to_coordinator_passes_all(self, boundary, coach, coordinator):
        """Schedule-only label — coordinator has schedule, ALL passes."""
        label = Label({"schedule"}, policy=Policy.ALL)
        result = boundary.check(label, coordinator.clearance)
        assert result == BoundaryResult.PASS

    def test_coach_sends_fitness_to_developer_blocked(self, boundary, coach, developer):
        """Developer doesn't have fitness. ALL blocks."""
        label = Label({"fitness", "schedule"}, policy=Policy.ALL)
        result = boundary.check(label, developer.clearance)
        assert result == BoundaryResult.BLOCK

    def test_coach_sends_identity_to_developer_passes(self, boundary, coach, developer):
        """Developer has identity — passes."""
        label = Label({"identity"})
        result = boundary.check(label, developer.clearance)
        assert result == BoundaryResult.PASS

    def test_transport_enforces_block_no_file_written(self, boundary, tmp_path):
        """Verify transport does NOT write file on BLOCK."""
        transport = LocalTransport(boundary, str(tmp_path / "enforce"))
        coach_card = AgentCard(name="coach", clearance=Clearance({"fitness", "schedule"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"project"}))

        msg = DBPMessage(id="secret-fit", label=Label({"fitness"}), origin="coach", payload={})
        result = transport.send(msg, coach_card, dev_card)
        assert result == BoundaryResult.BLOCK
        assert not (transport.base_path / "secret-fit.md").exists()

    def test_transport_writes_file_on_pass(self, boundary, tmp_path):
        """Verify transport writes file on PASS."""
        transport = LocalTransport(boundary, str(tmp_path / "pass-test"))
        coach_card = AgentCard(name="coach", clearance=Clearance({"schedule"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"schedule"}))

        msg = DBPMessage(id="schedule-msg", label=Label({"schedule"}), origin="coach", payload={"day": "Mon"})
        result = transport.send(msg, coach_card, dev_card)
        assert result == BoundaryResult.PASS
        assert (transport.base_path / "schedule-msg.md").exists()


# ---------------------------------------------------------------------------
# Scenario 2: Derived data inherits labels (Heritage)
# ---------------------------------------------------------------------------

class TestHeritageIntegration:
    """R4 — derived data inherits union of source labels."""

    def test_derived_data_inherits_labels(self, boundary):
        fitness_label = Label({"fitness"})
        schedule_label = Label({"schedule"})
        derived = boundary.heritage(fitness_label, schedule_label)
        assert derived.compartments == frozenset({"fitness", "schedule"})

    def test_heritage_data_more_restricted(self, boundary, coordinator):
        """Derived data with heritage label is at least as restricted."""
        derived = boundary.heritage(Label({"fitness"}), Label({"schedule"}))
        result_any = boundary.check(derived, coordinator.clearance, Policy.ANY)
        result_all = boundary.check(derived, coordinator.clearance, Policy.ALL)
        assert result_any == BoundaryResult.PASS  # schedule
        assert result_all == BoundaryResult.BLOCK  # missing fitness

    def test_heritage_chain_across_agents(self, boundary):
        """A → B → C: heritage accumulates at each step."""
        step1 = boundary.heritage(Label({"alpha"}), Label({"beta"}))
        step2 = boundary.heritage(step1, Label({"gamma"}))
        step3 = boundary.heritage(step2, Label({"delta"}))
        assert step3.compartments == frozenset({"alpha", "beta", "gamma", "delta"})


# ---------------------------------------------------------------------------
# Scenario 3: Read-in filtering at startup
# ---------------------------------------------------------------------------

class TestReadInIntegration:
    """R1 — agent receives only permitted data at startup."""

    class LabelledItem:
        def __init__(self, label, name=""):
            self.label = label
            self.name = name

    def test_coordinator_reads_only_permitted_data(self, boundary, coordinator):
        items = [
            self.LabelledItem(Label({"identity"}), "user-profile"),
            self.LabelledItem(Label({"fitness"}), "workout-plan"),
            self.LabelledItem(Label({"schedule"}), "calendar"),
            self.LabelledItem(Label({"project"}), "repo-access"),
            self.LabelledItem(Label(set()), "public-announcement"),
        ]
        allowed = boundary.read_in(items, coordinator.clearance)
        names = [i.name for i in allowed]
        assert "user-profile" in names       # identity shared
        assert "calendar" in names            # schedule shared
        assert "public-announcement" in names # empty label
        assert "workout-plan" not in names    # fitness not shared
        assert "repo-access" not in names     # project not shared

    def test_developer_reads_only_permitted_data(self, boundary, developer):
        items = [
            self.LabelledItem(Label({"identity"}), "user-profile"),
            self.LabelledItem(Label({"fitness"}), "workout-plan"),
            self.LabelledItem(Label({"project"}), "source-code"),
        ]
        allowed = boundary.read_in(items, developer.clearance)
        names = [i.name for i in allowed]
        assert "user-profile" in names
        assert "source-code" in names
        assert "workout-plan" not in names


# ---------------------------------------------------------------------------
# Scenario 4: Full chain — Coach → Coordinator → Developer
# ---------------------------------------------------------------------------

class TestFullChain:
    """End-to-end chain with boundary check at each hop."""

    def test_coach_to_coordinator_to_developer_chain(self, boundary, tmp_path):
        coach_card = AgentCard(name="coach", clearance=Clearance({"identity", "fitness", "schedule"}))
        coord_card = AgentCard(name="coordinator", clearance=Clearance({"identity", "schedule"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"identity", "project", "schedule"}))

        coord_inbox = LocalTransport(boundary, str(tmp_path / "coord"))
        dev_inbox = LocalTransport(boundary, str(tmp_path / "dev"))

        # Step 1: Coach sends "workout plan" to Coordinator
        workout_msg = DBPMessage(
            id="wp-1",
            label=Label({"fitness", "schedule"}),
            origin="coach",
            payload={"exercise": "pushups", "sets": 5},
        )
        result = coord_inbox.send(workout_msg, coach_card, coord_card)
        assert result == BoundaryResult.PASS  # ANY: schedule matches

        # Step 2: Coordinator receives it
        coord_received = coord_inbox.receive(coord_card)
        assert len(coord_received) == 1
        assert coord_received[0].id == "wp-1"

        # Step 3: Coach sends "client schedule" to Coordinator
        sched_msg = DBPMessage(
            id="cs-1",
            label=Label({"schedule"}),
            origin="coach",
            payload={"client": "Acme", "time": "10:00"},
        )
        coord_inbox.send(sched_msg, coach_card, coord_card)
        coord_received = coord_inbox.receive(coord_card)
        assert len(coord_received) == 2

        # Step 4: Coordinator derives new data (heritage)
        derived_label = boundary.heritage(Label({"fitness", "schedule"}), Label({"schedule"}))
        assert derived_label.compartments == frozenset({"fitness", "schedule"})

        # Step 5: Coordinator sends derived data to Developer
        derived_msg = DBPMessage(
            id="derived-1",
            label=derived_label,
            origin="coordinator",
            payload={"summary": "workout + schedule"},
        )
        result = dev_inbox.send(derived_msg, coord_card, dev_card)
        assert result == BoundaryResult.PASS  # ANY: schedule matches

        # Step 6: Developer receives derived data
        dev_received = dev_inbox.receive(dev_card)
        assert len(dev_received) == 1
        assert dev_received[0].id == "derived-1"
        assert dev_received[0].payload["summary"] == "workout + schedule"

        # Step 7: Verify trace log recorded everything
        assert len(boundary.trace_log) >= 5

    def test_blocked_chain_never_reaches_developer(self, boundary, tmp_path):
        """If Coordinator blocks, Developer never sees the data."""
        coach_card = AgentCard(name="coach", clearance=Clearance({"fitness"}))
        coord_card = AgentCard(name="coordinator", clearance=Clearance({"identity"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"identity"}))

        coord_inbox = LocalTransport(boundary, str(tmp_path / "coord-blocked"))
        dev_inbox = LocalTransport(boundary, str(tmp_path / "dev-blocked"))

        # Coach sends fitness data to Coordinator (no overlap — BLOCK)
        msg = DBPMessage(
            id="blocked-chain",
            label=Label({"fitness"}),
            origin="coach",
            payload={"secret": "training"},
        )
        result = coord_inbox.send(msg, coach_card, coord_card)
        assert result == BoundaryResult.BLOCK

        # No file written = Coordinator never receives it
        assert not (coord_inbox.base_path / "blocked-chain.md").exists()
        coord_received = coord_inbox.receive(coord_card)
        assert len(coord_received) == 0

        # Developer inbox is also empty
        assert len(dev_inbox.receive(dev_card)) == 0


# ---------------------------------------------------------------------------
# Scenario 5: Multiple messages, mixed results
# ---------------------------------------------------------------------------

class TestMixedMessages:
    """Multiple messages sent, only those passing boundary are received."""

    def test_mixed_pass_and_block(self, boundary, tmp_path):
        coach_card = AgentCard(name="coach", clearance=Clearance({"fitness", "schedule", "identity"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"identity", "project"}))

        transport = LocalTransport(boundary, str(tmp_path / "mixed"))

        messages = [
            DBPMessage(id="m1", label=Label({"identity"}), origin="coach", payload={"n": 1}),
            DBPMessage(id="m2", label=Label({"fitness"}), origin="coach", payload={"n": 2}),
            DBPMessage(id="m3", label=Label({"project"}), origin="coach", payload={"n": 3}),
            DBPMessage(id="m4", label=Label({"identity", "project"}), origin="coach", payload={"n": 4}),
        ]

        for msg in messages:
            transport.send(msg, coach_card, dev_card)

        received = transport.receive(dev_card)
        ids = [m.id for m in received]

        assert "m1" in ids   # identity shared
        assert "m2" not in ids  # fitness not in developer clearance
        assert "m3" in ids   # project shared
        assert "m4" in ids   # identity + project: ANY passes

    def test_trace_records_all_checks(self, boundary, tmp_path):
        coach_card = AgentCard(name="coach", clearance=Clearance({"A"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"B"}))

        transport = LocalTransport(boundary, str(tmp_path / "traced"))

        msg_pass = DBPMessage(id="p", label=Label({"B"}), origin="coach", payload={})
        msg_block = DBPMessage(id="b", label=Label({"A"}), origin="coach", payload={})

        transport.send(msg_pass, coach_card, dev_card)
        transport.send(msg_block, coach_card, dev_card)

        # 2 send checks + 1 receive check (receive checks msg_pass, skip msg_block on frontmatter)
        assert len(boundary.trace_log) >= 2


# ---------------------------------------------------------------------------
# Scenario 6: All policies and edge cases
# ---------------------------------------------------------------------------

class TestPolicyIntegration:
    """Integration with different policies across agents."""

    def test_any_policy_multi_agent(self, boundary):
        """ANY: one matching compartment among many is enough."""
        label = Label({"a", "b", "c"})

        agent1 = Clearance({"a"})
        agent2 = Clearance({"b"})
        agent3 = Clearance({"d", "e"})

        assert boundary.check(label, agent1, Policy.ANY) == BoundaryResult.PASS
        assert boundary.check(label, agent2, Policy.ANY) == BoundaryResult.PASS
        assert boundary.check(label, agent3, Policy.ANY) == BoundaryResult.BLOCK

    def test_all_policy_multi_agent(self, boundary):
        """ALL: every compartment must be in clearance."""
        label = Label({"a", "b"}, policy=Policy.ALL)

        agent1 = Clearance({"a", "b", "c"})
        agent2 = Clearance({"a"})
        agent3 = Clearance({"b"})
        agent4 = Clearance({"a", "b"})

        assert boundary.check(label, agent1) == BoundaryResult.PASS
        assert boundary.check(label, agent2) == BoundaryResult.BLOCK
        assert boundary.check(label, agent3) == BoundaryResult.BLOCK
        assert boundary.check(label, agent4) == BoundaryResult.PASS

    def test_empty_label_unrestricted(self, boundary):
        """Empty label passes regardless of policy."""
        unrestricted = Label(set())
        top_secret = Clearance({"top-secret"})
        assert boundary.check(unrestricted, top_secret, Policy.ANY) == BoundaryResult.PASS
        assert boundary.check(unrestricted, top_secret, Policy.ALL) == BoundaryResult.PASS

    def test_transport_all_policy_enforcement(self, boundary, tmp_path):
        coord_card = AgentCard(name="coordinator", clearance=Clearance({"identity"}))
        dev_card = AgentCard(name="developer", clearance=Clearance({"identity", "project"}))

        transport = LocalTransport(boundary, str(tmp_path / "all-pol"))

        msg_all = DBPMessage(
            id="all-msg",
            label=Label({"identity", "project"}, policy=Policy.ALL),
            origin="coordinator",
            payload={"task": "audit"},
            policy=Policy.ALL,
        )

        # Coordinator sending to Developer: both have identity + project → PASS
        result = transport.send(msg_all, coord_card, dev_card)
        assert result == BoundaryResult.PASS
        assert (transport.base_path / "all-msg.md").exists()

        # Coordinator sending to self (or someone missing project): would BLOCK
        msg_all_2 = DBPMessage(
            id="all-block-2",
            label=Label({"identity", "project"}, policy=Policy.ALL),
            origin="coordinator",
            payload={"task": "secret"},
            policy=Policy.ALL,
        )
        result = transport.send(msg_all_2, coord_card, coord_card)  # coordinator has only identity
        assert result == BoundaryResult.BLOCK
        assert not (transport.base_path / "all-block-2.md").exists()

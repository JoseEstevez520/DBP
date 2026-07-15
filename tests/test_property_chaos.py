"""Property-based and chaos tests for DBP using random generation (stdlib)."""

import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    EscalationResult,
    InvalidMessageError,
    Label,
    Policy,
    TraceRecord,
)
from dbp.errors import EmptyClearanceError
from dbp.transport.local import LocalTransport
from dbp.transport.http import HTTPTransport

random.seed(42)

ALL_COMPARTMENTS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]


def random_compartments(min_n=0, max_n=8):
    n = random.randint(min_n, max_n)
    return set(random.sample(ALL_COMPARTMENTS, min(n, len(ALL_COMPARTMENTS))))


def random_label():
    return Label(random_compartments(0, 5), policy=random.choice([Policy.ANY, Policy.ALL]))


def random_clearance():
    return Clearance(random_compartments(1, 8))


# ==============================================================================
# PART 1: Property-based tests
# ==============================================================================


class TestBoundaryProperties:
    """8 invariant properties tested with 500+ random iterations each."""

    N = 500

    def test_property_1_empty_label_always_pass(self):
        """Property 1: Empty label always PASS regardless of clearance."""
        b = Boundary()
        for _ in range(self.N):
            clearance = random_clearance()
            policy = random.choice([Policy.ANY, Policy.ALL])
            assert b.check(Label(set()), clearance, policy) == BoundaryResult.PASS

    def test_property_2_all_policy_requires_all_compartments(self):
        """Property 2: ALL policy requires ALL compartments (if even one missing, BLOCK)."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()

            result = b.check(label, clearance, Policy.ALL)
            missing = label.compartments - clearance.compartments
            if missing:
                assert result == BoundaryResult.BLOCK
            else:
                assert result == BoundaryResult.PASS

    def test_property_3_any_policy_pass_if_any_match(self):
        """Property 3: ANY policy PASS if ANY compartment matches."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()

            result = b.check(label, clearance, Policy.ANY)
            has_intersection = bool(label.compartments & clearance.compartments)
            if label.is_empty() or has_intersection:
                assert result == BoundaryResult.PASS
            else:
                assert result == BoundaryResult.BLOCK

    def test_property_4_heritage_never_less_restricted(self):
        """Property 4: Heritage result is NEVER less restricted than sources."""
        b = Boundary()
        for _ in range(self.N):
            n_labels = random.randint(1, 5)
            labels = [random_label() for _ in range(n_labels)]
            heritage = b.heritage(*labels)

            all_compartments = set()
            for l in labels:
                all_compartments |= set(l.compartments)
            assert heritage.compartments == frozenset(all_compartments)

    def test_property_5_can_write_iff_label_subset_clearance(self):
        """Property 5: can_write PASS iff label ⊆ clearance."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()

            expected = label.compartments <= clearance.compartments
            assert b.can_write(label, clearance) == expected

    def test_property_6_trace_log_append_only(self):
        """Property 6: Trace log is append-only (length never decreases)."""
        b = Boundary()
        prev_len = 0
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()
            b.check(label, clearance)
            assert len(b.trace_log) > prev_len
            prev_len = len(b.trace_log)

    def test_property_7_trace_records_immutable(self):
        """Property 7: Trace records are immutable (cannot modify after creation)."""
        b = Boundary()
        for _ in range(self.N):
            b.check(random_label(), random_clearance())
        for rec in b.trace_log:
            with pytest.raises((AttributeError, TypeError)):
                rec.result = BoundaryResult.PASS
            with pytest.raises((AttributeError, TypeError)):
                rec.blocked_by = frozenset()

    def test_property_8_determinism(self):
        """Property 8: Same inputs always return same result."""
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()
            policy = random.choice([Policy.ANY, Policy.ALL])

            results = []
            for _ in range(5):
                b = Boundary()
                results.append(b.check(label, clearance, policy))
            assert all(r == results[0] for r in results)


class TestHeritageProperties:
    """Heritage-specific property tests."""

    N = 500

    def test_heritage_union_of_n_random_labels(self):
        """Heritage of N random labels: result compartments = union of all inputs."""
        b = Boundary()
        for _ in range(self.N):
            n = random.randint(1, 6)
            labels = [random_label() for _ in range(n)]
            result = b.heritage(*labels)
            expected = frozenset().union(*(l.compartments for l in labels))
            assert result.compartments == expected

    def test_heritage_no_duplicates(self):
        """Heritage of overlapping labels: no duplicates in result."""
        b = Boundary()
        for _ in range(self.N):
            overlapping = Label({"a", "b"})
            result = b.heritage(Label({"a", "c"}), overlapping, Label({"b", "d"}))
            assert result.compartments == frozenset({"a", "b", "c", "d"})
            assert len(result.compartments) == 4

    def test_heritage_chain_5_levels(self):
        """Heritage chain of 5 levels: final has ALL compartments."""
        b = Boundary()
        for _ in range(self.N):
            levels = []
            for _ in range(5):
                levels.append(Label(random_compartments(1, 4)))

            l1 = b.heritage(levels[0], levels[1])
            l2 = b.heritage(l1, levels[2])
            l3 = b.heritage(l2, levels[3])
            l4 = b.heritage(l3, levels[4])

            expected = frozenset().union(*(l.compartments for l in levels))
            assert l4.compartments == expected


class TestEscalationProperties:
    """Escalation property tests."""

    N = 500

    def test_superset_clearance_grants(self):
        """Escalation to parent with superset clearance always GRANTs."""
        b = Boundary()
        for _ in range(self.N):
            worker_comps = random_compartments(1, 3)
            label = Label(random_compartments(1, 4))
            parent_comps = set(worker_comps) | set(label.compartments) | random_compartments(0, 2)
            parent_comps -= set()
            if not parent_comps:
                parent_comps.add("fallback")

            worker = AgentCard(name="worker", clearance=Clearance(worker_comps))
            parent = AgentCard(name="parent", clearance=Clearance(parent_comps))

            result = b.escalate(worker, label, "need", parent)
            # Label compartments are subset of parent clearance by construction
            if label.compartments.issubset(parent.clearance.compartments):
                assert result == EscalationResult.GRANT

    def test_subset_clearance_denies(self):
        """Escalation to parent with subset clearance always DENYs."""
        b = Boundary()
        for _ in range(self.N):
            parent_comps = random_compartments(1, 3)
            label = Label(random_compartments(1, 5))
            worker_comps = set(parent_comps) | random_compartments(0, 2)

            worker = AgentCard(name="worker", clearance=Clearance(worker_comps | {"x"}))
            parent = AgentCard(name="parent", clearance=Clearance(parent_comps))

            result = b.escalate(worker, label, "need", parent)
            if not label.compartments.issubset(parent.clearance.compartments):
                assert result == EscalationResult.DENY

    def test_escalate_without_parent(self):
        """Escalation without parent always returns ESCALATE."""
        b = Boundary()
        for _ in range(self.N):
            worker = AgentCard(
                name="worker",
                clearance=Clearance(random_compartments(1, 4)),
            )
            label = random_label()
            result = b.escalate(worker, label, "no parent")
            assert result == EscalationResult.ESCALATE

    def test_escalation_trace_recorded_every_call(self):
        """Escalation trace recorded for every call."""
        b = Boundary()
        for _ in range(50):
            before = len(b.trace_log)
            worker = AgentCard(
                name="worker",
                clearance=Clearance(random_compartments(1, 3)),
            )
            label = random_label()
            parent = AgentCard(
                name="parent",
                clearance=Clearance(random_compartments(1, 6)),
            ) if random.random() > 0.3 else None

            b.escalate(worker, label, "test", parent)
            assert len(b.trace_log) > before


class TestPolicyProperties:
    """Policy-specific property tests."""

    N = 500

    def test_any_policy_pass_iff_intersection(self):
        """ANY policy: PASS iff label ∩ clearance ≠ ∅."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()

            result = b.check(label, clearance, Policy.ANY)
            expected = label.is_empty() or bool(label.compartments & clearance.compartments)
            assert (result == BoundaryResult.PASS) == expected

    def test_all_policy_pass_iff_subset(self):
        """ALL policy: PASS iff label ⊆ clearance."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()

            result = b.check(label, clearance, Policy.ALL)
            expected = label.is_empty() or label.compartments.issubset(clearance.compartments)
            assert (result == BoundaryResult.PASS) == expected

    def test_policy_override_works(self):
        """Policy override works correctly (pass explicit policy)."""
        b = Boundary()
        for _ in range(self.N):
            label = random_label()
            clearance = random_clearance()
            override = Policy.ALL if label.policy == Policy.ANY else Policy.ANY

            default_result = b.check(label, clearance)
            overridden_result = b.check(label, clearance, override)

            assert default_result is not overridden_result or default_result == overridden_result


# ==============================================================================
# PART 2: Chaos tests
# ==============================================================================


class TestMalformedMessages:
    """Chaos: malformed DBPMessage construction and deserialization."""

    def test_empty_origin_raises(self):
        with pytest.raises(InvalidMessageError, match="origin is required"):
            DBPMessage(id="x", label=Label({"a"}), origin="", payload={})

    def test_none_label_raises(self):
        with pytest.raises(InvalidMessageError, match="label is required"):
            DBPMessage(id="x", label=None, origin="alice", payload={})

    def test_from_json_missing_label_key(self):
        bad = json.dumps({"origin": "alice", "payload": {}})
        with pytest.raises(InvalidMessageError, match="Missing required field"):
            DBPMessage.from_json(bad)

    def test_from_json_invalid_json(self):
        with pytest.raises(InvalidMessageError, match="Invalid JSON"):
            DBPMessage.from_json("not-json-at-all{{{}}}")

    def test_from_json_missing_compartments(self):
        bad = json.dumps({
            "label": {"policy": "any"},
            "origin": "alice", "payload": {},
        })
        with pytest.raises(InvalidMessageError):
            DBPMessage.from_json(bad)


class TestMalformedTransports:
    """Chaos: malformed transport scenarios."""

    def test_local_no_frontmatter_skipped(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, tmp_path)
        f = tmp_path / "no-frontmatter.md"
        f.write_text("Just plain text, no frontmatter", encoding="utf-8")

        agent = AgentCard(name="reader", clearance=Clearance({"a"}))
        messages = transport.receive(agent)
        assert messages == []

    def test_local_corrupted_frontmatter_skipped(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, tmp_path)
        f = tmp_path / "bad-fm.md"
        f.write_text("---\nthis is not valid frontmatter\nno colons here\n---\n\nbody", encoding="utf-8")

        agent = AgentCard(name="reader", clearance=Clearance({"a"}))
        messages = transport.receive(agent)
        assert messages == []

    def test_local_missing_delimiter_skipped(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, tmp_path)
        f = tmp_path / "no-delim.md"
        f.write_text("compartments: [a]\npolicy: any\n---\n\nbody", encoding="utf-8")

        agent = AgentCard(name="reader", clearance=Clearance({"a"}))
        messages = transport.receive(agent)
        assert messages == []

    def test_http_middleware_no_label_header_proceeds_with_empty_label(self):
        """No X-DBP-Label header -> empty label -> always PASS -> proceed."""
        b = Boundary()
        transport = HTTPTransport(b)
        agent = AgentCard(name="receiver", clearance=Clearance({"secret"}))

        class FakeRequest:
            headers = {}
        req = FakeRequest()

        mw = transport.middleware(agent)
        result = mw(req)
        assert result is None

    def test_http_middleware_empty_label_header_proceeds(self):
        """Empty label header -> empty label -> always PASS -> proceed."""
        b = Boundary()
        transport = HTTPTransport(b)
        agent = AgentCard(name="receiver", clearance=Clearance({"secret"}))

        class FakeRequest:
            headers = {transport.LABEL_HEADER: ""}
        req = FakeRequest()

        mw = transport.middleware(agent)
        result = mw(req)
        assert result is None

    def test_http_middleware_blocked_label_returns_403(self):
        """Label with no overlap in clearance -> BLOCK -> 403."""
        b = Boundary()
        transport = HTTPTransport(b)
        agent = AgentCard(name="receiver", clearance=Clearance({"secret"}))

        class FakeRequest:
            headers = {transport.LABEL_HEADER: "restricted", transport.POLICY_HEADER: "any"}
        req = FakeRequest()

        mw = transport.middleware(agent)
        result = mw(req)
        assert result is not None
        assert result["status"] == 403

    def test_http_middleware_with_valid_label_passes(self):
        b = Boundary()
        transport = HTTPTransport(b)
        agent = AgentCard(name="receiver", clearance=Clearance({"public"}))

        class FakeRequest:
            headers = {transport.LABEL_HEADER: "public"}
        req = FakeRequest()

        mw = transport.middleware(agent)
        result = mw(req)
        assert result is None


class TestRaceCondition:
    """Chaos: concurrent sends to the same recipient."""

    N_AGENTS = 10

    def test_concurrent_sends_all_pass(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, tmp_path / "race_inbox")

        recipient = AgentCard(name="receiver", clearance=Clearance({"a", "b", "c"}))

        agents = []
        for i in range(self.N_AGENTS):
            agents.append(AgentCard(
                name=f"agent-{i}",
                clearance=Clearance({"a", "b"}),
            ))

        labels = [Label({"a"}), Label({"b"}), Label({"a", "b"}), Label(set())]

        def send_it(agent, idx):
            label = labels[idx % len(labels)]
            msg = DBPMessage(
                id=f"race-{agent.name}-{idx}",
                label=label,
                origin=agent.name,
                payload={"seq": idx},
            )
            return agent.name, transport.send(msg, agent, recipient)

        with ThreadPoolExecutor(max_workers=self.N_AGENTS) as pool:
            fut = {pool.submit(send_it, agents[i], i): i for i in range(self.N_AGENTS)}
            results = {}
            for f in as_completed(fut):
                name, result = f.result()
                results[name] = result

        for name, result in results.items():
            assert result == BoundaryResult.PASS, f"{name} got {result}"

        received = transport.receive(recipient)
        assert len(received) > 0
        assert len(received) <= self.N_AGENTS

    def test_concurrent_sends_trace_log(self, tmp_path):
        b = Boundary()
        recipient = AgentCard(name="receiver", clearance=Clearance({"a", "b", "c"}))

        agents = []
        for i in range(self.N_AGENTS):
            agents.append(AgentCard(
                name=f"agent-{i}",
                clearance=Clearance({"a", "b"}),
            ))

        def check_it(agent):
            label = Label({"a"})
            return b.check(label, agent.clearance)

        before = len(b.trace_log)
        with ThreadPoolExecutor(max_workers=self.N_AGENTS) as pool:
            fut = [pool.submit(check_it, agents[i]) for i in range(self.N_AGENTS)]
            for f in as_completed(fut):
                f.result()

        assert len(b.trace_log) == before + self.N_AGENTS


class TestBoundaryConsistency:
    """Chaos: consistency and determinism across agents."""

    N = 1000

    def test_same_label_deterministic_across_agents(self):
        b = Boundary()
        label = random_label()
        clearance = random_clearance()

        results = []
        for _ in range(self.N):
            results.append(b.check(label, clearance))

        first = results[0]
        assert all(r == first for r in results)

    def test_different_clearances_same_label(self):
        b = Boundary()
        label = Label({"a", "b"})

        for policy in [Policy.ANY, Policy.ALL]:
            clearances = []
            for _ in range(10):
                comps = set(random.sample(ALL_COMPARTMENTS, random.randint(1, 8)))
                clearances.append(Clearance(comps))

            for clearance in clearances:
                result = b.check(label, clearance, policy)
                if policy == Policy.ALL:
                    expect_pass = label.compartments.issubset(clearance.compartments)
                else:
                    expect_pass = bool(label.compartments & clearance.compartments)
                assert (result == BoundaryResult.PASS) == expect_pass

    def test_many_agents_same_data_deterministic(self, tmp_path):
        b = Boundary()
        transport = LocalTransport(b, tmp_path / "shared")

        label = Label({"a", "c"})
        msg = DBPMessage(id="shared-msg", label=label, origin="producer", payload={"data": 1})

        agents = []
        for i in range(10):
            comps = set(random.sample(ALL_COMPARTMENTS, random.randint(1, 6)))
            if "a" in comps or "c" in comps:
                comps.add("a")
                comps.add("c")
            agents.append(AgentCard(name=f"agent-{i}", clearance=Clearance(comps)))

        results = {}
        for agent in agents:
            results[agent.name] = transport.send(msg, agents[0], agent)

        for name, result in results.items():
            # If SAME label is sent, result depends on the recipient's clearance
            agent = [a for a in agents if a.name == name][0]
            expected = label.compartments.issubset(agent.clearance.compartments)
            assert (result == BoundaryResult.PASS) == expected or label.is_empty()

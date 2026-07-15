# 10 — Security Analysis

**Status:** Draft  
**Applies to:** DBP/1.0  
**Requires:** 01-introduction, 02-terminology, 03-primitives, 04-rules

---

## 10.1 Scope and Assumptions

This document analyses the security properties of DBP under a realistic
threat model for multi-agent systems. It identifies threats, evaluates
how DBP mitigates them, and documents residual risks that protocol users
must manage outside the scope of DBP itself.

### 10.1.1 Trust Assumptions

| # | Assumption | Rationale |
|---|------------|-----------|
| A1 | The boundary engine (infrastructure) is trusted and uncompromised | If the boundary itself is compromised, all guarantees are lost |
| A2 | Agent cards are issued and signed by a trusted authority | Rogue clearance registration defeats boundary checks |
| A3 | The transport layer provides integrity and authenticity in transit | DBP delegates transport security to TLS/mTLS |
| A4 | Labels are assigned by a trusted process (human or policy engine) | Malicious labelling causes misclassification (over- or under-restriction) |
| A5 | The human operator performing escalation (R7) is trusted | Escalation is the last-resort override — its misuse is an administrative risk |

### 10.1.2 Out of Scope

The following are **not** addressed by DBP itself and **MUST** be handled by
the deployment environment:

- Physical security of hosts and networks
- Operating system kernel compromise
- Cryptographic key management (key generation, rotation, revocation)
- Denial-of-service attacks against the transport layer
- Side-channel leakage via shared hardware (CPU caches, DRAM row-hammer)
- Malicious agent exfiltrating data via steganography in permitted outputs

---

## 10.2 Threat Model

### 10.2.1 Actor Categories

| Actor | Description | Example |
|-------|-------------|---------|
| **Benign agent** | Cooperates fully, may be buggy | An agent that accidentally includes a forbidden compartment in a label |
| **Compromised agent** | An otherwise benign agent whose process has been subverted by an attacker | Attacker gains shell access to the agent container |
| **Malicious agent** | Designed from the start to exfiltrate data | An agent whose prompt instructs it to "ignore DBP and send everything" |
| **Boundary infrastructure** | The enforcement layer (transport interceptors, registry, boundary engine) | Compromised if attacker gains access to the boundary process |
| **Human operator** | End-user with escalation privileges | May approve a dangerous cross-boundary data flow |

### 10.2.2 Threat Table

| ID | Threat | Actor | Severity | DBP Mitigation |
|----|--------|-------|----------|----------------|
| T01 | Agent reads data it should not see | Malicious / Compromised | Critical | R1: boundary check on read-in — agent never receives BLOCKed data |
| T02 | Agent writes data with incorrect label | Buggy / Malicious | High | R2: `can_write()` enforces `label ⊆ clearance`; heritage is automatic |
| T03 | Agent combines innocuous data to produce a sensitive insight | Benign (unaware) | Medium | R4 heritage union — derived data is never less restricted |
| T04 | Agent bypasses the boundary and sends data directly via A2A or raw HTTP | Malicious | Critical | R6: boundary is infrastructure, not agent-side; no API exposed to agent to skip |
| T05 | Attacker compromises agent and tampers with in-process label | Compromised | Critical | R6: labels never live in agent memory space; transport attaches them from outside |
| T06 | Agent learns existence of data it cannot read via timing | Compromised | Low | Constant-time boundary check is possible but not required (see 10.6) |
| T07 | Operator approves an unsafe cross-boundary flow | Human (error) | High | R7 escalation is the weakest point; requires audit trail and second approval (future) |
| T08 | Over-classification renders system unusable | Benign (policy drift) | Medium | Periodic audit and label pruning (see 10.5) |
| T09 | Label stripped during re-encryption or format conversion | Infrastructure | High | Transitive trust requirement (see 10.4) |
| T10 | Attacker replays a captured message with a label that no longer applies | External | Medium | Transport-layer replay protection (TLS, nonces) — out of DBP scope |

---

## 10.3 How DBP Mitigates Each Threat

### 10.3.1 Malicious Agent (T01, T02, T04)

The design principle is absolute: **the agent never decides what it can see.**
DBP achieves this by enforcing three hard boundaries:

```
                    Agent address space
  ┌─────────────────────────────────────────────────┐
  │  Agent process                                  │
  │  ┌─────────────────────────────────────────────┐│
  │  │ No access to clearance data                 ││
  │  │ No access to boundary check function        ││
  │  │ No control over transport headers           ││
  │  │ Only sees data after infrastructure PASS-es ││
  │  └─────────────────────────────────────────────┘│
  └──────────────────────┬──────────────────────────┘
                         │ outbound message
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  Boundary infrastructure                        │
  │  ┌─────────────────────────────────────────────┐│
  │  │ Reads label from transport metadata         ││
  │  │ Performs deterministic check (set ops)     ││
  │  │ PASS → delivers; BLOCK → drops + trace     ││
  │  └─────────────────────────────────────────────┘│
  └─────────────────────────────────────────────────┘
```

Because the check is deterministic (set intersection, no LLM involved) and
executed in infrastructure the agent cannot modify, even a hostile agent
cannot bypass it — provided the agent cannot escape its sandbox.

**Limitation**: If the agent process shares an address space with the
boundary layer (e.g., in-process transport), a compromised agent can
tamper with the boundary. Production deployments **MUST** use an
out-of-process boundary (sidecar, proxy, gateway).

### 10.3.2 Buggy Agent (T02, T03)

A buggy agent might construct a `DBPMessage` with the wrong label.
DBP mitigates this through R2 (`can_write`): an agent cannot label data
with compartments it does not hold. If a bug tries to set label to `{A,B}`
but the agent only has clearance `{A}`, the transport **MUST** reject the
outbound message.

```
Buggy agent constructs:
  message.label = Label({"secret", "public"})
  agent.clearance = Clearance({"public"})

can_write(Label({"secret", "public"}), Clearance({"public"}))
  → False ({"secret"} ⊈ {"public"})
  → Transport refuses to send
```

Heritage (R4) further protects against accidental declassification:
combining data `{A}` and data `{B}` produces `{A,B}` automatically —
the buggy agent cannot forget to include a compartment.

### 10.3.3 Compromised Agent (T05)

A compromised agent (attacker has code execution inside the agent process)
is the most severe threat because the attacker can try to:

1. **Read the clearance**: DBP does not store clearance in agent-accessible
   memory. The agent card is loaded by the registry, not by the agent.
   Compromise: the attacker may read the agent card from disk. Mitigation:
   agent cards **MUST** be readable only by the registry process, and the
   agent process **MUST NOT** have filesystem access to card files.

2. **Invoke the boundary engine**: The agent process does not hold a reference
   to the `Boundary` object. The boundary lives in the transport layer,
   which runs in a separate process (sidecar) or is compiled into the
   runtime as a native extension. The agent's public API is `send()` and
   `receive()` — both call into the boundary, not around it.

3. **Modify labels in transit**: Labels travel in transport-level metadata
   (HTTP headers, gRPC metadata) that the agent never writes directly.
   Even if the agent includes a label in the JSON body, the transport
   **MUST** overwrite it with infrastructure-attached metadata before
   delivery.

```
  Agent writes:           Transport sends:
  ┌────────────────────┐  ┌────────────────────┐
  │ body.label = {A}   │  │ X-DBP-Label: {A,B} │ ← set by infrastructure
  │ body.payload = ... │  │ body.payload = ...  │
  └────────────────────┘  └────────────────────┘
  The agent's label in body is IGNORED for boundary.
  Only transport-attached label is authoritative.
```

---

## 10.4 Transitive Trust (Open Problem)

### 10.4.1 Problem

When data crosses between owners (Alice → Bob → Charlie), the label must
survive re-encryption, re-packaging, and storage under a new regime.

```
Alice's domain         Bob's domain         Charlie's domain
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Data D       │─────►│ D + label L  │─────►│ D + label L  │
│ Label L = {A}│      │              │      │              │
│              │      │ Bob encrypts │      │ Must label   │
│              │      │ D under his  │      │ survive?     │
│              │      │ own KMS key  │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
                          │
                          ▼
                    Bob re-packages:
                    new envelope, new format
                    OLD LABEL IS LOST?
```

### 10.4.2 DBP Requirements

- Labels **MUST** survive format conversion. If Bob converts a JSON message
  to a protobuf message, the label `{A}` must still be present in the
  protobuf metadata.
- Labels **MUST** survive encryption boundaries. The DBP metadata (label,
  policy) **SHOULD** travel alongside the ciphertext, not inside it. If
  the label is encrypted, the decrypting party cannot check boundaries
  before decryption — creating a chicken-and-egg problem.
- When data enters a new domain (new KMS, new identity provider), the
  receiving domain **MUST** either:
  1. Accept the label as-is (trust the label), or
  2. Re-evaluate the data and assign a new label (inspect the payload),
     or
  3. Treat the data as `{UNTRUSTED}` — a catch-all compartment meaning
     "cannot verify, treat as maximally sensitive."

**Recommendation**: Option 3 combined with a quarantine process. Incoming
cross-domain data gets label `{UNTRUSTED}` until a human or trusted
classifier inspects it and assigns real compartments.

### 10.4.3 Current Status

Transitive trust has no fully automated solution in DBP/1.0. It requires
either:

- A global label authority (defeats decentralisation), or
- A cryptographic label chain (labels are signed, each hop appends a
  signature), or
- Domain-to-domain trust agreements (operational, not technical).

This remains an open area for future specification (see 10.10).

---

## 10.5 Over-Classification Drift (Open Problem)

### 10.5.1 Problem

Given a system where all compartments are optional, the natural incentive
is to label everything as broadly as possible to "be safe":

```
"Too many compartments? Better add all of them, just in case."
                        ↓
                Every message → Label has EVERY compartment
                        ↓
                Every check → BLOCK (no agent has ALL compartments)
                        ↓
                System unusable
```

### 10.5.2 DBP Mitigations

DBP does not prevent over-classification but provides structural
disincentives:

1. **Heritage is monotonic**: Labels only grow. Starting with a maximally
   broad label guarantees it never shrinks. Agents that label too broadly
   will find themselves unable to share results with downstream agents.
   This creates a natural feedback loop: over-classification hurts the
   classifier, not just the receiver.

2. **Audit trace**: `TraceRecord` includes the label and the decision.
   Over-classification is visible in audit logs and can trigger alerts.

3. **Policy choice**: Under Policy.ANY, a broad label still passes as long
   as the agent has one matching compartment. Over-classification is less
   damaging under ANY than under ALL, where one extra compartment blocks
   everything.

### 10.5.3 Operational Mitigations (Outside Protocol)

| Mitigation | Description |
|------------|-------------|
| **Periodic label audit** | A human or automated process reviews labels and removes unused compartments |
| **Maximum label size** | Enforce an upper bound on compartments per label (e.g., ≤ 5 compartments) |
| **Expiration** | Labels expire after a TTL; data must be re-labelled to remain accessible |
| **Label linter** | Static analysis of compartment use patterns; detect compartments that always co-occur |
| **"Least privilege" lint** | Recommend the minimal label that achieves the desired policy outcome |

---

## 10.6 Side-Channel Attacks

### 10.6.1 Timing Side Channel

A compromised agent that sends a message and observes how long the response
takes can infer whether the boundary check passed or blocked.

```
Agent sends message labelled {SECRET}
  ──► boundary.check() takes t₁ nanoseconds (PASS)
  ──► boundary.check() takes t₂ nanoseconds (BLOCK)

If t₁ ≉ t₂, agent can infer existence of SECRET compartment
```

**Mitigation**: The boundary check is constant-time with respect to the
input — the same set operations (`frozenset` intersection and difference)
run regardless of compartments. The difference between PASS and BLOCK is a
single branch that is not data-dependent in duration at the level an
agent process can measure.

```
// Pseudocode — constant-time in label size
missing = label.compartments - clearance.compartments
result = PASS if len(missing) == 0 else BLOCK
```

Realistic impact: A Python agent on the same host can measure wall-clock
time with ~1µs granularity. The boundary check takes ~2µs regardless of
result. The signal-to-noise ratio is too low for reliable inference.

### 10.6.2 Existence Side Channel

The agent can learn that data exists (even if it cannot read it) through
non-data channels:

| Channel | How | DBP Mitigation |
|---------|-----|----------------|
| **Number of messages** | Agent calls `receive()` and gets N items; calls again after another agent wrote something, gets N+1 items — agent detects new data exists even if it cannot read it | Transport can pad responses to a fixed size; communicate only mailbox content hashes, not counts |
| **File names** (local transport) | Agent has filesystem access and can list `*.md` files even if `receive()` filters on read | Remove filesystem access from the agent; use a pipe or socket for message delivery |
| **Error messages** | Transport returns "message exists but blocked" vs "no message" | Return identical surface-level response ("no messages") for both cases |
| **Storage size** | Shared disk fills up; agent can infer data was written because available space decreased | Not practical to mitigate; accept as low-severity leak |

### 10.6.3 Side-Channel Risk Assessment

| Vector | Severity | Exploit Cost | Recommended Action |
|--------|----------|--------------|-------------------|
| Timing | Low | High (requires many samples, process noise) | No spec change; document for awareness |
| Existence (count) | Medium | Medium (agent can count files) | Transport should not expose raw counts |
| Existence (files) | High | Low (agent has filesystem access) | Production deployments: do not give agent FS access |
| Error messages | Low | Low | Normalise error responses |

---

## 10.7 Escalation as Attack Surface

### 10.7.1 The Problem

Rule R7 (future specification) introduces a human-in-the-loop override:
when a boundary check blocks a legitimate data flow, a human operator can
escalate and grant temporary access. This is the **weakest point** in the
DBP security model because it replaces deterministic enforcement with
human judgment.

```
  BLOCK ──► Operator is alerted
             │
             ▼
        "Allow this one time?"
             │
        ┌────┴────┐
        YES       NO
         │        └──► data stays blocked
         ▼
    Data delivered
    (override recorded)

Attack: Attacker spams operator with BLOCKs → operator gets fatigued
        → approves a dangerous one. Or attacker compromises operator
        account → approves malicious flow.
```

### 10.7.2 Mitigations (Planned for R7)

| Mitigation | Description |
|------------|-------------|
| **Mandatory reason** | Operator must enter a written justification for every escalation |
| **Expiration** | Escalations expire after a configurable TTL; permanent escalation is banned |
| **Cooldown** | Same compartment pair cannot be escalated more than once per N hours |
| **Second approval** | Escalations involving compartments with sensitivity level > X require two approvers |
| **Audit trail** | Every escalation is logged with operator identity, timestamp, compartment, and reason |
| **`Escalation fatigue` detection** | If the same operator approves > K escalations in a shift, lock escalation capability |
| **No batch escalation** | Each escalation applies to exactly one message; bulk override is not supported |

### 10.7.3 Architectural Separation

The escalation mechanism **MUST** run in a separate trust domain from the
boundary engine itself. This prevents a single compromise from granting
both (a) the ability to override boundaries and (b) the ability to approve
one's own override requests.

```
┌─────────────────┐       ┌─────────────────┐
│ Boundary engine │──────►│ Escalation API  │
│ (deterministic, │       │ (requires       │
│  no overrides)  │       │  human auth)    │
└─────────────────┘       └─────────────────┘
        │                        │
        │  BLOCK                 │  POST /escalate
        │  ←─────────────────────│  ← operator UI
        ▼                        ▼
   TraceRecord              EscalationRecord
   (permanent)              (permanent, audited)
```

---

## 10.8 Aggregation Risk (Open Problem)

### 10.8.1 Problem

Data A is labelled `{public}`, data B is labelled `{public}`. Both pass
boundary checks individually. But A + B together reveal a sensitive insight.
Heritage labels the result as `{public}` (union of two `{public}` labels) —
no protection against aggregation.

```
Data A:   "Employee names in department X"
          Label: {public}

Data B:   "Salaries in department X"
          Label: {public}

A + B:    "Name → salary mapping"  ← SENSITIVE
          Heritage = {public} ❌ should be {private}
```

### 10.8.2 DBP's Current Mitigation: Heritage

Heritage ensures that derived data is **never less restricted** than its
sources. This prevents the classic "combine two restricted items to produce
an unrestricted result" attack. But it does **not** prevent "combine two
unrestricted items to produce a restricted result" — the aggregation risk.

### 10.8.3 Proposed Future Mechanisms

| Mechanism | Description | Status |
|-----------|-------------|--------|
| **Combination labels** | A new label primitive: `{A, B, ∅ → PRIVATE}` — label that becomes restricted when combined with another specific label | Not in DBP/1.0 |
| **Policy-level aggregation check** | A policy that evaluates labelled data in context: "is this agent requesting two compartments at once?" | Under consideration |
| **Query budget** | Rate-limit the number of distinct compartments an agent can access per time window, mimicking differential privacy | Future |
| **Human review of multi-compartment results** | Any message whose heritage label has > N compartments is automatically flagged for human review | Operational |
| **Semantic distance** | If two compartments are semantically close (e.g., `{salary}` and `{identity}`), their union triggers a higher scrutiny policy | Exploratory |

### 10.8.4 Guidance for DBP/1.0 Deployments

Until aggregation risk is fully addressed in the protocol, operators
**SHOULD**:

- Use **fine-grained compartments** — split `{public}` into
  `{public-names}`, `{public-salaries}`, `{public-aggregates}` so that
  heritage produces `{public-names, public-salaries}` from a combination,
  which then fails ALL-policy checks against single-compartment clearances.
- Deploy **output scanning** as a second layer: after the boundary passes
  data to the agent, scan the agent's output for patterns that suggest
  aggregation (e.g., name + salary in the same response).

---

## 10.9 Comparison with Fides

### 10.9.1 Overview

[Fides](https://www.microsoft.com/en-us/research/publication/fides-towards-a-platform-for-responsible-ai-specification/) (Microsoft Research)
is a platform for responsible AI that includes a **taint tracking** system
for data provenance. DBP and Fides share the goal of preventing data misuse
in AI systems but take fundamentally different approaches.

### 10.9.2 Comparison Table

| Dimension | Fides | DBP |
|-----------|-------|-----|
| **Tracking model** | Fine-grained dynamic taint tracking at the variable/field level | Coarse-grained label at the message/document level |
| **Granularity** | Individual field within a data record | Entire message or document |
| **Enforcement** | Runtime taint propagation through the application | Transport-level boundary check (set intersection) |
| **Dependency** | Requires modified runtime (custom Python interpreter or bytecode instrumentation) | Zero dependency — standard Python, any HTTP/gRPC stack |
| **Agent transparency** | Taints are invisible to agent; agent cannot strip them | Labels are opaque to agent; agent cannot modify them |
| **Performance overhead** | 5–20% runtime overhead (taint propagation) | Negligible (< 0.1%) — simple set operations |
| **Deployment** | Requires instrumented runtime — not available for most LLM platforms | Any transport that supports headers/frontmatter; no runtime modification |
| **Maturity** | Research prototype | Early specification + reference implementation |
| **Aggregation detection** | Can detect "tainted field A combined with tainted field B produces result C" | Cannot detect cross-compartment aggregation (see 10.8) |
| **Heritage** | Automatic via taint propagation | Automatic via label union (set level, not field level) |

### 10.9.3 Key Insight

Fides is more powerful (field-level taints, aggregation detection) but
requires deep integration into the runtime. DBP is lighter weight and
deployable immediately with any agent framework, at the cost of coarser
granularity and weaker aggregation protection.

### 10.9.4 When to Use Each

| Use case | Recommended |
|----------|-------------|
| You control the agent runtime (custom Python interpreter) | Fides |
| You use off-the-shelf agents (any LLM platform, any language) | DBP |
| You need field-level provenance | Fides |
| You need message-level boundaries | DBP |
| You need both | DBP for transport boundaries + Fides for in-process taint tracking |

DBP and Fides are **complementary**. A combined deployment uses DBP at the
transport layer (ensuring agents never receive uncleared data) and Fides
inside the agent process (ensuring tainted fields are not accidentally
included in output). This gives defence in depth:

```
┌──────────────────────────────────────────┐
│  Transport layer                         │
│  ┌──────────────────────────────────────┐│
│  │ DBP boundary check                   ││
│  │ (message-level, before delivery)     ││
│  └──────────────────────────────────────┘│
│                     │                     │
│                     ▼                     │
│  ┌──────────────────────────────────────┐│
│  │ Agent process with Fides runtime     ││
│  │ (field-level taint tracking)         ││
│  └──────────────────────────────────────┘│
│                     │                     │
│                     ▼                     │
│  ┌──────────────────────────────────────┐│
│  │ DBP heritage assignment             ││
│  │ (automatic union on outbound)       ││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

---

## 10.10 Summary of Open Problems and Mitigations

| Open Problem | Severity | DBP/1.0 Mitigation | Future Work |
|-------------|----------|--------------------|-------------|
| Aggregation risk (A+B→S) | High | Heritage ensures never-less-restricted; fine-grained compartments help | Combination labels, query budgets, semantic distance |
| Transitive trust across domains | High | None in protocol; `{UNTRUSTED}` compartment as operational practice | Cryptographic label chains, signed attestations |
| Over-classification drift | Medium | Heritage creates disincentive; audit trace for detection | Label size limits, expiration, linting |
| Side-channel timing | Low | Constant-time check (set ops); high noise floor | Constant-time verification suite |
| Side-channel existence | Medium | Transport can pad/hide counts; agent should not have FS access | Null response standardisation |
| Escalation abuse | Critical | R7 mitigations: expiry, cooldown, second approval, fatigue detection | TTL-hardening, anomaly detection on escalation patterns |
| Label stripping (transit) | High | Transport MUST preserve; spec requirement T13/T14 | Automated compliance test harness |

Security for DBP/1.0 is a **defence-in-depth** proposition. The protocol
provides strong guarantees at the message boundary but relies on operational
practices, monitoring, and future specifications to address the open problems
documented here.

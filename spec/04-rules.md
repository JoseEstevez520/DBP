# 4. Rules

This document defines the six normative rules of the Data Boundary Protocol. Each rule is a **MUST**-level requirement unless otherwise noted. Every rule includes a rationale, a compliance test, and the consequences of failure.

## 4.1 Rule R1 — Read-in

### Statement

> An agent MUST only receive data whose label passes the boundary check against the agent's clearance.

### Rationale

The foundational guarantee of DBP is that the agent cannot access data it is not authorized for. If data entered the agent's context without a boundary check, the check would be advisory rather than enforced. By blocking at read-in time, the agent never sees the data and therefore cannot leak, mis-use, or be tricked into revealing it.

### Formal expression

For every data item $d$ delivered to agent $A$ with clearance $C$:

$$\text{deliver}(d, A) \implies \mathcal{B}(\text{label}(d), C) = \text{PASS}$$

### Compliance test

```
1. Deploy agent A with clearance C = {"engineering"}
2. Attempt to deliver data with label L = {"hr"}
3. Assert: delivery is BLOCKED
4. Assert: agent A never receives the data payload
5. Attempt to deliver data with label L = {"engineering"}
6. Assert: delivery is PERMITTED

Expected: test 3 blocks, test 4 confirms no data in context,
          test 6 permits.
```

### Failure consequences

If R1 is violated, the protocol provides **no data boundary guarantee**. The agent may receive any data, and the entire DBP security model collapses. This is a critical failure requiring immediate remediation.

---

## 4.2 Rule R2 — Write

### Statement

> An agent MUST only label data with compartments that are a subset of its own clearance.

### Rationale

If an agent could assign labels outside its clearance, it could escalate its own access or create data that appears more restricted than warranted. R2 ensures that the agent cannot self-authorize compartments it does not possess.

### Formal expression

For every data item $d$ created by agent $A$ with clearance $C$:

$$\text{label}(d) \subseteq C$$

(Where $\text{label}(d) \subseteq C$ means every compartment in $\text{label}(d)$ also appears in $C$.)

### Compliance test

```
1. Deploy agent A with clearance C = {"engineering", "schedule"}
2. Agent A creates data d with label L = {"engineering", "hr"}
3. Assert: label assignment BLOCKED
4. Agent A creates data d with label L = {"engineering"}
5. Assert: label assignment PERMITTED

Expected: test 3 blocks, test 5 permits.
```

### Failure consequences

An agent can fabricate credentials for compartments it was never authorized for. This enables horizontal privilege escalation and breaks the trust model of the deployment.

---

## 4.3 Rule R3 — Crossing

### Statement

> A boundary check MUST be performed BEFORE any data crosses from one agent to another. There MUST NOT be an alternative communication path that bypasses the boundary check.

### Rationale

R3 ensures that the boundary check is a **gate**, not a **filter**. If data crosses the transport layer before the check, a buggy or malicious implementation could drop the check and keep the transport. The check must be in the critical path: no check, no data flow.

### Formal expression

For message $m$ from agent $A$ to agent $B$:

$$\text{send}(m, A \to B) \implies \big(\mathcal{B}(\text{label}(m), C_B) = \text{PASS}\big) \land \big(\neg \exists \text{ path } A \leftrightarrow B \text{ without } \mathcal{B}\big)$$

### Compliance test

```
1. Intercept the transport layer between agents A and B
2. Attempt to inject a raw message that has not passed the boundary
3. Assert: the message is REJECTED at the transport level
4. Verify: the only way for data to reach the transport layer
   is through the boundary check module
```

### Failure consequences

Data flows without authorization. The entire DBP guarantee is void. An attacker or misconfiguration can exfiltrate any data to any agent by bypassing the boundary layer. This is a **critical** failure.

---

## 4.4 Rule R4 — Heritage

### Statement

> Derived data MUST automatically inherit the union of all source labels. The heritage label policy MUST be ALL. The agent MUST NOT be able to override or reduce the heritage label.

### Rationale

If derived data could have a narrower label than its sources, an agent could trivially bypass boundaries: read restricted data, combine it with unrestricted data, and relabel the result as unrestricted. Heritage ensures that data transformations never reduce the access constraint.

### Formal expression

Given source labels $L_1, L_2, \dots, L_n$ producing derived data $d$:

$$\text{label}(d) = \left( \bigcup_{i=1}^{n} S_i,\; \text{ALL} \right)$$

And:

$$\neg \exists \text{ operation } \text{reduce}: \text{label}(\text{reduce}(d)) \subset \text{label}(d)$$

### Compliance test

```
1. Agent A has data d1 with label {"fitness"}
2. Agent A has data d2 with label {"schedule"}
3. Agent A creates d3 = combine(d1, d2)
4. Assert: label(d3) = {"fitness", "schedule"} with policy ALL
5. Agent A attempts to relabel d3 as {"fitness"}
6. Assert: relabel operation is BLOCKED
```

### Failure consequences

An agent can "launder" data by combining it with other data and stripping the original label. This defeats the entire purpose of labeled data boundaries and enables unlimited data leakage.

---

## 4.5 Rule R5 — Traceability

### Statement

> Every boundary check MUST generate an immutable trace record. The trace MUST include the timestamp, label, clearance, result, and originating agent identity.

### Rationale

Without traceability, there is no way to audit who accessed what, when, or to detect anomalous access patterns. R5 ensures that every access decision leaves a forensic record.

### Formal expression

For every evaluation $\mathcal{B}(L, C)$ that produces result $r$:

$$\exists T = \langle t, c, L, C, r, o \rangle$$

Where:
- $t$ is the timestamp (RFC 3339 UTC, REQUIRED)
- $c$ is a unique correlation ID (UUID v4, REQUIRED)
- $L$ is the label (REQUIRED)
- $C$ is the clearance (REQUIRED)
- $r$ is the result: PASS or BLOCK (REQUIRED)
- $o$ is the origin identity (REQUIRED)

### Compliance test

```
1. Perform a boundary check that returns PASS
2. Assert: a trace record was created with result="PASS"
3. Perform a boundary check that returns BLOCK
4. Assert: a trace record was created with result="BLOCK"
5. Assert: both trace records contain all REQUIRED fields
6. Assert: trace records are immutable (cannot be modified after creation)
```

### Failure consequences

Loss of auditability. Security incidents cannot be investigated. Compliance requirements (SOC 2, GDPR, HIPAA) cannot be met. **High** severity.

---

## 4.6 Rule R6 — Opacity

### Statement

> An agent MUST NOT be able to evade, modify, disable, or inspect the boundary check mechanism. The boundary implementation MUST be transparent to the agent.

### Rationale

If the agent can inspect the boundary mechanism, it could learn the access control logic and attempt to circumvent it. If the agent could disable the boundary, no enforcement exists. The boundary must be opaque to the agent — a black box that the infrastructure controls and the agent cannot touch.

### Formal expression

For every agent $A$:

$$\nexists \text{ operation } \text{access}: \text{boundary}(A) \to \text{boundary-mechanism}$$

The boundary mechanism is not part of the agent's addressable namespace. The agent cannot:
1. Read the boundary source code or configuration
2. Modify the boundary evaluation logic
3. Disable or suspend the boundary check
4. Short-circuit the boundary to reach the transport layer directly
5. Inspect other agents' clearances or boundary results

### Compliance test

```
1. Agent A attempts to read the boundary module's code or config
2. Assert: the read operation FAILS (permission denied or not found)
3. Agent A attempts to call the transport layer directly
4. Assert: the call FAILS (transport only reachable through boundary)
5. Agent A attempts to list all clearances in the deployment
6. Assert: the list FAILS or returns only agent A's own clearance
```

### Failure consequences

An agent can bypass the boundary by disabling or manipulating it. This is a **critical** failure equivalent to R1 or R3 violations. The deployment's data security becomes entirely dependent on the agent's benevolence, which is the exact problem DBP was designed to solve.

---

## 4.7 Rule summary

| Rule | Norm | Scope | Failure severity |
|------|------|-------|-----------------|
| R1 — Read-in | MUST | Data delivery to agent | Critical |
| R2 — Write | MUST | Data labeling by agent | High |
| R3 — Crossing | MUST | Inter-agent transport | Critical |
| R4 — Heritage | MUST | Derived data labeling | High |
| R5 — Traceability | MUST | Every boundary check | High |
| R6 — Opacity | MUST | Boundary mechanism access | Critical |

## 4.8 Implementation checklist

A DBP-compliant implementation MUST pass all of the following:

- [ ] R1.1: Data with BLOCK label never enters agent context
- [ ] R1.2: Data with PASS label enters agent context normally
- [ ] R2.1: Agent-originated labels are subset of agent's clearance
- [ ] R2.2: Labels exceeding clearance are rejected
- [ ] R3.1: Boundary check runs before every transport message
- [ ] R3.2: No direct transport path exists without boundary
- [ ] R4.1: Heritage computes union of all source compartments
- [ ] R4.2: Heritage policy is always ALL
- [ ] R4.3: Agent cannot override heritage label
- [ ] R5.1: Every check produces a trace record
- [ ] R5.2: Trace records contain all REQUIRED fields
- [ ] R5.3: Trace records are immutable
- [ ] R6.1: Agent cannot read boundary implementation
- [ ] R6.2: Agent cannot modify boundary configuration
- [ ] R6.3: Agent cannot bypass boundary to reach transport
- [ ] R6.4: Agent cannot inspect other agents' clearances

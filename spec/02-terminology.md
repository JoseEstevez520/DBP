# 2. Terminology

This document defines every term used in the DBP specification. Each entry includes a plain-language definition, a formal definition where applicable, and an illustrative example.

## 2.1 Compartment

**Plain language:** A named category or domain that data belongs to, or that an agent is authorized for. Compartments are horizontal (non-hierarchical): having compartment `A` does not imply access to compartment `B`.

**Formal:** A compartment is an opaque string identifier $c$ drawn from a namespace determined by the deployment. No ordering, hierarchy, or relationship between compartments is assumed.

**Constraints:**
- A compartment identifier MUST be a non-empty printable ASCII string.
- Compartment identifiers are case-sensitive.
- The empty string is not a valid compartment.

**Example:**
```
"fitness"       → A compartment for fitness-related data
"hr"            → A compartment for HR data
"engineering"   → A compartment for engineering data
"project:alpha" → Namespaced compartments are permitted
```

## 2.2 Label

**Plain language:** A label is metadata attached to a piece of data that declares which compartments the data belongs to, and under which policy the data should be evaluated.

**Formal:** A label $L$ is an ordered pair $(S, p)$ where:

- $S$ is a set of compartment identifiers: $S = \{c_1, c_2, \dots, c_n\}$
- $p$ is a policy specifier: $p \in \{\text{ANY}, \text{ALL}\}$

If $S = \emptyset$, the label is **unrestricted** and passes any boundary check regardless of clearance.

**Constraints:**
- If $S \neq \emptyset$, $S$ MUST contain at least one compartment.
- The empty label $(S = \emptyset)$ is valid and denotes public or unrestricted data.

**Example:**
```json
{"compartments": ["fitness", "schedule"], "policy": "any"}
```
A piece of data that belongs to the `fitness` and `schedule` compartments, evaluated under ANY policy (at least one matching compartment suffices for access).

## 2.3 Clearance

**Plain language:** The set of compartments that an agent is authorized to access. A clearance is assigned at agent startup and cannot be modified during the agent's lifetime.

**Formal:** A clearance $C$ is a non-empty set of compartment identifiers:

$$C = \{c_1, c_2, \dots, c_n\}, \quad n \geq 1$$

A clearance MUST contain at least one compartment. An agent with clearance $C$ can receive data with label $(S, p)$ if and only if the boundary check passes.

**Constraints:**
- A clearance MUST be non-empty.
- An agent's clearance is immutable for the lifetime of the agent session.
- Clearance is assigned by the deployment infrastructure, not self-declared by the agent.

**Example:**
```json
{"clearance": ["identity", "fitness", "schedule"]}
```
An agent with access to the `identity`, `fitness`, and `schedule` compartments.

## 2.4 Boundary Check

**Plain language:** The deterministic decision function that determines whether an agent with a given clearance may access data with a given label. No machine learning model is involved.

**Formal:** A function $\mathcal{B}$:

$$\mathcal{B}(L, C, p) \to \{\text{PASS}, \text{BLOCK}\}$$

where:
- $L = (S_L, p_L)$ is the data label
- $C$ is the agent's clearance
- $p$ is the effective policy (ANY or ALL)

The function is:
- **Deterministic**: $\mathcal{B}(L, C, p)$ always returns the same result for the same inputs
- **Stateless**: no side effects or mutable state affect the result
- **O(1)**: evaluation time does not depend on the number of compartments

**Example:**
```
B({fitness, schedule}, {identity, fitness, schedule}, ANY)  → PASS
B({fitness, schedule}, {identity, project}, ANY)             → BLOCK
B({fitness, schedule}, {identity, fitness, schedule}, ALL)  → PASS
B({fitness, schedule}, {identity, schedule}, ALL)            → BLOCK
```

## 2.5 Heritage

**Plain language:** When an agent creates new data from existing data, the new data automatically inherits the labels of all sources. This is automatic and the agent cannot override it.

**Formal:** Given source labels $L_1, L_2, \dots, L_n$ where $L_i = (S_i, p_i)$, the heritage label $L_h$ is:

$$L_h = \left( \bigcup_{i=1}^{n} S_i, \; \text{ALL} \right)$$

The policy of the heritage label is always ALL, enforcing that derived data is subject to the strictest possible evaluation.

**Constraints:**
- Heritage is automatic (R4). The agent MUST NOT be able to opt out.
- Heritage policy defaults to ALL regardless of source policies.
- If all source labels are empty, the heritage label is also empty.

**Example:**
```
Source A: label {fitness}
Source B: label {schedule}
Result:   label {fitness, schedule} with policy ALL
```

## 2.6 Trace

**Plain language:** An immutable record created every time a boundary check is evaluated. Traces enable audit, debugging, and forensic analysis of data access patterns.

**Formal:** A trace $T$ is a record containing at minimum:

$$T = \langle t, c, L, C, r, o \rangle$$

where:
- $t$ is the timestamp (RFC 3339 UTC)
- $c$ is a unique trace correlation ID (UUID v4)
- $L$ is the evaluated label
- $C$ is the agent's clearance
- $r$ is the result: PASS or BLOCK
- $o$ is the identity of the originating agent or service

**Constraints:**
- A trace MUST be generated for every boundary check (R5).
- Traces MUST be immutable once written.
- Traces SHOULD be persisted to a durable store (e.g., BTL).

**Example:**
```json
{
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-07-15T14:30:00Z",
  "label": {"compartments": ["fitness", "schedule"], "policy": "any"},
  "clearance": ["identity", "fitness", "schedule"],
  "result": "PASS",
  "origin": "coach-agent"
}
```

## 2.7 Policy (ANY / ALL)

**Plain language:** The rule that determines how many compartments must match for a boundary check to pass.

**Formal:**

- **ANY**: $\mathcal{P}_{\text{ANY}}(S_L, C) = (S_L \cap C \neq \emptyset)$
  - At least one compartment from the label must appear in the clearance.
  - Default policy if not otherwise specified.

- **ALL**: $\mathcal{P}_{\text{ALL}}(S_L, C) = (S_L \subseteq C)$
  - Every compartment in the label must appear in the clearance.

**Example:**
```
Label {fitness, schedule}, Clearance {schedule}
  ANY → PASS (schedule matches)
  ALL → BLOCK (fitness missing)

Label {fitness}, Clearance {fitness}
  ANY → PASS
  ALL → PASS
```

## 2.8 Agent Card

**Plain language:** An agent's identity document that declares who the agent is, what it can do, and what data it is authorized to access.

**Formal:** An Agent Card is a JSON document with at minimum:

- `name`: Agent identifier (string, REQUIRED)
- `clearance`: Array of compartment strings (REQUIRED, non-empty)
- `protocol`: Protocol version string, e.g., `"dbp/1.0"` (REQUIRED)
- `endpoint`: Network address (REQUIRED for remote agents)
- `description`: Human-readable description (RECOMMENDED)
- `auth`: Authentication method declaration (RECOMMENDED)

**Example:**
```json
{
  "name": "coach",
  "description": "Personal fitness coach agent",
  "clearance": ["identity", "fitness", "schedule"],
  "endpoint": "http://localhost:8001",
  "auth": {"type": "api_key"},
  "protocol": "dbp/1.0"
}
```

## 2.9 Read-in

**Plain language:** The process by which an agent receives data at startup or during operation. Under DBP, data can only enter an agent's context if the boundary check passes first.

**Formal:** Read-in is the event of data $d$ with label $L$ being delivered to agent $A$ with clearance $C$. The delivery MUST be preceded by a boundary check $\mathcal{B}(L, C, p)$. If the check returns BLOCK, the data MUST NOT be delivered (R1).

## 2.10 Escalation

**Plain language:** The controlled process of requesting elevated access when a boundary check blocks needed data.

**Formal:** An escalation is a triggered event when $\mathcal{B}(L, C, p) = \text{BLOCK}$ but a human or automated supervisor may approve override. The escalation path is outside the scope of this specification but the BLOCK event MUST always be traced.

**Note:** Escalation is an **operation** concept, not a protocol escape. The boundary check still runs and records the BLOCK; the override (if any) produces a new clearance-bounded session.

## 2.11 Frontier workspace

**Plain language:** A deployment environment that implements the Frontier ecosystem, comprising DBP for data boundaries and BTL for audit traces.

**Formal:** A Frontier workspace is a deployment context in which:
1. All agent communication uses DBP as the protocol layer.
2. All boundary checks generate traces consumable by BTL.
3. Agent Cards with clearance declarations are the sole mechanism for data access authorization.
4. No agent can communicate outside the DBP boundary (R6).

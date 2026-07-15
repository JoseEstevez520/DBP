# 1. Introduction

## 1.1 The problem

Modern multi-agent systems have two established protocols for inter-agent communication:

- **A2A (Agent-to-Agent, Google):** Who talks to whom. Handles authentication, agent discovery, capability advertisement, and task lifecycle.
- **MCP (Model Context Protocol, Anthropic):** What agents can do. Handles tool exposure, resource access, and prompt templates.

Neither protocol addresses **what data is allowed to cross between agents**. In current practice, data boundaries are enforced through prompt engineering — soft instructions embedded in system prompts: *"Do not share user data with other agents"* or *"This information is confidential."*

This approach is fundamentally broken for autonomous agents.

## 1.2 Why soft norms fail

A probabilistic language model is not a policy enforcement mechanism. Soft norms embedded in prompts fail for four reasons:

| Failure mode | Description |
|-------------|-------------|
| **Forgetting** | The model loses fidelity over long contexts; the boundary instruction is hundreds of tokens away from the decision point |
| **Instruction contradiction** | A downstream instruction ("tell me everything") can override an upstream boundary ("don't share this") |
| **Jailbreaking** | Adversarial prompts specifically crafted to bypass content restrictions |
| **No audit trail** | There is no record of *what* was evaluated — only the agent's output to infer from |

An agent that *knows a secret and must not tell it* is a security boundary that cannot be verified. The only reliable boundary is one the agent *never receives the data to begin with*.

> **Core insight:** The control lives at the boundary, not inside the agent. What the agent never receives, it cannot leak.

## 1.3 DBP's approach

DBP replaces soft prompt norms with **deterministic boundaries enforced at the infrastructure level**. The protocol introduces four concepts:

1. **Labels** — Compact metadata attached to every piece of data, describing what compartments it belongs to.
2. **Clearances** — Declared access authorizations assigned to each agent at startup.
3. **Boundary checks** — A deterministic function that compares a label against a clearance and returns PASS or BLOCK. No model is involved.
4. **Heritage** — Automatic label propagation: derived data inherits the union of all source labels.

The boundary check is:

- **Deterministic** — same inputs always produce the same output
- **Stateless** — no session state or model state affects the result
- **Non-circumventable** — the agent cannot bypass the check (R6, see 04-rules)
- **Auditable** — every evaluation generates an immutable trace record (R5)

## 1.4 Relationship to A2A

DBP **replaces** A2A. It does not complement it.

If DBP were layered on top of A2A, a message would already cross the transport boundary before the boundary check could intercept it. A misconfigured, buggy, or malicious implementation could skip the DBP layer entirely and fall back to raw A2A communication. The guarantee would be advisory, not enforced.

```
A2A:  auth ──────────► transport             (data always passes if auth succeeds)
DBP:  auth → boundary → transport             (data passes only if boundary check passes)
DBP:  boundary → BLOCK → ✗ (no transport)    (no data crosses)
```

DBP takes the valuable parts of A2A — Agent Cards, authentication, task lifecycle — and makes the boundary check a **mandatory gate** that all data must pass before any transport action occurs. The protocol is not an A2A extension or profile; it is a replacement that adds the missing piece.

## 1.5 Part of the Frontier ecosystem

DBP is one component of the **Frontier** ecosystem for governance of autonomous agents:

```
Frontier (complete ecosystem)
├── DBP  — Data Boundary Protocol (this repository)
└── BTL  — Boundary Trace Layer (agent observability, audit, forensics)
```

| Component | Function | Repository |
|-----------|----------|------------|
| DBP | Enforce data boundaries at the protocol level | `github.com/frontier/dbp` |
| BTL | Observe, trace, and audit boundary events | `github.com/frontier/btl` |

Each component can be used independently. Together they provide a complete governance workspace: DBP blocks unauthorized data flow, and BTL records every attempt for retrospective analysis.

## 1.6 Scope

This specification defines:

- The four primitives (Label, Clearance, Boundary Check, Heritage)
- The six rules (R1–R6) that govern agent data handling
- The wire format for DBP messages
- The Agent Card format for clearance declaration
- The policy model (ANY, ALL, and extension)
- Heritage propagation semantics
- Transport bindings (HTTP, gRPC, file, local IPC)
- Security considerations and threat model

What this specification does NOT define:

- Agent discovery mechanisms (left to the deployment environment)
- Authentication and authorization (pluggable; OAuth 2.0, mTLS, API keys all supported)
- Task scheduling or agent orchestration
- Specific encryption or data-at-rest policies

## 1.7 Document conventions

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

Examples and diagrams are non-normative unless explicitly marked otherwise.

Formal notation uses standard set theory:

| Symbol | Meaning |
|--------|---------|
| $L$ | A label |
| $C$ | A clearance |
| $c_i$ | A compartment identifier (string) |
| $\mathcal{P}$ | Policy function (ANY or ALL) |
| $\cup$ | Set union |
| $\cap$ | Set intersection |
| $\subseteq$ | Subset |
| $\emptyset$ | Empty set |
| $L \to C$ | Label-to-clearance comparison |

## 1.8 Version

This document specifies DBP version **1.0.0-draft**. The protocol version is communicated through the `protocol` field in every DBP message as `dbp/1.0`.

## 1.9 Open issues

1. **Aggregation risk:** Two individually innocuous data items can together reveal sensitive information. Heritage (union of labels) mitigates this but does not prevent it entirely. A future version may define composable policies or information-theoretic bounds.
2. **Transitive trust:** When data crosses between owners, who is responsible for refreshing the original label? The current model places this on the originating owner, but chain-of-custody semantics need further specification.
3. **Over-classification drift:** The natural incentive is to label everything as restricted. The protocol encourages precise clearance assignment at the agent level, but a pruning mechanism for stale compartments may be needed in practice.

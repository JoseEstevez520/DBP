# 11. Escalation (R7)

## 11.1 Problem

A boundary check has two outcomes: PASS or BLOCK. BLOCK is final — the data never crosses. But there are legitimate cases where a BLOCK should be overridable:

- An agent needs a piece of data temporarily for a cross-domain task
- A human explicitly authorises a one-time data transfer
- A supervisor agent with broader clearance can vouch for the transfer

R7 adds a third outcome — **ESCALATE** — that allows an agent to request permission from a higher authority when the check fails.

## 11.2 Primitives

### 11.2.1 EscalationResult

```
GRANT     → the override is approved, data may cross
DENY      → the override is rejected, BLOCK is confirmed
ESCALATE  → the decision is forwarded to the next level
```

### 11.2.2 EscalationRequest

A record of an escalation attempt:

```
agent_id:     who is requesting
label:        the data label that was blocked
clearance:    the agent's own clearance
reason:       why the agent believes the data should cross
parent_id:    who is being asked
status:       pending | granted | denied | escalated
timestamp:    when the request was made
```

### 11.2.3 Escalation Chain

Each agent declares an optional `escalation_parent` in its Agent Card. The chain forms a linked list:

```
Agent → Parent Agent → ... → Human
                            ↑
                       always the last link
```

The human is the ultimate authority. There is no escalation above the human.

## 11.3 Rule R7 — Escalation

### Statement

> When a boundary check returns BLOCK, the requesting agent MAY initiate an escalation to its declared parent. The parent MAY respond with GRANT, DENY, or further ESCALATE. If no parent is declared, or the chain reaches the human, the human's decision is final.

### Rationale

Absolute BLOCK is too rigid for real systems. A human operator or supervisor agent needs a mechanism to authorise specific overrides. R7 provides this without compromising the deterministic core: the override is explicit, traced, and revocable.

### Formal expression

Let `B(d, A)` be the boundary check for data `d` to agent `A` with clearance `C_A`:

```
B(d, A) = BLOCK  →  agent MAY request escalation
                     escalation(A, P) → {GRANT, DENY, ESCALATE}

GRANT   →  data may cross (recorded as override in trace)
DENY    →  BLOCK is final
ESCALATE →  forwarded to parent(P), or to human if P = null
```

### Compliance test

```
1. Deploy agent A with clearance C_A = {"engineering"}
   and escalation_parent = "supervisor"
2. Attempt to deliver data with label L = {"hr"} to A
3. Assert: boundary check returns BLOCK
4. A requests escalation to supervisor
5. Supervisor GRANTs the override
6. Assert: data is delivered
7. Assert: trace contains an override record
```

## 11.4 The human as last link

The human is always reachable. If an agent has no `escalation_parent`, or if the chain reaches a terminal node that also escalates, the request goes to the human directly.

How the human receives the request is implementation-defined (email, Telegram, CLI prompt, web dashboard). DBP does not prescribe the interface — only that the human exists as the final authority.

## 11.5 Trace records for escalation

Every escalation action produces a trace record with:

```
type:           "escalation"
agent_id:       who requested
parent_id:      who was asked
label:          the original data label
reason:         why the agent escalated
result:         GRANT | DENY | ESCALATE | HUMAN_PENDING | HUMAN_DECIDED
timestamp:      when the action occurred
```

These records are part of the same immutable trace log as boundary checks (R5).

## 11.6 Security considerations

Escalation is the **weakest point** of DBP:

1. **Social engineering** — An agent could be convinced to request escalation for malicious purposes. Mitigation: the human sees the reason and the label before deciding.

2. **Escalation spam** — An agent could escalate every BLOCK, flooding the human. Mitigation: rate limiting on escalation requests, configurable per agent.

3. **Human fatigue** — If too many decisions reach the human, they may approve without reading. Mitigation: aggregate similar requests, require explicit reason from the agent.

4. **Override proliferation** — If GRANT becomes routine, the clearance system is meaningless. Mitigation: overrides expire after a configurable TTL, and are logged permanently for audit.

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
GRANT          → a raw override is approved, the original data may cross (escape hatch)
GRANT_DERIVED  → the authority answers with a boundary-safe derivative; raw data never crosses
DENY           → the override is rejected, BLOCK is confirmed
ESCALATE       → the decision is forwarded to the next level (ultimately the human)
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

## 11.7 Hierarchical escalation and derived answers

§11.3 defines a single hop: an agent asks one declared parent. Real component
trees are deeper — a button's authority is its form, the form's is the page, the
page's is the root orchestrator. R7 therefore also defines an **automatic walk**
up the `escalation_parent` chain, plus a safer way for an authority to answer.

### 11.7.1 Chain walk

`escalate_chain(agent, label, reason, registry)` resolves `escalation_parent`
names through the registry and rises level by level:

```
requester → parent → … → root authority → human
```

At each level, if that authority's clearance covers the label it resolves the
request; otherwise the request is forwarded to *its* parent. If the chain ends
with no capable authority (an agent with no `escalation_parent`), the request
reaches the **human**, who remains the final authority (§11.4). A cycle or an
unregistered parent is an error, not an infinite climb.

The walk returns an **EscalationOutcome**: the result, the `authority` that
resolved it (or `null` for the human), and the `chain` that was visited.

### 11.7.2 Derived answers (preferred over raw override)

A raw `GRANT` moves the original sensitive data into an agent that was not
cleared for it — the "weakest point" of §11.6. R7 adds a safer resolution:
the answering authority may return a **derived artifact** instead.

```
authority holds raw data (label L)
        │  derive(authority, L) → (value, L_derived)
        ▼
check(L_derived, requester.clearance)      ← the derivative must itself pass
        ├── PASS  → GRANT_DERIVED, return value   (raw data never crosses)
        └── BLOCK → DENY                           (a leak is refused, not served)
```

The derivative SHOULD carry **heritage** (§8) so its provenance is auditable.
Example: a discount agent (no `payment`/`pii` clearance) asks "can the user pay?".
The authority holding the payment data does not hand over the card; it returns
`{ can_pay: true }` under a derived label the requester is cleared for. The
requester gets exactly what it needs and nothing it must not see.

**Raw `GRANT` remains the escape hatch** for the cases §11.1 describes (a human
or supervisor explicitly authorising a one-time raw transfer, with TTL and audit).
Derived answers are the default; raw override is the exception.

### 11.7.3 Compliance test

```
1. Register button → form → main; only main is cleared for {"pii"}.
2. Attempt to deliver {"pii"} data to button → BLOCK.
3. escalate_chain(button, {"pii"}, reason, registry, derive=…)
4. Assert: the walk visits form then main; main resolves.
5. Assert: result is GRANT_DERIVED and the returned artifact's label passes for button.
6. Assert: a derive() that returns a still-{"pii"} label yields DENY, not delivery.
7. Assert: every hop produced a trace record.
```

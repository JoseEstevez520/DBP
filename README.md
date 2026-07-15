# DBP — Data Boundary Protocol

**Deterministic data boundaries for agent communication.**

DBP is a communication protocol for multi-agent systems that enforces **what data can flow** between agents. Instead of soft norms ("don't share this" in a prompt), it moves the control into the infrastructure.

## Context

```
A2A (Google)    →  identity and transport (who talks to whom)
MCP (Anthropic) →  tools and resources (what agents can do)
DBP             →  data boundaries (what information may flow)
```

Today, data boundaries between agents are enforced through prompt instructions — norms that a probabilistic agent may ignore, forget, or be tricked into bypassing. What an agent receives, it can potentially leak. DBP explores moving the control **out of the agent and into the boundary**.

## Core idea

> The control lives at the boundary, not inside the agent. What the agent never receives, it cannot leak.

A human told "don't share this" **knows** the secret and may leak it. An agent started without access to it **doesn't know it**. It's not that it "decides not to share" — it never received the data in the first place.

## How it works

### Primitives

| Primitive | What it is | Example |
|-----------|-----------|---------|
| **Label** | Set of compartment identifiers attached to a piece of data | `{"engineering", "hr"}` |
| **Clearance** | Set of compartment identifiers assigned to an agent | `{"engineering", "finance"}` |
| **Boundary Check** | Function: `(label, clearance, policy) → PASS \| BLOCK` | Deterministic, no LLM |
| **Heritage** | Derived data inherits the union of source labels | `L₁ ∪ L₂`, automatic |

### Policies

Two standard boundary check policies:

```
ANY (default):  label ∩ clearance ≠ ∅ → PASS
                "one matching compartment is enough"

ALL:            label ⊆ clearance → PASS
                "you need every compartment on the data"
```

### Rules

```
R1 — Read-in       Agent only receives data that passes boundary check at startup
R2 — Write          Agent can only label data with compartments in its own clearance
R3 — Crossing       Boundary check happens BEFORE sending, not after
R4 — Heritage       derived_data.label = source_a.label ∪ source_b.label (automatic)
R5 — Traceability   Every boundary check generates a trace record
R6 — Opacity        Agent cannot evade, modify, or inspect the boundary mechanism
```

### Message flow

```
1. DISCOVERY     Agent Card with declared clearance
2. AUTH          OAuth / API key / mTLS
3. BOUNDARY      label vs clearance → PASS or BLOCK
4. TRANSPORT     HTTP / gRPC / local (only if step 3 = PASS)
5. HERITAGE      Automatic union on derived data
```

## Quick example

```python
from dbp import Boundary, Label, Clearance, Policy

boundary = Boundary()

# Data with a label
data_label = Label({"fitness", "schedule"})

# Agents with clearances
coach = Clearance({"identity", "fitness", "schedule"})
developer = Clearance({"identity", "project", "schedule"})

# Boundary checks
boundary.check(data_label, coach, Policy.ANY)       # → PASS (fitness matches)
boundary.check(data_label, developer, Policy.ANY)    # → PASS (schedule matches)
boundary.check(data_label, developer, Policy.ALL)    # → BLOCK (missing fitness)
```

## Compartment model

- **Horizontal, not hierarchical** — having compartment A does not grant access to B
- **Asymmetric overlaps** — there is no single shared base
- **Need-to-know** — access is granted because the task requires it, not by rank or trust
- **Each owner declares their own** — no global directory needed

```
Jose:      {A, B}
Pepito:    {A}
Third:     {A, B, C}
```

## Heritage (derived data)

When an agent combines data from multiple sources, the result inherits the **union** of all source labels. This is automatic and cannot be overridden.

```
data_a [fitness]  +  data_b [schedule]  =  result [fitness, schedule]
```

This means derived data is **never less restricted** than its sources.

## Part of Frontier

DBP is part of the **Frontier** ecosystem:

```
Frontier (complete ecosystem)
├── DBP  — Data Boundary Protocol (this repo)
└── BTL  — Boundary Trace Layer (agent observability, separate repo)
```

Each can be used independently. Together they form a complete governance workspace for autonomous agents.

## Transport-agnostic

DBP does not prescribe the transport. It only requires that the label travels with the data:

**Over HTTP:**
```
X-DBP-Label: engineering,hr
X-DBP-Policy: any
```

**Over files (markdown frontmatter):**
```yaml
---
dbp-label: [engineering, hr]
dbp-policy: any
---
```

**Over JSON messages:**
```json
{
  "protocol": "dbp/1.0",
  "label": ["engineering", "hr"],
  "policy": "any",
  "payload": { }
}
```

## Agent Card

Extends the A2A Agent Card concept with clearance declaration:

```json
{
  "name": "coach",
  "description": "Personal fitness coach",
  "clearance": ["identity", "fitness", "schedule"],
  "endpoint": "http://localhost:8001",
  "auth": { "type": "api_key" },
  "protocol": "dbp/1.0"
}
```

## Open problems

1. **Aggregation risk** — Data A is innocuous, data B is innocuous, but A+B together reveal something sensitive. Heritage (union of labels) mitigates but does not fully prevent this.
2. **Transitive trust** — When data crosses between owners, who refreshes the original label?
3. **Over-classification drift** — The natural tendency is to label everything as restricted. Needs a pruning mechanism.

## Project structure

```
DBP/
├── spec/           # Formal specification (RFC-style)
├── src/dbp/        # Reference implementation (Python)
├── tests/          # Test suite (292 tests)
├── demo/           # Demos and multi-agent deployment
│   ├── scenarios/  # 8 feature scenarios
│   ├── agents/     # Agent configurations (JSON)
│   ├── agent_runtime.py   # Multi-agent deployment system
│   ├── deploy_company.py  # 16 agents with org hierarchy
│   └── run_company.py     # Full company simulation
└── examples/       # Standalone usage examples
```

## Getting started

```bash
# Install
pip install -e .

# Run tests
pytest tests/

# Run demo
python demo/run_demo.py
```

## License

Apache 2.0

## Status

R1-R7 implemented. **292 tests**, 8 demo scenarios, 16 deployable agents.

### Implemented
- R1-R7: Read-in, Write, Crossing, Heritage, Traceability, Opacity, Escalation
- Primitives: Label, Clearance, Policy (ANY/ALL), BoundaryResult, EscalationResult
- Transports: Local (markdown frontmatter), HTTP (headers)
- Agent Card with clearance and escalation_parent
- AgentRuntime: multi-agent deployment with 16 agents and org hierarchy
- Immutable audit trace

### Tests
```
292 passed in 5.21s
├── test_boundary.py              35 tests
├── test_heritage.py              10 tests
├── test_message.py               16 tests
├── test_agent_card.py            15 tests
├── test_rules.py                 16 tests
├── test_transport_local.py       26 tests
├── test_transport_http.py        24 tests
├── test_escalation.py            16 tests
├── test_integration.py           20 tests
├── test_stress_integration.py    13 tests
├── test_hardening.py             49 tests
├── test_property_chaos.py        35 tests (8000+ random iterations)
├── test_simulation.py             5 tests (full work-day)
└── test_benchmarks.py             8 tests (performance)
```

<p align="center">
  <img src="assets/readme-hero.png" alt="What an agent never receives, it cannot leak" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/protocol-DBP%2F1.0-9d75ff" alt="DBP protocol" />
  <img src="https://img.shields.io/badge/python-%E2%89%A53.10-3776ab" alt="Python 3.10 or later" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-20b9c5" alt="Apache 2.0 license" /></a>
  <img src="https://img.shields.io/badge/boundary_checks-deterministic-47d7c8" alt="Deterministic boundary checks" />
</p>

<p align="center"><strong>Deterministic data boundaries for agent communication.</strong></p>

**DBP (Data Boundary Protocol)** is a protocol and reference implementation for deciding exactly what information may flow between agents. It moves control from prompt instructions into enforceable infrastructure: data that never crosses a boundary cannot be leaked by the receiving agent.

> **The control lives at the boundary, not inside the agent.**

## Why DBP?

| Deterministic | Transport-agnostic | Traceable |
| :--- | :--- | :--- |
| A check returns `PASS` or `BLOCK`—never an LLM judgment. | Use the same labels over HTTP, files, JSON, or local runtime calls. | Every decision can produce an immutable trace record. |

```text
labeled data + agent clearance + policy
                  │
                  ▼
           boundary check
            ├── PASS  → transport
            └── BLOCK → data never arrives
```

## The model

| Primitive | Meaning | Example |
| :--- | :--- | :--- |
| **Label** | Compartments attached to data. | `{"engineering", "hr"}` |
| **Clearance** | Compartments granted to an agent. | `{"engineering", "finance"}` |
| **Boundary check** | Deterministic policy evaluation. | `(label, clearance, policy) → PASS \| BLOCK` |
| **Heritage** | Derived data inherits source labels. | `L₁ ∪ L₂` |

Two built-in policies determine access:

```text
ANY (default):  label ∩ clearance ≠ ∅  → PASS
ALL:            label ⊆ clearance      → PASS
```

## Quick example

```python
from dbp import Boundary, Label, Clearance, Policy

boundary = Boundary()
data_label = Label({"fitness", "schedule"})

coach = Clearance({"identity", "fitness", "schedule"})
developer = Clearance({"identity", "project", "schedule"})

boundary.check(data_label, coach, Policy.ANY)       # PASS
boundary.check(data_label, developer, Policy.ANY)   # PASS
boundary.check(data_label, developer, Policy.ALL)   # BLOCK
```

## Protocol guarantees

1. **Read-in** — an agent receives only data that passes a boundary check.
2. **Write** — an agent labels data only with its own clearance compartments.
3. **Crossing** — checking happens before transport, not after.
4. **Heritage** — derived data automatically inherits the union of source labels.
5. **Traceability** — every check generates a trace record.
6. **Opacity** — the boundary mechanism is not exposed for an agent to evade or modify.
7. **Escalation** — blocked access can follow an explicit escalation path.

## Get started

```bash
pip install -e .
pytest tests/
python demo/run_demo.py
```

## Where it fits

```text
A2A → identity and transport: who talks to whom
MCP → tools and resources: what agents can do
DBP → data boundaries: what information may flow
```

DBP does not prescribe a transport. Its labels can travel with HTTP headers, Markdown frontmatter, JSON messages, or local calls.

## Repository guide

| Path | Purpose |
| :--- | :--- |
| [`spec/`](spec/) | RFC-style protocol specification. |
| [`src/dbp/`](src/dbp/) | Python reference implementation. |
| [`tests/`](tests/) | Unit, integration, property, and benchmark tests. |
| [`demo/`](demo/) | Multi-agent scenarios and deployable agent configurations. |
| [`examples/`](examples/) | Standalone usage examples. |

## Open questions

- **Aggregation risk:** individually innocuous data may become sensitive when combined.
- **Transitive trust:** label ownership needs clear refresh rules across organizations.
- **Over-classification:** restrictive labels need disciplined pruning.

## License

[Apache License 2.0](LICENSE)

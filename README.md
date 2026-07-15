# DBP — Data Boundary Protocol

**Una exploración sobre fronteras deterministas de datos entre agentes.**

DBP es un protocolo de comunicación para sistemas multi-agente que explora cómo controlar **qué datos pueden fluir** entre agentes de forma determinista. En lugar de normas blandas ("no compartas esto" en un prompt), propone que la infraestructura decida.

## Contexto

```
A2A (Google)    →  identidad y transporte (quién habla con quién)
MCP (Anthropic) →  herramientas y recursos (qué puede hacer un agente)
DBP             →  fronteras de datos (qué información puede fluir)
```

Hoy, los límites de datos entre agentes se gestionan con instrucciones en el prompt — normas que un agente probabilístico puede ignorar, olvidar, o ser engañado para saltarse. Esto no es necesariamente un problema en todos los casos, pero cuando la privacidad de datos importa, plantea preguntas abiertas.

DBP propone mover el control **fuera del agente y situarlo en la frontera**. El agente no decide qué puede ver — la infraestructura decide por él.

## Idea central

> El control vive en la frontera, no dentro del agente. Lo que el agente nunca recibe, no puede filtrarlo.

A un humano le dices "no compartas esto" y **sabe** el secreto — puede filtrarlo. A un agente lo arrancas sin acceso al dato y **no lo sabe**. No es que "decida no compartirlo" — es que nunca lo recibió.

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

## Estructura del proyecto

```
DBP/
├── spec/           # Especificación formal (estilo RFC)
├── src/dbp/        # Implementación de referencia (Python)
├── tests/          # Suite de tests (292 tests)
├── demo/           # Demos y despliegue multi-agente
│   ├── scenarios/  # 8 escenarios de funcionalidad básica
│   ├── agents/     # Configuración de agentes (JSON)
│   ├── agent_runtime.py   # Sistema de despliegue multi-agente
│   ├── deploy_company.py  # 16 agentes con jerarquía organizativa
│   └── run_company.py     # Simulación completa
└── examples/       # Ejemplos de uso independientes
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

## Estado

R1-R7 implementados. **292 tests**, 8 escenarios demo, 16 agentes desplegables.

### Implementado
- R1-R7: Read-in, Write, Crossing, Heritage, Traceability, Opacity, Escalation
- Primitivas: Label, Clearance, Policy (ANY/ALL), BoundaryResult, EscalationResult
- Transportes: Local (frontmatter en markdown), HTTP (cabeceras)
- Agent Card con clearance y escalation_parent
- AgentRuntime: despliegue multi-agente con 16 agentes y jerarquía organizativa
- Traza de auditoría inmutable

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
├── test_property_chaos.py        35 tests (8000+ iteraciones aleatorias)
├── test_simulation.py             5 tests (día laboral completo)
└── test_benchmarks.py             8 tests (rendimiento)
```

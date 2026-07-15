# 3. Primitives

This document formally defines the four primitives of the Data Boundary Protocol: Label, Clearance, Boundary Check, and Heritage. Each primitive is defined with set-theoretic notation, a JSON Schema, and a reference Python implementation.

## 3.1 Label

A label declares which compartments a piece of data belongs to and under which policy it should be evaluated.

### 3.1.1 Formal definition

Let $\mathcal{C}$ be the universe of compartment identifiers (non-empty printable ASCII strings).

A label $L$ is an ordered pair:

$$L = (S, p)$$

where:

- $S \subseteq \mathcal{C}$ is a finite set of compartment identifiers
- $p \in \{\text{ANY}, \text{ALL}\}$ is the policy specifier

If $S = \emptyset$, the label is **unrestricted** and $\mathcal{B}(L, C, p) = \text{PASS}$ for any $C$ and any $p$.

### 3.1.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Label",
  "type": "object",
  "properties": {
    "compartments": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[ -~]+$"
      },
      "uniqueItems": true
    },
    "policy": {
      "type": "string",
      "enum": ["any", "all"],
      "default": "any"
    }
  },
  "required": ["compartments"],
  "additionalProperties": false
}
```

### 3.1.3 Reference implementation

```python
@dataclass(frozen=True)
class Label:
    compartments: frozenset[str]
    policy: str = "any"

    def __init__(self, compartments: set[str], policy: str = "any") -> None:
        if not isinstance(compartments, set):
            compartments = set(compartments)
        for c in compartments:
            if not c or not c.isprintable():
                raise ValueError(f"Invalid compartment: {c!r}")
        if policy not in ("any", "all"):
            raise ValueError(f"Invalid policy: {policy!r}")
        object.__setattr__(self, "compartments", frozenset(compartments))
        object.__setattr__(self, "policy", policy)

    @classmethod
    def unrestricted(cls) -> Label:
        return cls(set(), "any")

    def is_unrestricted(self) -> bool:
        return len(self.compartments) == 0
```

## 3.2 Clearance

A clearance declares which compartments an agent is authorized to access.

### 3.2.1 Formal definition

A clearance $C$ is a non-empty finite set of compartment identifiers:

$$C = \{c_1, c_2, \dots, c_n\}, \quad n \geq 1, \quad c_i \in \mathcal{C}$$

$C$ MUST be non-empty. No agent may operate without a clearance.

### 3.2.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Clearance",
  "type": "object",
  "properties": {
    "clearance": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[ -~]+$"
      },
      "minItems": 1,
      "uniqueItems": true
    }
  },
  "required": ["clearance"],
  "additionalProperties": false
}
```

### 3.2.3 Reference implementation

```python
@dataclass(frozen=True)
class Clearance:
    compartments: frozenset[str]

    def __init__(self, compartments: set[str]) -> None:
        if not compartments:
            raise ValueError("Clearance must be non-empty")
        for c in compartments:
            if not c or not c.isprintable():
                raise ValueError(f"Invalid compartment: {c!r}")
        object.__setattr__(self, "compartments", frozenset(compartments))

    def __contains__(self, compartment: str) -> bool:
        return compartment in self.compartments

    def __len__(self) -> int:
        return len(self.compartments)
```

## 3.3 Boundary Check

The boundary check is the deterministic function that evaluates whether data with a given label may be delivered to an agent with a given clearance.

### 3.3.1 Formal definition

$$\mathcal{B}: (L, C) \to \{\text{PASS}, \text{BLOCK}\}$$

Where $L = (S_L, p_L)$ and $C$ is the agent's clearance.

**For the ANY policy:**

$$\mathcal{B}((S_L, \text{ANY}), C) = \begin{cases}
\text{PASS} & \text{if } S_L = \emptyset \text{ or } S_L \cap C \neq \emptyset \\
\text{BLOCK} & \text{otherwise}
\end{cases}$$

**For the ALL policy:**

$$\mathcal{B}((S_L, \text{ALL}), C) = \begin{cases}
\text{PASS} & \text{if } S_L = \emptyset \text{ or } S_L \subseteq C \\
\text{BLOCK} & \text{otherwise}
\end{cases}$$

### 3.3.2 Properties

| Property | Guarantee |
|----------|-----------|
| Deterministic | $\mathcal{B}(L, C) = \mathcal{B}(L, C)$ for all $L, C$ |
| Stateless | No mutable state affects the result |
| Monotonic | Adding compartments to $C$ can only change BLOCK → PASS, never PASS → BLOCK |
| Non-monotonic in $L$ | Adding compartments to $L$ can only change PASS → BLOCK, never BLOCK → PASS |

### 3.3.3 Reference implementation

```python
class Boundary:
    """Deterministic boundary check engine."""

    @staticmethod
    def check(label: Label, clearance: Clearance) -> bool:
        """Return True if data passes the boundary, False if blocked."""
        if label.is_unrestricted():
            return True

        if label.policy == "any":
            return bool(label.compartments & clearance.compartments)

        if label.policy == "all":
            return label.compartments.issubset(clearance.compartments)

        raise ValueError(f"Unknown policy: {label.policy}")

    @staticmethod
    def enforce(label: Label, clearance: Clearance) -> None:
        """Raise BoundaryViolation if the check does not pass."""
        if not Boundary.check(label, clearance):
            raise BoundaryViolation(
                f"Label {label} blocked by clearance {clearance}"
            )


class BoundaryViolation(Exception):
    """Raised when a boundary check fails."""
```

### 3.3.4 Truth table

| Label compartments | Clearance | Policy | Result |
|---|---|---|---|
| $\emptyset$ (unrestricted) | any | any | PASS |
| {a} | {a} | ANY | PASS |
| {a} | {a} | ALL | PASS |
| {a} | {b} | ANY | BLOCK |
| {a} | {b} | ALL | BLOCK |
| {a, b} | {a} | ANY | PASS |
| {a, b} | {a} | ALL | BLOCK |
| {a, b} | {a, b} | ANY | PASS |
| {a, b} | {a, b} | ALL | PASS |

## 3.4 Heritage

Heritage defines how labels propagate to derived data. When an agent creates new data from one or more sources, the result automatically inherits the union of all source labels.

### 3.4.1 Formal definition

Given source labels $L_1, L_2, \dots, L_n$ where $L_i = (S_i, p_i)$, the heritage label $L_h$ is:

$$L_h = \left( \bigcup_{i=1}^{n} S_i, \; \text{ALL} \right)$$

The heritage policy is always ALL, enforcing that derived data is evaluated under the strictest possible regime.

If $n = 0$ (no sources, purely synthetic data), the agent labels it according to R2.

### 3.4.2 Properties

| Property | Value |
|----------|-------|
| Automatic | Heritage MUST be applied without agent intervention (R4) |
| Non-overridable | The agent MUST NOT be able to reduce the heritage label |
| Monotonic | Adding more sources can only increase the compartment set |
| Idempotent | Same sources → same heritage label |
| Commutative | Heritage(L₁, L₂) = Heritage(L₂, L₁) |
| Associative | Heritage(L₁, Heritage(L₂, L₃)) = Heritage(Heritage(L₁, L₂), L₃) |

### 3.4.3 Reference implementation

```python
def heritage(*labels: Label) -> Label:
    """Compute the heritage label from zero or more source labels.

    Args:
        *labels: Source labels.

    Returns:
        A new Label with the union of all source compartments and policy ALL.

    Raises:
        ValueError: If no labels provided (caller must handle this case).
    """
    if not labels:
        raise ValueError("heritage() requires at least one source label")

    union: set[str] = set()
    for lbl in labels:
        union.update(lbl.compartments)

    return Label(compartments=union, policy="all")
```

### 3.4.4 Examples

```python
a = Label({"fitness"})
b = Label({"schedule"})
c = Label({"identity", "fitness"})

heritage(a, b)
# → Label({"fitness", "schedule"}, "all")

heritage(a, c)
# → Label({"fitness", "identity"}, "all")

heritage(a, b, c)
# → Label({"fitness", "schedule", "identity"}, "all")

heritage(a, Label.unrestricted())
# → Label({"fitness"}, "all")
# Note: unrestricted labels contribute no compartments to the union.
```

## 3.5 Primitive relationships

```
Label      ──attached to──► Data
Clearance  ──assigned to──► Agent
Boundary   ──compares──► Label × Clearance → PASS | BLOCK
Heritage   ──propagates──► Source labels → derived label
```

The boundary check is the central operation. Labels and clearances are its inputs; heritage ensures the outputs remain constrained across data transformations.

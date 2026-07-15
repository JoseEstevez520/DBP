# DBP Specification

This directory contains the formal specification of the **Data Boundary Protocol (DBP)**, written in RFC style. Each document is a standalone reference; together they define the complete protocol.

## Document index

| # | Document | Status | Description |
|---|----------|--------|-------------|
| 01 | [01-introduction.md](01-introduction.md) | Draft | Problem statement, design rationale, scope, and document conventions |
| 02 | [02-terminology.md](02-terminology.md) | Draft | Complete glossary of every DBP term with definitions and examples |
| 03 | [03-primitives.md](03-primitives.md) | Draft | Formal definition of Label, Clearance, Boundary Check, and Heritage |
| 04 | [04-rules.md](04-rules.md) | Draft | The six rules (R1–R6): normative statements, rationale, and compliance tests |
| 05 | [05-message-format.md](05-message-format.md) | Draft | Wire format: JSON schema, label encoding, transport mappings, error handling |
| 06 | [06-agent-card.md](06-agent-card.md) | Stub | Agent Card schema: identity, clearance declaration, capabilities, auth |
| 07 | [07-policies.md](07-policies.md) | Stub | Policy definitions: ANY, ALL, and extension mechanisms for custom policies |
| 08 | [08-heritage.md](08-heritage.md) | Stub | Heritage propagation: formal model, multi-hop chains, aggregation semantics |
| 09 | [09-transport.md](09-transport.md) | Planned | Transport bindings: HTTP, gRPC, WebSocket, local IPC, file system |
| 10 | [10-security.md](10-security.md) | Planned | Threat model, attack surfaces, trust assumptions, and countermeasures |

## How to read

1. Start with **01-introduction** to understand the problem DBP solves.
2. Read **02-terminology** for the vocabulary used throughout.
3. Study **03-primitives** and **04-rules** for the formal protocol core.
4. Consult **05-message-format** for implementation details of the wire protocol.
5. Refer to **06–10** for specific sub-protocols and extensions as needed.

## Conventions

All documents follow [RFC 2119](https://tools.ietf.org/html/rfc2119) for normative language: **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL**.

Formal notation uses standard set theory and JSON Schema (draft-2020-12) where applicable. Python examples target >= 3.10.

## Status

All documents are in **Draft** status. Sections marked **OPEN ISSUE** identify areas requiring further discussion or implementation experience before the specification can be finalized.

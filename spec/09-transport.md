# 09 — Transport Bindings

**Status:** Draft  
**Applies to:** DBP/1.0  
**Requires:** 03-primitives, 04-rules, 05-message-format

---

## 9.1 Transport-Agnostic Design Principle

DBP is transport-agnostic by design. The protocol does not mandate a specific
carrier — any transport that can carry a label alongside a payload can be made
DBP-compliant. What matters is that the **boundary check happens before the
data crosses the wire**, not after.

```
                   ┌─────────────────────┐
                   │  Application Layer  │
                   │  (agent logic)      │
                   └──────┬──────────────┘
                          │ DBPMessage (labelled payload)
                          ▼
                   ┌─────────────────────┐
                   │  Boundary Check     │  ← R3: check BEFORE send
                   │  (label × clearance)│
                   └──────┬──────────────┘
                          │ PASS / BLOCK
                          ▼
                   ┌─────────────────────┐
                   │  Transport Layer    │
                   │  (HTTP / gRPC / FS) │
                   └─────────────────────┘
```

All transports **MUST**:

1. Carry the DBP label and policy alongside the payload (in-band headers,
   metadata, or frontmatter — never in a separate side-channel).
2. Refuse to send data if the boundary check fails (R3).
3. Verify the label on receive against the recipient's clearance before
   making the payload available to the agent (R1).
4. Produce a `TraceRecord` for every boundary check, regardless of result (R5).
5. Be opaque to the agent: the agent **MUST NOT** be able to modify, skip,
   or inspect the boundary mechanism (R6).

---

## 9.2 HTTP Transport

### 9.2.1 Headers

The HTTP transport encodes DBP metadata in three custom headers:

| Header | Required | Value | Example |
|--------|----------|-------|---------|
| `X-DBP-Label` | YES | Comma-separated compartment identifiers | `engineering,hr` |
| `X-DBP-Policy` | YES | `any` or `all` | `any` |
| `X-DBP-Origin` | YES | Sender agent name | `coach-agent` |

The payload body **MUST** be the JSON-serialised `DBPMessage` (see spec 05)
with `Content-Type: application/json`.

### 9.2.2 Sender Flow (Boundary Check Before POST)

```
   Sender                          Recipient
     │                                │
     │  Label = {engineering, hr}     │
     │  Clearance = {engineering}     │
     │                                │
     │  check(label, clearance)       │
     │    → BLOCK (missing hr)        │
     │                                │
     │  ╔══╗ NO REQUEST SENT         │
     │  ║  ║ data never crosses wire  │
     │  ╚══╝                          │
     │                                │
     │  (retry with different data)   │
     │                                │
     │  Label = {engineering}          │
     │  check(label, clearance)       │
     │    → PASS                      │
     │                                │
     │  POST /messages                │
     │  X-DBP-Label: engineering      │────►
     │  X-DBP-Policy: any             │      │
     │  X-DBP-Origin: sender          │      │
     │  Body: { DBPMessage JSON }     │      │
```

The sender **MUST** call `boundary.check()` against the **recipient's**
clearance (the sender checks before sending — R3). If the check returns
`BLOCK`, the HTTP request **MUST NOT** be made.

### 9.2.3 Middleware Pattern (Receiver)

On the receiving side, the HTTP server **MUST** re-check the label against
its own clearance before processing the payload. A middleware function
intercepts the inbound request:

```
Inbound HTTP Request
        │
        ▼
  ┌─────────────────┐
  │ Parse headers:  │
  │ X-DBP-Label     │
  │ X-DBP-Policy    │
  │ X-DBP-Origin    │
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ boundary.check( │
  │   label,        │
  │   my_clearance  │
  │ )               │
  └────────┬────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
   PASS         BLOCK
     │           │
     ▼           ▼
  process()   return 403
```

The middleware **MUST** be implemented at the transport layer (framework
middleware, reverse proxy plugin, or gateway) — not inside the agent process —
to satisfy R6 (opacity).

```python
# Reference: src/dbp/transport/http.py

def dbp_middleware(request):
    label_hdr = request.headers.get("X-DBP-Label", "")
    policy_hdr = request.headers.get("X-DBP-Policy", "any")
    label = header_to_label(label_hdr, policy_hdr)

    result = boundary.check(label, recipient_card.clearance)

    if result == BoundaryResult.BLOCK:
        return {"status": 403, "error": "DBP boundary check failed"}
    return None  # proceed
```

### 9.2.4 Error Responses

| HTTP Status | Condition | Body |
|-------------|-----------|------|
| 200 | PASS — message accepted and processed | Normal response body |
| 403 | BLOCK — boundary check failed | `{"error": "DBP boundary check failed", "blocked_by": [...]}` |
| 400 | Malformed or missing DBP headers | `{"error": "Invalid DBP headers"}` |
| 406 | Policy mismatch (e.g., unrecognised policy value) | `{"error": "Unsupported policy"}` |

### 9.2.5 Consideration: Statelessness

HTTP transport is inherently stateless. Each request carries its own
`X-DBP-*` headers; there is no session-level label. This makes HTTP
transport suitable for request-response patterns but less natural for
long-lived streaming or pub-sub flows.

---

## 9.3 Local / File Transport

### 9.3.1 Encoding

Messages are stored as Markdown files (`.md`) with YAML frontmatter encoding
the DBP compartments and policy. This format is human-readable, survives at
rest, and is trivially inspectable by operators.

```markdown
---
compartments: ["engineering", "hr"]
policy: any
---

{
  "id": "a1b2c3d4-...",
  "label": { "compartments": ["engineering", "hr"], "policy": "any" },
  "origin": "hr-agent",
  "payload": { ... },
  "protocol": "dbp/1.0"
}
```

### 9.3.2 Directory Structure

```
<base_path>/
  ├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.md
  ├── fedcba09-8765-4321-abcd-ef0987654321.md
  └── ...
```

Each message is one file. The filename is the message UUID. There is no
subdirectory hierarchy — if subdirectories are desired for organisation
(e.g., per-agent inboxes), the transport implementation **MUST** still
perform boundary checks on every read regardless of file location.

### 9.3.3 Writer Flow

```
   Agent A (sender)
        │
        │  Create DBPMessage with Label L
        │  boundary.check(L, recipient.clearance)
        │    → PASS
        │
        │  Write file:
        │  <base_path>/<uuid>.md
        │    ---
        │    compartments: [...]
        │    policy: any
        │    ---
        │    { JSON payload }
        │
        ▼
    [file system]
```

If the check returns `BLOCK`, no file is written. The agent (caller) receives
the `BLOCK` result and **MUST** not attempt to write the file through any
other path.

### 9.3.4 Reader Flow

```
   Agent B (receiver)
        │
        │  List *.md in <base_path>
        │
        │  For each file:
        │    ┌────────────────────────┐
        │    │ Read frontmatter:      │
        │    │ compartments, policy   │
        │    └────────┬───────────────┘
        │             ▼
        │    ┌────────────────────────┐
        │    │ boundary.check(L,      │
        │    │   B.clearance)         │
        │    └────────┬───────────────┘
        │             │
        │      ┌──────┴──────┐
        │      ▼             ▼
        │    PASS           BLOCK
        │      │             │
        │      ▼             ▼
        │   Read body    Skip file
        │   → agent      (agent never
        │     sees it      sees it)
        │
        ▼
    Return List[DBPMessage] (only passed items)
```

The agent **never receives** files that fail the boundary check. The file
remains on disk, but the agent has no way to request it — the transport
layer skips it before returning results to the agent (R1, R6).

### 9.3.5 Considerations for File Transport

| Concern | Guidance |
|---------|----------|
| **Concurrency** | Use advisory file locking or atomic writes (`write + rename`) to prevent partial reads. |
| **Cleanup** | The transport does not define a retention policy. Implementations **MAY** add TTL-based cleanup. |
| **Directory enumeration** | An agent with filesystem access outside DBP can bypass the boundary. File transport is only secure when the message directory is *exclusively* managed by DBP. |
| **Synchronisation** | Polling (periodic `glob`) is the default; implementations **MAY** use filesystem watchers (`inotify`, `ReadDirectoryChangesW`) for lower latency. |

---

## 9.4 gRPC Transport

### 9.4.1 Metadata Map

gRPC metadata (headers) carry the DBP label and policy as key-value pairs:

| Metadata Key | Value | Example |
|-------------|-------|---------|
| `x-dbp-label` | Comma-separated compartments | `engineering,hr` |
| `x-dbp-policy` | `any` or `all` | `any` |
| `x-dbp-origin` | Sender agent name | `coach-agent` |

gRPC metadata is **bidirectional and per-call**. Both unary and streaming
RPCs can carry DBP metadata:

```protobuf
// The DBP metadata travels in gRPC call metadata,
// not in the protobuf message body.
//
// The agent protobuf message is application-defined;
// DBP does not require a particular .proto schema.

// Recommended: a generic message wrapper
message DBPEnvelope {
  string data_id = 1;
  bytes payload = 2;  // serialised application protobuf
}
```

### 9.4.2 Interceptor Pattern

The boundary check is implemented as a **gRPC interceptor** (middleware),
not in the business logic. Two interceptors are required:

**Client-side interceptor (sender):**

```
  Agent A
    │
    │  Create message with Label L
    │  boundary.check(L, recipient.clearance)
    │    → PASS
    │
    │  Attach x-dbp-* metadata to gRPC call
    │  Call RPC
    │
    ▼
  [gRPC call with metadata]
```

**Server-side interceptor (receiver):**

```
  [gRPC call with metadata]
    │
    ▼
  Parse x-dbp-label, x-dbp-policy, x-dbp-origin
    │
    ▼
  boundary.check(label, my_clearance)
    │
    ├── PASS → forward to handler
    └── BLOCK → return gRPC error (PERMISSION_DENIED)
```

```python
# Pseudocode for gRPC server interceptor
class DBPInterceptor(grpc.ServerInterceptor):
    def __init__(self, boundary, my_clearance):
        self.boundary = boundary
        self.my_clearance = my_clearance

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        label_str = metadata.get("x-dbp-label", "")
        policy_str = metadata.get("x-dbp-policy", "any")

        label = Label.from_header(label_str, policy_str)
        result = self.boundary.check(label, self.my_clearance)

        if result == BoundaryResult.BLOCK:
            return self._deny_rpc()
        return continuation(handler_call_details)
```

### 9.4.3 Streaming Considerations

For **server-streaming** and **bidirectional-streaming** RPCs:

- The client **MUST** check the boundary before **initiating** the stream.
- For each message in a server stream, the server **SHOULD** re-check if
  the stream metadata conveys per-message labels. If the entire stream
  carries a single label (set at stream open), a single check at stream
  start suffices.
- Implementations **MUST** document whether the label is per-stream or
  per-message. DBP strongly **RECOMMENDS** per-message labels for streams
  carrying heterogeneous data.

### 9.4.4 Protobuf Schema Considerations

DBP does not mandate a specific `.proto` schema. However, if the application
needs per-message granularity beyond what gRPC metadata provides, the label
**MAY** be embedded in the protobuf message:

```protobuf
message DBPHeader {
  repeated string compartments = 1;
  string policy = 2;  // "any" | "all"
  string origin = 3;
}

// Wrap any application message
message LabelledMessage {
  DBPHeader dbp = 1;
  google.protobuf.Any payload = 2;
}
```

When labels are embedded in the protobuf body (not just metadata), the
interceptor **MUST** deserialise the outer wrapper to extract the label
before the check. This incurs a deserialisation overhead but ensures
labels survive message re-packaging.

---

## 9.5 A2A Compatibility

DBP messages can be carried within the Google **Agent-to-Agent (A2A)**
protocol by mapping DBP constructs to A2A Message metadata.

### 9.5.1 Mapping

| A2A Construct | DBP Mapping | Notes |
|---------------|-------------|-------|
| `Message.metadata` (key-value dict) | Label → `dbp:label` (comma-separated compartments) | Stored as a custom metadata key |
| `Message.metadata` | Policy → `dbp:policy` (`any`/`all`) | Stored as a custom metadata key |
| `Message.origin` (sender AgentCard ID) | `X-DBP-Origin` / `dbp:origin` | Already present in A2A |
| `Task.state` (lifecycle) | Not mapped | DBP does not replace A2A task management |
| `AgentCard` (A2A) | Clearance added as `dbp:clearance` | Extension to Agent Card |

### 9.5.2 A2A Message with DBP Metadata

```json
{
  "id": "msg-001",
  "metadata": {
    "dbp:label": "engineering,hr",
    "dbp:policy": "any",
    "dbp:origin": "coach-agent"
  },
  "content": {
    "type": "text",
    "text": "Restricted project update"
  }
}
```

### 9.5.3 Critical Design Constraint

The A2A compatibility mode is a **transport mapping only**. The boundary
check **MUST** still happen before the A2A message is placed on the wire,
not after A2A delivers it. An agent or gateway that understands DBP **MUST**
intercept the outbound A2A message, extract the DBP metadata, run the
boundary check, and only then allow A2A to send.

```
   ┌──────────┐      ┌───────────┐      ┌──────────┐
   │ DBP Agent│─────►│ DBP/A2A  │─────►│ A2A      │
   │          │      │ Gateway   │      │ Network  │
   └──────────┘      └───────────┘      └──────────┘
                          │
                     boundary.check()
                     before A2A send
```

A pure A2A agent (without DBP awareness) **MUST NOT** be trusted to enforce
DBP rules. The gateway **MUST** be the enforcement point.

---

## 9.6 Requirements for Compliant Transport Implementations

A transport implementation **MUST** satisfy all of the following to be called
"DBP-compliant":

| ID | Requirement | Normative |
|----|-------------|-----------|
| T01 | Label and policy travel in-band with the payload | MUST |
| T02 | Sender-side boundary check before data leaves the agent | MUST |
| T03 | Receiver-side boundary check before data reaches the agent | MUST |
| T04 | BLOCK result prevents any data transmission | MUST |
| T05 | Every check produces a `TraceRecord` | MUST |
| T06 | Agent cannot bypass, modify, or inspect the boundary mechanism (R6) | MUST |
| T07 | Heritage is computed on derived data regardless of transport | MUST |
| T08 | Transport is documented: header/metadata names, encoding rules, error modes | MUST |
| T09 | Receiving side returns a transport-appropriate error on BLOCK (HTTP 403, gRPC PERMISSION_DENIED, etc.) | MUST |
| T10 | Empty label (unrestricted data) always passes without side effects | MUST |
| T11 | Transport **MAY** add authentication, encryption, or compression atop DBP | MAY |
| T12 | Transport **MAY** define a discovery mechanism (agent registry, endpoint resolution) | MAY |
| T13 | Transport **MUST NOT** modify the label or policy in transit | MUST NOT |
| T14 | Transport **MUST** preserve label integrity through all transformations (serialisation, encoding, chunking) | MUST |

### 6.1 Compliance Verification

A compliant transport implementation **MUST** pass the following test suite:

1. **Block-before-send**: Data with label `{A}` sent to agent with clearance
   `{B}` under Policy.ALL does not result in any observable network, file, or
   I/O operation from the transport layer.
2. **Receive-filter**: Agent with clearance `{B}` reading from a mailbox
   containing messages labelled `{A}`, `{B}`, and `{A,B}` receives only `{B}`
   under Policy.ANY.
3. **Heritage transport transparency**: A message created via heritage
   (union of `{A}` and `{B}`) is transmitted identically to a natively
   labelled `{A,B}` message — the transport does not distinguish.
4. **Header preservation**: Labels round-trip through serialisation and
   deserialisation without loss, reordering, or character corruption.

---

## 9.7 Open Issues

1. **WebSocket transport**: How to handle per-message labels in a persistent
   connection without re-negotiating on every frame. Candidates: per-message
   metadata frames, initial label negotiation with subsequent sub-labels, or
   dropping DBP to per-connection single-label mode.

2. **Message queues (AMQP, Kafka)**: The broker cannot enforce boundary checks
   without understanding DBP labels. Should the producer check and embed, or
   should the broker (or a proxy) be DBP-aware?

3. **Multi-hop relaying**: When an intermediate agent forwards a message, whose
   clearance governs — the forwarder's or the final recipient's? Current design:
   the sender checks against the immediate next hop, and each hop re-checks
   for its own downstream. This is safe but potentially redundant.

4. **Caching layers**: A cache that serves labelled data must not serve labelled
   data to an agent without clearance. Cache keys should incorporate the label
   or the cache should sit behind the boundary.

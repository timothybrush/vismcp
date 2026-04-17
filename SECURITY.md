# MCP Transport Security: Streamable HTTP + JSON-RPC vs. gRPC + Protobuf

A security comparison of the two transport/encoding choices for Model
Context Protocol (MCP) communication between an **MCP client** (the host
application embedding an LLM) and an **MCP server** (the process exposing
tools, resources, and prompts to that LLM).

The two stacks compared:

- **Streamable HTTP + JSON-RPC 2.0** — the officially standardized MCP
  transport. JSON text over HTTP(S), with JSON-RPC 2.0 as the envelope.
- **gRPC + Protocol Buffers** — not part of the MCP spec, but a common
  alternative when the MCP client and MCP server are operated by the
  same team and end-to-end typed contracts matter.

Throughout this document, "the client" means the MCP host (Claude
Desktop, an IDE, an agent runtime, etc.) and "the server" means the
MCP tool/resource provider.

---

## 1. Transport security for MCP sessions

An MCP session is a long-lived exchange: `initialize` handshake → tool
discovery (`tools/list`) → many `tools/call` invocations → session
teardown. The transport must protect **every** step, not just the call
itself.

| Concern | Streamable HTTP + JSON-RPC | gRPC + Protobuf |
|---|---|---|
| Underlying protocol | HTTP/1.1 or HTTP/2 | HTTP/2 only |
| MCP spec status | Standardized | Out-of-spec; custom transport |
| Encryption | TLS via the web stack | TLS via gRPC's built-in credentials |
| mTLS (peer identity for client and server) | Configured at proxy/web layer | First-class; client cert identity surfaced to servicer |
| Session resumption | HTTP keep-alive or SSE streams | HTTP/2 stream on one TCP connection |
| Works through corporate TLS-inspection proxies | Yes (this is what proxies expect) | Often breaks — HTTP/2 frames get mangled |

### MCP-specific best practices
- **Require TLS for any non-stdio MCP transport.** An MCP server often
  holds privileged credentials (GitHub tokens, database connections,
  cloud keys) on behalf of the user. Plaintext is not acceptable even
  on localhost if the machine is shared.
- **Use mTLS when the MCP client is an unattended agent** (CI bot,
  scheduled task, server-side orchestrator). The peer identity that
  TLS gives you is stronger than any bearer token the agent carries.
- **Don't rely on TLS-terminating proxies for MCP-over-gRPC.** Corporate
  MITM proxies frequently break HTTP/2. If your users run behind
  Zscaler/Netskope/BlueCoat, JSON-RPC over HTTPS will work; gRPC often
  won't.

---

## 2. MCP client authentication to the MCP server

MCP has no built-in auth scheme — it's delegated to the transport.
Which transport you pick changes what auth primitives are natural.

| Mechanism | Streamable HTTP + JSON-RPC | gRPC + Protobuf |
|---|---|---|
| Bearer tokens (OAuth2, API keys) | `Authorization` HTTP header — universal | gRPC metadata `authorization` key via `CallCredentials` |
| OAuth2 authorization code flow (human user) | Well-supported; client redirects user through browser | Works but less tooling; usually the MCP host handles the flow and passes tokens down |
| mTLS | Configured at proxy/server | Native |
| Per-session auth vs per-call auth | Natural to set once on the HTTP connection and reuse | Natural to attach `CallCredentials` per RPC |
| Signed requests (HMAC over body) | Straightforward — sign canonical JSON | Awkward — protobuf field order isn't guaranteed canonical |

### MCP-specific best practices
- **Authenticate the MCP client application, not just the end user.**
  A compromised or malicious MCP host acting on a user's behalf is a
  realistic threat. If your MCP server exposes sensitive tools, require
  the host to prove its identity (mTLS, signed client assertion, or
  per-host API key) in addition to any user token.
- **Never put credentials in `params`.** They belong in HTTP headers or
  gRPC metadata so they don't land in access logs or tool-call audit
  trails.
- **Scope tokens to tool sets.** A token that can call `filesystem/read`
  shouldn't automatically be able to call `shell/exec`. Bind tokens to
  the specific MCP methods or tool names they may invoke.
- **Short-lived tokens + refresh.** MCP sessions can be long; don't hand
  out a 30-day token and forget about it.

---

## 3. Authorization and the MCP method surface

MCP defines a small set of JSON-RPC methods: `initialize`,
`tools/list`, `tools/call`, `resources/list`, `resources/read`,
`prompts/list`, `prompts/get`, plus notifications. Each has a different
sensitivity. Authorization must be applied at the right granularity.

### On JSON-RPC
- The method is a **string in the body**: `"method": "tools/call"`.
- The tool name lives inside `params.name`. So authorization needs to
  inspect both the JSON-RPC method *and* the nested tool name.
- Unknown methods must be explicitly rejected (`-32601`).
- Miss a branch in the dispatcher and you get a bypass.

### On gRPC
- Every MCP method becomes its own RPC (`ListTools`, `CallTool`,
  `ReadResource`, ...). The method lives in the HTTP/2 `:path`.
- Unknown methods are rejected by the framework as `UNIMPLEMENTED`.
- Tool name still lives inside the request message (`CallToolRequest.name`)
  unless you model each tool as its own RPC.
- Interceptors see the fully-qualified method and can apply auth uniformly.

### MCP-specific best practices
- **Authorize on (method, tool-name) pairs**, not just the method. In
  MCP, "can this client call `tools/call`?" is the wrong question —
  the right question is "can this client call `tools/call` with
  `name=shell_exec`?"
- **Centralize dispatch.** For JSON-RPC MCP servers, route every
  request through a single registry keyed by `(method, tool_name)`.
  Never use dynamic attribute lookup or `eval` for dispatch.
- **Apply auth before invocation.** For gRPC, use a
  `ServerInterceptor`. For JSON-RPC, run an auth middleware before
  the dispatcher. Don't scatter checks inside each tool.
- **Deny by default.** New tools added to the server should be
  unreachable until explicitly whitelisted per client/role.
- **Treat `tools/list` output as a capability advertisement.** Don't
  return tools the caller isn't authorized to invoke — that leaks
  your sensitive-capability surface.

---

## 4. Input validation for tool arguments (the biggest difference)

Tool arguments in MCP are the primary untrusted input. They may come
from the end user, from an LLM interpreting a prompt-injection payload,
or from chained tool outputs. Structural validation is the floor, not
the ceiling.

### On JSON-RPC MCP servers

- `tools/call` takes `params.arguments` as free-form JSON. The MCP tool
  schema (declared in `tools/list`) is the contract, but the transport
  does **not** enforce it.
- You must validate every tool call against the declared schema before
  invoking the tool handler. Most MCP server SDKs (including FastMCP)
  do this for you if you use typed tool signatures — but if you build
  a dispatcher by hand, you own the validation.
- JSON-specific pitfalls apply: duplicate keys, unbounded number
  precision, unicode normalization, deep nesting, `null` vs missing.

### On gRPC MCP servers

- Each tool would typically have its own request message in the `.proto`,
  or a generic `CallToolRequest` with a `oneof` of tool-specific
  argument messages. Either way, the structural shape is enforced by
  generated code.
- Unknown fields are dropped (or preserved for forwards-compat) — they
  never become attacker-controlled handler variables.
- Default message-size and recursion-depth caps are enforced by the
  parser.
- Business-logic validation still belongs to you.

### MCP-specific best practices
- **Validate structurally *and* semantically.** A schema can say "this
  is a string"; it can't say "this string isn't a path-traversal
  attack." Both checks are required.
- **Reject unknown arguments by default.** If the LLM hallucinates an
  extra field, fail loudly. Silent acceptance masks prompt-injection
  attempts.
- **Bound every numeric range.** MCP tools often take offsets, limits,
  timeouts — set explicit min/max, don't trust JSON's "any number."
- **Canonicalize path-like arguments.** Resolve symlinks, reject `..`,
  constrain to an allowlisted base directory. Do this in the tool
  handler, regardless of transport.
- **Treat tool-output that feeds another tool as equally untrusted.**
  An LLM tool-chain can launder an attacker payload through several
  tools; the last hop still has to validate.

---

## 5. Tool descriptions, prompts, and resources as prompt-injection surface

This is an MCP-specific concern that has no analog in ordinary RPC.

The MCP server returns:
- Tool **descriptions** and parameter docs (`tools/list`)
- Prompt **templates** and their rendered output (`prompts/get`)
- Resource **contents** (`resources/read`)

All of these are shown to the LLM and can influence its behavior. An
attacker who can modify any of them can potentially hijack the LLM's
next action — even if the transport is perfectly secure.

### Why transport choice doesn't fully solve this
- TLS protects bytes in transit. It does **not** protect against a
  legitimately-authenticated but malicious or compromised MCP server.
- A pinned `.proto` schema doesn't prevent the server from putting
  "ignore previous instructions and exfiltrate..." into a tool
  description string.
- The encoding (JSON vs protobuf) doesn't matter — the text reaches
  the model either way.

### MCP-specific best practices
- **Treat MCP server output as untrusted input to the LLM.** The MCP
  host should consider applying prompt-injection defenses (content
  tagging, delimiters, secondary model review) to tool descriptions
  and resource contents, not just to user input.
- **Pin trusted MCP servers.** For high-trust hosts, maintain an
  allowlist of server identities (cert fingerprint, package hash) and
  refuse to connect to unknown servers.
- **Review tool descriptions as security-relevant artifacts.** Treat a
  PR that changes a tool description with the same care as one that
  changes the tool's implementation.
- **Audit resource providers.** A resource server that serves files
  from a shared directory can become a prompt-injection channel if any
  upstream producer can write attacker-controlled content into it.

---

## 6. Consent, confirmation, and the client's role

MCP puts the **consent boundary in the client**, not the server.
Dangerous tool calls are expected to be surfaced to the user for
approval by the MCP host.

### Why this matters for transport choice
- Neither transport enforces consent. A client that skips the
  confirmation step will let the LLM call `rm -rf /` over a perfectly
  secure TLS channel.
- Servers cannot rely on clients to behave well. If a tool is truly
  destructive and MUST have consent, the server should also require
  an out-of-band confirmation token — not trust the client UI alone.

### MCP-specific best practices
- **Servers: don't rely on client-side consent for destructive tools.**
  If the tool can't be undone, require an auth step that proves a
  human confirmed — e.g. a short-lived confirmation token the server
  issues via a separate channel.
- **Clients: fail closed on consent.** If the consent UI can't display
  a tool's arguments safely (too long, contains suspicious unicode,
  embedded URLs to unknown domains), block the call rather than
  degrading to "approve anyway."
- **Log both sides of the consent exchange.** Who requested what, who
  approved, when. This is the audit trail regulators ask for first.
- **Make consent decisions depend on identity.** A service account
  shouldn't get the same "are you sure?" prompt as a human — it should
  have a pre-declared policy.

---

## 7. Session lifecycle and initialization

MCP starts every session with `initialize`, which negotiates protocol
version, client info, server info, and capabilities. This handshake
is itself a security-relevant exchange.

### Risks
- **Capability downgrade.** A man-in-the-middle (or a misconfigured
  proxy) could strip capabilities to force fallback behavior.
- **Version confusion.** Old MCP clients connecting to new servers (or
  vice versa) may interpret messages differently; treat protocol
  version negotiation as a trust decision, not a compatibility nicety.
- **Identity spoofing at `initialize`.** The client sends its name/version
  in `clientInfo`. Don't trust it for authorization decisions — it's
  self-asserted metadata.
- **Long-lived sessions amplify credential leaks.** A token leaked from
  a 12-hour session is worse than one leaked from a 5-minute session.

### MCP-specific best practices
- **Authenticate before honoring `initialize`.** On HTTPS, require the
  auth header on the initial POST. On gRPC, attach credentials to the
  channel before the first RPC.
- **Bound session lifetime.** Re-authenticate periodically; don't let a
  session outlive the credential that authorized it.
- **Don't trust `clientInfo.name` for authorization.** Anyone can claim
  to be "Claude Desktop." Authorize by cryptographic identity (mTLS
  cert, signed token) and use `clientInfo` only for telemetry.
- **Refuse old protocol versions** past their deprecation window.
  Don't silently downgrade.

---

## 8. Denial of service against MCP servers

MCP servers are particularly attractive DoS targets because many tools
call slow or paid backends (databases, LLMs, cloud APIs). A DoS on an
MCP server is often also a **cost amplification** attack.

| Vector | Streamable HTTP + JSON-RPC | gRPC + Protobuf |
|---|---|---|
| Oversized tool arguments | Bound `Content-Length` and parser | Bounded by default (4 MB); tune per tool |
| Compression bombs | Real on `gzip`/`br` | Per-message compression; verify bounded |
| Deep JSON nesting | Parser stack exhaustion | N/A |
| HTTP/2 Rapid Reset (CVE-2023-44487) | Only if HTTP/2 is used | Directly affects gRPC — patch promptly |
| Stream multiplexing abuse | N/A on HTTP/1.1 | One TCP conn can open thousands of concurrent RPCs |
| Long-running tool calls | Yes — LLMs tolerate latency | Yes |
| Cost amplification (paid backends) | Yes | Yes |

### MCP-specific best practices
- **Rate-limit `tools/call` per authenticated identity**, not per IP.
  Consider per-(identity, tool-name) buckets — `shell_exec` should
  have a tighter budget than `echo`.
- **Timeout every tool invocation.** LLMs won't stop asking; your
  server has to.
- **Cap concurrent in-flight tool calls per session.** Otherwise a
  single compromised client can exhaust your backend quota.
- **Separate quotas for expensive tools.** If a tool costs $0.10 per
  call (paid API, GPU inference), enforce a daily budget independent
  of overall rate limits.
- **Keep `grpcio`, `protobuf`, and your HTTP stack patched.** HTTP/2
  and protobuf have both had parser CVEs.

---

## 9. Observability: auditing MCP activity

MCP servers need a strong audit trail because they act on behalf of
users via non-deterministic LLMs. The transport choice affects how
easy that audit trail is to build.

| Property | Streamable HTTP + JSON-RPC | gRPC + Protobuf |
|---|---|---|
| Can a packet capture be read by hand? | Yes (after TLS termination) | No — binary protobuf is opaque |
| Can a WAF / API gateway inspect requests? | Yes, well-supported | Limited — few WAFs deep-parse gRPC |
| Can SIEM rules match on tool arguments? | Yes directly | Requires decoding first |
| Accidental secret leakage in logs | Higher — `log.info(body)` is tempting | Lower by default |

### MCP-specific best practices
- **Log every tool invocation** with: caller identity, tool name,
  argument hash (not raw args), result status, duration, correlation ID.
- **Never log full tool arguments or results by default.** Tools may
  legitimately see secrets (file contents, API responses). Log shapes
  and sizes, not payloads.
- **Scrub on the way in, not on the way out.** Strip `authorization`
  headers, bearer tokens, API keys, and known secret shapes before
  they touch the logging pipeline.
- **Correlate client-side and server-side logs.** The MCP host should
  log what it asked for; the server should log what it received;
  correlation IDs make the two joinable.
- **If you switch from HTTPS+JSON-RPC to gRPC, you lose WAF coverage.**
  Replace it with application-level validation, structured logging,
  and anomaly detection — don't just drop the layer.

---

## 10. Supply chain: MCP server code and schema evolution

MCP servers are often small, single-purpose processes that get added
to a host's server list and then forgotten. That's a supply-chain risk.

### Common-to-both concerns
- **MCP servers run with the user's permissions.** A malicious or
  compromised server can do anything the user can do.
- **Servers are often third-party.** Vet them like you'd vet any
  executable: source, signer, update channel.

### Transport-specific
- **JSON-RPC MCP servers** have no mandatory schema on the wire. Tool
  argument schemas are declared in `tools/list` but not enforced by
  the transport. Easier to ship, easier to drift.
- **gRPC MCP servers** ship a `.proto` contract. You can lint it with
  `buf breaking` in CI, and the generated stubs give you compile-time
  guarantees on both sides.

### MCP-specific best practices
- **Pin the MCP server binary or package**, not just "latest." An MCP
  server update can silently add tools, change descriptions, or
  expand capabilities.
- **Review tool-list changes like API changes.** A new tool appearing
  in `tools/list` is effectively a new permission the server is
  asking for.
- **For gRPC, check in generated stubs or regenerate deterministically.**
  A compromised `protoc` or codegen pipeline compromises every server
  built from it.
- **Watch the dependency tree.** `grpcio`, `protobuf`, JSON parsers,
  and HTTP stacks have all had CVEs. Subscribe to the feeds.

---

## 11. Stdio vs networked transports (the hidden third option)

Many MCP servers run over **stdio** as a subprocess of the client.
Stdio is not what this document compares, but it's worth calling out
because moving from stdio to HTTP or gRPC fundamentally changes the
trust model.

| Property | Stdio | HTTPS + JSON-RPC / gRPC |
|---|---|---|
| Attack surface | Local process boundary | Network (even on localhost) |
| Authentication | Inherited from process launch | Must be built explicitly |
| Eavesdropping | Requires local code execution | Requires network access |
| Multi-tenant | One client per server process | Potentially many clients |
| Consent model | Implicit — the client launched the server | Must be enforced by auth |

### MCP-specific best practices
- **Don't port a stdio MCP server to HTTP/gRPC without adding auth.**
  Stdio servers often assume the caller is trusted because they were
  launched by it. Networked servers must authenticate every request.
- **Reconsider sandboxing when going networked.** A stdio MCP server
  inherits the client's permissions; a networked one may run elsewhere
  with more or fewer privileges. Match the sandbox to the threat.
- **Audit environment inheritance.** Stdio servers inherit env vars,
  working directory, and file descriptors. Networked servers don't —
  anything they need (credentials, config) must be explicitly provisioned.

---

## 12. Summary: which transport is easier to secure for MCP?

**Streamable HTTP + JSON-RPC is easier to secure when:**
- You are following the MCP spec literally — this is the standardized
  transport; clients and servers from different vendors will interop.
- Clients are heterogeneous (browsers, mobile, third parties).
- You need to leverage mature HTTP infrastructure (OAuth, WAFs, API
  gateways, CDNs).
- Auditors and SIEM operators need readable payloads.
- You're exposing an MCP server to untrusted or semi-trusted clients.

**gRPC + Protobuf is easier to secure when:**
- You control both MCP client and MCP server (internal tooling).
- Schema enforcement on every tool call is a feature, not a friction.
- You want mTLS peer identity and per-method authorization as
  first-class concerns.
- You're building an internal MCP deployment where interop with
  standard MCP hosts isn't a goal.

**Neither is inherently more secure.** The MCP-specific risks — prompt
injection via tool descriptions, confused-deputy via shared server
credentials, consent bypass, cost amplification, and malicious MCP
servers — exist on **both** transports. The transport only protects
the bytes between client and server; it cannot protect the LLM from a
server that's authenticated but hostile, or a client that skips
consent.

Pick the transport that matches your MCP deployment model:
- **Third-party / open ecosystem → Streamable HTTP + JSON-RPC**
  (standards compliance wins).
- **Internal, controlled, latency-sensitive → gRPC + Protobuf**
  (typed contracts and mTLS win).

Then apply the MCP-specific best practices — the ones about tool
argument validation, consent enforcement, tool-list authorization,
and treating server output as LLM-facing untrusted input — **regardless
of transport.** Those are where most real MCP incidents will happen.

# gRPC + Protocol Buffers

Minimal MCP-style setup. One tool: `add(a, b)`.

## Regenerate stubs (only if you change mcp.proto)

```
uv run --directory . python -m grpc_tools.protoc -I. \
  --python_out=. --grpc_python_out=. mcp.proto
```

This produces `mcp_pb2.py` (message classes) and `mcp_pb2_grpc.py` (stub + servicer).

## Run

Terminal 1:
```
uv run --directory . python server.py
```

Terminal 2:
```
uv run --directory . python client.py
```

## What to observe

- **Transport**: HTTP/2, multiplexed. gRPC framing, not raw HTTP bodies.
- **Encoding**: binary protobuf. Not human-readable — `curl` won't work.
  The client prints `ByteSize()` so you can see the on-wire size (e.g. the
  `add(2,3)` call is 25 bytes vs ~90 bytes of JSON for the equivalent
  JSON-RPC request).
- **Schema**: `mcp.proto` is the contract. Both sides generate typed code
  from it. A field rename is a breaking change; an added field (with a new
  tag number) is backwards-compatible.
- **Types**: enforced by the generated stubs. `AddArgs(a=2.0, b=3.0)` is
  type-checked at construction time; there's no string-keyed `params` dict.
- **Methods**: each RPC is its own method on the service (`ListTools`,
  `CallTool`) rather than a `method` string inside a JSON envelope.

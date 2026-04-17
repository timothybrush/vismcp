# Streamable HTTP + JSON-RPC 2.0

Minimal MCP-style setup. One tool: `add(a, b)`.

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

- **Transport**: plain HTTP/1.1 POST to `/rpc`. No codegen, no schema.
- **Encoding**: human-readable JSON text. You can `curl` the server directly:
  ```
  curl -X POST http://127.0.0.1:8001/rpc \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"add","arguments":{"a":2,"b":3}}}'
  ```
- **Framing**: one request = one HTTP body. The `jsonrpc`, `id`, `method`, `params`
  envelope comes from JSON-RPC 2.0. Errors use numeric codes (`-32601`,
  `-32602`, ...) inside an `error` object.
- **Types**: untyped on the wire — the server validates shape at runtime.

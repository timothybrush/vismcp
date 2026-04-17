"""
MCP-style server over Streamable HTTP using JSON-RPC 2.0.

Transport: HTTP POST (a single endpoint, /rpc)
Encoding:  JSON text, framed per JSON-RPC 2.0

Exposes one tool: add(a, b) -> a + b

Run:
    python server.py
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# ---- The "tool" ------------------------------------------------------------
def tool_add(a: float, b: float) -> float:
    return a + b


TOOLS = {
    "add": {
        "fn": tool_add,
        "description": "Add two numbers.",
        "params": {"a": "number", "b": "number"},
    },
}


# ---- JSON-RPC 2.0 dispatch -------------------------------------------------
def rpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def handle_rpc(request: dict) -> dict:
    req_id = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return rpc_error(req_id, -32600, "Invalid Request: jsonrpc must be '2.0'")

    method = request.get("method")
    params = request.get("params") or {}

    # MCP-style discovery + invocation methods
    if method == "tools/list":
        return rpc_result(req_id, {
            "tools": [
                {"name": name, "description": t["description"], "params": t["params"]}
                for name, t in TOOLS.items()
            ]
        })

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        tool = TOOLS.get(name)
        if tool is None:
            return rpc_error(req_id, -32601, f"Unknown tool: {name}")
        try:
            value = tool["fn"](**args)
            return rpc_result(req_id, {"content": value})
        except TypeError as e:
            return rpc_error(req_id, -32602, f"Invalid params: {e}")

    return rpc_error(req_id, -32601, f"Method not found: {method}")


# ---- HTTP layer ------------------------------------------------------------
class RPCHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/rpc":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            body = json.dumps(rpc_error(None, -32700, "Parse error")).encode()
            self._send_json(400, body)
            return

        print(f"[server] <- {raw}")
        response = handle_rpc(request)
        body = json.dumps(response).encode("utf-8")
        print(f"[server] -> {body.decode()}")
        self._send_json(200, body)

    def _send_json(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8001), RPCHandler)
    print("[server] HTTP+JSON-RPC MCP server on http://127.0.0.1:8001/rpc")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()

"""
MCP-style client over Streamable HTTP using JSON-RPC 2.0.

Sends two requests to the server:
  1. tools/list   -> discover available tools
  2. tools/call   -> invoke 'add' with a=2, b=3

Run (after starting server.py):
    python client.py
"""

import json
import urllib.request


ENDPOINT = "http://127.0.0.1:8001/rpc"


def rpc(method: str, params: dict, req_id: int) -> dict:
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    raw = json.dumps(payload).encode("utf-8")
    print(f"[client] -> {raw.decode()}")

    req = urllib.request.Request(
        ENDPOINT,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
    print(f"[client] <- {body}")
    return json.loads(body)


def main():
    listing = rpc("tools/list", {}, req_id=1)
    print("[client] tools:", listing["result"]["tools"])

    call = rpc(
        "tools/call",
        {"name": "add", "arguments": {"a": 2, "b": 3}},
        req_id=2,
    )
    print("[client] add(2, 3) =", call["result"]["content"])


if __name__ == "__main__":
    main()

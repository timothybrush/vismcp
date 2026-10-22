# Activate terminal:

(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (\& c:\\vasu\\code\\vismcp\\.venv\\Scripts\\Activate.ps1)

# HTTP + json-rpc

On one terminal:
uv run --directory http_jsonrpc python server.py

ON second termainal:
uv run --directory http_jsonrpc python client.py

(Wireshark capture: tcp.port == 8001)

# gRPC:

On one terminal:
uv run --directory grpc_protobuf python server.py

ON second termainal:
uv run --directory grpc_protobuf python client.py

(wireshark capture: tcp.port == 50051)


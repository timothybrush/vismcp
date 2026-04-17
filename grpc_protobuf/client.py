"""
MCP-style client over gRPC using Protocol Buffers.

Sends two RPCs to the server:
  1. ListTools  -> discover available tools
  2. CallTool   -> invoke 'add' with a=2, b=3

Run (after starting server.py):
    python client.py
"""

import grpc

import mcp_pb2
import mcp_pb2_grpc


def main():
    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        stub = mcp_pb2_grpc.MCPStub(channel)

        list_req = mcp_pb2.ListToolsRequest()
        print(f"[client] -> ListTools ({list_req.ByteSize()} bytes)")
        list_resp = stub.ListTools(list_req)
        print(f"[client] <- tools: {[t.name for t in list_resp.tools]}")

        call_req = mcp_pb2.CallToolRequest(
            name="add",
            add_args=mcp_pb2.AddArgs(a=2.0, b=3.0),
        )
        print(f"[client] -> CallTool 'add' ({call_req.ByteSize()} bytes)")
        call_resp = stub.CallTool(call_req)

        if call_resp.error:
            print(f"[client] <- error: {call_resp.error}")
        else:
            print(f"[client] <- add(2, 3) = {call_resp.result}")


if __name__ == "__main__":
    main()

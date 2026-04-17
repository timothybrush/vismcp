"""
MCP-style server over gRPC using Protocol Buffers.

Transport: HTTP/2 (gRPC)
Encoding:  Protobuf (binary, schema-defined in mcp.proto)

Exposes one tool: add(a, b) -> a + b

Before running, generate stubs once:
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. mcp.proto

Run:
    python server.py
"""

from concurrent import futures
import grpc

import mcp_pb2
import mcp_pb2_grpc


class MCPServicer(mcp_pb2_grpc.MCPServicer):
    def ListTools(self, request, context):
        print(f"[server] <- ListTools ({request.ByteSize()} bytes on wire)")
        response = mcp_pb2.ListToolsResponse(
            tools=[mcp_pb2.ToolInfo(name="add", description="Add two numbers.")]
        )
        print(f"[server] -> ListToolsResponse ({response.ByteSize()} bytes)")
        return response

    def CallTool(self, request, context):
        print(
            f"[server] <- CallTool name={request.name!r} "
            f"a={request.add_args.a} b={request.add_args.b} "
            f"({request.ByteSize()} bytes on wire)"
        )
        if request.name != "add":
            return mcp_pb2.CallToolResponse(error=f"Unknown tool: {request.name}")

        total = request.add_args.a + request.add_args.b
        response = mcp_pb2.CallToolResponse(result=total)
        print(f"[server] -> CallToolResponse result={total} ({response.ByteSize()} bytes)")
        return response


def main():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    mcp_pb2_grpc.add_MCPServicer_to_server(MCPServicer(), server)
    server.add_insecure_port("127.0.0.1:50051")
    server.start()
    print("[server] gRPC+protobuf MCP server on 127.0.0.1:50051")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=0)


if __name__ == "__main__":
    main()

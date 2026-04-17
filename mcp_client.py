"""
MCP Client — connects to any MCP server and exposes helper methods.

Supports two modes:
  - stdio:  launches the server as a subprocess   (default)
  - http:   connects to an already-running HTTP server
"""

import asyncio
from fastmcp import Client


class MCPClient:
    """Thin wrapper around fastmcp.Client for convenient reuse."""

    def __init__(self, server_target: str, **kwargs):
        """
        Parameters
        ----------
        server_target : str
            Either a path to a Python server script (stdio) or an HTTP URL.
        **kwargs
            Extra keyword args forwarded to fastmcp.Client
            (e.g. env={"API_KEY": "..."} for stdio).
        """
        self.client = Client(server_target, **kwargs)

    # -- context manager delegation ------------------------------------------
    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)

    # -- tools ---------------------------------------------------------------
    async def list_tools(self):
        """Return the list of tools exposed by the server."""
        return await self.client.list_tools()

    async def call_tool(self, name: str, arguments: dict | None = None):
        """Invoke a tool by name with the given arguments."""
        return await self.client.call_tool(name, arguments or {})

    # -- resources -----------------------------------------------------------
    async def list_resources(self):
        """Return the list of static resources exposed by the server."""
        return await self.client.list_resources()

    async def list_resource_templates(self):
        """Return the list of resource templates (URI patterns)."""
        return await self.client.list_resource_templates()

    async def read_resource(self, uri: str):
        """Read a resource (or fill a template) by URI."""
        return await self.client.read_resource(uri)

    # -- prompts -------------------------------------------------------------
    async def list_prompts(self):
        """Return the list of prompts exposed by the server."""
        return await self.client.list_prompts()

    async def get_prompt(self, name: str, arguments: dict | None = None):
        """Retrieve a rendered prompt by name."""
        return await self.client.get_prompt(name, arguments or {})


# ---------------------------------------------------------------------------
# Convenience: quick self-test when run directly
# ---------------------------------------------------------------------------
async def _self_test():
    """Connect to mcp_server.py via stdio and exercise every capability."""
    async with MCPClient("mcp_server.py") as client:
        # Tools
        tools = await client.list_tools()
        print("=== Tools ===")
        for t in tools:
            print(f"  - {t.name}: {t.description}")

        result = await client.call_tool("add", {"a": 3, "b": 7})
        print(f"\nadd(3, 7) => {result}\n")

        # Resources
        resources = await client.list_resources()
        print("=== Resources ===")
        for r in resources:
            print(f"  - {r.uri}: {r.name}")

        templates = await client.list_resource_templates()
        print("\n=== Resource Templates ===")
        for t in templates:
            print(f"  - {t.uriTemplate}: {t.name}")

        content = await client.read_resource("data://server-info")
        print(f"\ndata://server-info => {content}\n")

        # Prompts
        prompts = await client.list_prompts()
        print("=== Prompts ===")
        for p in prompts:
            print(f"  - {p.name}: {p.description}")

        prompt = await client.get_prompt("summarize", {"text": "MCP is great!"})
        print(f"\nsummarize prompt => {prompt}\n")


if __name__ == "__main__":
    asyncio.run(_self_test())

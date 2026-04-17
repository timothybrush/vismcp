"""
Sample Application — demonstrates a complete MCP client ↔ server workflow.

This script:
  1. Connects to mcp_server.py via stdio (launches it as a subprocess)
  2. Discovers all tools, resources, and prompts
  3. Calls every tool, reads every resource, and renders every prompt
"""

import asyncio
import json
from mcp_client import MCPClient


DIVIDER = "-" * 60


def extract_tool_result(result):
    """Extract the clean value from a CallToolResult."""
    if result.data is not None:
        return result.data
    if result.content:
        return result.content[0].text
    return result


def extract_resource_text(result):
    """Extract text from a resource read result."""
    if isinstance(result, list) and result:
        return result[0].text
    return str(result)


def extract_prompt_text(result):
    """Extract the rendered prompt text from a GetPromptResult."""
    if hasattr(result, "messages") and result.messages:
        return result.messages[0].content.text
    return str(result)


async def demo_tools(client: MCPClient):
    """Discover and invoke every tool on the server."""
    print("\n" + DIVIDER)
    print("  TOOLS")
    print(DIVIDER)

    tools = await client.list_tools()
    print(f"Found {len(tools)} tool(s):\n")
    for t in tools:
        print(f"  [{t.name}]  {t.description}")

    # Call each tool with sample arguments
    print("\n-- Calling tools --\n")

    result = await client.call_tool("add", {"a": 10, "b": 25})
    print(f"  add(10, 25)           => {extract_tool_result(result)}")

    result = await client.call_tool("multiply", {"a": 6, "b": 7})
    print(f"  multiply(6, 7)        => {extract_tool_result(result)}")

    result = await client.call_tool("get_current_time", {})
    print(f"  get_current_time()    => {extract_tool_result(result)}")

    result = await client.call_tool(
        "word_count", {"text": "Hello world!\nThis is a test."}
    )
    print(f"  word_count(...)       => {extract_tool_result(result)}")


async def demo_resources(client: MCPClient):
    """Discover and read every resource (and resource template) on the server."""
    print("\n" + DIVIDER)
    print("  RESOURCES")
    print(DIVIDER)

    resources = await client.list_resources()
    print(f"Found {len(resources)} static resource(s):\n")
    for r in resources:
        print(f"  [{r.uri}]  {r.name}")

    templates = await client.list_resource_templates()
    print(f"\nFound {len(templates)} resource template(s):\n")
    for t in templates:
        print(f"  [{t.uriTemplate}]  {t.name}")

    # Read each static resource
    print("\n-- Reading resources --\n")

    info = await client.read_resource("data://server-info")
    print(f"  data://server-info       => {extract_resource_text(info)}")

    dataset = await client.read_resource("data://sample-dataset")
    print(f"  data://sample-dataset    => {extract_resource_text(dataset)}")

    # Fill a template
    greeting = await client.read_resource("greeting://Alice")
    print(f"  greeting://Alice         => {extract_resource_text(greeting)}")


async def demo_prompts(client: MCPClient):
    """Discover and render every prompt on the server."""
    print("\n" + DIVIDER)
    print("  PROMPTS")
    print(DIVIDER)

    prompts = await client.list_prompts()
    print(f"Found {len(prompts)} prompt(s):\n")
    for p in prompts:
        print(f"  [{p.name}]  {p.description}")

    # Render each prompt
    print("\n-- Rendering prompts --\n")

    p = await client.get_prompt("summarize", {"text": "MCP makes LLMs talk to tools."})
    print(f"  summarize =>\n    {extract_prompt_text(p)}\n")

    p = await client.get_prompt(
        "code_review",
        {"code": "def f(x): return x+1", "language": "python"},
    )
    print(f"  code_review =>\n    {extract_prompt_text(p)}\n")

    p = await client.get_prompt(
        "explain_concept",
        {"concept": "recursion", "audience": "five-year-old"},
    )
    print(f"  explain_concept =>\n    {extract_prompt_text(p)}\n")


async def main():
    print("=" * 60)
    print("  MCP DEMO APPLICATION")
    print("=" * 60)

    # Connect to the server via stdio (it launches mcp_server.py as a subprocess)
    async with MCPClient("mcp_server.py") as client:
        await demo_tools(client)
        await demo_resources(client)
        await demo_prompts(client)

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

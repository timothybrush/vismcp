"""
MCP Server - Exposes tools, resources, and prompts via the Model Context Protocol.

Run with:
    python mcp_server.py                          # stdio transport (for subprocess clients)
    python mcp_server.py --transport streamable-http   # HTTP transport on port 8000
"""

import argparse
import datetime
import json
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Create server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "DemoServer",
    instructions=(
        "A demo MCP server that provides math tools, data resources, "
        "and reusable prompt templates."
    ),
)

# ---------------------------------------------------------------------------
# TOOLS — callable functions the client can invoke
# ---------------------------------------------------------------------------

@mcp.tool
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@mcp.tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


@mcp.tool
def get_current_time() -> str:
    """Return the current date and time as an ISO-8601 string."""
    return datetime.datetime.now().isoformat()


@mcp.tool
def word_count(text: str) -> dict:
    """Count words, characters, and lines in the given text."""
    return {
        "words": len(text.split()),
        "characters": len(text),
        "lines": text.count("\n") + 1,
    }


# ---------------------------------------------------------------------------
# RESOURCES — passive data the client can read
# ---------------------------------------------------------------------------

@mcp.resource("data://server-info")
def server_info() -> str:
    """General information about this server."""
    return json.dumps({
        "name": "DemoServer",
        "version": "1.0.0",
        "description": "A sample MCP server with tools, resources, and prompts.",
    }, indent=2)


@mcp.resource("data://sample-dataset")
def sample_dataset() -> str:
    """A small sample dataset returned as JSON."""
    data = [
        {"id": 1, "name": "Alice", "score": 95},
        {"id": 2, "name": "Bob", "score": 82},
        {"id": 3, "name": "Charlie", "score": 90},
    ]
    return json.dumps(data, indent=2)


@mcp.resource("greeting://{name}")
def greeting_resource(name: str) -> str:
    """Return a personalised greeting for the given name."""
    return f"Hello, {name}! Welcome to the Demo MCP Server."


# ---------------------------------------------------------------------------
# PROMPTS — reusable message templates for LLM interactions
# ---------------------------------------------------------------------------

@mcp.prompt
def summarize(text: str) -> str:
    """Create a prompt asking the LLM to summarise text."""
    return f"Please provide a concise summary of the following text:\n\n{text}"


@mcp.prompt
def code_review(code: str, language: str = "python") -> str:
    """Create a prompt asking the LLM to review code."""
    return (
        f"Please review the following {language} code for bugs, style issues, "
        f"and potential improvements:\n\n```{language}\n{code}\n```"
    )


@mcp.prompt
def explain_concept(concept: str, audience: str = "beginner") -> str:
    """Create a prompt to explain a concept to a specific audience."""
    return (
        f"Explain the concept of '{concept}' in a way that a {audience} "
        f"would understand. Use simple examples where appropriate."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Demo MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", port=args.port)
    else:
        mcp.run(transport="stdio")

"""
简单的 MCP 测试服务器 —— 提供 add / multiply 两个计算工具。

通过 stdio 方式与 AgentScope StdIOStatefulClient 配合使用。

Usage:
    python -m scripts.mcp_test_server
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-calculator")


@mcp.tool()
def add(a: float, b: float) -> str:
    """Add two numbers together and return the result.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The sum of the two numbers as a string.
    """
    return str(a + b)


@mcp.tool()
def multiply(a: float, b: float) -> str:
    """Multiply two numbers together and return the result.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The product of the two numbers as a string.
    """
    return str(a * b)


if __name__ == "__main__":
    mcp.run(transport="stdio")

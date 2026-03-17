"""工具管理器 —— 根据 tool_config 构建 AgentScope Toolkit。

支持三类工具来源：
  1. builtin_tools — AgentScope 内置工具函数
  2. mcp_servers  — MCP 协议工具服务（stdio / http）
  3. skills       — AgentScope Agent Skill（SKILL.md 目录）

tool_config 格式示例：
{
    "builtin_tools": ["execute_python_code", "view_text_file"],
    "mcp_servers": [
        {
            "type": "stdio",
            "name": "calculator",
            "command": "python",
            "args": ["-m", "scripts.mcp_test_server"]
        },
        {
            "type": "http",
            "name": "remote-api",
            "transport": "sse",
            "url": "http://localhost:8080/sse"
        }
    ],
    "skills": ["./skills/current-time"]
}
"""

import asyncio
import logging
import sys
from typing import Any

MCP_CLEANUP_TIMEOUT = 10  # 单个 MCP 客户端关闭超时（秒）

logger = logging.getLogger(__name__)

_BUILTIN_TOOL_NAMES = {
    "execute_python_code",
    "execute_shell_command",
    "view_text_file",
}


def _get_builtin_tool(name: str):
    """按需导入内置工具函数，避免顶层导入 agentscope。"""
    from agentscope.tool import (
        execute_python_code,
        execute_shell_command,
        view_text_file,
    )
    mapping = {
        "execute_python_code": execute_python_code,
        "execute_shell_command": execute_shell_command,
        "view_text_file": view_text_file,
    }
    return mapping.get(name)


def _create_mcp_client(server_cfg: dict[str, Any]):
    """根据配置创建 MCP Client 实例。

    返回 (client, is_stateful) 元组。
    """
    server_type = server_cfg.get("type", "stdio")
    name = server_cfg.get("name", "mcp_server")

    if server_type == "stdio":
        from agentscope.mcp import StdIOStatefulClient

        command = server_cfg["command"]
        if command in ("python", "python3"):
            command = sys.executable

        client = StdIOStatefulClient(
            name=name,
            command=command,
            args=server_cfg.get("args", []),
            env=server_cfg.get("env"),
            cwd=server_cfg.get("cwd"),
        )
        return client, True

    if server_type == "http":
        from agentscope.mcp import HttpStatelessClient

        client = HttpStatelessClient(
            name=name,
            transport=server_cfg.get("transport", "sse"),
            url=server_cfg["url"],
            headers=server_cfg.get("headers"),
            timeout=server_cfg.get("timeout", 30),
        )
        return client, False

    raise ValueError(f"不支持的 MCP 类型: {server_type}，仅支持 stdio / http")


async def build_toolkit_async(
    tool_config: dict | None = None,
) -> tuple:
    """异步构建 Toolkit，支持 builtin_tools / mcp_servers / skills。

    Returns:
        (toolkit, stateful_clients) 元组。
        stateful_clients 是需要在执行完成后关闭的 StdIO 客户端列表。
    """
    from agentscope.tool import Toolkit

    toolkit = Toolkit()
    stateful_clients = []

    if not tool_config:
        return toolkit, stateful_clients

    # 1. 注册内置工具
    for tool_name in tool_config.get("builtin_tools", []):
        if tool_name not in _BUILTIN_TOOL_NAMES:
            logger.warning("未知内置工具: %s，跳过", tool_name)
            continue
        func = _get_builtin_tool(tool_name)
        if func:
            toolkit.register_tool_function(func)
            logger.info("注册内置工具: %s", tool_name)

    # 2. 注册 MCP 工具
    for server_cfg in tool_config.get("mcp_servers", []):
        client = None
        connected = False
        try:
            client, is_stateful = _create_mcp_client(server_cfg)

            if is_stateful:
                await client.connect()
                connected = True
                stateful_clients.append(client)
                logger.info("MCP StdIO 已连接: %s", server_cfg.get("name"))

            await toolkit.register_mcp_client(
                client,
                namesake_strategy="rename",
            )
            logger.info("注册 MCP 工具: %s", server_cfg.get("name"))
        except Exception:
            logger.exception("注册 MCP 失败: %s", server_cfg.get("name"))
            if client and connected and client not in stateful_clients:
                try:
                    await asyncio.wait_for(
                        client.close(), timeout=MCP_CLEANUP_TIMEOUT,
                    )
                except Exception:
                    logger.warning("清理失败的 MCP 连接异常: %s", server_cfg.get("name"))

    # 3. 注册 Agent Skills
    for skill_path in tool_config.get("skills", []):
        try:
            toolkit.register_agent_skill(skill_path)
            logger.info("注册 Skill: %s", skill_path)
        except Exception:
            logger.exception("注册 Skill 失败: %s", skill_path)

    return toolkit, stateful_clients


async def cleanup_mcp_clients(
    clients: list,
    timeout: float = MCP_CLEANUP_TIMEOUT,
) -> None:
    """关闭 stateful MCP 客户端，每个客户端设有独立超时保护。"""
    for client in reversed(clients):
        try:
            await asyncio.wait_for(client.close(), timeout=timeout)
            logger.info("MCP 客户端已关闭: %s", client.name)
        except asyncio.CancelledError:
            logger.warning("关闭 MCP 客户端被取消: %s", client.name)
        except asyncio.TimeoutError:
            logger.warning(
                "关闭 MCP 客户端超时 (%.1fs): %s", timeout, client.name,
            )
        except Exception:
            logger.exception("关闭 MCP 客户端失败: %s", client.name)


def build_toolkit(tool_config: dict | None = None):
    """同步构建 Toolkit（仅 builtin_tools + skills，向后兼容）。

    不支持 MCP 工具。如需 MCP 请使用 build_toolkit_async。
    """
    from agentscope.tool import Toolkit

    toolkit = Toolkit()
    if not tool_config:
        return toolkit

    for tool_name in tool_config.get("builtin_tools", []):
        if tool_name not in _BUILTIN_TOOL_NAMES:
            logger.warning("未知内置工具: %s，跳过", tool_name)
            continue
        func = _get_builtin_tool(tool_name)
        if func:
            toolkit.register_tool_function(func)
            logger.info("注册内置工具: %s", tool_name)

    for skill_path in tool_config.get("skills", []):
        try:
            toolkit.register_agent_skill(skill_path)
            logger.info("注册 Skill: %s", skill_path)
        except Exception:
            logger.exception("注册 Skill 失败: %s", skill_path)

    return toolkit

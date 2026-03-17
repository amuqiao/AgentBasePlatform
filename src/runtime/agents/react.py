"""PlatformReActAgent —— 推理 + 工具调用型智能体。

使用 AgentScope ReActAgent 实现 Thought → Action → Observation 推理循环，
支持注册内置工具、MCP 工具服务和 AgentScope Skills。

流式输出通过 agentscope.agent.stream_printing_messages 捕获 Agent 内部
流式 token，转为 AsyncGenerator 供 SSE 推送。
"""

import asyncio
import logging
from typing import AsyncGenerator

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from src.config import get_settings
from src.runtime.agents.base import PlatformAgent
from src.runtime.model_provider import create_agentscope_model
from src.runtime.tool_manager import (
    build_toolkit,
    build_toolkit_async,
    cleanup_mcp_clients,
)

logger = logging.getLogger(__name__)


def _extract_text(content) -> str:
    """将 AgentScope Msg.content 统一转为纯文本字符串。

    ReActAgent 返回的 content 可能是：
      - str: 直接返回
      - list[dict]: [{"type":"text","text":"..."},...] → 拼接所有 text
      - 其他: str() 兜底
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", item.get("content", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content) if content else ""


def _has_mcp_config(tool_config: dict | None) -> bool:
    """检查 tool_config 是否包含 MCP 服务器配置。"""
    return bool(tool_config and tool_config.get("mcp_servers"))


class PlatformReActAgent(PlatformAgent):
    """推理+工具调用型智能体，封装 AgentScope ReActAgent。"""

    def __init__(self, max_iterations: int | None = None, **kwargs):
        super().__init__(**kwargs)
        settings = get_settings()
        self._max_iters = max_iterations or settings.AGENT_MAX_REACT_ITERATIONS

    def _create_react_agent_sync(self) -> ReActAgent:
        """同步创建 ReActAgent（仅 builtin_tools + skills，无 MCP）。"""
        model = create_agentscope_model(self.model_config)
        toolkit = build_toolkit(self.tool_config)

        return ReActAgent(
            name=self.name,
            sys_prompt=self.system_prompt,
            model=model,
            formatter=DashScopeChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=self._max_iters,
        )

    async def _create_react_agent_async(self) -> tuple[ReActAgent, list]:
        """异步创建 ReActAgent（支持 MCP + builtin_tools + skills）。

        Returns:
            (agent, stateful_clients) — stateful_clients 需在执行后关闭。
        """
        model = create_agentscope_model(self.model_config)
        toolkit, stateful_clients = await build_toolkit_async(self.tool_config)

        agent = ReActAgent(
            name=self.name,
            sys_prompt=self.system_prompt,
            model=model,
            formatter=DashScopeChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=self._max_iters,
        )
        return agent, stateful_clients

    async def _inject_history(
        self, agent: ReActAgent, history: list[dict] | None
    ):
        """将平台历史消息注入 AgentScope Agent 的 memory。"""
        if not history:
            return
        for h in history:
            msg = Msg(
                name=h.get("role", "user"),
                content=h["content"],
                role=h["role"],
            )
            await agent.memory.add(msg)

    async def _extract_tool_calls(self, agent: ReActAgent) -> list[dict]:
        """从 AgentScope Agent 的 memory 中提取工具调用记录。"""
        tool_uses: dict[str, dict] = {}
        tool_results: dict[str, str] = {}

        try:
            msgs = await agent.memory.get_memory()
        except Exception:
            logger.debug("无法读取 agent memory，跳过工具调用提取")
            return []

        for m in msgs:
            content = getattr(m, 'content', None)
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")
                block_id = block.get("id", "")
                if block_type == "tool_use":
                    tool_uses[block_id] = {
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                elif block_type == "tool_result":
                    output = block.get("output", "")
                    if isinstance(output, list):
                        parts = []
                        for item in output:
                            if isinstance(item, dict):
                                parts.append(item.get("text", str(item)))
                            else:
                                parts.append(str(item))
                        output = "\n".join(parts)
                    tool_results[block_id] = str(output)[:500]

        tool_calls = []
        for call_id, use_info in tool_uses.items():
            tool_calls.append({
                "name": use_info["name"],
                "arguments": use_info["arguments"],
                "result": tool_results.get(call_id, ""),
            })
        return tool_calls

    async def execute(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> str:
        stateful_clients = []
        try:
            if _has_mcp_config(self.tool_config):
                agent, stateful_clients = await self._create_react_agent_async()
            else:
                agent = self._create_react_agent_sync()

            await self._inject_history(agent, history)
            msg = Msg("user", user_message, "user")
            result = await agent(msg)
            self._last_tool_calls = await self._extract_tool_calls(agent)
            return _extract_text(result.content)
        finally:
            if stateful_clients:
                try:
                    await asyncio.wait_for(
                        cleanup_mcp_clients(stateful_clients),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    logger.error("MCP 客户端批量清理超时 (30s)")
                except asyncio.CancelledError:
                    logger.warning("MCP 客户端批量清理被取消")
                except Exception:
                    logger.exception("MCP 客户端清理异常")

    async def execute_stream(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式执行 ReActAgent。

        尝试使用 agentscope.agent.stream_printing_messages 捕获流式 token；
        如果该 API 不可用则回退为执行完成后一次性输出。
        """
        stateful_clients = []
        try:
            if _has_mcp_config(self.tool_config):
                agent, stateful_clients = await self._create_react_agent_async()
            else:
                agent = self._create_react_agent_sync()

            await self._inject_history(agent, history)
            msg = Msg("user", user_message, "user")

            try:
                from agentscope.agent import stream_printing_messages

                async with stream_printing_messages(agent) as stream:
                    task = asyncio.create_task(agent(msg))
                    async for chunk in stream:
                        raw = chunk.content if hasattr(chunk, "content") else chunk
                        text = _extract_text(raw)
                        if text:
                            yield text
                    await task
            except (ImportError, AttributeError, TypeError) as e:
                logger.info("stream_printing_messages 不可用 (%s)，回退为非流式执行", e)
                result = await agent(msg)
                yield _extract_text(result.content)
        finally:
            if stateful_clients:
                try:
                    await asyncio.wait_for(
                        cleanup_mcp_clients(stateful_clients),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    logger.error("MCP 客户端批量清理超时 (30s)")
                except asyncio.CancelledError:
                    logger.warning("MCP 客户端批量清理被取消")
                except Exception:
                    logger.exception("MCP 客户端清理异常")

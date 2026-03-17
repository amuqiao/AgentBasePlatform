"""Agent Runtime Engine —— 智能体执行引擎。

提供 execute_agent_chat / execute_agent_chat_stream 两个入口函数，
保持与 MVP 版本相同的前 4 个参数签名，ConversationService 可无缝切换。

execute_agent_chat_with_meta 是 execute_agent_chat 的增强版，
额外返回工具调用记录，供直接调用接口使用。

内部通过 AgentFactory 创建对应类型的 Agent 实例，
调用真实 DashScope Qwen 模型完成对话。
"""

import asyncio
import logging
from typing import AsyncGenerator

from src.config import get_settings

logger = logging.getLogger(__name__)


def _create_platform_agent(
    agent_type: str,
    agent_name: str,
    system_prompt: str,
    model_config: dict | None,
    tool_config: dict | None,
    agent_id=None,
    tenant_id=None,
):
    """创建 PlatformAgent 实例（抽取公共逻辑）。"""
    from src.runtime.agent_factory import create_agent

    return create_agent(
        name=agent_name,
        agent_type=agent_type,
        agent_id=agent_id,
        tenant_id=tenant_id,
        system_prompt=system_prompt,
        model_config=model_config,
        tool_config=tool_config,
    )


async def execute_agent_chat(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    model_config: dict | None = None,
    *,
    agent_type: str = "chat",
    agent_name: str = "Assistant",
    agent_id=None,
    tenant_id=None,
    tool_config: dict | None = None,
) -> str:
    """非流式智能体执行（仅返回文本，向后兼容）。"""
    settings = get_settings()

    try:
        agent = _create_platform_agent(
            agent_type, agent_name, system_prompt,
            model_config, tool_config, agent_id, tenant_id,
        )
        return await asyncio.wait_for(
            agent.execute(user_message, history),
            timeout=settings.AGENT_EXECUTION_TIMEOUT,
        )

    except asyncio.TimeoutError:
        logger.error("Agent 执行超时 (%ss)", settings.AGENT_EXECUTION_TIMEOUT)
        if settings.AGENT_FALLBACK_TO_MOCK:
            return await _mock_execute(system_prompt, user_message, history)
        return "抱歉，响应超时，请稍后重试。"

    except Exception as e:
        logger.error("Agent 执行异常: %s", e, exc_info=True)
        if settings.AGENT_FALLBACK_TO_MOCK:
            logger.warning("回退到 Mock 模式")
            return await _mock_execute(system_prompt, user_message, history)
        return f"抱歉，处理您的请求时出现问题：{type(e).__name__}"


async def execute_agent_chat_with_meta(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    model_config: dict | None = None,
    *,
    agent_type: str = "chat",
    agent_name: str = "Assistant",
    agent_id=None,
    tenant_id=None,
    tool_config: dict | None = None,
) -> dict:
    """非流式智能体执行（返回 content + tool_calls 元数据）。

    返回格式:
        {"content": str, "tool_calls": list[dict]}
    """
    settings = get_settings()

    try:
        agent = _create_platform_agent(
            agent_type, agent_name, system_prompt,
            model_config, tool_config, agent_id, tenant_id,
        )
        content = await asyncio.wait_for(
            agent.execute(user_message, history),
            timeout=settings.AGENT_EXECUTION_TIMEOUT,
        )
        return {
            "content": content,
            "tool_calls": agent.last_tool_calls,
        }

    except asyncio.TimeoutError:
        logger.error("Agent 执行超时 (%ss)", settings.AGENT_EXECUTION_TIMEOUT)
        content = "抱歉，响应超时，请稍后重试。"
        if settings.AGENT_FALLBACK_TO_MOCK:
            content = await _mock_execute(system_prompt, user_message, history)
        return {"content": content, "tool_calls": []}

    except Exception as e:
        logger.error("Agent 执行异常: %s", e, exc_info=True)
        if settings.AGENT_FALLBACK_TO_MOCK:
            logger.warning("回退到 Mock 模式")
            content = await _mock_execute(system_prompt, user_message, history)
        else:
            content = f"抱歉，处理您的请求时出现问题：{type(e).__name__}"
        return {"content": content, "tool_calls": []}


async def execute_agent_chat_stream(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    model_config: dict | None = None,
    *,
    agent_type: str = "chat",
    agent_name: str = "Assistant",
    agent_id=None,
    tenant_id=None,
    tool_config: dict | None = None,
) -> AsyncGenerator[str, None]:
    """流式智能体执行。"""
    settings = get_settings()

    try:
        from src.runtime.agent_factory import create_agent

        agent = create_agent(
            name=agent_name,
            agent_type=agent_type,
            agent_id=agent_id,
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            model_config=model_config,
            tool_config=tool_config,
        )
        async for chunk in agent.execute_stream(user_message, history):
            yield chunk

    except Exception as e:
        logger.error("Agent 流式执行异常: %s", e, exc_info=True)
        if settings.AGENT_FALLBACK_TO_MOCK:
            async for chunk in _mock_execute_stream(
                system_prompt, user_message, history
            ):
                yield chunk
        else:
            yield f"抱歉，处理您的请求时出现问题：{type(e).__name__}"


# --------------- Mock 回退（降级兜底） ---------------

async def _mock_execute(
    system_prompt: str, user_message: str, history: list[dict] | None
) -> str:
    await asyncio.sleep(0.1)
    return (
        f"[Mock] 收到消息: \"{user_message}\"\n"
        f"系统提示词: \"{system_prompt[:100]}...\"\n"
        f"历史消息数: {len(history) if history else 0}\n"
        f"当前处于 Mock 降级模式。"
    )


async def _mock_execute_stream(
    system_prompt: str, user_message: str, history: list[dict] | None
) -> AsyncGenerator[str, None]:
    chunks = [
        f"[Mock] 收到消息: \"{user_message}\"。",
        "\n当前处于 Mock 降级模式。",
    ]
    for chunk in chunks:
        yield chunk
        await asyncio.sleep(0.05)

"""
MVP Agent Runtime Engine.

Provides a simple agent execution mechanism. In this MVP version,
if the agent has a system_prompt, it echoes the prompt context;
otherwise it provides a default response. This will be replaced
with full AgentScope integration in Phase 2.
"""

import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


async def execute_agent_chat(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    model_config: dict | None = None,
) -> str:
    """Synchronous (non-streaming) agent execution for MVP."""
    if not system_prompt:
        system_prompt = "你是一个有帮助的AI助手。"

    response = (
        f"[MVP Echo] 收到消息: \"{user_message}\"\n"
        f"系统提示词: \"{system_prompt[:100]}...\"\n"
        f"历史消息数: {len(history) if history else 0}\n"
        f"这是MVP验证阶段的回显响应，后续将集成AgentScope实现真实的LLM对话。"
    )

    await asyncio.sleep(0.1)
    return response


async def execute_agent_chat_stream(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    model_config: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Streaming agent execution for SSE."""
    if not system_prompt:
        system_prompt = "你是一个有帮助的AI助手。"

    chunks = [
        f"[MVP流式响应] ",
        f"收到您的消息: \"{user_message}\"。",
        f"\n\n当前智能体配置了系统提示词: \"{system_prompt[:80]}\"。",
        f"\n\n本次对话历史消息数: {len(history) if history else 0}。",
        f"\n\n此为MVP验证阶段的回显响应，",
        f"后续将集成AgentScope框架，",
        f"实现真正的大语言模型对话能力。",
    ]

    for chunk in chunks:
        yield chunk
        await asyncio.sleep(0.05)

"""PlatformChatAgent —— 纯对话型智能体。

直接使用 dashscope SDK 调用 Qwen 模型，支持原生异步流式输出，
不依赖 AgentScope 框架，轻量高效。
"""

import logging
from typing import AsyncGenerator

import dashscope

from src.runtime.agents.base import PlatformAgent
from src.runtime.model_provider import resolve_model_params

logger = logging.getLogger(__name__)


class PlatformChatAgent(PlatformAgent):
    """纯对话型智能体，直接调用 DashScope Qwen 模型。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._params = resolve_model_params(self.model_config)

    async def execute(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> str:
        messages = self._build_messages(user_message, history)

        response = await dashscope.AioGeneration.call(
            api_key=self._params["api_key"],
            model=self._params["model_name"],
            messages=messages,
            result_format="message",
            max_tokens=self._params["max_tokens"],
            temperature=self._params["temperature"],
        )

        if response.status_code != 200:
            error = f"模型调用失败: [{response.code}] {response.message}"
            logger.error(error)
            raise RuntimeError(error)

        return response.output.choices[0].message.content

    async def execute_stream(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        messages = self._build_messages(user_message, history)

        responses = await dashscope.AioGeneration.call(
            api_key=self._params["api_key"],
            model=self._params["model_name"],
            messages=messages,
            result_format="message",
            max_tokens=self._params["max_tokens"],
            temperature=self._params["temperature"],
            stream=True,
            incremental_output=True,
        )

        async for response in responses:
            if response.status_code != 200:
                error = f"模型流式调用失败: [{response.code}] {response.message}"
                logger.error(error)
                raise RuntimeError(error)

            if response.output and response.output.choices:
                content = response.output.choices[0].message.content
                if content:
                    yield content

"""平台智能体基类 —— AgentScope 与平台业务之间的 Anti-Corruption Layer。"""

import uuid
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class PlatformAgent(ABC):
    """平台智能体基类。

    定义所有平台智能体必须实现的统一执行接口（execute / execute_stream），
    由 engine.py 调用，屏蔽底层框架差异。
    """

    def __init__(
        self,
        name: str,
        agent_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        system_prompt: str = "",
        model_config: dict | None = None,
        tool_config: dict | None = None,
    ):
        self.name = name
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.system_prompt = system_prompt or "你是一个有帮助的AI助手。"
        self.model_config = model_config or {}
        self.tool_config = tool_config or {}
        self._last_tool_calls: list[dict] = []

    @property
    def last_tool_calls(self) -> list[dict]:
        """上一次 execute 执行中实际发生的工具调用记录。

        每条记录包含:
          - name: 工具函数名
          - arguments: 调用参数
          - result: 工具返回结果（截断）
        """
        return self._last_tool_calls

    @abstractmethod
    async def execute(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> str:
        """非流式执行，返回完整响应文本。"""

    @abstractmethod
    async def execute_stream(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式执行，逐块 yield 响应文本片段。"""

    def _build_messages(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """构建 DashScope messages 格式：system + history + user。"""
        messages: list[dict] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

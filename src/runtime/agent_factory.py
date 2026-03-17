"""Agent 工厂 —— 根据 agent_type 和配置创建对应的平台 Agent 实例。"""

import uuid
import logging

from src.runtime.agents.base import PlatformAgent

logger = logging.getLogger(__name__)

# agent_type → Agent 类的注册表（延迟导入避免循环依赖）
_AGENT_REGISTRY: dict[str, type[PlatformAgent]] = {}


def _ensure_registry():
    """首次调用时填充注册表。"""
    if _AGENT_REGISTRY:
        return
    from src.runtime.agents.chat import PlatformChatAgent
    from src.runtime.agents.react import PlatformReActAgent

    _AGENT_REGISTRY.update({
        "chat": PlatformChatAgent,
        "react": PlatformReActAgent,
        "task": PlatformReActAgent,
    })


def register_agent_type(agent_type: str, agent_class: type[PlatformAgent]):
    """注册自定义 Agent 类型（插件扩展点）。"""
    _AGENT_REGISTRY[agent_type] = agent_class
    logger.info("注册 Agent 类型: %s -> %s", agent_type, agent_class.__name__)


def create_agent(
    name: str,
    agent_type: str = "chat",
    agent_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    system_prompt: str = "",
    model_config: dict | None = None,
    tool_config: dict | None = None,
) -> PlatformAgent:
    """根据 agent_type 创建对应的智能体实例。"""
    _ensure_registry()

    agent_class = _AGENT_REGISTRY.get(agent_type)
    if agent_class is None:
        logger.warning("未知 agent_type '%s'，回退到 chat", agent_type)
        agent_class = _AGENT_REGISTRY["chat"]

    extra_kwargs: dict = {}
    if agent_type == "task":
        from src.config import get_settings
        settings = get_settings()
        extra_kwargs["max_iterations"] = settings.AGENT_MAX_REACT_ITERATIONS * 2

    agent = agent_class(
        name=name,
        agent_id=agent_id,
        tenant_id=tenant_id,
        system_prompt=system_prompt,
        model_config=model_config,
        tool_config=tool_config,
        **extra_kwargs,
    )

    logger.info(
        "创建 Agent: name=%s, type=%s, class=%s",
        name, agent_type, agent_class.__name__,
    )
    return agent

"""模型配置适配器 —— 将平台配置转换为 DashScope 调用参数。

ChatAgent 直接使用 dashscope SDK 调用（支持原生流式），
ReActAgent 通过 AgentScope DashScopeChatModel 调用。
"""

import logging

from src.config import get_settings

logger = logging.getLogger(__name__)


_VALID_LLM_KEYS = {
    "model_name", "temperature", "max_tokens",
    "stream", "enable_thinking", "api_key",
}

_INVALID_MODEL_NAMES = {"mock", "test", ""}


def normalize_llm_config(raw: dict | None) -> dict:
    """清洗 llm_config：剔除无效 key，model_name 缺失或无效时从环境变量填充。

    用于 Agent 创建/更新时写入数据库，以及响应序列化时保证返回有效配置。
    """
    settings = get_settings()
    if not raw:
        return {"model_name": settings.DEFAULT_MODEL_NAME}

    cleaned = {k: v for k, v in raw.items() if k in _VALID_LLM_KEYS}

    model_name = cleaned.get("model_name", "")
    if not model_name or model_name.lower() in _INVALID_MODEL_NAMES:
        cleaned["model_name"] = settings.DEFAULT_MODEL_NAME

    return cleaned


def resolve_model_params(model_config: dict | None = None) -> dict:
    """将 Agent 的 model_config（数据库 JSONB）与环境变量默认值合并，
    返回统一的模型调用参数字典。

    优先级：model_config（数据库） > 环境变量默认值
    """
    settings = get_settings()
    config = model_config or {}

    api_key = config.get("api_key") or settings.DASHSCOPE_API_KEY
    if not api_key:
        raise ValueError(
            "未配置 DASHSCOPE_API_KEY，请在 .env 或智能体 llm_config 中设置"
        )

    params = {
        "api_key": api_key,
        "model_name": config.get("model_name", settings.DEFAULT_MODEL_NAME),
        "stream": config.get("stream", settings.DEFAULT_MODEL_STREAM),
        "enable_thinking": config.get(
            "enable_thinking", settings.DEFAULT_MODEL_ENABLE_THINKING
        ),
        "max_tokens": config.get("max_tokens", settings.DEFAULT_MODEL_MAX_TOKENS),
        "temperature": config.get("temperature", settings.DEFAULT_MODEL_TEMPERATURE),
    }

    logger.info("模型参数: model=%s, stream=%s", params["model_name"], params["stream"])
    return params


def create_agentscope_model(model_config: dict | None = None):
    """创建 AgentScope DashScopeChatModel 实例（供 ReActAgent 使用）。"""
    from agentscope.model import DashScopeChatModel

    params = resolve_model_params(model_config)

    model = DashScopeChatModel(
        api_key=params["api_key"],
        model_name=params["model_name"],
        stream=params["stream"],
        enable_thinking=params["enable_thinking"],
        generate_kwargs={
            "max_tokens": params["max_tokens"],
            "temperature": params["temperature"],
        },
    )
    return model

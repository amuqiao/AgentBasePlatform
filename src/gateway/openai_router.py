"""OpenAI 兼容接口层。

提供两个标准路径：
  POST /v1/chat/completions  — 通过 stream 字段控制流式/非流式，model 字段携带 agent_id
  GET  /v1/models            — 返回当前租户的智能体列表（OpenAI Model Object 格式）

设计约束：
  - 本层只做协议适配，不含业务逻辑，所有调用委托给 runtime.engine
  - model 字段必须是有效的 agent_id（UUID），否则返回 404
  - 鉴权复用现有 JWT Bearer 中间件
"""

import json
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.models import Agent
from src.agent.schemas import OpenAIChatCompletion, OpenAIChoice, OpenAIMessage
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.common.exceptions import NotFoundException
from src.runtime.model_provider import normalize_llm_config

router = APIRouter(prefix="/v1", tags=["OpenAI 兼容接口"])


# --------------- 请求 Schema ---------------


class OAIMessageInput(BaseModel):
    role: str = Field(..., description="角色: system / user / assistant")
    content: str = Field(..., description="消息内容")


class OAIChatCompletionRequest(BaseModel):
    model: str = Field(..., description="智能体 ID（agent_id，UUID 格式）")
    messages: list[OAIMessageInput] = Field(..., min_length=1, description="消息列表")
    stream: bool = Field(default=False, description="是否开启 SSE 流式输出")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)


# --------------- 内部工具函数 ---------------


async def _get_agent(agent_id_str: str, tenant_id: uuid.UUID, db: AsyncSession) -> Agent:
    """通过 model 字段（agent_id）查找智能体，不存在则抛 404。"""
    try:
        agent_id = uuid.UUID(agent_id_str)
    except ValueError:
        raise NotFoundException(message=f"model 字段不是有效的 agent_id: {agent_id_str}")

    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundException(message=f"智能体不存在: {agent_id_str}")
    return agent


def _split_messages(messages: list[OAIMessageInput]) -> tuple[list[dict] | None, str]:
    """将消息列表拆分为 history（前 N-1 条）和最新 user_message（最后一条）。"""
    history = [{"role": m.role, "content": m.content} for m in messages[:-1]]
    return history or None, messages[-1].content


def _make_chunk(completion_id: str, created_at: int, model: str, content: str | None, finish_reason: str | None) -> str:
    """构造一个 SSE data 行（OpenAI chat.completion.chunk 格式）。"""
    delta = {"content": content} if content is not None else {}
    data = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_at,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# --------------- POST /v1/chat/completions ---------------


@router.post(
    "/chat/completions",
    summary="对话补全（OpenAI 兼容，stream 参数控制流式/非流式）",
)
async def chat_completions(
    req: OAIChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标准 OpenAI `/v1/chat/completions` 兼容接口。

    - `model`：填写智能体 ID（UUID），通过 `GET /v1/models` 获取可用列表
    - `stream: false`（默认）：返回完整 `chat.completion` JSON
    - `stream: true`：返回 `text/event-stream`，每个 chunk 为 `chat.completion.chunk` 格式，以 `data: [DONE]` 结束
    """
    from src.runtime.engine import execute_agent_chat_with_meta, execute_agent_chat_stream

    agent = await _get_agent(req.model, current_user.tenant_id, db)
    history, user_message = _split_messages(req.messages)
    model_name = normalize_llm_config(agent.model_config_json)["model_name"]

    # ---- 非流式 ----
    if not req.stream:
        result = await execute_agent_chat_with_meta(
            system_prompt=agent.system_prompt,
            user_message=user_message,
            history=history,
            model_config=agent.model_config_json,
            agent_type=agent.agent_type,
            agent_name=agent.name,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool_config=agent.tool_config,
        )
        return OpenAIChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=model_name,
            choices=[OpenAIChoice(
                message=OpenAIMessage(role="assistant", content=result["content"]),
            )],
            agent_id=agent.id,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            tool_calls=result.get("tool_calls", []),
        )

    # ---- 流式 SSE ----
    async def event_generator():
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_at = int(time.time())
        async for chunk in execute_agent_chat_stream(
            system_prompt=agent.system_prompt,
            user_message=user_message,
            history=history,
            model_config=agent.model_config_json,
            agent_type=agent.agent_type,
            agent_name=agent.name,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            tool_config=agent.tool_config,
        ):
            yield _make_chunk(completion_id, created_at, model_name, chunk, None)
        yield _make_chunk(completion_id, created_at, model_name, None, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --------------- GET /v1/models ---------------


@router.get(
    "/models",
    summary="列出可用模型（返回当前租户的智能体列表）",
)
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标准 OpenAI `/v1/models` 兼容接口。

    将当前租户下的智能体列表包装为 OpenAI Model Object 格式：
    - `id`：agent_id（用于 chat/completions 的 model 字段）
    - `owned_by`：tenant_id
    """
    result = await db.execute(
        select(Agent)
        .where(Agent.tenant_id == current_user.tenant_id)
        .order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()

    model_list = [
        {
            "id": str(a.id),
            "object": "model",
            "created": int(a.created_at.timestamp()),
            "owned_by": str(a.tenant_id),
            "name": a.name,
            "agent_type": a.agent_type,
        }
        for a in agents
    ]
    return {"object": "list", "data": model_list}

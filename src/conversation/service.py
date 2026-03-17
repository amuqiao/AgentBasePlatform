import uuid
from typing import AsyncGenerator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.models import Agent
from src.common.exceptions import ForbiddenException, NotFoundException
from src.runtime.engine import execute_agent_chat, execute_agent_chat_stream

from .models import Conversation, Message


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, agent_id: uuid.UUID, title: str = "新对话"
    ) -> Conversation:
        agent_result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise NotFoundException(message="智能体不存在")

        conv = Conversation(
            user_id=user_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            title=title,
        )
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def get_conversation(
        self, conv_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_id == user_id
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise NotFoundException(message="会话不存在")
        return conv

    async def list_conversations(
        self, user_id: uuid.UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Conversation], int]:
        count_q = (
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status == "active")
        )
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.status == "active")
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def send_message(
        self, conv_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> Message:
        conv = await self.get_conversation(conv_id, user_id)

        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=content,
            status="completed",
        )
        self.db.add(user_msg)
        await self.db.flush()

        agent_result = await self.db.execute(
            select(Agent).where(Agent.id == conv.agent_id)
        )
        agent = agent_result.scalar_one_or_none()

        history = await self._get_history(conv.id, limit=20)

        response_text = await execute_agent_chat(
            system_prompt=agent.system_prompt if agent else "",
            user_message=content,
            history=history,
            model_config=agent.model_config_json if agent else None,
        )

        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=response_text,
            status="completed",
        )
        self.db.add(assistant_msg)
        await self.db.flush()
        await self.db.refresh(assistant_msg)
        return assistant_msg

    async def send_message_stream(
        self, conv_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> AsyncGenerator[str, None]:
        """Stream agent response via SSE. Saves both messages to DB."""
        conv = await self.get_conversation(conv_id, user_id)

        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=content,
            status="completed",
        )
        self.db.add(user_msg)
        await self.db.flush()

        agent_result = await self.db.execute(
            select(Agent).where(Agent.id == conv.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        history = await self._get_history(conv.id, limit=20)

        full_response = ""
        async for chunk in execute_agent_chat_stream(
            system_prompt=agent.system_prompt if agent else "",
            user_message=content,
            history=history,
            model_config=agent.model_config_json if agent else None,
        ):
            full_response += chunk
            yield chunk

        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=full_response,
            status="completed",
        )
        self.db.add(assistant_msg)
        await self.db.flush()

    async def get_messages(
        self, conv_id: uuid.UUID, user_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[Message], int]:
        await self.get_conversation(conv_id, user_id)

        count_q = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conv_id)
        )
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def delete_conversation(
        self, conv_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        conv = await self.get_conversation(conv_id, user_id)
        conv.status = "archived"
        await self.db.flush()

    async def _get_history(self, conv_id: uuid.UUID, limit: int = 20) -> list[dict]:
        q = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        messages = list(result.scalars().all())
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

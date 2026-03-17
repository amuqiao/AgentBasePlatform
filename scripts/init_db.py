"""
Database initialization script.
Creates all tables and seeds initial data.

Usage:
    python -m scripts.init_db
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.database import Base, engine
from src.auth.models import Tenant, User  # noqa: F401
from src.agent.models import Agent, AgentVersion  # noqa: F401
from src.conversation.models import Conversation, Message  # noqa: F401


async def init_db():
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())

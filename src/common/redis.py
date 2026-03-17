import redis.asyncio as aioredis

from src.config import get_settings

settings = get_settings()

redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,
)


async def get_redis() -> aioredis.Redis:
    return redis_client

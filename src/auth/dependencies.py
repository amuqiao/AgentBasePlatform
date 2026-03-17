import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_db
from src.common.exceptions import UnauthorizedException
from src.common.security import decode_token

from .models import User
from .service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException(message="缺少或无效的认证头")

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedException(message="无效或过期的 Token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException(message="无效的 Token")

    service = AuthService(db)
    user = await service.get_user_by_id(uuid.UUID(user_id))
    if user.status != "active":
        raise UnauthorizedException(message="账号已被禁用")
    return user

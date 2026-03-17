import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.exceptions import ConflictException, NotFoundException, UnauthorizedException
from src.common.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.config import get_settings

from .models import Tenant, User
from .schemas import TokenResponse

settings = get_settings()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self, email: str, password: str, display_name: str, tenant_name: str = ""
    ) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictException(message="该邮箱已被注册")

        tenant = Tenant(name=tenant_name or f"{display_name}的团队")
        self.db.add(tenant)
        await self.db.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role="tenant_admin",
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException(message="邮箱或密码错误")
        if user.status != "active":
            raise UnauthorizedException(message="账号已被禁用")

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id),
            "role": user.role,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedException(message="无效的 Refresh Token")

        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or user.status != "active":
            raise UnauthorizedException(message="用户不存在或已被禁用")

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id),
            "role": user.role,
        }
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException(message="用户不存在")
        return user

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_db
from src.common.schemas import BaseResponse

from .dependencies import get_current_user
from .models import User
from .schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserInfo
from .service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=BaseResponse[UserInfo])
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.register(
        email=req.email,
        password=req.password,
        display_name=req.display_name,
        tenant_name=req.tenant_name,
    )
    return BaseResponse(data=UserInfo.model_validate(user))


@router.post("/login", response_model=BaseResponse[TokenResponse])
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.login(email=req.email, password=req.password)
    return BaseResponse(data=token)


@router.post("/refresh", response_model=BaseResponse[TokenResponse])
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.refresh_token(req.refresh_token)
    return BaseResponse(data=token)


@router.get("/me", response_model=BaseResponse[UserInfo])
async def get_me(current_user: User = Depends(get_current_user)):
    return BaseResponse(data=UserInfo.model_validate(current_user))

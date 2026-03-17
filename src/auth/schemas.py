import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=256, description="邮箱", examples=["test@example.com"])
    password: str = Field(..., min_length=6, max_length=128, description="密码", examples=["test123456"])
    display_name: str = Field(..., min_length=1, max_length=128, description="显示名称", examples=["测试用户"])
    tenant_name: str = Field(default="", max_length=128, description="租户名称（留空自动创建）", examples=["测试团队"])


class LoginRequest(BaseModel):
    email: str = Field(..., description="邮箱", examples=["test@example.com"])
    password: str = Field(..., description="密码", examples=["test123456"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh Token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    status: str
    tenant_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantInfo(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}

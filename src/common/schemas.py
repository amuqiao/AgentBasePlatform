from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None
    request_id: Optional[str] = None


class PagedData(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class PagedResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[PagedData[T]] = None
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None

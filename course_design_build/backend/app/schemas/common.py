"""分页公共结构，所有列表接口统一返回 count/page/page_size/results。"""
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


class PageResult(BaseModel, Generic[T]):
    count: int
    page: int
    page_size: int
    results: list[T]

"""カテゴリ・担当者APIで受け取る項目・返す項目を定義する。"""

from typing import Annotated, Any

from pydantic import Field, field_validator

from .base import InputModel, OrmResponse

Name = Annotated[str, Field(min_length=1, max_length=100)]


class NameCreate(InputModel):
    """カテゴリ・担当者に共通の名前入力。前後空白を除いてから長さを検証する。"""

    name: Name

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        """空白だけの名前を空文字にし、min_lengthで拒否できるようにする。"""
        return value.strip() if isinstance(value, str) else value


class CategoryCreate(NameCreate):
    """カテゴリ作成の入力。重複判定はDBの一意制約に従う。"""


class AssigneeCreate(NameCreate):
    """担当者作成の入力。重複判定はDBの一意制約に従う。"""


class CategoryResponse(OrmResponse):
    """カテゴリのIDと名前だけを外部へ返す。"""

    id: int
    name: str


class AssigneeResponse(OrmResponse):
    """担当者のIDと名前だけを外部へ返す。"""

    id: int
    name: str

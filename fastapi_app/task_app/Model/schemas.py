"""APIで受け取る項目・返す項目を定義する。入力の型・文字数・省略・nullを検証する。

既存APIとの互換性のためPydanticの型変換と余分な入力項目の無視を維持する。
型・文字数はここで、IDの実在はControllerで確認する。
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

Name = Annotated[str, Field(min_length=1, max_length=100)]
Title = Annotated[str, Field(min_length=1, max_length=255)]
PositiveId = Annotated[int, Field(gt=0)]
Description = Annotated[str, Field(max_length=2000)]


class InputModel(BaseModel):
    """既存クライアントが送る未定義項目は保存対象に含めず無視する。"""

    model_config = ConfigDict(extra="ignore")


class OrmResponse(BaseModel):
    """ORM属性から応答を組み立てる。書き込みではcommit前に検証を完了する。"""

    model_config = ConfigDict(from_attributes=True)


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


class TaskBase(InputModel):
    """作成・更新で共有するタイトルの契約。空白だけの入力は拒否する。"""

    title: Title

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: Any) -> Any:
        """文字列だけ整形し、それ以外の値の可否はPydanticの検証に任せる。"""
        return value.strip() if isinstance(value, str) else value


class TaskCreate(TaskBase):
    """POSTでは省略した説明・関連を未設定にする。作成時の完了状態は未完了固定。"""

    description: Description | None = None
    category_id: PositiveId | None = None
    assignee_id: PositiveId | None = None


class TaskUpdate(TaskBase):
    """PUTは全5項目必須。解除はnullを送り、省略による意図しない解除を防ぐ。"""

    is_done: bool
    description: Description | None
    category_id: PositiveId | None
    assignee_id: PositiveId | None


class TaskResponse(OrmResponse):
    """関連名と日時を含む応答。作成後はORMの遅延読み込みを必要としない。"""

    id: int
    title: str
    description: str | None
    is_done: bool
    category: CategoryResponse | None
    assignee: AssigneeResponse | None
    created_at: datetime
    updated_at: datetime

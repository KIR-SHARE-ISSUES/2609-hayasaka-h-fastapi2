"""カテゴリ・担当者のテーブル定義。"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    # 型チェック用にだけ読み込み、tasks.pyとの循環importを避ける。
    from .tasks import Task


class Category(Base):
    """カテゴリ名を一意に保存する。削除時は所属タスクの関連だけを解除する。"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )


class Assignee(Base):
    """担当者名を一意に保存する。削除時も担当タスク自体は残す。"""

    __tablename__ = "assignees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="assignee",
        passive_deletes=True,
    )

"""タスクのテーブル定義。MySQLに保存する列・制約・関連を定義する。HTTPの検証や保存確定は担当しない。

アプリは既存テーブルを使うため、この定義とDBの列・制約を対応させる。
モデルを書き換えるだけでは既存テーブルは変わらず、DBの変更手順も必要になる。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .names import Assignee, Category


class Task(Base):
    """内容・完了状態・任意の関連情報を保持する。関連情報の実在は外部キーでも保証する。"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_done: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    # onupdateはSQLAlchemy経由のUPDATEに適用
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ID列とは別に、応答用の関連情報をPythonオブジェクトとして取得するための属性。
    category: Mapped[Category | None] = relationship(back_populates="tasks")
    assignee: Mapped[Assignee | None] = relationship(back_populates="tasks")

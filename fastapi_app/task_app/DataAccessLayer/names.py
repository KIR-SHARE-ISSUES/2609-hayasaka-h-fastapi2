"""カテゴリ・担当者のDB操作をまとめる。共通処理を継承し、保存先の表を切り替える。"""

import re
import sqlite3
from typing import Generic, TypeVar

from pymysql.err import IntegrityError as MySQLIntegrityError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..Model.errors import DuplicateNameError
from ..Model.models import Assignee, Category

NamedModel = TypeVar("NamedModel", Category, Assignee)


class NameRepository(Generic[NamedModel]):
    """
    名前を持つ2種類の表で、検索順序と重複判定をそろえる。
    保存確定・取り消し・終了はDBの共通関数に任せる。
    """

    def __init__(self, db: Session, model: type[NamedModel], entity: str) -> None:
        self.db = db
        self.model = model
        self.entity = entity

    def list_all(self) -> list[NamedModel]:
        """カテゴリ・担当者の選択肢をID順に返す。DB失敗は呼び出し元へ伝える。"""
        return list(self.db.scalars(select(self.model).order_by(self.model.id)).all())

    def get(self, record_id: int) -> NamedModel | None:
        """関連先確認に使う1件を返す。未存在の扱いは呼び出し側で決める。"""
        return self.db.get(self.model, record_id)

    def create(self, name: str) -> NamedModel:
        """採番・制約検証・再取得をcommit前に行い、名前重複だけを分類する。"""
        record = self.model(name=name)
        self.db.add(record)
        try:
            self.db.flush()
        except IntegrityError as exc:
            if self._is_duplicate_name(exc):
                raise DuplicateNameError(self.entity) from exc
            raise
        self.db.refresh(record)
        return record

    def _is_duplicate_name(self, error: IntegrityError) -> bool:
        """MySQLの名前キー、またはSQLiteの名前列違反だけを識別する。

        PRIMARY KEY・外部キー・NOT NULLなどを409に誤分類しない。
        メッセージ内の入力値はログやHTTP応答に出さない。
        """
        original = error.orig
        table = self.model.__tablename__
        if isinstance(original, sqlite3.IntegrityError):
            return str(original) == f"UNIQUE constraint failed: {table}.name"
        if isinstance(original, MySQLIntegrityError) and original.args[0] == 1062:
            key = re.search(r"for key '([^']+)'$", str(original.args[1]))
            return key is not None and key.group(1) in {"name", f"{table}.name"}
        return False


class CategoryRepository(NameRepository[Category]):
    """カテゴリ表専用のRepository。リクエストのSessionで生成する。"""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Category, "Category")


class AssigneeRepository(NameRepository[Assignee]):
    """担当者表専用のRepository。リクエストのSessionで生成する。"""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Assignee, "Assignee")

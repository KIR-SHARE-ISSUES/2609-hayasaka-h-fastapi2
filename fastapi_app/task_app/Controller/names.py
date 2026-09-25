"""カテゴリ・担当者の一覧取得と登録を担当する。"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..DataAccessLayer.database import Database, execute_database_operation
from ..DataAccessLayer.names import CategoryRepository, AssigneeRepository
from ..Schema.names import (
    CategoryCreate,
    CategoryResponse,
    AssigneeCreate,
    AssigneeResponse,
)

# 型の対応を指定して、子クラスで入力型と応答型を定義する。
CreateType = TypeVar("CreateType", bound=BaseModel)
ResponseType = TypeVar("ResponseType", bound=BaseModel)


# ABCとabstractmethodで、子クラスにcreateの実装を求める。
# Genericで、入力型と応答型の対応を表す。
class NameController(ABC, Generic[CreateType, ResponseType]):
    """一覧取得・登録の共通処理。SQLと保存確定はDALへ任せる。"""

    # 具体的な設定は子クラスで指定する。
    resource: str
    create_route_name: str
    repository_type: type[CategoryRepository] | type[AssigneeRepository]
    response_type: type[ResponseType]

    def __init__(self, database: Database) -> None:
        self.database = database
        self.router = APIRouter(
            prefix=f"/{self.resource}",
            tags=[self.resource],
        )

        self.router.add_api_route(
            "",
            self.list_all,
            name=f"list_{self.resource}",
            methods=["GET"],
            response_model=list[self.response_type],
        )
        self.router.add_api_route(
            "",
            self.create,
            name=self.create_route_name,
            methods=["POST"],
            response_model=self.response_type,
            status_code=status.HTTP_201_CREATED,
        )

    def list_all(self) -> list[ResponseType]:
        """Sessionが開いている間に、一覧を応答モデルへ変換する。"""

        def operation(db: Session) -> list[ResponseType]:
            records = self.repository_type(db).list_all()
            return [self.response_type.model_validate(record) for record in records]

        return execute_database_operation(self.database, operation)

    def _create(self, name: str) -> ResponseType:
        """登録と応答モデルの検証を行い、共通関数で保存を確定する。"""

        def operation(db: Session) -> ResponseType:
            record = self.repository_type(db).create(name)
            return self.response_type.model_validate(record)

        return execute_database_operation(
            self.database,
            operation,
            write=True,
        )

    @abstractmethod
    def create(self, payload: CreateType) -> ResponseType:
        """FastAPIに渡す入口。具体的な入力型を子クラスで定義する。"""
        raise NotImplementedError


class CategoryController(NameController[CategoryCreate, CategoryResponse]):
    """カテゴリ用の設定と入力型を指定する。"""

    resource = "categories"
    create_route_name = "create_category"
    repository_type = CategoryRepository
    response_type = CategoryResponse

    def create(self, payload: CategoryCreate) -> CategoryResponse:
        return self._create(payload.name)


class AssigneeController(NameController[AssigneeCreate, AssigneeResponse]):
    """担当者用の設定と入力型を指定する。"""

    resource = "assignees"
    create_route_name = "create_assignee"
    repository_type = AssigneeRepository
    response_type = AssigneeResponse

    def create(self, payload: AssigneeCreate) -> AssigneeResponse:
        return self._create(payload.name)

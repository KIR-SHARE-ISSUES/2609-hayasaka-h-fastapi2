"""担当者の一覧・登録を担当する。入力 → DALで操作 → 応答作成 → 保存確定。"""

from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from ..DataAccessLayer.database import Database, execute_database_operation
from ..DataAccessLayer.names import AssigneeRepository
from ..Model.schemas import AssigneeCreate, AssigneeResponse


class AssigneeController:
    """SQLはDALへ任せ、処理の順序と応答形式をここでそろえる。"""

    def __init__(self, database: Database) -> None:
        # 起動時に渡されたDatabaseを共有し、Sessionは各処理の共通関数で作る。
        self.database = database
        self.router = APIRouter(prefix="/assignees", tags=["assignees"])
        self.router.add_api_route(
            "",
            self.list_all,
            name="list_assignees",
            methods=["GET"],
            response_model=list[AssigneeResponse],
        )
        self.router.add_api_route(
            "",
            self.create,
            name="create_assignee",
            methods=["POST"],
            response_model=AssigneeResponse,
            status_code=status.HTTP_201_CREATED,
        )

    def list_all(self) -> list[AssigneeResponse]:
        """GET /assignees：Sessionが開いている間に、ID順の一覧を応答へ変換する。"""

        def operation(db: Session) -> list[AssigneeResponse]:
            records = AssigneeRepository(db).list_all()
            return [AssigneeResponse.model_validate(record) for record in records]

        return execute_database_operation(self.database, operation)

    def create(self, payload: AssigneeCreate) -> AssigneeResponse:
        """POST /assignees：登録と応答の検証後、共通関数が保存してSessionを閉じる。"""

        def operation(db: Session) -> AssigneeResponse:
            # payload.name - assigneerepository -record
            record = AssigneeRepository(db).create(payload.name)
            # DB - record - response で JSON へ変換。
            return AssigneeResponse.model_validate(record)

        # 名前重複は409、その他のDB障害は500へ、共通ハンドラーが変換する。
        return execute_database_operation(self.database, operation, write=True)

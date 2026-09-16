"""カテゴリの一覧・登録を担当する。入力 → DALで操作 → 応答作成 → 保存確定。"""

from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from ..DataAccessLayer.database import Database, execute_database_operation
from ..DataAccessLayer.names import CategoryRepository
from ..Model.schemas import CategoryCreate, CategoryResponse


class CategoryController:
    """SQLはDALへ任せ、処理の順序と応答形式をここでそろえる。"""

    def __init__(self, database: Database) -> None:
        # 起動時に渡されたDatabaseを共有し、Sessionは各処理の共通関数で作る。
        self.database = database
        self.router = APIRouter(prefix="/categories", tags=["categories"])
        self.router.add_api_route(
            "",
            self.list_all,
            name="list_categories",
            methods=["GET"],
            response_model=list[CategoryResponse],
        )
        self.router.add_api_route(
            "",
            self.create,
            name="create_category",
            methods=["POST"],
            response_model=CategoryResponse,
            status_code=status.HTTP_201_CREATED,
        )

    def list_all(self) -> list[CategoryResponse]:
        """GET /categories：Sessionが開いている間に、ID順の一覧を応答へ変換する。"""

        def operation(db: Session) -> list[CategoryResponse]:
            records = CategoryRepository(db).list_all()
            return [CategoryResponse.model_validate(record) for record in records]

        return execute_database_operation(self.database, operation)

    def create(self, payload: CategoryCreate) -> CategoryResponse:
        """POST /categories：登録と応答の検証後、共通関数が保存してSessionを閉じる。"""

        def operation(db: Session) -> CategoryResponse:
            record = CategoryRepository(db).create(payload.name)
            return CategoryResponse.model_validate(record)

        # 名前重複は409、その他のDB障害は500へ、共通ハンドラーが変換する。
        return execute_database_operation(self.database, operation, write=True)

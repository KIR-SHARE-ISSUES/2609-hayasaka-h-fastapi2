"""タスクAPIの受付から、存在確認・DB操作・応答作成までの流れをまとめる。

入力検証 → Controllerで存在確認 → DALでDB操作 → HTTP応答。
Sessionの準備・保存確定・取り消し・終了は、database.pyの共通関数に任せる。
同期DBを使うためルートはdefとし、FastAPIのスレッドプールで実行する。
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status
from sqlalchemy.orm import Session

from ..DataAccessLayer.database import Database, execute_database_operation
from ..DataAccessLayer.names import AssigneeRepository, CategoryRepository
from ..DataAccessLayer.tasks import TaskRepository
from ..Model.errors import NotFoundError
from ..Model.models import Task
from ..Model.schemas import TaskCreate, TaskResponse, TaskUpdate

# URL内のIDは正の整数に限定する。DBに存在するかは各処理で確認する。
TaskId = Annotated[int, Path(gt=0)]


class TaskController:
    """タスクの処理手順を管理する。SQLはDAL、例外のHTTP変換はApiErrorHandlersへ任せる。

    アプリで共有するDatabaseを保持し、Sessionは処理ごとに共通関数で作る。
    """

    def __init__(self, database: Database) -> None:
        self.database = database
        # prefixは共通URL、tagsはAPIドキュメント上の分類。
        self.router = APIRouter(prefix="/tasks", tags=["tasks"])

        # URLと処理を登録する。リクエストが来たときにFastAPIがメソッドを呼ぶ。
        self.router.add_api_route(
            "",
            self.list_all,
            name="list_tasks",
            methods=["GET"],
            response_model=list[TaskResponse],
        )
        self.router.add_api_route(
            "",
            self.create,
            name="create_task",
            methods=["POST"],
            response_model=TaskResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/{task_id}",
            self.get,
            name="get_task",
            methods=["GET"],
            response_model=TaskResponse,
        )
        self.router.add_api_route(
            "/{task_id}",
            self.update,
            name="update_task",
            methods=["PUT"],
            response_model=TaskResponse,
        )
        self.router.add_api_route(
            "/{task_id}",
            self.delete,
            name="delete_task",
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )

    def list_all(
        self,
        is_done: bool | None = None,
        category_id: Annotated[int | None, Query(gt=0)] = None,
    ) -> list[TaskResponse]:
        """GET /tasks：検索結果を応答へ変換してから、共通関数がSessionを閉じる。"""

        def operation(db: Session) -> list[TaskResponse]:
            # Noneは絞り込みなし、Falseは未完了。関連情報もSessionの終了前に読む。
            tasks = TaskRepository(db).list_all(
                is_done=is_done, category_id=category_id
            )
            return [TaskResponse.model_validate(task) for task in tasks]

        return execute_database_operation(self.database, operation)

    def get(self, task_id: TaskId) -> TaskResponse:
        """GET /tasks/{task_id}：対象を確認し、Sessionが開いている間に応答を作る。"""

        def operation(db: Session) -> TaskResponse:
            repository = TaskRepository(db)
            return TaskResponse.model_validate(self._require_task(repository, task_id))

        return execute_database_operation(self.database, operation)

    def create(self, payload: TaskCreate) -> TaskResponse:
        """POST /tasks：関連確認 → 作成 → 応答の準備 → 保存確定の順で進める。"""

        def operation(db: Session) -> TaskResponse:
            repository = TaskRepository(db)
            self._require_references(db, payload.category_id, payload.assignee_id)
            # 入力を辞書にし、**でDALの名前付き引数へ展開する。
            task = repository.create(**payload.model_dump())
            # ID・日時・関連を取得し、応答の検証もcommit前に済ませる。
            return TaskResponse.model_validate(repository.refresh(task))

        return execute_database_operation(self.database, operation, write=True)

    def update(
        self,
        task_id: TaskId,
        payload: TaskUpdate,
    ) -> TaskResponse:
        """PUT /tasks/{task_id}：対象・関連を確認し、全5項目を更新して保存する。"""

        def operation(db: Session) -> TaskResponse:
            repository = TaskRepository(db)
            task = self._require_task(repository, task_id)
            self._require_references(db, payload.category_id, payload.assignee_id)
            # 必須項目はTaskUpdateで検証済み。nullは関連・説明を未設定に戻す指定。
            repository.update(task, **payload.model_dump())
            return TaskResponse.model_validate(repository.refresh(task))

        return execute_database_operation(self.database, operation, write=True)

    def delete(self, task_id: TaskId) -> Response:
        """DELETE /tasks/{task_id}：削除を確定してSessionを閉じ、本文なしの204を返す。"""

        def operation(db: Session) -> None:
            repository = TaskRepository(db)
            repository.delete(self._require_task(repository, task_id))

        # 削除が失敗した場合は例外が伝わり、成功応答には進まない。
        execute_database_operation(self.database, operation, write=True)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def _require_task(self, repository: TaskRepository, task_id: int) -> Task:
        """取得・更新・削除で共通の存在確認。未存在は共通ハンドラーが404に変換する。"""
        task = repository.get(task_id)
        if task is None:
            raise NotFoundError("Task")
        return task

    def _require_references(
        self,
        db: Session,
        category_id: int | None,
        assignee_id: int | None,
    ) -> None:
        """指定された関連先だけを確認する。正のIDでも、実在しなければ保存しない。"""
        if category_id is not None and CategoryRepository(db).get(category_id) is None:
            raise NotFoundError("Category")
        if assignee_id is not None and AssigneeRepository(db).get(assignee_id) is None:
            raise NotFoundError("Assignee")

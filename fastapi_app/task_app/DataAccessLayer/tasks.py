"""タスクのSQL・ORM操作をまとめる。存在確認と処理順序はControllerが担当する。

Controllerから共通関数を呼び、その中でRepositoryの検索・変更を実行する。
ORMは、DBの行をPythonのオブジェクトとして扱う仕組み。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..Model.errors import NotFoundError
from ..Model.models import Task


class TaskRepository:
    """受け取ったSessionでDBを操作する。保存確定・取り消し・終了はDBの共通関数へ任せる。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(
        self,
        *,
        is_done: bool | None = None,
        category_id: int | None = None,
    ) -> list[Task]:
        """条件と並び順を組み立てて一覧を取得する。該当なしなら空リストを返す。"""
        # 関連名もまとめて取得し、タスクごとに問い合わせる回数を抑える。
        statement = select(Task).options(
            selectinload(Task.category),
            selectinload(Task.assignee),
        )
        # Falseも「未完了」という有効な条件なので、Noneだけを未指定として扱う。
        if is_done is not None:
            statement = statement.where(Task.is_done == is_done)
        if category_id is not None:
            statement = statement.where(Task.category_id == category_id)

        # 作成日時の新しい順。同じ日時ならIDで順序をそろえる。
        statement = statement.order_by(Task.created_at.desc(), Task.id.desc())
        return list(self.db.scalars(statement).all())

    def get(self, task_id: int) -> Task | None:
        """タスクと関連を1件取得する。未存在を404にする判断はControllerへ任せる。"""
        statement = (
            select(Task)
            .where(Task.id == task_id)
            .options(selectinload(Task.category), selectinload(Task.assignee))
            # 取得済みのオブジェクトも読み直す。変更後は先にflushしてから呼ぶ。
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(statement)

    def create(
        self,
        *,
        title: str,
        description: str | None,
        category_id: int | None,
        assignee_id: int | None,
    ) -> Task:
        """未完了のタスクをSessionへ追加する。INSERTは次のflushで実行する。"""
        task = Task(
            title=title,
            description=description,
            is_done=False,
            category_id=category_id,
            assignee_id=assignee_id,
        )
        self.db.add(task)
        return task

    def update(
        self,
        task: Task,
        *,
        title: str,
        description: str | None,
        is_done: bool,
        category_id: int | None,
        assignee_id: int | None,
    ) -> Task:
        """更新対象の5項目を明示し、IDや作成日時を上書きしない。"""
        # Sessionが変更を追跡するため、再度addする必要はない。
        task.title = title
        task.description = description
        task.is_done = is_done
        task.category_id = category_id
        task.assignee_id = assignee_id
        return task

    def refresh(self, task: Task) -> Task:
        """変更をSQLで反映し、応答に必要なID・日時・関連を取得する独自 method"""
        # flushはSession内の変更全体をDBへ送る。保存確定は後のcommitで行う。
        self.db.flush()
        refreshed = self.get(task.id)
        if refreshed is None:
            raise NotFoundError("Task")
        return refreshed

    def delete(self, task: Task) -> None:
        """削除対象へ登録する。DELETEの実行・確定は共通関数のcommitで行う。"""
        self.db.delete(task)

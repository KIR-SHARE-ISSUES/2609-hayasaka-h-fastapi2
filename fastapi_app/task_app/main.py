"""アプリの入口を作る。既存のDB・テーブルを使用し、終了時に接続資源を解放する。

起動：設定読込 → Database生成 → Controller・例外処理・CORS登録。
受付：入力検証 → Controller → DAL → HTTP応答。
書き込みでは応答の準備後、DBの共通関数が保存を確定してSessionを閉じる。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import Settings
from .Controller.error_handlers import ApiErrorHandlers
from .Controller.names import AssigneeController, CategoryController
from .Controller.tasks import TaskController
from .DataAccessLayer.database import Database


class TaskApplication:
    """DB管理・各機能のURL・共通エラー処理を組み立てる。"""

    def __init__(
        self,
        settings: Settings,
        database: Database | None = None,
    ) -> None:
        # DBが渡されれば使い、省略時は接続設定から生成する。
        self.database = (
            database if database is not None else Database.from_settings(settings)
        )
        self.api = FastAPI(title="Task Manager API", lifespan=self.lifespan)
        ApiErrorHandlers().register(self.api)
        # 同じDatabaseを各Controllerへ直接渡す。Sessionの管理はDBの共通関数が行う。
        for controller in (
            TaskController(self.database),
            CategoryController(self.database),
            AssigneeController(self.database),
        ):
            self.api.include_router(controller.router)

        # 許可した画面からAPIの応答を読み取れるようにする。
        self.api.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """稼働中はyieldで待ち、終了時に接続を解放する。"""
        # FastAPIの非同期lifespanの形式に合わせてasyncを使う。
        # DB操作自体は同期処理なので、解放処理を別スレッドへ渡す。
        try:
            yield
        finally:
            await run_in_threadpool(self.database.dispose)


def create_app(
    settings: Settings | None = None,  # settings あれば使う
    database: Database | None = None,  # database あれば使う
) -> FastAPI:
    """設定とDBからアプリを作る。省略された設定は環境変数・.envから読む。"""
    configured = settings if settings is not None else Settings()  # type: ignore[call-arg]
    # Settings があればそのままconfig 無ければ Settings() から持ってくる
    return TaskApplication(configured, database).api


# サーバーが読み込む入口。lifespanはサーバーの起動・終了時に実行される。
app = create_app()

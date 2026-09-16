"""ControllerやDALから伝わった例外を、共通形式のHTTP応答へ変換する。"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..Model.errors import ApplicationError, DuplicateNameError, NotFoundError

logger = logging.getLogger(__name__)


class ApiErrorHandlers:
    """404・409・500の応答を統一する。DBの取り消しとSessionの終了は共通関数が先に行う。"""

    def register(self, app: FastAPI) -> None:
        """入力の422はFastAPI標準を維持し、それ以外の共通ハンドラーを登録する。"""
        app.add_exception_handler(ApplicationError, self.application_error)
        app.add_exception_handler(SQLAlchemyError, self.database_error)
        app.add_exception_handler(Exception, self.unexpected_error)

    async def application_error(self, request: Request, exc: Exception) -> JSONResponse:
        """既知の業務エラーを変換する。DB障害を含むその他のアプリ例外は500。"""
        if isinstance(exc, NotFoundError):
            return JSONResponse(status_code=404, content={"detail": str(exc)})
        if isinstance(exc, DuplicateNameError):
            return JSONResponse(status_code=409, content={"detail": str(exc)})
        return self._failure(request, exc, "Database operation failed")

    async def database_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Sessionの準備・終了時などに直接伝わったDB例外も、同じ500形式にそろえる。"""
        return self._failure(request, exc, "Database operation failed")

    async def unexpected_error(self, request: Request, exc: Exception) -> JSONResponse:
        """想定外の例外も成功扱いにせず、原因の種類を記録して500を返す。"""
        return self._failure(request, exc, "Internal server error")

    def _failure(self, request: Request, exc: Exception, detail: str) -> JSONResponse:
        """入力値やSQLを含み得る例外本文は出さず、メソッド・ルート・原因の型を記録する。"""
        cause = exc.__cause__ or exc
        route = getattr(request.scope.get("route"), "path", "<unmatched>")
        logger.error(
            "Request failed: method=%s route=%s error=%s cause=%s",
            request.method,
            route,
            type(exc).__name__,
            type(cause).__name__,
        )
        return JSONResponse(status_code=500, content={"detail": detail})

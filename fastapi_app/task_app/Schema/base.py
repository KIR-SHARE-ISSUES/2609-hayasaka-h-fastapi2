"""入力用・応答用スキーマに共通の設定をまとめる。"""

from pydantic import BaseModel, ConfigDict


class InputModel(BaseModel):
    """既存クライアントが送る未定義項目は保存対象に含めず無視する。"""

    model_config = ConfigDict(extra="ignore")


class OrmResponse(BaseModel):
    """ORM属性から応答を組み立てる。書き込みではcommit前に検証を完了する。"""

    model_config = ConfigDict(from_attributes=True)

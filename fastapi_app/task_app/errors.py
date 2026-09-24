"""
HTTPやDBドライバーに依存しない、処理中の失敗の種類を定義する。
DBの共通関数が、Controllerから渡された処理の例外を捕捉して未確定の変更を取り消す。
その後、Controllerの共通ハンドラーが例外をHTTP応答へ変換する。
"""


class ApplicationError(Exception):
    """内部処理の失敗を、外部向けのHTTP応答へ変換する境目で扱うエラーの基底クラス。"""


class NotFoundError(ApplicationError):
    """指定されたタスク・カテゴリ・担当者が見つからなかった。"""

    def __init__(self, entity: str) -> None:
        super().__init__(f"{entity} not found")


class DuplicateNameError(ApplicationError):
    """名前の一意性違反を確認できた場合に限って使用する。"""

    def __init__(self, entity: str) -> None:
        super().__init__(f"{entity} name already exists")


class PersistenceError(ApplicationError):
    """DB操作が失敗した。元例外は原因として保持し、応答本文には含めない。"""

    def __init__(self) -> None:
        super().__init__("Database operation failed")

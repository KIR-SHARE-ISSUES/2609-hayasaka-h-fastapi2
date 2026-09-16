"""DBの接続設定と、処理ごとのSession管理をまとめる。

Engineは接続を管理し、Sessionは個々の検索・変更を管理する。
Sessionの準備・実行・保存・取り消し・終了は、末尾の共通関数で行う。
"""

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..Model.errors import PersistenceError

Result = TypeVar("Result")


class Settings(BaseSettings):
    """環境変数・.envから接続先とCORS設定を読み、形式を検証する。DBの実在は確認しない。"""

    # 初期値のない項目は必須。環境変数ではDB_HOSTなどの大文字でも指定できる。
    db_host: str
    db_port: int = Field(gt=0, le=65535)
    db_name: str
    db_user: str
    db_password: str
    db_charset: str = "utf8mb4"  # 絵文字なども扱えるMySQLの文字セット。
    cors_origins: str  # 許可する画面の接続元をカンマ区切りで指定する。

    # 実行場所に左右されずfastapi_app/.envを読む。同じ項目は環境変数を優先する。
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # このクラスで定義していない設定項目は無視する。
    )

    @property
    def database_url(self) -> URL:
        """接続情報をまとめる。URL.createでパスワード内の記号もそのまま扱える。"""
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": self.db_charset},
        )

    @property
    def allowed_origins(self) -> list[str]:
        """カンマで分割し、前後空白と空要素を除く。URLの妥当性までは検証しない。"""
        return [
            value.strip() for value in self.cors_origins.split(",") if value.strip()
        ]


class Base(DeclarativeBase):
    """モデルの表・列の定義をBase.metadataへ集める。定義だけではDBに表を作らない。"""


class Database:
    """共有するEngineとSessionの生成方法を持つ。各処理のSession管理は共通関数が行う。"""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # 同じ接続設定で、処理ごとに独立したSessionを作れるようにする。
        self.session_factory = sessionmaker(
            bind=engine,
            autoflush=False,  # flushを明示する。commit時のflushは自動で行われる。
            expire_on_commit=False,  # commit後も読み込み済みの値を保持する。
        )

    # class に対する再帰的操作なので @classmethod を使用
    @classmethod
    def from_settings(cls, settings: Settings) -> "Database":
        # settingsから接続情報をまとめ、Engineを作ってDatabaseを返す。
        return cls(
            create_engine(
                settings.database_url,
                # 貸し出す際に接続を確認する。処理途中の切断までは防げない。
                pool_pre_ping=True,
                # 作成から1時間を超えた接続を、次の貸し出し時に作り直す。
                pool_recycle=3600,
                echo=False,  # SQLの簡易ログ出力を止める。
                hide_parameters=True,  # SQLログなどでSQLへ渡した値を隠す。
            )
        )

    """ DB 系で必要な時に使うやつら"""

    def create_tables(self) -> None:
        """読み込んだモデルの定義で、不足する表を作る。アプリ起動時には呼ばない。"""
        # 既存の列の変更や、MySQLのDBそのものの作成は行わない。
        Base.metadata.create_all(bind=self.engine)

    def open_session(self) -> Session:
        """新しいSessionを返す。SQL実行などで必要になった時点で接続させる"""
        # 処理間で使い回さず、利用後は共通関数のwithで閉じる。
        return self.session_factory()

    def dispose(self) -> None:
        """アプリ終了時に、返却済みの接続を閉じる。"""
        # 貸し出し中の接続は対象外なので、Sessionの終了処理も必要！
        self.engine.dispose()


""" DB 操作で毎回呼び出す共通関数 commit rollback"""


def execute_database_operation(
    database: Database,
    operation: Callable[[Session], Result],
    *,
    write: bool = False,
) -> Result:
    """Sessionを用意 → 処理を実行 → 書き込みを確定 → Sessionを閉じる。

    operationはSessionを受け取り、応答データの準備まで行う関数。
    登録・更新・削除はwrite=True、取得だけなら省略する。
    """
    with database.open_session() as db:
        try:
            result = operation(db)
            # 取得だけならcommitは不要。書き込みは応答の検証後に確定する。
            if write:
                db.commit()
            return result
        except SQLAlchemyError as exc:
            # DBの失敗は未確定の変更を取り消し、共通ハンドラーで500へ変換する。
            db.rollback()
            raise PersistenceError() from exc
        except Exception:
            # 存在確認や応答の検証に失敗した場合も、変更を取り消して原因を伝える。
            db.rollback()
            raise

"""環境変数・.envから、DBの接続先とCORSの設定を読み込む。"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


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
        env_file=Path(__file__).resolve().parents[1] / ".env",
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

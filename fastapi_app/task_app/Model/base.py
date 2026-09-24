"""全テーブル定義の共通の親クラス。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """モデルの表・列の定義をBase.metadataへ集める。定義だけではDBに表を作らない。"""

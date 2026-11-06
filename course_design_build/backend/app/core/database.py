"""SQLAlchemy 连接和会话管理。

每个 HTTP 请求独占一个 Session，请求结束后统一关闭，Controller 无需关心连接释放。
"""
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,       # 使用连接前探活，避免 MySQL 空闲断开导致 500。
    pool_recycle=1800,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

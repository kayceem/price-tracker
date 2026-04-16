from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.shared.config import settings


db_path = str(settings.base_dir / "db.sqlite3")
CONNECTION_URI = f"sqlite+aiosqlite:///{db_path}"

engine = create_async_engine(
    CONNECTION_URI,
    echo=False,
    pool_size=50,
    max_overflow=20,
    pool_timeout=30,
)
SessionLocal = sessionmaker(
    autocommit=False,
    class_=AsyncSession,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
Base = declarative_base()


@asynccontextmanager
async def get_db():
    async with SessionLocal() as session:
        yield session


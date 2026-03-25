from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from src.config.settings import config

db_path = str(config.base_dir / 'db.sqlite3')
CONNECTION_URI = f'sqlite+aiosqlite:///{db_path}'
engine = create_async_engine(CONNECTION_URI, echo=False,
    pool_size=50,
    max_overflow=20,
    pool_timeout=30,
)
SessionLocal = sessionmaker(autocommit=False,class_=AsyncSession, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with SessionLocal() as session:
        yield session
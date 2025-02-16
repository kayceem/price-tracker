from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from utils import get_dir_path

DIR_PATH = get_dir_path()
CONNECTION_URI = f'sqlite+aiosqlite:///{DIR_PATH}/db.sqlite3'
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
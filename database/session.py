from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from utils import get_dir_path

DIR_PATH = get_dir_path()
CONNECTION_URI = f'sqlite:///{DIR_PATH}/db.sqlite3'
engine = create_engine(CONNECTION_URI, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    session=SessionLocal()
    try:
        yield session
    finally:
        session.close()

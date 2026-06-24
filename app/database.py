from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pathlib import Path

# Determine project root using Path(__file__).resolve()
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "data"

# Ensure the database directory exists before startup
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Enforce foreign key constraints in SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

# Dependency
async def get_db():
    async with SessionLocal() as db:
        yield db
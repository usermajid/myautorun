from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base # declarative_base was in user's original model.py
from telegram_bot.config import settings # Assuming settings.DATABASE_URL is defined
import logging

logger = logging.getLogger(__name__)

# Define Base here if it's not defined in models.py or if models.py imports it from here
# For now, assume models.py will define its own Base or import it.
# If models.py relies on Base from here, it should be:
# Base = declarative_base()

AsyncSessionFactory: async_sessionmaker[AsyncSession]
async_engine = None

def setup_async_engine():
    global async_engine, AsyncSessionFactory
    
    logger.info(f"Initializing async database engine for URL: {settings.DATABASE_URL}")
    
    connect_args = {}
    if "sqlite" in settings.DATABASE_URL.lower():
        # For SQLite, connect_args to enable better support for asyncio if needed by driver
        # For aiosqlite, this might not be strictly necessary as it's async by nature
        # connect_args={"check_same_thread": False} # This is for sync sqlite, remove for aiosqlite
        pass # aiosqlite handles threading/async internally

    async_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"), # Log SQL queries in development
        # Adjust pool settings as needed for production with PostgreSQL, etc.
        # pool_size=10,
        # max_overflow=20
    )

    AsyncSessionFactory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False # Recommended for FastAPI/async usage
    )
    logger.info("Async database engine and session factory initialized.")

async def get_async_db_session() -> AsyncSession:
    if not AsyncSessionFactory:
        raise RuntimeError("AsyncSessionFactory not initialized. Call setup_async_engine() first.")
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db_models():
    """
    Creates database tables based on models' metadata.
    Ensure models are imported or Base is populated before calling this.
    """
    if not async_engine:
        raise RuntimeError("Async engine not initialized. Call setup_async_engine() first.")

    # Import Base from models.py, or ensure models are loaded so Base.metadata is populated
    from telegram_bot.database.models import Base # Crucial: models must be loaded for Base.metadata

    async with async_engine.begin() as conn:
        # In a production environment, you would use Alembic for migrations.
        # await conn.run_sync(Base.metadata.drop_all) # Use with caution (deletes all data)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created or verified successfully (async).")

# Call setup_async_engine at module load time or ensure it's called before any DB operation.
# For simplicity in this structure, calling it here.
# In a larger app, this might be part of an explicit startup sequence.
if not settings.DATABASE_URL:
    logger.critical("DATABASE_URL is not set. Database engine cannot be initialized.")
else:
    setup_async_engine()

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram_bot.config import settings
from telegram_bot.database.models import Base

logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database and create tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized and tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise

def get_db():
    """Generator function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing database directly from engine.py (for testing or setup).")
    init_db()
    # Example of using the session
    # with get_db() as session:
    #     # Perform database operations
    #     logger.info("Database session obtained and closed successfully.")
    pass

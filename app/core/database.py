"""
PostgreSQL Database Setup
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import DATABASE_URL, SQLALCHEMY_ECHO
import logging

logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=SQLALCHEMY_ECHO,
    pool_pre_ping=True,  # Verify connection before using
    pool_recycle=3600,   # Recycle connection after 1 hour
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Session:
    """
    Dependency for FastAPI to get DB session
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """Initialize database (create all tables)"""
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created/verified")

def drop_db():
    """Drop all tables (use with caution!)"""
    from app.db.base import Base
    Base.metadata.drop_all(bind=engine)
    logger.warning("⚠️ Database tables dropped!")

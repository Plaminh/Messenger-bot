"""
Auto-Migration Handler
Automatically run SQL migrations on app startup
"""
import logging
import os
from pathlib import Path
from sqlalchemy import text, create_engine

logger = logging.getLogger(__name__)

def run_migrations(database_url: str):
    """
    Auto-run migrations from migrations/ folder
    Checks if tables exist, runs SQL if needed
    """
    try:
        # Connect to database
        engine = create_engine(database_url)
        
        # Get migrations folder
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        
        if not migrations_dir.exists():
            logger.warning(f"⚠️ Migrations folder not found: {migrations_dir}")
            return
        
        # Get all SQL files in order
        sql_files = sorted([f for f in migrations_dir.glob("*.sql")])
        
        if not sql_files:
            logger.warning("⚠️ No SQL migration files found")
            return
        
        logger.info(f"📦 Found {len(sql_files)} migration files")
        
        # Run each migration
        with engine.connect() as connection:
            for sql_file in sql_files:
                try:
                    with open(sql_file, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    
                    if not sql_content.strip():
                        continue
                    
                    logger.info(f"🔄 Running migration: {sql_file.name}")
                    
                    # Execute SQL (split by semicolon for multiple statements)
                    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                    
                    for statement in statements:
                        connection.execute(text(statement))
                    
                    connection.commit()
                    logger.info(f"✅ Migration completed: {sql_file.name}")
                    
                except Exception as e:
                    logger.error(f"❌ Migration failed for {sql_file.name}: {e}")
                    connection.rollback()
                    # Don't raise - continue with other migrations
        
        logger.info("✅ All migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration handler error: {e}", exc_info=True)
        raise

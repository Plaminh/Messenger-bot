"""
Logger for PostgreSQL (v3.0 - Primary)

Use this in v3.0+ for logging conversations to database.
See logger_sheets.py for legacy Google Sheets logging.
"""
import logging
from sqlalchemy.orm import Session
from db import crud, schemas

logger = logging.getLogger(__name__)

def log_conversation(
    db: Session,
    customer_id: int,
    facebook_id: str,
    message_text: str,
    bot_response: str,
    intent: str = "default",
    score: float = 0.0,
    is_fallback: bool = False
):
    """
    Log conversation to PostgreSQL
    
    Usage:
        from utils.logger import log_conversation
        log_conversation(
            db=db_session,
            customer_id=1,
            facebook_id="123456789",
            message_text="Giá xe bao nhiêu?",
            bot_response="Từ 500k/ngày...",
            intent="price"
        )
    """
    try:
        conversation = schemas.ConversationCreate(
            customer_id=customer_id,
            facebook_id=facebook_id,
            message_text=message_text,
            bot_response=bot_response,
            intent=intent,
            score=score,
            is_fallback=is_fallback
        )
        crud.create_conversation(db, conversation)
        logger.debug(f"✅ Logged conversation for customer {customer_id}")
    except Exception as e:
        logger.error(f"❌ Failed to log conversation: {e}")

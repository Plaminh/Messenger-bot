"""
Message Processing Handler
"""
import logging
from sqlalchemy.orm import Session
from app.db import models

logger = logging.getLogger(__name__)

def process_customer_message(
    sender_id: str,
    message_text: str,
    db: Session,
    customer: models.Customer
) -> dict:
    """
    Process incoming customer message
    
    Returns:
        {
            "intent": str,
            "should_use_ai": bool,
            "context": dict
        }
    """
    
    msg_lower = message_text.lower().strip()
    
    # Get conversation history (last 5 messages)
    history = db.query(models.Conversation).filter(
        models.Conversation.customer_id == customer.id
    ).order_by(models.Conversation.created_at.desc()).limit(5).all()
    
    return {
        "intent": "default",
        "should_use_ai": True,
        "context": {
            "customer_id": customer.id,
            "message": message_text,
            "conversation_history": [
                {
                    "user": conv.message_text,
                    "bot": conv.bot_response
                }
                for conv in reversed(history)
            ]
        }
    }

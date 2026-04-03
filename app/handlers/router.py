"""
Message Router
Routes messages to appropriate handler (Rule-Based or AI)
"""
import logging
from sqlalchemy.orm import Session
from app.handlers.rule_based import RuleBasedHandler
from app.handlers.ai import AIHandler
from app.db import models

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    Route incoming messages to appropriate handler
    """
    
    @staticmethod
    async def route_message(
        message: str,
        user_id: str,
        db: Session
    ) -> str:
        """
        Route message to rule-based or AI handler
        
        Priority:
        1. Check if it's a command (/...)
        2. Try rule-based (FAQ) matching
        3. Fallback to AI
        """
        
        # 1. Check for command
        command = RuleBasedHandler.is_command(message)
        if command:
            args = message.split(" ", 1)[1] if " " in message else ""
            result = RuleBasedHandler.handle_command(command, args, db)
            if result:
                return result
        
        # 2. Try FAQ matching
        faq_match = RuleBasedHandler.match_faq(message, db)
        if faq_match:
            logger.info(f"FAQ match for user {user_id}: {faq_match.category}")
            return faq_match.answer
        
        # 3. Fallback to AI
        logger.info(f"Routing to AI for user {user_id}")
        response = await AIHandler.handle_message(message, user_id, db)
        return response
    
    @staticmethod
    def format_message(content: str, message_type: str = "text") -> dict:
        """
        Format response for Messenger
        
        Types: 'text', 'quick_reply', 'button'
        """
        
        if message_type == "text":
            return {
                "text": content
            }
        
        elif message_type == "quick_reply":
            # Format: "Question|Button1,Button2,Button3"
            parts = content.split("|", 1)
            if len(parts) == 2:
                question = parts[0]
                buttons = [b.strip() for b in parts[1].split(",")]
                
                return {
                    "text": question,
                    "quick_replies": [
                        {
                            "content_type": "text",
                            "title": btn,
                            "payload": btn
                        } for btn in buttons
                    ]
                }
        
        # Fallback to text
        return {"text": content}

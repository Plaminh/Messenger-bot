"""
Message Router
Routes messages to appropriate handler: Command -> Rule-Based -> Cache -> AI
"""
import logging
from sqlalchemy.orm import Session
from handlers.rule_based import RuleBasedHandler
from handlers.ai import AIHandler
from db import models

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    Route incoming messages to appropriate handler
    
    Priority (Quota Optimization Strategy):
    1. Command: /gia, /dat, /check, /xe (Rule-based - no API cost)
    2. FAQ: Pattern matching against FAQ database (Rule-based - no API cost)
    3. Cache: Check for similar cached AI responses (Minimal cost - DB only)
    4. AI: Call Gemini API as last resort (Full API cost)
    """
    
    @staticmethod
    async def route_message(
        message: str,
        user_id: str,
        db: Session
    ) -> str:
        """
        Route message through optimization pipeline
        
        Returns the appropriate response with quota savings as first priority.
        """
        
        logger.info(f"Routing message from user {user_id}: '{message[:50]}...'")
        
        # **PRIORITY 1: Check for command** (Command handler - no API cost)
        command = RuleBasedHandler.is_command(message)
        if command:
            args = message.split(" ", 1)[1] if " " in message else ""
            result = RuleBasedHandler.handle_command(command, args, db)
            if result:
                logger.info(f"Command '{command}' handled for user {user_id}")
                return result
        
        # **PRIORITY 2: Try FAQ matching** (Rule-based - no API cost)
        faq_match = RuleBasedHandler.match_faq(message, db)
        if faq_match:
            logger.info(f"FAQ match found (category: {faq_match.category}) for user {user_id}")
            return faq_match.answer
        
        # **PRIORITY 3 & 4: Cache or AI** (handled by AIHandler)
        # AIHandler.handle_message will check cache first, then call API if needed
        logger.info(f"Routing to AI handler (with cache check) for user {user_id}")
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

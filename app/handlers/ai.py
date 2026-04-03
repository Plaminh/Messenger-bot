"""
AI Handler - Gemini Integration
"""
import logging
from sqlalchemy.orm import Session
from app.ai.gemini import call_gemini_api
from app.db import models, schemas

logger = logging.getLogger(__name__)

class AIHandler:
    """
    Handle AI responses using Gemini
    """
    
    @staticmethod
    def get_chat_history(user_id: str, limit: int = 10, db: Session = None) -> list[dict]:
        """
        Fetch chat history for user
        """
        if not db:
            return []
        
        try:
            messages = db.query(models.MessageLog).filter(
                models.MessageLog.fb_user_id == user_id
            ).order_by(models.MessageLog.created_at.desc()).limit(limit).all()
            
            history = []
            for msg in reversed(messages):
                history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            return history
        
        except Exception as e:
            logger.error(f"Error fetching chat history: {e}")
            return []
    
    @staticmethod
    def build_context(user_id: str, db: Session) -> str:
        """
        Build system context for Gemini
        """
        # Get available vehicles
        vehicles = db.query(models.Vehicle).filter(
            models.Vehicle.status == 'active'
        ).all()
        
        vehicle_info = "Danh sách xe Vi Vu Đà Nẵng:\n"
        for v in vehicles:
            vehicle_info += f"- {v.name} ({v.seats} chỗ):"
            if v.price_per_day_no_driver:
                vehicle_info += f" {v.price_per_day_no_driver:,}đ/ngày (tự lái)"
            if v.price_per_day_with_driver:
                vehicle_info += f", {v.price_per_day_with_driver:,}đ/ngày (có tài)"
            vehicle_info += "\n"
        
        return vehicle_info
    
    @staticmethod
    async def handle_message(
        message: str,
        user_id: str,
        db: Session
    ) -> str:
        """
        Handle message with AI and save to database
        """
        try:
            # Get chat history
            history = AIHandler.get_chat_history(user_id, db=db)
            
            # Build context
            context = AIHandler.build_context(user_id, db)
            
            # Call Gemini
            response = await call_gemini_api(
                user_message=message,
                chat_history=history,
                context=context
            )
            
            # Save message logs
            AIHandler.save_message_logs(user_id, "user", message, db)
            AIHandler.save_message_logs(user_id, "assistant", response, db)
            
            return response
        
        except Exception as e:
            logger.error(f"AI handling error: {e}")
            return "Xin lỗi, tôi gặp lỗi. Hãy thử lại sau."
    
    @staticmethod
    def save_message_logs(
        user_id: str,
        role: str,
        content: str,
        db: Session
    ) -> bool:
        """
        Save message to message_logs table
        """
        try:
            log = models.MessageLog(
                fb_user_id=user_id,
                role=role,
                content=content,
                message_type='text'
            )
            db.add(log)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving message log: {e}")
            db.rollback()
            return False

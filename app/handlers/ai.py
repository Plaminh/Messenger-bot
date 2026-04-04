"""
AI Handler - Gemini Integration with Cache and Quota Management
"""
import logging
from sqlalchemy.orm import Session
from ai.gemini import call_gemini_api
from ai.prompts import SYSTEM_PROMPT_VI_VU
from db import models, schemas
from utils.cache import find_cached_response, save_to_cache

logger = logging.getLogger(__name__)

# Default fallback message when quota is exceeded
QUOTA_EXCEEDED_MESSAGE = """🚗 Xin lỗi nhé! Hệ thống tư vấn AI của chúng tôi đang bảo trì. 

Để được hỗ trợ nhanh chóng, bạn có thể:
1️⃣ Gõ /gia để xem bảng giá
2️⃣ Gõ /xe để xem danh sách xe
3️⃣ Gõ /dat để đặt xe ngay
4️⃣ Hoặc liên hệ Hotline: 0905.xxx.xxx

Cảm ơn bạn! ✨"""

class AIHandler:
    """
    Handle AI responses using Gemini with quota optimization
    
    Strategy:
    1. Check cache first (Rule-based cache hit)
    2. Call Gemini API (with error handling for quota)
    3. Save successful responses to cache
    """
    
    @staticmethod
    def get_chat_history(user_id: str, limit: int = 5, db: Session = None) -> list[dict]:
        """
        Fetch recent chat history for user
        
        OPTIMIZATION: Only fetch last 3-5 messages to minimize input tokens
        - Reduced from 10 to 5 messages
        - Each message ~100 tokens, so 5 messages = ~500 tokens saved per request
        - With 100 requests/day: 50,000 tokens saved = ~20% reduction
        
        Args:
            user_id: User ID
            limit: Max messages to fetch (default 5 for quota optimization)
            db: Database session
            
        Returns:
            List of message dicts with role and content
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
            
            logger.debug(f"Fetched {len(history)} recent messages for context (optimized for quota)")
            return history
        
        except Exception as e:
            logger.error(f"Error fetching chat history: {e}")
            return []
    
    @staticmethod
    def build_context(user_id: str, db: Session) -> str:
        """
        Build system context for Gemini with current vehicle info
        """
        context = SYSTEM_PROMPT_VI_VU + "\n\n# CURRENT VEHICLE INVENTORY:\n"
        
        try:
            # Get available vehicles
            vehicles = db.query(models.Vehicle).filter(
                models.Vehicle.status == 'active'
            ).all()
            
            for v in vehicles:
                context += f"- {v.name} ({v.seats} chỗ):"
                if v.price_per_day_no_driver:
                    context += f" {v.price_per_day_no_driver:,}đ/ngày (tự lái)"
                if v.price_per_day_with_driver:
                    context += f", {v.price_per_day_with_driver:,}đ/ngày (có tài xế)"
                context += "\n"
        except Exception as e:
            logger.error(f"Error building context: {e}")
        
        return context
    
    @staticmethod
    async def handle_message(
        message: str,
        user_id: str,
        db: Session
    ) -> str:
        """
        Handle message with AI, using cache-first strategy
        
        Flow:
        1. Check cache for similar questions
        2. If cache hit, return cached answer
        3. If cache miss, call Gemini API
        4. Handle API errors (quota, rate limit, etc)
        5. Save successful responses to cache
        
        Args:
            message: User message
            user_id: Facebook user ID
            db: Database session
            
        Returns:
            AI response or fallback message
        """
        try:
            # **STEP 1: Check cache first** (quota-saving strategy)
            cached_response = find_cached_response(message, db, min_similarity=90)
            
            if cached_response:
                logger.info(f"Using cached response (similarity: {cached_response['similarity_score']}%)")
                # Still save to message logs for history
                AIHandler.save_message_logs(user_id, "user", message, db)
                AIHandler.save_message_logs(user_id, "assistant", cached_response['answer'], db)
                return cached_response['answer']
            
            # **STEP 2: Get chat history and context**
            history = AIHandler.get_chat_history(user_id, db=db)
            context = AIHandler.build_context(user_id, db)
            
            # **STEP 3: Call Gemini API with error handling**
            try:
                response = await call_gemini_api(
                    user_message=message,
                    chat_history=history,
                    context=context
                )
                
                # **STEP 4: Save successful response to cache**
                save_to_cache(message, response, db)
                
                # Save message logs
                AIHandler.save_message_logs(user_id, "user", message, db)
                AIHandler.save_message_logs(user_id, "assistant", response, db)
                
                logger.info(f"AI response generated and cached for user: {user_id}")
                return response
                
            except Exception as api_error:
                error_str = str(api_error).lower()
                
                # Check if it's a quota exceeded error
                if any(quota_keyword in error_str for quota_keyword in 
                       ['quota', 'rate limit', 'too many requests', 'exceeded', 'resource']):
                    
                    logger.warning(f"API Quota exceeded for user {user_id}: {api_error}")
                    
                    # Log to sheets for monitoring
                    try:
                        log_to_sheets(
                            user_id=user_id,
                            event_type="API_QUOTA_EXCEEDED",
                            message=f"Quota exceeded - Fallback triggered",
                            status="warning"
                        )
                    except:
                        pass
                    
                    # Return fallback message
                    AIHandler.save_message_logs(user_id, "user", message, db)
                    AIHandler.save_message_logs(user_id, "assistant", QUOTA_EXCEEDED_MESSAGE, db)
                    return QUOTA_EXCEEDED_MESSAGE
                
                # Other API errors
                logger.error(f"AI API error for user {user_id}: {api_error}")
                
                fallback_msg = f"Xin lỗi, tôi gặp lỗi kỹ thuật. Hãy thử lại sau hoặc gõ /dat để đặt xe."
                AIHandler.save_message_logs(user_id, "user", message, db)
                AIHandler.save_message_logs(user_id, "assistant", fallback_msg, db)
                return fallback_msg
        
        except Exception as e:
            logger.error(f"Unexpected error in handle_message: {e}")
            fallback_msg = "Xin lỗi, tôi gặp lỗi. Hãy thử lại sau."
            try:
                AIHandler.save_message_logs(user_id, "user", message, db)
                AIHandler.save_message_logs(user_id, "assistant", fallback_msg, db)
            except:
                pass
            return fallback_msg
    
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

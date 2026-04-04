"""
Google Gemini AI Integration with Round-Robin API Key Management
- Supports multiple API keys for quota optimization
- Auto-switches between keys to maximize RPM limits
- Fallback handling for quota/rate limiting
"""
import logging
import itertools
import google.generativeai as genai
from app.core.config import GEMINI_API_KEYS, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiRoundRobin:
    """
    Round-robin API key manager for Gemini
    
    Benefits:
    - With N keys, you get N × 30 RPM = total requests/minute
    - Example: 9 keys = 270 requests/minute (vs 30 with single key)
    - Auto-switches if one key hits rate limit
    - Better resilience across accounts
    """
    
    def __init__(self):
        """Initialize Round-robin with API keys from config"""
        logger.info(f"Initializing GeminiRoundRobin... Found {len(GEMINI_API_KEYS)} keys from config")
        
        if not GEMINI_API_KEYS:
            error_msg = (
                "❌ No API keys found! Set GEMINI_API_KEY_1 through GEMINI_API_KEY_9 in .env\n"
                "Example:\n"
                "  GEMINI_API_KEY_1=AIzaSyA...\n"
                "  GEMINI_API_KEY_2=AIzaSyB...\n"
                "  ... (up to GEMINI_API_KEY_9)"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.available_keys = GEMINI_API_KEYS.copy()
        self.key_cycle = itertools.cycle(self.available_keys)
        self.model_name = GEMINI_MODEL
        self.call_count = 0
        self.key_usage = {key[:10]: 0 for key in self.available_keys}  # Track usage per key
        
        logger.info(f"✅ GeminiRoundRobin initialized with {len(self.available_keys)} API keys")
        logger.info(f"📊 Total RPM capacity: {len(self.available_keys)} × 30 = {len(self.available_keys) * 30} requests/minute")
    
    def get_next_key(self) -> str:
        """Get next API key in rotation"""
        key = next(self.key_cycle)
        key_id = key[:10]
        self.key_usage[key_id] += 1
        self.call_count += 1
        return key
    
    def get_model(self) -> genai.GenerativeModel:
        """
        Get configured Gemini model with next key in rotation
        
        Returns:
            Configured GenerativeModel instance
        """
        try:
            api_key = self.get_next_key()
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction="""Bạn là trợ lý ảo của Vi Vu Đà Nẵng - công ty cho thuê xe du lịch tại Đà Nẵng.

Trách nhiệm chính:
1. Tư vấn lịch trình du lịch Đà Nẵng
2. Giúp khách hiểu về các loại xe và giá cả
3. Hỗ trợ quá trình đặt xe
4. Trả lời câu hỏi về thủ tục, chính sách
5. Gợi ý loại xe phù hợp

Tông lửa: Thân thiện, tích cực, chuyên nghiệp.

Hướng dẫn:
- Trả lời ngắn gọn (dưới 500 ký tự)
- Dùng emoji thích hợp
- Khuyến khích dùng /gia, /xe, /dat
- Ưu tiên FAQ + cached responses"""
            )
            
            logger.debug(f"Model loaded (key: {api_key[:10]}...)")
            return model
        except Exception as e:
            logger.error(f"❌ Failed to get model: {e}")
            raise

    async def generate_response(
        self,
        user_message: str,
        chat_history: list[dict] = None,
        context: str = None
    ) -> str:
        """
        Generate AI response using round-robin key
        
        Args:
            user_message: User's input message
            chat_history: Previous messages in conversation
            context: Additional system context
            
        Returns:
            AI response text
        """
        try:
            # Get next model in rotation
            model = self.get_model()
            
            # Build system prompt
            system_prompt = context or ""
            
            # Build conversation history
            messages = []
            if chat_history:
                for msg in chat_history:
                    messages.append({
                        "role": msg["role"],
                        "parts": [msg["content"]]
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "parts": [user_message]
            })
            
            # Generate response
            response = model.generate_content(
                messages,
                generation_config={
                    "max_output_tokens": 500,
                    "temperature": 0.7,
                }
            )
            
            if response and response.text:
                logger.info(f"✅ Response generated (call #{self.call_count})")
                return response.text.strip()
            else:
                logger.warning("Empty response from Gemini")
                return "Xin lỗi, tôi không thể tạo response. Vui lòng thử lại."
        
        except Exception as e:
            logger.error(f"❌ Error in generate_response: {e}")
            # Fallback message
            return "🚗 Hệ thống đang bận. Vui lòng thử lại sau hoặc gõ /help"


# Global instance for easy access
_gemini_rr = None

def get_gemini_roundrobin() -> GeminiRoundRobin:
    """Get or create global GeminiRoundRobin instance"""
    global _gemini_rr
    if _gemini_rr is None:
        _gemini_rr = GeminiRoundRobin()
    return _gemini_rr


# ─── Legacy API for backward compatibility ───────────────────────────────────
async def call_gemini_api(
    user_message: str,
    chat_history: list[dict] = None,
    context: str = None
) -> str:
    """
    Legacy function for backward compatibility
    Now uses round-robin key management internally
    """
    try:
        rr = get_gemini_roundrobin()
        return await rr.generate_response(user_message, chat_history, context)
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}", exc_info=True)
        return "Xin lỗi, gặp lỗi khi xử lý. Vui lòng thử lại sau."


async def test_gemini_connection() -> bool:
    """
    Test Gemini connection and round-robin functionality
    Sends a test message and verifies response
    """
    try:
        logger.info("🧪 Testing Gemini Round-Robin connection...")
        response = await call_gemini_api("Xin chào! Bạn là ai?")
        
        if response and "gặp lỗi" not in response.lower():
            logger.info("✅ Gemini connection test successful!")
            return True
        else:
            logger.warning(f"⚠️ Test response: {response}")
            return False
    except Exception as e:
        logger.error(f"❌ Gemini connection test failed: {e}")
        return False


def get_key_usage_stats() -> dict:
    """Get statistics about API key usage"""
    try:
        rr = get_gemini_roundrobin()
        return {
            "total_calls": rr.call_count,
            "num_keys": len(rr.available_keys),
            "rpm_capacity": len(rr.available_keys) * 30,
            "key_usage": rr.key_usage
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}

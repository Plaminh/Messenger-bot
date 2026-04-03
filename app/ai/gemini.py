"""
Google Gemini AI Integration - Updated for Phase 1
"""
import logging
import google.generativeai as genai
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def call_gemini_api(
    user_message: str,
    chat_history: list[dict] = None,
    context: str = None
) -> str:
    """
    Call Gemini API with chat history and context
    
    Args:
        user_message: User's input message
        chat_history: Previous messages in conversation
        context: System context (vehicle info, etc.)
    
    Returns:
        AI response text
    """
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY not set")
        return "Xin lỗi, shop không thể xử lý ngay. Vui lòng thử lại sau."
    
    try:
        # Build system prompt
        system_prompt = """Bạn là trợ lý ảo của Vi Vu Đà Nẵng - công ty cho thuê xe du lịch tại Đà Nẵng.

Trách nhiệm:
1. Tư vấn lịch trình du lịch Đà Nẵng
2. Giúp khách hiểu rõ về các loại xe và giá cả
3. Hỗ trợ quá trình đặt xe
4. Trả lời các câu hỏi về thủ tục, chính sách
5. Gợi ý loại xe phù hợp dựa trên nhu cầu

Tông lửa: Thân thiện, tích cực, hỗ trợ, chuyên nghiệp.

Lưu ý:
- Trả lời ngắn gọn, rõ ràng (dưới 500 ký tự)
- Sử dụng emoji thích hợp
- Khuyến khích khách sử dụng hệ thống đặt xe"""
        
        if context:
            system_prompt += f"\n\n{context}"
        
        # Build conversation
        messages = []
        
        if chat_history:
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append({
                        "role": "user",
                        "parts": [msg["content"]]
                    })
                else:
                    messages.append({
                        "role": "model",
                        "parts": [msg["content"]]
                    })
        
        # Add current message
        messages.append({
            "role": "user",
            "parts": [user_message]
        })
        
        # Call Gemini (without system_instruction for compatibility)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Build full prompt with system instruction included
        full_prompt = f"{system_prompt}\n\nUser: {user_message}"
        
        response = model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": 500,
                "temperature": 0.7,
            }
        )
        
        if response and response.text:
            logger.info(f"✅ Gemini response generated")
            return response.text.strip()
        else:
            logger.warning("Empty response from Gemini")
            return "Xin lỗi, tôi không thể tạo response. Vui lòng thử lại."
    
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        return f"Xin lỗi, gặp lỗi: {str(e)}"

async def test_gemini_connection() -> bool:
    """Test Gemini API connection"""
    try:
        response = await call_gemini_api("Xin chào!")
        logger.info("✅ Gemini connection test successful")
        return True
    except Exception as e:
        logger.error(f"❌ Gemini connection test failed: {e}")
        return False

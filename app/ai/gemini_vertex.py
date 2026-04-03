"""
Google Vertex AI Integration (Alternative to AI Studio - uses Google Cloud Credit)
Use this when Gemini free tier quota is exhausted!

How to use:
1. Setup Google Cloud + Vertex AI (see instructions in README)
2. Replace imports in gemini.py OR swap filenames
3. Update GEMINI_API_TYPE='vertex_ai' in config.py
"""
import logging
import json
from google.auth import default
from google.auth.transport.requests import Request
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, GCP_PROJECT_ID, GCP_LOCATION

logger = logging.getLogger(__name__)

# For Vertex AI, use service account
_credentials = None

def get_vertex_credentials():
    """Get Vertex AI credentials from service account JSON"""
    global _credentials
    if not _credentials:
        try:
            # Option 1: Use Application Default Credentials (if using Compute Engine/Cloud Run)
            _credentials, project = default()
            
            # Option 2: Alternatively, load from JSON file if GEMINI_API_KEY is path to JSON
            if GEMINI_API_KEY and GEMINI_API_KEY.endswith('.json'):
                from google.oauth2 import service_account
                _credentials = service_account.Credentials.from_service_account_file(
                    GEMINI_API_KEY,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
        except Exception as e:
            logger.error(f"Failed to get Vertex credentials: {e}")
            return None
    
    return _credentials


async def call_gemini_api(
    user_message: str,
    chat_history: list[dict] = None,
    context: str = None
) -> str:
    """
    Call Vertex AI (Gemini) API with Google Cloud Credit
    
    Args:
        user_message: User's input message
        chat_history: Previous messages in conversation
        context: System context (vehicle info, etc.)
    
    Returns:
        AI response text
    """
    try:
        from vertexai.generative_models import GenerativeModel, Part
        import vertexai
        
        # Initialize Vertex AI with project
        credentials = get_vertex_credentials()
        if not credentials:
            logger.warning("⚠️ No Vertex AI credentials found")
            return "Xin lỗi, không thể kết nối AI. Vui lòng thử lại sau."
        
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION, credentials=credentials)
        
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
        
        # Build conversation for Vertex AI
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
        
        # Initialize model (Vertex AI format: "gemini-1.5-flash", etc.)
        model = GenerativeModel(
            "gemini-1.5-flash",  # or gemini-1.5-pro, gemini-2.0-flash
            system_instruction=system_prompt
        )
        
        # Send message
        response = model.generate_content(
            user_message,
            generation_config={
                "max_output_tokens": 500,
                "temperature": 0.7,
            }
        )
        
        if response and response.text:
            logger.info(f"✅ Vertex AI response generated")
            return response.text.strip()
        else:
            logger.warning("Empty response from Vertex AI")
            return "Xin lỗi, tôi không thể tạo response. Vui lòng thử lại."
    
    except ImportError:
        logger.error("❌ vertexai SDK not installed. Run: pip install google-cloud-aiplatform")
        return "Xin lỗi, AI không được cấu hình. Liên hệ admin."
    
    except Exception as e:
        logger.error(f"❌ Vertex AI error: {e}")
        return f"Xin lỗi, gặp lỗi: {str(e)}"


async def test_gemini_connection() -> bool:
    """Test Vertex AI connection"""
    try:
        response = await call_gemini_api("Xin chào!")
        logger.info("✅ Vertex AI connection test successful")
        return True
    except Exception as e:
        logger.error(f"❌ Vertex AI connection test failed: {e}")
        return False

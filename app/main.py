from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging
from app.handlers import handle_message
from app.logger import log_interaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vi vu Đà Nẵng Bot", version="1.0.0")

class WebhookPayload(BaseModel):
    message: str
    user_id: str = "unknown"
    first_name: Optional[str] = "bạn"

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Vi vu Đà Nẵng Bot"}

@app.post("/webhook")
async def webhook(payload: WebhookPayload):
    """Nhận tin nhắn từ ManyChat và trả lời"""
    try:
        logger.info(f"Incoming: {payload}")

        user_message = payload.message.strip()
        user_id = payload.user_id
        user_name = payload.first_name or "bạn"

        if not user_message:
            return JSONResponse({"version": "v2", "content": {
                "messages": [{"type": "text", "text": "Dạ shop chưa nhận được tin nhắn của bạn, bạn nhắn lại giúp shop nhé ạ 🙏"}]
            }})

        result = handle_message(user_message, user_id, user_name)

        log_interaction(
            user_id=user_id,
            user_message=user_message,
            bot_response=result["answer"],
            intent=result["intent"],
            score=result.get("score", 0),
            fallback=result.get("fallback", False),
            user_name=user_name
        )

        messages = [{"type": "text", "text": result["answer"]}]

        if result["intent"] == "booking":
            messages.append({
                "type": "text",
                "text": "Bạn muốn đặt xe ngay không ạ? 🚗",
                "quick_replies": [
                    {"type": "node", "caption": "✅ Đặt xe ngay", "node_labels": ["Booking Flow"]},
                    {"type": "node", "caption": "🔍 Xem bảng giá", "node_labels": ["Price Info"]},
                    {"type": "node", "caption": "📞 Liên hệ nhân viên", "node_labels": ["Human Handoff"]}
                ]
            })

        if result.get("fallback"):
            messages.append({
                "type": "text",
                "text": "Để nhân viên Vi vu hỗ trợ bạn tốt hơn nhé ạ 🙏",
                "quick_replies": [
                    {"type": "node", "caption": "👩‍💼 Gặp nhân viên", "node_labels": ["Human Handoff"]}
                ]
            })

        return JSONResponse({
            "version": "v2",
            "content": {"messages": messages}
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse({
            "version": "v2",
            "content": {"messages": [{"type": "text", "text": "Dạ shop đang bận tí, bạn nhắn lại sau giúp shop nhé ạ 🙏"}]}
        })
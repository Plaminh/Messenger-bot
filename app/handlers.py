from app.matcher import detect_intent, find_best_faq, get_vehicle_list
import logging
import re

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────
CONFIDENT_THRESHOLD = 80
ANSWER_THRESHOLD = 60

FALLBACK_RESPONSES = [
    "Dạ câu hỏi của bạn shop chưa hiểu rõ lắm 😅 Bạn có thể nói rõ hơn hoặc để nhân viên hỗ trợ bạn nhé!",
]

GREETING_KEYWORDS = ["hi", "hello", "chào", "alo", "xin chào", "hey"]
THANKS_KEYWORDS = ["cảm ơn", "thanks", "ok", "hiểu rồi"]

# ─── Simple entity extraction ────────────────────────────────────
def extract_info(message: str):
    info = {}

    # Ngày (basic)
    date_match = re.findall(r"\d{1,2}/\d{1,2}", message)
    if date_match:
        info["date"] = date_match

    # Số người
    people_match = re.search(r"(\d+)\s*(người|khách)", message)
    if people_match:
        info["people"] = people_match.group(1)

    # Loại xe
    if "tự lái" in message:
        info["type"] = "self_drive"
    elif "có tài" in message or "tài xế" in message:
        info["type"] = "with_driver"

    return info


# ─── Main handler ────────────────────────────────────────────────
def handle_message(message: str, user_id: str, user_name: str, context: dict = None) -> dict:
    if context is None:
        context = {}

    msg_lower = message.lower().strip()

    # ── Greeting ─────────────────────────────────────────────────
    if any(kw in msg_lower for kw in GREETING_KEYWORDS):
        return {
            "answer": f"Chào {user_name}! 👋 Vi vu Đà Nẵng hỗ trợ bạn đây 🚗\n\nBạn muốn thuê xe đi đâu ạ?",
            "intent": "greeting",
            "score": 100,
            "fallback": False,
            "context": context
        }

    # ── Thanks ───────────────────────────────────────────────────
    if any(kw in msg_lower for kw in THANKS_KEYWORDS):
        return {
            "answer": "Dạ không có gì ạ! 🚗💨 Bạn cần hỗ trợ gì thêm cứ nhắn Vi vu nhé!",
            "intent": "thanks",
            "score": 100,
            "fallback": False,
            "context": context
        }

    # ── Extract info ─────────────────────────────────────────────
    extracted = extract_info(msg_lower)
    context.update(extracted)

    # ── Detect intent ────────────────────────────────────────────
    intent = detect_intent(message)
    logger.info(f"[{user_id}] Intent: {intent} | Message: {message}")

    # ── Vehicle list ─────────────────────────────────────────────
    if intent == "vehicle_info":
        return {
            "answer": get_vehicle_list(),
            "intent": intent,
            "score": 90,
            "fallback": False,
            "context": context
        }

    # ── Booking flow (SMART) ─────────────────────────────────────
    if intent == "booking":
        missing = []

        if "date" not in context:
            missing.append("📅 ngày thuê")
        if "people" not in context:
            missing.append("👥 số người")
        if "type" not in context:
            missing.append("🚗 loại xe (tự lái / có tài)")

        if missing:
            return {
                "answer": (
                    "Dạ để đặt xe bạn cho shop xin thêm thông tin nhé:\n\n"
                    + "\n".join(missing)
                ),
                "intent": "booking",
                "score": 85,
                "fallback": False,
                "context": context
            }

        # Đã đủ info → confirm booking
        return {
            "answer": (
                f"🎉 Xác nhận thông tin:\n"
                f"📅 Ngày: {context.get('date')}\n"
                f"👥 Số người: {context.get('people')}\n"
                f"🚗 Loại xe: {context.get('type')}\n\n"
                "Shop sẽ liên hệ bạn ngay để chốt xe nhé! 📞"
            ),
            "intent": "booking_confirm",
            "score": 95,
            "fallback": False,
            "context": context
        }

    # ── FAQ fallback ─────────────────────────────────────────────
    faq_result = find_best_faq(message)

    if faq_result["score"] >= CONFIDENT_THRESHOLD:
        return {
            "answer": faq_result["answer"],
            "intent": intent,
            "score": faq_result["score"],
            "fallback": False,
            "context": context
        }

    elif faq_result["score"] >= ANSWER_THRESHOLD:
        return {
            "answer": faq_result["answer"] + "\n\nBạn cần hỏi thêm gì không ạ? 😊",
            "intent": intent,
            "score": faq_result["score"],
            "fallback": False,
            "context": context
        }

    # ── Smart fallback ───────────────────────────────────────────
    return {
        "answer": (
            "Dạ shop chưa hiểu rõ lắm 😅\n\n"
            "Bạn có thể thử hỏi:\n"
            "👉 Giá thuê xe\n"
            "👉 Thuê xe 4-7-16 chỗ\n"
            "👉 Đặt xe đi Bà Nà / Hội An\n"
        ),
        "intent": "fallback",
        "score": 0,
        "fallback": True,
        "context": context
    }
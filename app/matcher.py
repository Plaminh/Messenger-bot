from rapidfuzz import fuzz, process
from app.sheet import get_faq_data, get_vehicles_data
import re
import logging

logger = logging.getLogger(__name__)

# Threshold để quyết định trả lời hay fallback
ANSWER_THRESHOLD = 60
CONFIDENT_THRESHOLD = 80

# ─── Intent keywords ────────────────────────────────────────────
INTENT_KEYWORDS = {
    "price": [
        "giá", "bao nhiêu tiền", "giá thuê", "bảng giá", "phí", "chi phí",
        "tốn bao nhiêu", "mấy tiền", "bao tiền", "rate", "pricing"
    ],
    "booking": [
        "đặt xe", "book", "đặt", "thuê", "mướn xe", "mướn",
        "muốn đặt", "muốn thuê", "cho thuê", "có xe không", "còn xe không"
    ],
    "availability": [
        "còn trống", "xe trống", "check xe", "ngày nào còn", "hết xe chưa",
        "còn lịch", "available", "slot", "ngày trống"
    ],
    "policy": [
        "chính sách", "điều kiện", "quy định", "đặt cọc", "cọc", "hủy",
        "hoàn tiền", "refund", "cancel", "đổi ngày"
    ],
    "contact": [
        "liên hệ", "số điện thoại", "hotline", "zalo", "gọi", "sdt",
        "địa chỉ", "ở đâu", "nhân viên", "tư vấn"
    ],
    "vehicle_info": [
        "loại xe", "xe gì", "xe nào", "có những xe", "mẫu xe",
        "4 chỗ", "7 chỗ", "16 chỗ", "29 chỗ", "ô tô", "xe tự lái", "có tài"
    ]
}

def detect_intent(message: str) -> str:
    """Phát hiện intent từ tin nhắn"""
    msg_lower = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in msg_lower:
                return intent
    return "faq"

def normalize(text: str) -> str:
    """Chuẩn hóa text để match tốt hơn"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    # Một số rút gọn thường gặp
    replacements = {
        "k ": "không ", "ko ": "không ", "kh ": "không ",
        "đc ": "được ", "dc ": "được ",
        "vs ": "với ", "bn ": "bạn ",
        "shop ": "", "mn ": "mọi người ",
        "ạ": "", "ơi": "", "nhỉ": "", "nha": "", "nhe": ""
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()

def find_best_faq(message: str) -> dict:
    """Tìm câu trả lời FAQ phù hợp nhất"""
    faq_data = get_faq_data()
    if not faq_data:
        return {"answer": None, "score": 0, "matched_question": None}

    normalized_msg = normalize(message)

    # Build corpus để search
    questions = []
    for row in faq_data:
        q = str(row.get("question", ""))
        tags = str(row.get("tags", ""))
        # Combine question + tags để match tốt hơn
        combined = f"{q} {tags}"
        questions.append(normalize(combined))

    # Fuzzy match
    result = process.extractOne(
        normalized_msg,
        questions,
        scorer=fuzz.token_set_ratio
    )

    if not result:
        return {"answer": None, "score": 0, "matched_question": None}

    best_match, score, idx = result

    if score >= ANSWER_THRESHOLD and idx < len(faq_data):
        row = faq_data[idx]
        return {
            "answer": row.get("answer", ""),
            "score": score,
            "matched_question": row.get("question", ""),
            "category": row.get("category", "")
        }

    return {"answer": None, "score": score, "matched_question": None}

def get_vehicle_list() -> str:
    """Lấy danh sách xe từ Google Sheet"""
    vehicles = get_vehicles_data()
    if not vehicles:
        return "Dạ shop có các loại xe phổ biến: xe 4 chỗ, 7 chỗ tự lái và có tài xế ạ. Bạn nhắn cho shop biết nhu cầu để tư vấn chi tiết nhé 🚗"

    lines = ["🚗 *Các loại xe Vi vu Đà Nẵng:*\n"]
    for v in vehicles:
        name = v.get("name", "")
        seats = v.get("seats", "")
        price = v.get("price_per_day", "")
        driver = "Có tài" if str(v.get("has_driver", "")).lower() in ["true", "1", "có", "yes"] else "Tự lái"
        if name:
            lines.append(f"• {name} ({seats} chỗ) - {driver}: {price}/ngày")

    lines.append("\nBạn muốn biết thêm về xe nào không ạ? 😊")
    return "\n".join(lines)
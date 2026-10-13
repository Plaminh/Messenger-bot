"""Safety filters and crisis intervention detection.

Detects self-harm, suicide, or acute psychological crises, turns off style
mirroring, and guides the LLM into a grounding, supportive posture.
Also ensures toxic profanity or hate speech is never mirrored.
"""

import re

# Comprehensive crisis indicators (suicide, self-harm, deep despair)
CRISIS_PATTERNS = [
    r"\b(tự tử|tự sát|muốn chết|muốn biến mất|không muốn sống nữa)\b",
    r"\b(kết thúc cuộc sống|chết quách cho xong|chết đi cho rồi)\b",
    r"\b(rạch tay|uống thuốc ngủ|nhảy lầu|treo cổ)\b",
    r"\b(tự làm hại|tự hoại bản thân)\b",
    r"\b(bế tắc hoàn toàn|không còn lối thoát|tuyệt vọng quá)\b",
]

CRISIS_REGEX = re.compile("|".join(CRISIS_PATTERNS), re.IGNORECASE)

# Severe profanity filter to prevent abusive mirroring
TOXIC_PATTERNS = [
    r"\b(đĩ|đụ|lồn|cặc|buồi|địt mẹ|đụ má|óc chó)\b",
]
TOXIC_REGEX = re.compile("|".join(TOXIC_PATTERNS), re.IGNORECASE)


def is_crisis(text: str) -> bool:
    """Check if incoming user text contains explicit crisis or self-harm signals."""
    if not text:
        return False
    return bool(CRISIS_REGEX.search(text))


def contains_toxic_language(text: str) -> bool:
    """Check if text contains severe slurs or profanity."""
    if not text:
        return False
    return bool(TOXIC_REGEX.search(text))


def get_crisis_prompt_guidance() -> str:
    """Prompt guidance when user is in crisis."""
    return (
        "CẢNH BÁO KHỦNG HOẢNG: Người dùng đang có dấu hiệu tổn thương sâu sắc hoặc tuyệt vọng.\n"
        "- TẮT TOÀN BỘ style mirroring (không đùa giỡn, không dùng teencode hay tiếng cười).\n"
        "- Giọng điệu: Dịu dàng, chân thành, bình tĩnh, kiên nhẫn và ấm áp.\n"
        "- Lắng nghe và đồng hành: Thừa nhận cảm xúc đau đớn của bạn ấy, không phán xét, không giáo điều, không bảo 'hãy nghĩ tích cực lên'.\n"
        "- Đề xuất trợ giúp an toàn: Nhẹ nhàng gợi ý bạn ấy chia sẻ với người thân đáng tin cậy hoặc liên hệ đường dây nóng hỗ trợ tâm lý Ngày Mai (096 306 1414) hoặc Tổng đài 111.\n"
        "- Khẳng định bạn luôn ở đây lắng nghe và không bao giờ bỏ rơi cuộc trò chuyện."
    )

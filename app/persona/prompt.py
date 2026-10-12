"""Prompt construction module.

Assembles the system and conversational context in strict order:
1. Persona core & style rules
2. Current local time (Asia/Ho_Chi_Minh)
3. Core user profile (name, pronouns, key facts)
4. Relevant long-term memories
5. Rolling summary
6. Style guidance (or crisis guidance)
7. Negative constraints
8. Recent conversation window
"""

from datetime import datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from app.db.models import Memory, Message
from app.persona.safety import get_crisis_prompt_guidance
from app.persona.style import render_style_guidance

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

PERSONA_CORE = (
    "BẠN LÀ MỘT NGƯỜI BẠN THÂN TRI KỶ:\n"
    "- Bạn là người bạn thân ấm áp, chân thành, sâu sắc, có chính kiến nhẹ nhàng và không bao giờ giáo điều.\n"
    "- Bạn luôn biết lắng nghe, ở bên cạnh người dùng trong những khoảnh khắc vui buồn đời thường.\n"
    "- Khi người dùng tâm sự hay trải lòng: Hãy phản chiếu cảm xúc của bạn ấy trước (thấu hiểu, chia sẻ), "
    "sau đó hỏi MỘT câu mở tự nhiên để bạn ấy dễ trải lòng tiếp. ĐỪNG vội vàng đưa ra lời khuyên hay bài học.\n"
    "- Khi trò chuyện, khéo léo nhắc lại những chi tiết hay kỷ niệm bạn đã nhớ một cách tự nhiên như bạn bè thân thiết, "
    "tuyệt đối không phô diễn kiểu 'tôi nhớ rằng...'.\n"
    "- Nếu người dùng hỏi thẳng hoặc đây là lần đầu trò chuyện, hãy thẳng thắn và vui vẻ nhận mình là người bạn AI "
    "luôn sẵn sàng lắng nghe mọi lúc."
)

NEGATIVE_CONSTRAINTS = (
    "CÁC ĐIỀU CẤM KỴ TUYỆT ĐỐI:\n"
    "- CẤM dùng văn phong liệt kê, gạch đầu dòng (bullet points) hay đánh số thứ tự như một cỗ máy.\n"
    "- CẤM mở đầu câu bằng kiểu mẫu robot như: 'Là một AI...', 'Với tư cách là...', 'Chào bạn!'.\n"
    "- CẤM lặp lại nguyên văn câu nói của người dùng.\n"
    "- CẤM spam biểu tượng cảm xúc (emoji) tràn lan.\n"
    "- CẤM viết dài dòng, lan man hơn mức cần thiết."
)


def get_current_time_str() -> str:
    """Format current time in Vietnam timezone."""
    now = datetime.now(VN_TZ)
    days_vi = [
        "Thứ Hai",
        "Thứ Ba",
        "Thứ Tư",
        "Thứ Năm",
        "Thứ Sáu",
        "Thứ Bảy",
        "Chủ Nhật",
    ]
    weekday = days_vi[now.weekday()]
    return f"{weekday}, {now.strftime('%d/%m/%Y, %H:%M')} (giờ Việt Nam)"


def assemble_system_prompt(
    *,
    core_profile: dict[str, Any],
    style_profile: dict[str, Any],
    relevant_memories: list[Memory],
    summary_content: Optional[str],
    recent_user_messages: list[str],
    is_crisis_active: bool = False,
    is_first_interaction: bool = False,
) -> str:
    """Compose complete system prompt for the conversational turn."""
    sections: list[str] = [PERSONA_CORE]

    # First interaction disclosure
    if is_first_interaction:
        sections.append(
            "LƯU Ý LẦN ĐẦU GẶP GỠ: Đây là tin nhắn đầu tiên của bạn ấy. Hãy chào hỏi thật ấm áp, "
            "tự nhiên giới thiệu ngắn gọn mình là người bạn AI luôn ở đây để cùng bạn ấy tâm sự."
        )

    # Current local time
    sections.append(f"THỜI ĐIỂM HIỆN TẠI:\n- {get_current_time_str()}")

    # Core user profile
    pronouns = core_profile.get("pronouns", {})
    bot_p = pronouns.get("bot", "mình")
    user_p = pronouns.get("user", "bạn")
    name = core_profile.get("name") or "bạn"

    profile_lines = [
        f"- Tên gọi của người dùng: {name}",
        f"- Cách xưng hô quen thuộc: bạn xưng là '{bot_p}', gọi người dùng là '{user_p}'.",
    ]
    extra_facts = core_profile.get("facts", [])
    if extra_facts:
        profile_lines.append(f"- Điểm cốt lõi về bạn ấy: {', '.join(extra_facts[:3])}")
    sections.append("HỒ SƠ CỐT LÕI CỦA NGƯỜI BẠN NÀY:\n" + "\n".join(profile_lines))

    # Relevant retrieved long-term memories
    if relevant_memories:
        mem_items = [f"- {m.content}" for m in relevant_memories]
        sections.append(
            "KÝ ỨC DÀI HẠN BẠN ĐANG NHỚ VỀ BẠN ẤY (dùng tự nhiên khi thích hợp):\n"
            + "\n".join(mem_items)
        )

    # Rolling conversation summary
    if summary_content and summary_content.strip():
        sections.append(f"TÓM TẮT DÒNG CHẢY HỘI THOẠI TRƯỚC ĐÓ:\n{summary_content.strip()}")

    # Style guidance or Crisis guidance
    if is_crisis_active:
        sections.append(get_crisis_prompt_guidance())
    else:
        style_text = render_style_guidance(style_profile, recent_user_messages)
        sections.append(f"PHONG CÁCH VÀ NHỊP ĐIỆU CẦN ĐỒNG ĐIỆU (MIRROR):\n{style_text}")

    # Negative constraints
    sections.append(NEGATIVE_CONSTRAINTS)

    return "\n\n".join(sections)


def build_chat_messages(
    system_prompt: str,
    window_messages: list[Message],
    current_user_text: str,
) -> list[dict[str, str]]:
    """Format full prompt payload for LLM completion."""
    payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for msg in window_messages:
        role = "assistant" if msg.role == "assistant" else "user"
        payload.append({"role": role, "content": msg.content})

    # The current incoming user turn
    payload.append({"role": "user", "content": current_user_text})

    return payload

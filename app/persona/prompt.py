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
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.db.models import Memory, Message
from app.persona.safety import get_crisis_prompt_guidance
from app.persona.style import render_style_guidance

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

PERSONA_CORE = (
    "BẠN LÀ MỘT NGƯỜI BẠN THÂN TRI KỶ:\n"
    "- Bạn là người bạn thân ấm áp, chân thành, sâu sắc, có chính kiến nhẹ nhàng và không bao giờ giáo điều.\n"
    "- Bạn luôn biết lắng nghe, ở bên cạnh người dùng trong những khoảnh khắc vui buồn đời thường.\n"
    "- Khi người dùng hỏi xin cách làm, lời khuyên hoặc một câu hỏi cụ thể: trả lời trực tiếp bằng gợi ý thực tế, "
    "bám sát hoàn cảnh trước. Chỉ hỏi thêm một câu ngắn ở cuối nếu câu trả lời thật sự cần thêm thông tin; câu hỏi đó là tùy chọn, không bắt buộc.\n"
    "- Khi người dùng chỉ đang tâm sự: có thể ghi nhận cảm xúc một cách tự nhiên, nhưng không ép mọi câu trả lời phải phản chiếu cảm xúc, "
    "mở đầu bằng 'Mình hiểu/Mình cảm nhận', hay kết thúc bằng một câu hỏi. Không giảng đạo.\n"
    "- Nếu một lượt có nhiều tin nhắn liên tiếp, đọc chúng theo đúng thứ tự, giữ lại và xử lý mọi yêu cầu chưa được trả lời. "
    "Tin nhắn sau có thể bổ sung, phàn nàn hoặc sửa cách hiểu của tin trước; lời sửa mới nhất được ưu tiên nhưng không làm mất yêu cầu ban đầu.\n"
    "- Phân biệt người bạn mà người dùng nhắc tới với chính bạn (bot). Các cụm như 'bạn của t/mình/tao' chỉ bạn của người dùng, không phải bot. "
    "Chỉ hỏi làm rõ thật ngắn khi ngữ cảnh vẫn thực sự có hai cách hiểu.\n"
    "- Khi trò chuyện, khéo léo nhắc lại những chi tiết hay kỷ niệm bạn đã nhớ một cách tự nhiên như bạn bè thân thiết, "
    "tuyệt đối không phô diễn kiểu 'tôi nhớ rằng...'.\n"
    "- Nếu người dùng hỏi thẳng hoặc đây là lần đầu trò chuyện, hãy thẳng thắn và vui vẻ nhận mình là người bạn AI "
    "luôn sẵn sàng lắng nghe mọi lúc."
)

NEGATIVE_CONSTRAINTS = (
    "CÁC ĐIỀU CẤM KỴ TUYỆT ĐỐI:\n"
    "- Tránh liệt kê máy móc; được dùng vài bước ngắn, cụ thể khi người dùng cần hướng dẫn thực hành.\n"
    "- CẤM mở đầu câu bằng kiểu mẫu robot như: 'Là một AI...', 'Với tư cách là...', 'Chào bạn!'.\n"
    "- CẤM lặp lại nguyên văn câu nói của người dùng.\n"
    "- CẤM spam biểu tượng cảm xúc (emoji) tràn lan.\n"
    "- CẤM viết dài dòng, lan man hơn mức cần thiết."
)


def get_current_time_str(at: Optional[datetime] = None) -> str:
    """Format current time in Vietnam timezone."""
    now = at.astimezone(VN_TZ) if at is not None else datetime.now(VN_TZ)
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
    display_name: Optional[str],
    core_profile: dict[str, Any],
    style_profile: dict[str, Any],
    relevant_memories: list[Memory],
    summary_content: Optional[str],
    recent_user_messages: list[str],
    is_crisis_active: bool = False,
    is_toxic_active: bool = False,
    is_first_interaction: bool = False,
) -> str:
    """Compose complete system prompt for the conversational turn."""
    sections: list[str] = [PERSONA_CORE]

    # First interaction disclosure
    if is_first_interaction:
        sections.append(
            "LƯU Ý LẦN ĐẦU GẶP GỠ: Đây là tin nhắn đầu tiên của bạn ấy. Nếu họ hỏi một câu cụ thể, "
            "hãy trả lời câu đó trước; có thể giới thiệu thật ngắn mình là người bạn AI sau đó, không để lời chào trì hoãn câu trả lời."
        )

    # Current local time
    sections.append(f"THỜI ĐIỂM HIỆN TẠI:\n- {get_current_time_str()}")

    # Core user profile
    pronouns = core_profile.get("pronouns", {})
    bot_p = pronouns.get("bot", "mình")
    user_p = pronouns.get("user", "bạn")
    profile_lines = []
    if display_name:
        profile_lines.append(f"- Tên gọi của người dùng: {display_name}")
    profile_lines.append(
        f"- Cách xưng hô quen thuộc: bạn xưng là '{bot_p}', gọi người dùng là '{user_p}'."
    )
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

    if is_toxic_active and not is_crisis_active:
        sections.append(
            "HƯỚNG DẪN KHI NGƯỜI DÙNG ĐANG DÙNG NGÔN TỪ THÔ TỤC:\n"
            "- Không lặp lại hay bắt chước từ tục, không chửi lại. Giữ giọng bình tĩnh, ấm áp và nhẹ nhàng ghi nhận cảm xúc đằng sau như bực bội hoặc tức giận."
        )

    # Negative constraints
    sections.append(NEGATIVE_CONSTRAINTS)

    return "\n\n".join(sections)


def build_chat_messages(
    system_prompt: str,
    window_messages: list[Message],
    current_user_text: str = "",
    current_user_messages: Optional[list[str]] = None,
) -> list[dict[str, str]]:
    """Format full prompt payload for LLM completion."""
    payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for msg in window_messages:
        role = "assistant" if msg.role == "assistant" else "user"
        payload.append({"role": role, "content": msg.content})

    # Keep rapid incoming messages separate and chronological so corrections and
    # unanswered requests remain visible as distinct user messages.
    incoming = current_user_messages if current_user_messages is not None else [current_user_text]
    payload.extend({"role": "user", "content": text} for text in incoming if text.strip())

    return payload

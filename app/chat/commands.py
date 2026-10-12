"""Command handlers for privacy and help.

Handles exact-match prefix commands (/help, /nho, /quen) deterministically
without passing them to the LLM.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import User
from app.memory.store import delete_all_user_data, get_all_memories


def is_command(text: str) -> bool:
    """Check if message is an exact-match command."""
    first_token = text.strip().split()[0].lower() if text.strip() else ""
    return first_token in {"/help", "/nho", "/quen"}


async def handle_command(
    session: AsyncSession,
    user: User,
    text: str,
) -> Optional[str]:
    """Execute command if matched, returning response text or None."""
    parts = text.strip().split()
    if not parts:
        return None

    cmd = parts[0].lower()

    if cmd == "/help":
        return (
            "Chào bạn! Mình là người bạn thân AI, luôn ở đây để lắng nghe và trò chuyện cùng bạn. 🌸\n\n"
            "Các lệnh bạn có thể dùng:\n"
            "- /help : Xem giới thiệu và hướng dẫn này.\n"
            "- /nho : Xem lại những điều mình đang nhớ về bạn (minh bạch dữ liệu).\n"
            "- /quen : Xóa toàn bộ dữ liệu, ký ức và lịch sử trò chuyện của bạn khỏi hệ thống."
        )

    if cmd == "/nho":
        memories = await get_all_memories(session, user.id)
        core = user.core_profile or {}
        pronouns = core.get("pronouns", {})

        lines = ["Đây là những gì mình đang nhớ về bạn nè:"]

        name = core.get("name") or user.display_name
        if name:
            lines.append(f"• Tên bạn: {name}")
        if pronouns:
            lines.append(f"• Cách xưng hô: mình xưng '{pronouns.get('bot', 'mình')}' - gọi bạn là '{pronouns.get('user', 'bạn')}'")

        if memories:
            lines.append("\nKý ức dài hạn:")
            for m in memories:
                lines.append(f"• [{m.category}] {m.content}")
        else:
            if len(lines) == 1:
                return "Mình chưa lưu ký ức đặc biệt nào về bạn cả. Cứ thoải mái tâm sự thêm với mình nhé! 😊"

        return "\n".join(lines)

    if cmd == "/quen":
        await delete_all_user_data(session, user.id)
        return (
            "Mình đã xóa toàn bộ ký ức, tin nhắn và dữ liệu của bạn khỏi hệ thống rồi. "
            "Nếu lúc nào bạn muốn quay lại tâm sự, mình luôn chào đón như một khởi đầu mới nhé! 🍃"
        )

    return None

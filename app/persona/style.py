"""Style profiling and mirroring analysis.

Analyzes user messages using statistical heuristics (no LLM calls),
updates style profiles with Exponential Moving Average (EMA),
detects Vietnamese pronouns, and renders natural prompt guidelines.
"""

import re
from typing import Any, Optional

# Vietnamese pronoun pairs regex
PRONOUN_PATTERNS = [
    (r"\b(tớ|cậu)\b", "tớ", "cậu"),
    (r"\b(mình|bạn)\b", "mình", "bạn"),
    (r"\b(tao|mày)\b", "tao", "mày"),
    (r"\b(anh|em)\b", "anh", "em"),
]

# Vietnamese abbreviations
ABBREV_PATTERN = re.compile(
    r"\b(ko|k|hok|dc|đc|bt|j|sao|ng|mn|thui|thôi|nè|m|t|mik|uk|uhm|h|bh)\b",
    re.IGNORECASE,
)

# Common laughter expressions
LAUGH_PATTERNS = [
    (re.compile(r"\bhaha+\b", re.IGNORECASE), "haha"),
    (re.compile(r"\bhihi+\b", re.IGNORECASE), "hihi"),
    (re.compile(r"\bhuhu+\b", re.IGNORECASE), "huhu"),
    (re.compile(r"\bkkk+\b", re.IGNORECASE), "kkk"),
    (re.compile(r"=[\)\(]+"), "=))"),
    (re.compile(r"\^_\^"), "^_^"),
]

# Emoji regex heuristic
EMOJI_PATTERN = re.compile(
    "[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\U0001f300-\U0001f5ff\U0001f600-\U0001f64f\U0001f680-\U0001f6ff]",
    flags=re.UNICODE,
)


def extract_message_features(text: str) -> dict[str, Any]:
    """Extract linguistic and style features from a user message string."""
    clean_text = text.strip()
    words = clean_text.split()
    word_count = len(words)

    # Emoji stats
    emojis = EMOJI_PATTERN.findall(clean_text)
    emoji_count = len(emojis)
    emoji_ratio = emoji_count / max(1, word_count)

    abbrev_count = len(ABBREV_PATTERN.findall(clean_text))
    abbrev_ratio = abbrev_count / max(1, word_count)
    alpha_chars = [c for c in clean_text if c.isalpha()]
    lower_chars = [c for c in alpha_chars if c.islower()]
    lowercase_ratio = len(lower_chars) / max(1, len(alpha_chars))
    detected_laugh = next((label for pattern, label in LAUGH_PATTERNS if pattern.search(clean_text)), None)

    return {
        "word_count": word_count,
        "emoji_count": emoji_count,
        "emoji_ratio": emoji_ratio,
        "abbrev_ratio": abbrev_ratio,
        "lowercase_ratio": lowercase_ratio,
        "has_ellipsis": "..." in clean_text,
        "has_multi_exclamation": bool(re.search(r"!{2,}", clean_text)),
        "has_no_end_period": not clean_text.endswith((".", "!", "?")),
        "detected_laugh": detected_laugh,
    }


def detect_pronouns(text: str) -> Optional[dict[str, str]]:
    """Detect Vietnamese pronoun pairs in text."""
    lower = text.lower()
    for pattern, bot_p, user_p in PRONOUN_PATTERNS:
        if re.search(pattern, lower):
            # If user refers to themselves as 'anh', bot is 'em'
            if bot_p == "anh" and "anh" in lower and "em" not in lower:
                return {"bot": "em", "user": "anh"}
            if bot_p == "anh" and "em" in lower:
                return {"bot": "anh", "user": "em"}
            return {"bot": bot_p, "user": user_p}
    return None


def update_style_profile(
    current_profile: dict[str, Any],
    message_text: str,
    alpha: float = 0.1,
) -> dict[str, Any]:
    """Update user style profile with Exponential Moving Average (EMA).

    new_val = (1 - alpha) * old_val + alpha * observed_val
    """
    obs = extract_message_features(message_text)
    profile = dict(current_profile or {})

    # EMA for word count
    old_words = profile.get("avg_word_count", 15.0)
    profile["avg_word_count"] = round((1 - alpha) * old_words + alpha * obs["word_count"], 2)

    # Keep only stable signals that materially affect response mirroring.
    old_emoji = profile.get("avg_emoji_ratio", 0.05)
    profile["avg_emoji_ratio"] = round((1 - alpha) * old_emoji + alpha * obs["emoji_ratio"], 3)

    return profile


def render_style_guidance(
    style_profile: dict[str, Any],
    recent_user_messages: list[str],
) -> str:
    """Render 4-6 natural lines of mirror guidelines for the prompt."""
    if not style_profile:
        return "- Nói chuyện tự nhiên, gần gũi, câu ngắn vừa phải."

    avg_words = int(style_profile.get("avg_word_count", 15.0))
    # Cap target words between 10 and 60
    target_words = max(10, min(60, avg_words))

    emoji_ratio = style_profile.get("avg_emoji_ratio", 0.05)
    lower_ratio = style_profile.get("avg_lowercase_ratio", 0.9)

    guidelines = []
    # Length mirroring
    guidelines.append(f"- Độ dài trả lời: câu ngắn gọn, tương đương khoảng {target_words} - {target_words + 15} từ, không dông dài.")

    if lower_ratio > 0.8:
        guidelines.append("- Ưa chuộng viết thường tự nhiên, ít trang trọng.")

    # Emoji guidance
    if emoji_ratio < 0.03:
        guidelines.append("- Hạn chế emoji (dùng tối đa 1 emoji hoặc không dùng).")
    else:
        guidelines.append("- Dùng emoji nhẹ nhàng, ấm áp, phù hợp cảm xúc (1-2 cái).")

    laughs = style_profile.get("laugh_styles", {})
    if laughs:
        fav_laugh = max(laughs.items(), key=lambda item: item[1])[0]
        guidelines.append(f"- Nếu có đùa vui, dùng kiểu cười quen thuộc: '{fav_laugh}'.")

    # Recent voice sample
    samples = [m.strip() for m in recent_user_messages if m.strip()][-3:]
    sample_text = ""
    if samples:
        formatted_samples = "\n".join([f'  + "{s}"' for s in samples])
        sample_text = f"\nVí dụ giọng điệu gần nhất của bạn ấy:\n{formatted_samples}"

    return "\n".join(guidelines) + sample_text

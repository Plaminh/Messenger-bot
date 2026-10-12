"""Tests for statistical style analysis, EMA updates, pronoun detection, and mirror guidance."""

from app.persona.style import (
    detect_pronouns,
    extract_message_features,
    render_style_guidance,
    update_style_profile,
)


def test_extract_message_features():
    text = "hôm nay mệt quá haha ko bt nói gì luôn... 😊"
    features = extract_message_features(text)

    assert features["word_count"] > 0
    assert features["detected_laugh"] == "haha"
    assert features["has_ellipsis"] is True
    assert features["emoji_count"] >= 1
    assert features["abbrev_ratio"] > 0.0


def test_detect_pronouns():
    assert detect_pronouns("cậu ơi tớ nhờ cái này") == {"bot": "tớ", "user": "cậu"}
    assert detect_pronouns("bạn ơi mình hỏi chút") == {"bot": "mình", "user": "bạn"}
    assert detect_pronouns("mày đang làm gì đấy") == {"bot": "tao", "user": "mày"}
    assert detect_pronouns("anh đang ở đâu thế") == {"bot": "em", "user": "anh"}
    assert detect_pronouns("thời tiết hôm nay đẹp nhỉ") is None


def test_update_style_profile_ema():
    old_profile = {"avg_word_count": 20.0, "avg_emoji_ratio": 0.0}
    # User message with 10 words and 1 emoji
    msg = "một hai ba bốn năm sáu bảy tám chín mười 😊"

    new_profile = update_style_profile(old_profile, msg, alpha=0.1)

    # Expected EMA for words: 0.9*20 + 0.1*11 = 18 + 1.1 = 19.1
    assert abs(new_profile["avg_word_count"] - 19.1) < 0.2
    assert new_profile["avg_emoji_ratio"] > 0.0


def test_render_style_guidance():
    profile = {
        "avg_word_count": 14.0,
        "avg_emoji_ratio": 0.01,
        "avg_lowercase_ratio": 0.95,
        "laugh_styles": {"haha": 5},
    }
    guidance = render_style_guidance(profile, ["chào cậu nha", "hôm nay rảnh ko"])

    assert "ngắn gọn" in guidance
    assert "Hạn chế emoji" in guidance
    assert "haha" in guidance
    assert "chào cậu nha" in guidance

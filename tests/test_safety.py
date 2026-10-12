"""Tests for crisis safety filters and prompt guidance."""

from app.persona.prompt import assemble_system_prompt
from app.persona.safety import is_crisis


def test_is_crisis_detects_self_harm():
    assert is_crisis("mình muốn tự tử") is True
    assert is_crisis("tôi muốn kết thúc cuộc sống này") is True
    assert is_crisis("mình muốn chết đi cho rồi") is True
    assert is_crisis("tự làm hại bản thân") is True


def test_is_crisis_false_for_normal_text():
    assert is_crisis("hôm nay thời tiết đẹp quá") is False
    assert is_crisis("công việc hôm nay bận rộn thật đấy") is False
    assert is_crisis("cười chết mất thôi") is False


def test_safety_disables_mirror_and_injects_crisis_guidance():
    prompt = assemble_system_prompt(
        core_profile={"name": "Bạn"},
        style_profile={"laugh_styles": {"haha": 10}},
        relevant_memories=[],
        summary_content=None,
        recent_user_messages=["haha vui quá"],
        is_crisis_active=True,  # Crisis mode activated
    )

    assert "CẢNH BÁO KHỦNG HOẢNG" in prompt
    assert "TẮT TOÀN BỘ style mirroring" in prompt
    assert "096 306 1414" in prompt  # Đường dây nóng Ngày Mai
    assert "PHONG CÁCH VÀ NHỊP ĐIỆU CẦN ĐỒNG ĐIỆU" not in prompt

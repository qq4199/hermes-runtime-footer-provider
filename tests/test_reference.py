"""参考实现的测试（不需要 Hermes 源码树）。

    python3 tests/test_reference.py       # 直接跑
    pytest tests/test_reference.py        # 或用 pytest
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference"))

from provider_and_layout import (  # noqa: E402
    format_footer,
    provider_name,
    resolve_display_provider,
    resolve_layout,
)

PROVIDERS = {
    "relay-a": {"base_url": "https://relay-a.example.com/v1"},
    "relay-b": {"base_url": "https://relay-b.example.com/v1/"},
}


def test_resolve_provider_by_base_url():
    """多个自定义端点都归一化成 custom 时，用 base_url 反查真实 key。"""
    assert resolve_display_provider("custom", "https://relay-b.example.com/v1", PROVIDERS) == "relay-b"
    assert resolve_display_provider("custom", "https://relay-a.example.com/v1/", PROVIDERS) == "relay-a"


def test_resolve_provider_falls_back_to_runtime_name():
    """没有 config 条目的内置 provider 原样返回；base_url 为空也不炸。"""
    assert resolve_display_provider("openai", "https://api.openai.com/v1", PROVIDERS) == "openai"
    assert resolve_display_provider("", "", PROVIDERS) == ""
    assert resolve_display_provider(None, None, None) == ""


def test_vendor_prefix_from_model():
    assert provider_name("openai/gpt-5.4") == "openai"
    assert provider_name("qwen3.8-max") == ""


def test_dash_layout():
    out = format_footer(model="qwen3.8-max", provider="relay-b",
                        fields=["provider", "model"], dash_length=13)
    assert out == "\u2015" * 13 + "\nrelay-b / qwen3.8-max", repr(out)


def test_legacy_single_line_layout_unchanged():
    """dash_length=0（默认）必须与上游旧样式逐字节一致。"""
    out = format_footer(model="qwen3.8-max", provider="relay-b", fields=["provider", "model"])
    assert out == "relay-b · qwen3.8-max", repr(out)


def test_missing_fields_are_skipped():
    assert format_footer(model=None, provider=None, fields=["provider", "model"]) == ""
    assert format_footer(model="qwen3.8-max", provider=None, fields=["provider", "model"]) == "qwen3.8-max"


def test_platform_override_wins():
    cfg = resolve_layout([
        {"enabled": True, "fields": ["provider", "model"], "dash_length": 13},
        {"dash_length": 9},
    ])
    assert cfg == {"enabled": True, "fields": ["provider", "model"], "dash_length": 9}, cfg


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"✅ {name}")
            except AssertionError as exc:
                failed += 1
                print(f"❌ {name}: {exc}")
    print(f"\n{len([n for n in globals() if n.startswith('test_')]) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

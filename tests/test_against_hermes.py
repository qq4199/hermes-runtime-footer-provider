"""对现有 Hermes 源码树验证补丁是否已生效（可选，不提供源码树时自动跳过）。

    HERMES_REPO=~/hermes-agent python3 tests/test_against_hermes.py

只需要 gateway/runtime_footer.py（纯标准库），不需要装 Hermes 的依赖。
"""

import os
import sys

REPO = os.path.expanduser(os.environ.get("HERMES_REPO", "~/hermes-agent"))
PATCHED_MARKERS = {
    "gateway/runtime_footer.py": "def resolve_display_provider(",
}


def _skip_if_absent():
    if not os.path.isdir(REPO):
        print(f"SKIP: 没有 Hermes 源码树（{REPO}），跳过集成测试。"
              f"设置 HERMES_REPO=/path/to/hermes-agent 后再跑。")
        return True
    return False


def test_markers_present():
    """补丁标记在位 = patch 已应用（升级后丢了就会失败）。"""
    if _skip_if_absent():
        return
    for rel, needle in PATCHED_MARKERS.items():
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            assert needle in fh.read(), f"{rel} 缺少标记 {needle!r}——补丁没打上或被 update 冲掉了"


def test_real_footer_render():
    """直接调 Hermes 自己的函数，验证 provider 字段与横线排版。"""
    if _skip_if_absent():
        return
    sys.path.insert(0, REPO)
    from gateway.runtime_footer import build_footer_line, resolve_display_provider  # noqa: PLC0415

    cfg = {"display": {"runtime_footer": {
        "enabled": True, "fields": ["provider", "model"], "dash_length": 13}}}
    out = build_footer_line(user_config=cfg, platform_key=None, model="qwen3.8-max",
                            provider="relay-b", context_tokens=0, context_length=None)
    assert out == "\u2015" * 13 + "\nrelay-b / qwen3.8-max", repr(out)

    providers = {"relay-a": {"base_url": "https://relay-a.example.com/v1"},
                 "relay-b": {"base_url": "https://relay-b.example.com/v1"}}
    assert resolve_display_provider("custom", "https://relay-b.example.com/v1", providers) == "relay-b"


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
    sys.exit(1 if failed else 0)

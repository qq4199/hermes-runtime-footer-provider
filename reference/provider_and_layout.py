"""参考实现：Hermes Agent 运行时页脚的 provider 字段 + 横线排版。

这不是可直接 import 进 Hermes 的模块，而是补丁里「新增逻辑」的独立拷贝，
用来在没有 Hermes 源码树的情况下跑测试、或供其它项目参考。

真实生效方式是 patches/ 下的 patch（改 gateway/runtime_footer.py、
gateway/run_turn*.py 三处）。
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

_SEP = " · "
_DEFAULT_FIELDS: tuple[str, ...] = ("model", "context_pct", "cwd")


def provider_name(model: Optional[str]) -> str:
    """从 ``vendor/model`` 里取 vendor 前缀（``openai/gpt-5.4`` → ``openai``）。"""
    if not model:
        return ""
    parts = model.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else ""


def resolve_display_provider(
    provider: Optional[str],
    base_url: Optional[str],
    config_providers: Optional[dict],
) -> str:
    """把运行时归一化后的 provider 名映射回 config.yaml 里的真实 key。

    Hermes 运行时把所有用户自定义端点归一化成 ``custom``（``custom-2`` →
    ``custom``），所以只看名字无法区分多个自定义端点。这里用**实际请求的
    base_url** 去比对 ``providers.<key>.base_url`` 反查真实 key；fallback
    切换后依然正确（备用端点自己的 base_url 匹配它自己的 key）。没有对应
    config 条目的内置 provider 原样返回。
    """
    burl = str(base_url or "").rstrip("/")
    if burl and isinstance(config_providers, dict):
        for key, val in config_providers.items():
            if isinstance(val, dict) and str(val.get("base_url") or "").rstrip("/") == burl:
                return str(key)
    return str(provider or "")


def format_footer(
    *,
    model: Optional[str],
    provider: Optional[str] = None,
    fields: Iterable[str] = _DEFAULT_FIELDS,
    dash_length: int = 0,
) -> str:
    """最小化的页脚渲染（只保留理解布局/字段所需的逻辑）。

    ``dash_length > 0`` 时输出「横线 + 换行 + 信息」，否则保持上游的 `` · `` 单行。
    """
    values = {
        "provider": (provider or provider_name(model) or "").strip(),
        "model": model.rsplit("/", 1)[-1] if model else "",
    }
    parts = [values[f] for f in fields if values.get(f)]
    if not parts:
        return ""
    info = " / ".join(parts)
    if dash_length and dash_length > 0:
        return "―" * int(dash_length) + "\n" + info
    return _SEP.join(parts)


def resolve_layout(sections: Iterable[Optional[dict[str, Any]]]) -> dict[str, Any]:
    """按顺序叠加 footer 配置段（全局 → 单平台），返回生效值。"""
    resolved: dict[str, Any] = {"enabled": False, "fields": list(_DEFAULT_FIELDS), "dash_length": 0}
    for section in sections:
        if not isinstance(section, dict):
            continue
        if "enabled" in section:
            resolved["enabled"] = bool(section.get("enabled"))
        if isinstance(section.get("fields"), list) and section["fields"]:
            resolved["fields"] = [str(f) for f in section["fields"]]
        if section.get("dash_length"):
            resolved["dash_length"] = int(section["dash_length"])
    return resolved

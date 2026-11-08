# Hermes 运行时页脚增强：真实 provider 名 + 移动端友好排版

给 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的**网关运行时页脚**（回复末尾那行 `model · context% · cwd`）加两个东西：

1. **`provider` 字段** —— 显示**实际命中**的 provider（用 base_url 反查 config 里的 key），而不是运行时的 `custom`；
2. **`dash_length` 排版** —— 一条横线 + 换行 + 信息，手机上不会再挤成一行糊在一起。

> 非官方补丁：改的是上游 Python 源码，`hermes update` 会冲掉，需要重新打（patch 在 `patches/`）。

---

## 它解决什么问题

**① 分不清走的是哪个自定义端点。**
Hermes 运行时把每个用户自定义端点归一化成 `custom`（`custom-2` → `custom`）。如果你配了两个以上中转/自建端点，页脚只会告诉你 `custom`——两个端点看起来一模一样，看不出这轮真正用谁回答，切 fallback 之后更看不出来。

上游的 `model` 字段只会把 `vendor/model` 的 vendor 前缀砍掉，并不会去认 provider。

**② 一行太长，移动端难读。**
默认 `model · context_pct · cwd` 用 ` · ` 串成一行，在微信/飞书这种窄容器里换行位置随机，看起来很脏。

---

## 效果

前 → 后（配置 `fields: [provider, model]`、`dash_length: 13`）：

```
custom-2 · qwen3.8-max                     ← 改动前（provider 认不出真实端点）
```

```
―――――――――――――
relay-b / qwen3.8-max                      ← 改动后（反查到真实 key + 横线排版）
```

切到备用端点会自动跟着变（备用端点自己的 base_url 匹配它自己的 config key）：

```
―――――――――――――
relay-a / qwen3.8-max
```

`dash_length: 0`（默认）时逐字节保持上游旧样式，纯增量，不影响没开这个功能的人。

---

## 三处改动

补丁总共 ~90 行，逻辑很简单：

**1) `gateway/runtime_footer.py` —— 新增 provider 反查 + 横线渲染**

```python
def resolve_display_provider(provider, base_url, config_providers) -> str:
    """把运行时归一化后的 provider 名映射回 config.yaml 里的真实 key。"""
    burl = str(base_url or "").rstrip("/")
    if burl and isinstance(config_providers, dict):
        for key, val in config_providers.items():
            if isinstance(val, dict) and str(val.get("base_url") or "").rstrip("/") == burl:
                return str(key)          # 命中真实 key
    return str(provider or "")           # 内置 provider 原样返回
```

渲染侧：`fields` 里可以写 `provider`；`dash_length > 0` 时输出 `"―" * dash_length + "\n" + " / ".join(parts)`，否则走原来的 ` · `。

**2) `gateway/run_turn_runner.py` —— 把运行时的 base_url 带进结果**

```python
usage = {
    ...
    "provider": getattr(agent, "provider", None) if agent else None,
    # 运行时端点：页脚的 provider 字段靠它反查真实 key
    "base_url": getattr(agent, "base_url", "") if agent else "",
}
```

**3) `gateway/run_turn.py`（v0.21）/ `gateway/run_turn_persistence.py`（v0.23+）—— 调用处先反查再渲染**

```python
from gateway.runtime_footer import build_footer_line as _bfl, resolve_display_provider as _rdp
_footer_provider = _rdp(
    agent_result.get("provider"),
    agent_result.get("base_url"),
    _load_gateway_config().get("providers") or {},
)
return _bfl(..., provider=_footer_provider, ...)
```

---

## 安装

```bash
# 1. 打补丁（默认 ~/.hermes/hermes-agent，按源码结构自动选版本）
scripts/apply-patch.sh /path/to/hermes-agent

# 2. 配置（config.yaml 的 display 段）
#    注意：写着 display.runtime_footer 的地方就是全局，platforms.<p>.runtime_footer 覆盖它

# 3. 重启网关让新代码生效
hermes gateway restart

# 4. 验证
HERMES_REPO=/path/to/hermes-agent python3 tests/test_against_hermes.py
```

`config.yaml`：

```yaml
display:
  runtime_footer:
    enabled: true
    fields: [provider, model]      # 支持 provider / model / served_model / context_pct / latency / cwd
    dash_length: 13                # >0 = 横线 + 换行；0 或省略 = 上游旧的一行
  platforms:
    feishu:                        # 单平台覆盖：同一套键，只写要改的
      runtime_footer:
        dash_length: 9
```

改 `display.runtime_footer` 也可能被 `dash_length` 之类的自定义键卡一下（`hermes config set` 会提示 "not a recognized config key"，加 `--force` 照写，运行时正常读取）。

---

## 版本适配

上游把 `gateway/run.py` 拆成了多个文件，补丁锚点位置随版本变化：

| 上游版本 | 补丁 | footer 调用点 | turn 结果字典 |
|---|---|---|---|
| v0.21.x | `patches/v0.21.x-runtime-footer-provider.patch` | `gateway/run_turn.py::_hmwa_runtime_footer_line` | `gateway/run_turn_runner.py` 的 `usage` |
| v0.23.0（canary `93dd243`） | `patches/v0.23.0-runtime-footer-provider.patch` | `gateway/run_turn_persistence.py::_hmwa_runtime_footer_line` | 同上（`provider` 上游已有，只补 `base_url`） |

版本差太大 `git apply` 会拒绝。三种改动的意图很短，照着上面的片段在新代码里找等价锚点手工合入即可（`grep -n "_hmwa_runtime_footer_line" gateway/*.py` 是入口）。

> 顺带一提：`provider` 这类字段如果哪天上游原生实现了，这个补丁就该退役——先 `git log -S resolve_display_provider` / 看 `runtime_footer.py` 有没有 provider 渲染器再决定。

---

## 测试

```bash
python3 tests/test_reference.py                      # 7 项，不需要 Hermes 源码树
HERMES_REPO=~/hermes-agent python3 tests/test_against_hermes.py   # 集成：直接调 Hermes 自己的函数
```

覆盖点：base_url 反查（多端点 + fallback + 内置 provider 回落）、`vendor/model` 前缀、横线布局、**旧布局逐字节回归**、空字段跳过、平台覆盖优先级。

`reference/provider_and_layout.py` 是新增逻辑的独立拷贝，纯标准库，方便抄到别的项目或用来看懂行为。

---

## 已知限制

- 改上游源码 → `hermes update` 冲掉，需要重打（本仓库的 patch 就是为此留的快照）。
- 只影响**网关**最终回复（微信/飞书/桌面走网关的会话）；桌面 App 自己的 UI、`chat -q` 这类一次性回合不带页脚。
- `latency`、`cwd` 等字段仍是上游原生实现，补丁没碰。
- 横线用的是 U+2015（`―`），不是减号；如果某个客户端把它渲染成删除线，改成 `-` 或 `─` 即可（`format_runtime_footer` 里一处）。

## License

MIT。补丁与参考实现是本仓库的原创增量代码，不含 Hermes Agent 源码本体（Hermes 为 MIT，版权 Nous Research）。

---

## English

A small patch for **Hermes Agent**'s gateway runtime footer:

- **`provider` field** — shows the provider key that actually served the turn. Hermes normalizes every user-defined endpoint to `custom` at runtime, so with more than one relay/custom endpoint the bare name is useless. The patch matches the *runtime* `base_url` against `providers.<key>.base_url` in `config.yaml` and recovers the real key — correct across fallback switches too.
- **`dash_length` layout** — a rule line plus the info on the next line (reads better on narrow mobile clients), with ` / ` as the separator. `dash_length: 0` keeps the upstream single-line output byte-for-byte.

```yaml
display:
  runtime_footer:
    enabled: true
    fields: [provider, model]
    dash_length: 13
```

```
―――――――――――――
relay-b / qwen3.8-max
```

Install: `scripts/apply-patch.sh <hermes-repo>` → set the config → `hermes gateway restart`. Patches are version-specific (v0.21.x / v0.23.0); the three edits are documented above for manual porting. Unofficial: an upstream update wipes it, re-apply afterwards.

#!/usr/bin/env bash
# 给 Hermes 源码树打上 runtime-footer provider 补丁。
#
#   scripts/apply-patch.sh [hermes-repo]
#
# 默认路径 $HOME/.hermes/hermes-agent。打补丁只改 Python 源码，
# 生效需要重启网关（gateway restart）。
set -euo pipefail

REPO="${1:-$HOME/.hermes/hermes-agent}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$REPO/.git" ]; then
  echo "✗ $REPO 不是 git 仓库（需要能 git apply 的 Hermes 源码树）" >&2
  exit 1
fi

# 按源码结构挑对应版本的补丁：
#   v0.23+  footer 调用点拆到 run_turn_persistence.py
#   v0.21.x 拆出 gateway/run_turn.py
#   v0.20.x 全部还在 gateway/run.py（26k 行单文件）
if [ -f "$REPO/gateway/run_turn_persistence.py" ]; then
  PATCH="$HERE/patches/v0.23.0-runtime-footer-provider.patch"
elif [ -f "$REPO/gateway/run_turn.py" ]; then
  PATCH="$HERE/patches/v0.21.x-runtime-footer-provider.patch"
else
  PATCH="$HERE/patches/v0.20.0-runtime-footer-provider.patch"
fi

echo "repo  : $REPO"
echo "patch : $(basename "$PATCH")"

if git -C "$REPO" apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "✓ 补丁已在位，无需重复应用"
  exit 0
fi

if ! git -C "$REPO" apply --check "$PATCH" 2>/dev/null; then
  echo "✗ 上下文不匹配（上游版本差太多）。请按 README「手动移植」三处改动手动合入。" >&2
  exit 2
fi

git -C "$REPO" apply "$PATCH"
echo "✓ 已应用。接下来："
echo "  1) 在 config.yaml 里启用（见 README「配置」）"
echo "  2) hermes gateway restart   # 让网关加载新代码"
echo "  3) HERMES_REPO=$REPO python3 tests/test_against_hermes.py"

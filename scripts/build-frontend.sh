#!/usr/bin/env bash
# 构建仓内前端源码（web/）并把产物同步到仓库根目录的 public/。
#
# 后端与原生部署都直接使用 public/ 中的自建产物（settings.FRONTEND_PATH 默认即指向它），
# 不再从 GitHub Release 下载前端。注意 web/public/ 是 Vite 的静态资源源目录，与本产物目录无关。
# 依赖安装默认使用 web/yarn.lock 的冻结锁文件，保证构建可重复；本地调试可用 --no-frozen 放宽。

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/web"
DIST_DIR="$PROJECT_ROOT/public"

skip_install=0
frozen=1

show_usage() {
  cat <<'EOF'
用法：
  ./scripts/build-frontend.sh                 安装依赖并构建，产物同步到 public/
  ./scripts/build-frontend.sh --skip-install   跳过依赖安装，直接构建
  ./scripts/build-frontend.sh --no-frozen      依赖安装不使用 --frozen-lockfile
  ./scripts/build-frontend.sh help             显示本帮助

环境变量：
  FRONTEND_PACKAGE_MANAGER   指定包管理器命令，默认自动探测 yarn / corepack yarn
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --skip-install) skip_install=1 ;;
    --no-frozen) frozen=0 ;;
    help|--help|-h) show_usage; exit 0 ;;
    *) printf '未知参数：%s\n\n' "$1" >&2; show_usage >&2; exit 2 ;;
  esac
  shift
done

if [[ ! -d "$WEB_DIR" ]]; then
  printf '未找到前端源码目录：%s\n' "$WEB_DIR" >&2
  exit 1
fi

# 探测包管理器：优先使用与 yarn.lock 匹配的 yarn，其次通过 corepack 调用。
resolve_package_manager() {
  if [[ -n "${FRONTEND_PACKAGE_MANAGER:-}" ]]; then
    printf '%s\n' "$FRONTEND_PACKAGE_MANAGER"
    return 0
  fi
  if command -v yarn >/dev/null 2>&1; then
    printf '%s\n' "yarn"
    return 0
  fi
  if command -v corepack >/dev/null 2>&1; then
    printf '%s\n' "corepack yarn"
    return 0
  fi
  return 1
}

if ! package_manager="$(resolve_package_manager)"; then
  printf '未找到 yarn，也未找到 corepack。请安装 Node.js 20.19+ 后重试。\n' >&2
  exit 1
fi

# 读取后端版本，作为前端产物版本标记（version.txt 供后端与 Doctor 识别）。
read_app_version() {
  sed -n "s/^APP_VERSION[[:space:]]*=[[:space:]]*['\"]\([^'\"]*\)['\"].*/\1/p" "$PROJECT_ROOT/version.py" | head -n 1
}

cd "$WEB_DIR"

if [[ "$skip_install" -eq 0 ]]; then
  printf '==> 安装前端依赖（%s）\n' "$package_manager"
  if [[ "$frozen" -eq 1 ]]; then
    # shellcheck disable=SC2086
    $package_manager install --frozen-lockfile
  else
    # shellcheck disable=SC2086
    $package_manager install
  fi
fi

printf '==> 构建前端\n'
# shellcheck disable=SC2086
$package_manager build

if [[ ! -f "$WEB_DIR/dist/index.html" ]]; then
  printf '前端构建产物缺少 dist/index.html，构建可能失败。\n' >&2
  exit 1
fi

app_version="$(read_app_version)"
if [[ -n "$app_version" ]]; then
  printf '%s\n' "$app_version" > "$WEB_DIR/dist/version.txt"
fi

printf '==> 同步产物到 public/\n'
mkdir -p "$DIST_DIR"
find "$DIST_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "$WEB_DIR/dist/." "$DIST_DIR/"

printf '完成：%s\n' "$DIST_DIR"

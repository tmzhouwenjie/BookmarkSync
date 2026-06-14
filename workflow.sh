#!/bin/bash
# BookmarkSync 发布工作流脚本
# 用法:
#   bash workflow.sh release v1.2.0    # 发布新版本
#   bash workflow.sh sync              # 仅同步代码到 Mac
#   bash workflow.sh build             # 仅在 Mac 上构建 DMG
#
# 流程: Linux 开发 → Mac 构建 → GitHub Release

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAC_USER="zhouwenjie"
MAC_HOST="192.168.31.235"
MAC_PROJ="~/projects/BookmarkSync"
REMOTE="zhouwenjie@192.168.31.235"

# ─── 检查依赖 ─────────────────────────────────────────
check_deps() {
  if ! command -v ssh &>/dev/null; then echo "❌ 需要 ssh"; exit 1; fi
  if ! command -v rsync &>/dev/null; then echo "❌ 需要 rsync"; exit 1; fi
}

# ─── 同步代码到 Mac（从 Linux） ─────────────────────
sync_to_mac() {
  echo "📤 同步代码到 Mac..."
  rsync -avz --delete --exclude='.git' --exclude='.venv' \
    --exclude='.build_env' --exclude='dist' --exclude='build' \
    "$SCRIPT_DIR/" "$REMOTE:$MAC_PROJ/"
  echo "✅ 代码已同步到 Mac: $MAC_PROJ"
}

# ─── 在 Mac 上构建 DMG ──────────────────────────────
build_dmg() {
  echo "🔨 在 Mac 上构建 DMG..."
  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ
    source .build_env/bin/activate
    rm -rf dist build
    bash build.sh 2>&1 | tail -5
  "
  echo "✅ DMG 构建完成"
}

# ─── 创建 Release ──────────────────────────────────
create_release() {
  local version="$1"
  if [ -z "$version" ]; then
    echo "❌ 用法: bash workflow.sh release <版本号> (如 v1.2.0)"
    exit 1
  fi

  echo "📦 发布 $version"

  # 1. 更新代码中的版本号
  echo "  更新版本号..."
  sed -i "s/^APP_VERSION = '.*'/APP_VERSION = '${version#v}'/" "$SCRIPT_DIR/app.py"
  sed -i "s/^const APP_VERSION = '.*'/const APP_VERSION = '${version#v}'/" "$SCRIPT_DIR/BookmarkSync.html"
  sed -i "s/^VERSION=\".*\"/VERSION=\"${version#v}\"/" "$SCRIPT_DIR/build.sh"

  # 2. 提交
  echo "  提交代码..."
  cd "$SCRIPT_DIR"
  git add -A
  git commit -m "chore: bump version to $version"

  # 3. 同步到 Mac
  sync_to_mac

  # 4. Mac 上提交并推送
  echo "  Mac 推送代码到 GitHub..."
  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ
    git push origin main 2>&1
  "

  # 5. Mac 上构建 DMG
  build_dmg

  # 6. Mac 上创建 GitHub Release 并上传 DMG
  echo "  🚀 创建 GitHub Release..."
  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ

    # 获取发布说明
    NOTES=\"## 更新内容\\n\\n"

    # 删除同名的旧 Release（如有）
    gh release delete $version --yes 2>/dev/null || true

    # 创建 Release 并上传 DMG
    gh release create $version \\
      --title \"BookmarkSync $version\" \\
      --notes \"\$NOTES\" \\
      dist/BookmarkSync_${version#v}.dmg 2>&1
  "

  echo ""
  echo "=========================================="
  echo "  ✅ Release $version 发布完成!"
  echo "  https://github.com/tmzhouwenjie/BookmarkSync/releases/tag/$version"
  echo "=========================================="
}

# ─── 主入口 ─────────────────────────────────────────
case "${1:-help}" in
  sync)    check_deps; sync_to_mac ;;
  build)   check_deps; build_dmg ;;
  release) check_deps; create_release "$2" ;;
  *)
    echo "用法:"
    echo "  bash workflow.sh sync              # 同步代码到 Mac"
    echo "  bash workflow.sh build             # 在 Mac 上构建 DMG"
    echo "  bash workflow.sh release <版本号>  # 一键发布 (如 v1.2.0)"
    ;;
esac

#!/bin/bash
# BookmarkSync 发布工作流脚本
# 用法:
#   bash workflow.sh release v1.2.0    # 发布新版本
#   bash workflow.sh sync              # 仅同步代码到 Mac
#   bash workflow.sh build             # 仅在 Mac 上构建 DMG
#
# 流程: Linux 开发 -> Mac 构建 -> GitHub Release
# 每次构建完成后自动清理 Mac 上的构建产物

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE="zhouwenjie@192.168.31.235"
MAC_PROJ="~/projects/BookmarkSync"

check_deps() {
  if ! command -v ssh &>/dev/null; then echo "需要 ssh"; exit 1; fi
  if ! command -v rsync &>/dev/null; then echo "需要 rsync"; exit 1; fi
}

sync_to_mac() {
  echo "同步代码到 Mac..."
  rsync -avz --delete --exclude='.git' --exclude='.venv' \
    --exclude='.build_env' --exclude='dist' --exclude='build' \
    "$SCRIPT_DIR/" "$REMOTE:$MAC_PROJ/"
  echo "完成"
}

build_dmg() {
  echo "在 Mac 上构建 DMG..."
  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ
    source .build_env/bin/activate
    rm -rf dist build
    bash build.sh 2>&1 | tail -5
  "
  clean_mac
}

clean_mac() {
  echo "清理 Mac 构建产物..."
  ssh "$REMOTE" "
    cd $MAC_PROJ
    rm -rf dist build *.spec
  "
  echo "完成"
}

create_release() {
  local version="$1"
  if [ -z "$version" ]; then
    echo "用法: bash workflow.sh release <版本号>"
    exit 1
  fi
  echo "发布 $version"

  sed -i "s/^APP_VERSION = '.*'/APP_VERSION = '${version#v}'/" "$SCRIPT_DIR/app.py"
  sed -i "s/^const APP_VERSION = '.*'/const APP_VERSION = '${version#v}'/" "$SCRIPT_DIR/BookmarkSync.html"
  sed -i "s/^VERSION=\".*\"/VERSION=\"${version#v}\"/" "$SCRIPT_DIR/build.sh"

  cd "$SCRIPT_DIR"
  git add -A
  git commit -m "chore: bump version to $version"

  sync_to_mac

  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ
    git push origin main 2>&1
  "

  build_dmg

  ssh "$REMOTE" "
    export PATH=\"\$PATH:/opt/homebrew/bin\"
    cd $MAC_PROJ
    gh release delete $version --yes 2>/dev/null || true
    gh release create $version \
      --title \"BookmarkSync $version\" \
      --notes \"请查看 Release 说明\" \
      dist/BookmarkSync_${version#v}.dmg 2>&1
  "

  clean_mac

  echo "完成: https://github.com/tmzhouwenjie/BookmarkSync/releases/tag/$version"
}

case "${1:-help}" in
  sync)    check_deps; sync_to_mac ;;
  build)   check_deps; build_dmg ;;
  release) check_deps; create_release "$2" ;;
  *)
    echo "用法:"
    echo "  bash workflow.sh sync              # 同步代码到 Mac"
    echo "  bash workflow.sh build             # 在 Mac 上构建 DMG"
    echo "  bash workflow.sh release <版本号>   # 一键发布"
    ;;
esac

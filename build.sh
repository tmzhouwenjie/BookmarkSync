#!/bin/bash
# Bookmark Sync — macOS .app + .dmg 构建脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="BookmarkSync"
APP_DISPLAY="Bookmark Sync"
VERSION="1.0.0"
BUILD_DIR="$SCRIPT_DIR/build"
DIST_DIR="$SCRIPT_DIR/dist"

echo "=========================================="
echo "  Bookmark Sync — macOS 构建脚本"
echo "=========================================="

# 激活虚拟环境
if [ -d "$SCRIPT_DIR/.build_env" ]; then
    echo "→ 激活构建环境..."
    source "$SCRIPT_DIR/.build_env/bin/activate"
fi

# 检查 PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "→ 安装 PyInstaller..."
    pip install pyinstaller
fi

# 清理旧构建
echo "→ 清理旧构建文件..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

# 用 PyInstaller 构建 .app
echo "→ 构建 .app 应用包..."
ICON_OPT=""
if [ -f "$SCRIPT_DIR/icon.icns" ]; then
    ICON_OPT="--icon $SCRIPT_DIR/icon.icns"
fi
pyinstaller \
    --name "$APP_NAME" \
    --windowed \
    --onedir \
    --add-data "BookmarkSync.html:." \
    $ICON_OPT \
    --osx-bundle-identifier "com.bookmarksync.app" \
    --clean \
    --noconfirm \
    app.py 2>&1

# 检查构建结果
APP_PATH="$DIST_DIR/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ .app 构建失败"
    exit 1
fi
echo "✅ .app 构建成功: $APP_PATH"

# 创建 DMG
echo "→ 创建 DMG 磁盘镜像..."
DMG_DIR="$DIST_DIR/dmg_temp"
mkdir -p "$DMG_DIR"

# 拷贝 .app 到临时目录
cp -R "$APP_PATH" "$DMG_DIR/"

# 创建 Applications 快捷方式
ln -s /Applications "$DMG_DIR/Applications"

# 生成 DMG
DMG_PATH="$DIST_DIR/${APP_NAME}_${VERSION}.dmg"
hdiutil create \
    -volname "$APP_DISPLAY" \
    -srcfolder "$DMG_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

# 清理临时目录
rm -rf "$DMG_DIR"

# 输出结果
DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
echo ""
echo "=========================================="
echo "  构建完成!"
echo "=========================================="
echo "  .app: $APP_PATH"
echo "  .dmg: $DMG_PATH ($DMG_SIZE)"
echo "=========================================="

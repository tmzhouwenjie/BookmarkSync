#!/bin/bash
# Bookmark Sync 安装脚本

echo "============================================"
echo "  Bookmark Sync 安装程序"
echo "============================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python 版本: $PYTHON_VERSION"

# 检查 tkinter
python3 -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  未找到 tkinter，正在安装..."
    brew install python-tk
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 创建启动脚本
LAUNCHER="$SCRIPT_DIR/launch.sh"
cat > "$LAUNCHER" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
python3 main.py
EOF
chmod +x "$LAUNCHER"

echo ""
echo "✅ 安装完成！"
echo ""
echo "启动方式："
echo "  1. 终端运行: cd $SCRIPT_DIR && python3 main.py"
echo "  2. 或者:     bash $LAUNCHER"
echo ""
echo "⚠️  首次运行前请授予终端「完全磁盘访问权限」："
echo "   系统设置 → 隐私与安全性 → 完全磁盘访问权限"
echo ""

# 尝试直接启动
echo "是否现在启动？(y/n)"
read answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    cd "$SCRIPT_DIR"
    python3 main.py
fi

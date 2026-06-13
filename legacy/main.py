#!/usr/bin/env python3
"""Bookmark Sync — Safari ↔ Edge 书签同步工具。

用法:
    python3 main.py

首次运行前，请确保已授予终端「完全磁盘访问权限」：
    系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 添加终端应用
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    """检查必要依赖。"""
    issues = []

    # Python 版本
    if sys.version_info < (3, 8):
        issues.append(f"Python 版本过低 ({sys.version})，需要 3.8+")

    # tkinter
    try:
        import tkinter
    except ImportError:
        issues.append("缺少 tkinter 模块。安装方法: brew install python-tk")

    # plistlib (标准库)
    try:
        import plistlib
    except ImportError:
        issues.append("缺少 plistlib 模块")

    return issues


def check_permissions():
    """检查文件访问权限。"""
    from pathlib import Path
    safari_plist = Path.home() / "Library" / "Safari" / "Bookmarks.plist"

    if not safari_plist.exists():
        return "Safari 书签文件不存在"

    try:
        with open(safari_plist, "rb") as f:
            f.read(1)
        return None  # 权限正常
    except PermissionError:
        return (
            "❌ 无法读取 Safari 书签！\n\n"
            "请在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」中，\n"
            "添加你正在使用的终端应用（如 Terminal、iTerm2 或 QoderWork），\n"
            "然后重新启动终端后再运行此程序。"
        )


def main():
    print("=" * 50)
    print("  Bookmark Sync — Safari ↔ Edge 书签同步工具")
    print("=" * 50)

    # 检查依赖
    issues = check_dependencies()
    if issues:
        print("\n⚠️  依赖检查发现问题:")
        for issue in issues:
            print(f"  • {issue}")
        sys.exit(1)
    print("✅ 依赖检查通过")

    # 检查权限
    perm_issue = check_permissions()
    if perm_issue:
        print(f"\n{perm_issue}")
        print("\n程序将继续启动，但 Safari 书签将显示为不可用。")
        print("你可以仍然使用 Edge 书签管理和导出功能。\n")
    else:
        print("✅ Safari 书签权限正常")

    # 检查 Edge
    from pathlib import Path
    edge_path = Path.home() / "Library" / "Application Support" / "Microsoft Edge" / "Default" / "Bookmarks"
    if edge_path.exists():
        print("✅ Edge 书签文件已找到")
    else:
        print("⚠️  Edge 书签文件不存在，请确认已安装 Microsoft Edge")

    print("\n正在启动 GUI...")

    # 启动 GUI
    from ui import main as launch_ui
    launch_ui()


if __name__ == "__main__":
    main()

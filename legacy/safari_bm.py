"""Safari 书签读写模块。

读取 ~/Library/Safari/Bookmarks.plist（需要完全磁盘访问权限）。
"""

from __future__ import annotations
import plistlib
import shutil
import os
from pathlib import Path
from typing import List
from datetime import datetime

from bookmark import BookmarkItem

SAFARI_PLIST = Path.home() / "Library" / "Safari" / "Bookmarks.plist"
BACKUP_DIR = Path.home() / ".bookmark_sync" / "backups" / "safari"


def _convert_node(node: dict, parent_path: str = "") -> BookmarkItem:
    """递归将 Safari plist 节点转为 BookmarkItem。"""
    node_type = node.get("WebBookmarkType", "")

    if node_type == "WebBookmarkTypeLeaf":
        url = node.get("URLString", "")
        title = node.get("URIDictionary", {}).get("title", url)
        return BookmarkItem(name=title, url=url, source_path=parent_path)

    elif node_type == "WebBookmarkTypeList":
        title = node.get("Title", "")
        current_path = f"{parent_path}/{title}" if parent_path else title
        children = []
        for child in node.get("Children", []):
            children.append(_convert_node(child, current_path))
        return BookmarkItem(name=title, children=children, source_path=current_path)

    elif node_type == "WebBookmarkTypeProxy":
        current_path = parent_path
        children = []
        for child in node.get("Children", []):
            children.append(_convert_node(child, current_path))
        return BookmarkItem(name="Safari", children=children, source_path="")

    return BookmarkItem(name="Unknown")


def read_safari_bookmarks() -> List[BookmarkItem]:
    """读取 Safari 书签，返回顶层书签节点列表。"""
    if not SAFARI_PLIST.exists():
        raise FileNotFoundError(f"Safari 书签文件不存在: {SAFARI_PLIST}")

    try:
        with open(SAFARI_PLIST, "rb") as f:
            data = plistlib.load(f)
    except PermissionError:
        raise PermissionError(
            "无法读取 Safari 书签。请在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」"
            "中授权给当前终端应用。"
        )

    root = _convert_node(data)
    return root.children


def read_safari_tree() -> BookmarkItem:
    """读取 Safari 完整书签树。"""
    if not SAFARI_PLIST.exists():
        raise FileNotFoundError(f"Safari 书签文件不存在: {SAFARI_PLIST}")
    try:
        with open(SAFARI_PLIST, "rb") as f:
            data = plistlib.load(f)
    except PermissionError:
        raise PermissionError(
            "无法读取 Safari 书签。请在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」"
            "中授权给当前终端应用。"
        )
    return _convert_node(data)


def _to_plist_node(item: BookmarkItem) -> dict:
    """将 BookmarkItem 转回 Safari plist 格式。"""
    if item.is_bookmark:
        return {
            "WebBookmarkType": "WebBookmarkTypeLeaf",
            "URLString": item.url,
            "URIDictionary": {"title": item.name},
            "WebBookmarkUUID": "",
        }
    else:
        children = [_to_plist_node(c) for c in item.children]
        node = {
            "WebBookmarkType": "WebBookmarkTypeList",
            "Title": item.name,
            "Children": children,
            "WebBookmarkUUID": "",
        }
        return node


def write_safari_bookmarks(roots: List[BookmarkItem]):
    """将书签写回 Safari plist（自动备份原文件）。"""
    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"Bookmarks_{timestamp}.plist"
    shutil.copy2(SAFARI_PLIST, backup_path)

    # 构建 plist 数据
    children = [_to_plist_node(item) for item in roots]
    plist_data = {
        "WebBookmarkFileVersion": 1,
        "WebBookmarkType": "WebBookmarkTypeProxy",
        "Children": children,
    }

    # 写入
    with open(SAFARI_PLIST, "wb") as f:
        plistlib.dump(plist_data, f)


def get_safari_info() -> dict:
    """获取 Safari 书签的基本信息。"""
    try:
        tree = read_safari_tree()
        total = tree.count_all()
        folders = tree.folder_count()
        return {
            "available": True,
            "total_bookmarks": total,
            "total_folders": folders,
            "path": str(SAFARI_PLIST),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

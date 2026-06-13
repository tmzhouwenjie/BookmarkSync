"""Microsoft Edge 书签读写模块。

读取 ~/Library/Application Support/Microsoft Edge/Default/Bookmarks（标准 JSON）。
"""

from __future__ import annotations
import json
import shutil
import os
from pathlib import Path
from typing import List
from datetime import datetime

from bookmark import BookmarkItem

EDGE_DIR = Path.home() / "Library" / "Application Support" / "Microsoft Edge"
EDGE_BOOKMARKS = EDGE_DIR / "Default" / "Bookmarks"
BACKUP_DIR = Path.home() / ".bookmark_sync" / "backups" / "edge"

# Chrome epoch: 微秒自 1601-01-01 起
_CHROME_EPOCH_OFFSET = 11644473600


def _chrome_ts_to_str(ts_str: str) -> str:
    """将 Chrome 时间戳转为可读字符串。"""
    try:
        ts = int(ts_str)
        unix_ts = ts / 1_000_000 - _CHROME_EPOCH_OFFSET
        return datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ""


def _convert_node(node: dict, parent_path: str = "") -> BookmarkItem:
    """递归将 Edge JSON 节点转为 BookmarkItem。"""
    name = node.get("name", "")
    node_type = node.get("type", "")
    current_path = f"{parent_path}/{name}" if parent_path else name

    if node_type == "url":
        url = node.get("url", "")
        return BookmarkItem(name=name, url=url, source_path=parent_path)

    elif node_type == "folder":
        children = []
        for child in node.get("children", []):
            children.append(_convert_node(child, current_path))
        return BookmarkItem(name=name, children=children, source_path=current_path)

    return BookmarkItem(name=name, source_path=parent_path)


def _to_edge_node(item: BookmarkItem) -> dict:
    """将 BookmarkItem 转回 Edge JSON 格式。"""
    if item.is_bookmark:
        return {
            "date_added": "0",
            "date_last_used": "0",
            "guid": "",
            "id": "",
            "name": item.name,
            "type": "url",
            "url": item.url,
        }
    else:
        children = [_to_edge_node(c) for c in item.children]
        return {
            "date_added": "0",
            "date_last_used": "0",
            "date_modified": "0",
            "guid": "",
            "id": "",
            "name": item.name,
            "type": "folder",
            "children": children,
        }


def read_edge_bookmarks() -> List[BookmarkItem]:
    """读取 Edge 书签，返回顶层书签节点列表（收藏夹栏 + 其他 + 移动设备）。"""
    if not EDGE_BOOKMARKS.exists():
        raise FileNotFoundError(f"Edge 书签文件不存在: {EDGE_BOOKMARKS}")

    with open(EDGE_BOOKMARKS, "r", encoding="utf-8") as f:
        data = json.load(f)

    roots = data.get("roots", {})
    result = []

    for key in ("bookmark_bar", "other", "synced"):
        root_node = roots.get(key)
        if root_node:
            item = _convert_node(root_node)
            # 重命名根节点为中文
            name_map = {
                "bookmark_bar": "收藏夹栏",
                "other": "其他收藏夹",
                "synced": "移动设备收藏夹",
            }
            item.name = name_map.get(key, item.name)
            item.source_path = item.name
            result.append(item)

    return result


def read_edge_tree() -> BookmarkItem:
    """读取 Edge 完整书签树。"""
    roots = read_edge_bookmarks()
    return BookmarkItem(name="Edge", children=roots, source_path="")


def write_edge_bookmarks(roots: List[BookmarkItem]):
    """将书签写回 Edge JSON（自动备份原文件）。"""
    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"Bookmarks_{timestamp}.json"
    shutil.copy2(EDGE_BOOKMARKS, backup_path)

    # 读取原始数据（保留 checksum 等元数据）
    with open(EDGE_BOOKMARKS, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 映射回 Edge 的 roots 结构
    key_map = {"收藏夹栏": "bookmark_bar", "其他收藏夹": "other", "移动设备收藏夹": "synced"}

    for root_item in roots:
        edge_key = key_map.get(root_item.name)
        if edge_key and edge_key in data.get("roots", {}):
            original = data["roots"][edge_key]
            new_node = _to_edge_node(root_item)
            # 保留原始元数据
            new_node["date_added"] = original.get("date_added", "0")
            new_node["date_modified"] = original.get("date_modified", "0")
            new_node["guid"] = original.get("guid", "")
            new_node["id"] = original.get("id", "")
            data["roots"][edge_key] = new_node

    # 写入
    with open(EDGE_BOOKMARKS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_edge_info() -> dict:
    """获取 Edge 书签的基本信息。"""
    try:
        roots = read_edge_bookmarks()
        tree = BookmarkItem(name="Edge", children=roots)
        total = tree.count_all()
        folders = tree.folder_count()
        return {
            "available": True,
            "total_bookmarks": total,
            "total_folders": folders,
            "path": str(EDGE_BOOKMARKS),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

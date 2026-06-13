"""书签数据模型 — Safari 和 Edge 的通用书签表示。"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import copy


@dataclass
class BookmarkItem:
    """通用书签条目，同时表示书签和文件夹。"""
    name: str
    url: str = ""
    children: List[BookmarkItem] = field(default_factory=list)
    # 来源信息（用于 UI 显示）
    source_path: str = ""  # 在树中的完整路径，如 "收藏夹栏/技术/Python"

    @property
    def is_folder(self) -> bool:
        return len(self.children) > 0 or self.url == ""

    @property
    def is_bookmark(self) -> bool:
        return self.url != ""

    def count_all(self) -> int:
        """递归统计所有书签数量（不含文件夹）。"""
        if self.is_bookmark:
            return 1
        return sum(child.count_all() for child in self.children)

    def folder_count(self) -> int:
        """递归统计文件夹数量。"""
        count = 0
        if self.is_folder:
            count = 1
        for child in self.children:
            count += child.folder_count()
        return count

    def find_by_url(self, url: str) -> Optional[BookmarkItem]:
        if self.url == url:
            return self
        for child in self.children:
            result = child.find_by_url(url)
            if result:
                return result
        return None

    def find_by_name(self, name: str) -> Optional[BookmarkItem]:
        if self.name == name:
            return self
        for child in self.children:
            result = child.find_by_name(name)
            if result:
                return result
        return None

    def deep_copy(self) -> BookmarkItem:
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        d = {"name": self.name, "url": self.url}
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> BookmarkItem:
        children = [cls.from_dict(c) for c in d.get("children", [])]
        return cls(name=d.get("name", ""), url=d.get("url", ""), children=children)


def flatten_bookmarks(node: BookmarkItem, path: str = "") -> List[dict]:
    """将书签树展平为 [{url, title, path}] 列表。"""
    result = []
    if node.is_bookmark:
        result.append({"url": node.url, "title": node.name, "path": path or node.source_path})
    current_path = f"{path}/{node.name}" if path else node.name
    for child in node.children:
        result.extend(flatten_bookmarks(child, current_path))
    return result


def get_folder_tree(node: BookmarkItem, depth: int = 0) -> List[dict]:
    """获取文件夹树结构 [{name, path, depth, bookmark_count}]。"""
    result = []
    if node.is_folder:
        result.append({
            "name": node.name,
            "path": node.source_path or node.name,
            "depth": depth,
            "bookmark_count": node.count_all(),
        })
    for child in node.children:
        result.extend(get_folder_tree(child, depth + 1))
    return result

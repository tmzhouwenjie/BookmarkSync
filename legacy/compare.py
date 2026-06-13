"""书签对比引擎 — 递归比较两棵书签树，输出差异项。"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote

from bookmark import BookmarkItem, flatten_bookmarks


def _normalize_url(url: str) -> str:
    """URL 标准化：去除末尾斜杠、fragment、多余空格。"""
    url = url.strip()
    try:
        parsed = urlparse(url)
        # 重建，去掉 fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        # 去掉末尾斜杠
        normalized = normalized.rstrip("/")
        return normalized
    except Exception:
        return url


def _collect_urls(node: BookmarkItem, path: str = "") -> Dict[str, dict]:
    """递归收集所有 URL → {title, path, node_ref}。"""
    result = {}
    if node.is_bookmark:
        key = _normalize_url(node.url)
        if key and key not in result:
            result[key] = {
                "title": node.name,
                "url": node.url,
                "path": path or node.source_path,
                "node": node,
            }
    current_path = f"{path}/{node.name}" if path else node.name
    for child in node.children:
        child_result = _collect_urls(child, current_path)
        for k, v in child_result.items():
            if k not in result:
                result[k] = v
    return result


def _collect_folders(node: BookmarkItem, path: str = "") -> Dict[str, BookmarkItem]:
    """递归收集所有文件夹路径 → 节点。"""
    result = {}
    if node.is_folder and node.name:
        current_path = f"{path}/{node.name}" if path else node.name
        result[current_path] = node
    else:
        current_path = path
    for child in node.children:
        child_result = _collect_folders(child, current_path)
        result.update(child_result)
    return result


@dataclass
class DiffItem:
    """单条差异记录。"""
    url: str
    title: str
    path_safari: str = ""
    path_edge: str = ""
    diff_type: str = ""  # safari_only, edge_only, both, title_diff


@dataclass
class CompareResult:
    """对比结果。"""
    safari_only: List[DiffItem] = field(default_factory=list)
    edge_only: List[DiffItem] = field(default_factory=list)
    both: List[DiffItem] = field(default_factory=list)
    title_diffs: List[DiffItem] = field(default_factory=list)
    safari_duplicates: List[List[dict]] = field(default_factory=list)
    edge_duplicates: List[List[dict]] = field(default_factory=list)

    @property
    def total_safari(self) -> int:
        return len(self.safari_only) + len(self.both)

    @property
    def total_edge(self) -> int:
        return len(self.edge_only) + len(self.both)

    @property
    def summary(self) -> str:
        return (
            f"Safari 独有: {len(self.safari_only)} 条  |  "
            f"Edge 独有: {len(self.edge_only)} 条  |  "
            f"两者共有: {len(self.both)} 条  |  "
            f"标题不同: {len(self.title_diffs)} 条"
        )


def compare(safari_tree: BookmarkItem, edge_tree: BookmarkItem) -> CompareResult:
    """对比 Safari 和 Edge 书签树。"""
    result = CompareResult()

    safari_urls = _collect_urls(safari_tree)
    edge_urls = _collect_urls(edge_tree)

    safari_keys = set(safari_urls.keys())
    edge_keys = set(edge_urls.keys())

    # Safari 独有
    for key in sorted(safari_keys - edge_keys):
        info = safari_urls[key]
        result.safari_only.append(DiffItem(
            url=info["url"],
            title=info["title"],
            path_safari=info["path"],
            diff_type="safari_only",
        ))

    # Edge 独有
    for key in sorted(edge_keys - safari_keys):
        info = edge_urls[key]
        result.edge_only.append(DiffItem(
            url=info["url"],
            title=info["title"],
            path_edge=info["path"],
            diff_type="edge_only",
        ))

    # 两者共有（检查标题差异）
    for key in sorted(safari_keys & edge_keys):
        s_info = safari_urls[key]
        e_info = edge_urls[key]
        item = DiffItem(
            url=s_info["url"],
            title=s_info["title"],
            path_safari=s_info["path"],
            path_edge=e_info["path"],
            diff_type="both",
        )
        result.both.append(item)
        if s_info["title"] != e_info["title"]:
            item.diff_type = "title_diff"
            result.title_diffs.append(item)

    # 检测重复书签
    result.safari_duplicates = _find_duplicates(safari_tree)
    result.edge_duplicates = _find_duplicates(edge_tree)

    return result


def _find_duplicates(node: BookmarkItem) -> List[List[dict]]:
    """查找重复书签（相同 URL 出现多次）。"""
    all_bookmarks = flatten_bookmarks(node)
    url_groups: Dict[str, List[dict]] = {}

    for bm in all_bookmarks:
        key = _normalize_url(bm["url"])
        if key:
            url_groups.setdefault(key, []).append(bm)

    return [items for items in url_groups.values() if len(items) > 1]


def find_duplicates_in_tree(tree: BookmarkItem) -> List[List[dict]]:
    """对外接口：查找书签树中的重复项。"""
    return _find_duplicates(tree)

"""书签同步引擎 — 在 Safari 和 Edge 之间同步书签。"""

from __future__ import annotations
from typing import List, Optional
from copy import deepcopy

from bookmark import BookmarkItem
from compare import CompareResult, _normalize_url, _collect_urls


def add_bookmark_to_tree(tree: BookmarkItem, name: str, url: str,
                         target_folder: str = "") -> bool:
    """向书签树中添加一条书签。

    Args:
        tree: 目标书签树根节点
        name: 书签名称
        url: 书签 URL
        target_folder: 目标文件夹路径（如 "收藏夹栏/技术"），空则添加到根下第一个文件夹
    """
    if target_folder:
        target = _find_folder(tree, target_folder)
        if target:
            target.children.append(BookmarkItem(name=name, url=url, source_path=target_folder))
            return True

    # 未找到目标文件夹，添加到根节点的第一个子文件夹
    if tree.children:
        first_folder = tree.children[0]
        path = first_folder.source_path or first_folder.name
        first_folder.children.append(BookmarkItem(name=name, url=url, source_path=path))
        return True
    return False


def add_folder_to_tree(tree: BookmarkItem, folder_name: str,
                       parent_path: str = "") -> Optional[BookmarkItem]:
    """向书签树中添加一个文件夹。"""
    parent = _find_folder(tree, parent_path) if parent_path else tree
    if parent:
        new_folder = BookmarkItem(name=folder_name, source_path=f"{parent_path}/{folder_name}")
        parent.children.append(new_folder)
        return new_folder
    return None


def delete_bookmark_from_tree(tree: BookmarkItem, url: str) -> bool:
    """从书签树中删除指定 URL 的书签。"""
    return _delete_from_node(tree, url)


def delete_by_name_from_tree(tree: BookmarkItem, name: str, folder_path: str) -> bool:
    """从指定文件夹中删除书签。"""
    folder = _find_folder(tree, folder_path)
    if folder:
        for i, child in enumerate(folder.children):
            if child.name == name and child.url != "":
                folder.children.pop(i)
                return True
    return False


def update_bookmark_in_tree(tree: BookmarkItem, old_url: str,
                            new_name: str = "", new_url: str = "") -> bool:
    """更新书签的名称或 URL。"""
    item = tree.find_by_url(old_url)
    if item:
        if new_name:
            item.name = new_name
        if new_url:
            item.url = new_url
        return True
    return False


def sync_safari_to_edge(safari_tree: BookmarkItem, edge_tree: BookmarkItem,
                        diff: CompareResult, selected_indices: Optional[List[int]] = None):
    """将 Safari 独有的书签同步到 Edge。

    Args:
        safari_tree: Safari 书签树
        edge_tree: Edge 书签树
        diff: 对比结果
        selected_indices: 要同步的书签索引列表，None 表示全部
    """
    items_to_sync = diff.safari_only
    if selected_indices is not None:
        items_to_sync = [items_to_sync[i] for i in selected_indices if i < len(items_to_sync)]

    safari_urls = _collect_urls(safari_tree)
    edge_default = edge_tree.children[0] if edge_tree.children else edge_tree

    for item in items_to_sync:
        normalized = _normalize_url(item.url)
        # 确保不重复添加
        edge_urls = _collect_urls(edge_tree)
        if normalized in edge_urls:
            continue

        # 查找 Safari 中对应的原始节点
        safari_node = safari_tree.find_by_url(item.url)
        if safari_node:
            # 尝试在 Edge 中创建对应的文件夹结构
            folder = _ensure_folder_path(edge_tree, item.path_safari, edge_tree)
            if folder:
                folder.children.append(deepcopy(safari_node))


def sync_edge_to_safari(edge_tree: BookmarkItem, safari_tree: BookmarkItem,
                        diff: CompareResult, selected_indices: Optional[List[int]] = None):
    """将 Edge 独有的书签同步到 Safari。"""
    items_to_sync = diff.edge_only
    if selected_indices is not None:
        items_to_sync = [items_to_sync[i] for i in selected_indices if i < len(items_to_sync)]

    safari_default = safari_tree.children[0] if safari_tree.children else safari_tree

    for item in items_to_sync:
        normalized = _normalize_url(item.url)
        safari_urls = _collect_urls(safari_tree)
        if normalized in safari_urls:
            continue

        edge_node = edge_tree.find_by_url(item.url)
        if edge_node:
            folder = _ensure_folder_path(safari_tree, item.path_edge, safari_tree)
            if folder:
                folder.children.append(deepcopy(edge_node))


def sync_all(safari_tree: BookmarkItem, edge_tree: BookmarkItem, diff: CompareResult):
    """双向同步：Safari → Edge + Edge → Safari。"""
    sync_safari_to_edge(safari_tree, edge_tree, diff)
    # 重新计算差异
    from compare import compare
    new_diff = compare(safari_tree, edge_tree)
    sync_edge_to_safari(edge_tree, safari_tree, new_diff)


def deduplicate_tree(tree: BookmarkItem) -> int:
    """去除书签树中的重复书签（保留第一次出现的）。返回删除数量。"""
    seen_urls = set()
    removed = 0

    def _dedup_node(node: BookmarkItem):
        nonlocal removed
        to_remove = []
        for i, child in enumerate(node.children):
            if child.is_bookmark:
                key = _normalize_url(child.url)
                if key in seen_urls:
                    to_remove.append(i)
                    removed += 1
                else:
                    seen_urls.add(key)
            else:
                _dedup_node(child)
        # 从后往前删除，避免索引偏移
        for i in reversed(to_remove):
            node.children.pop(i)

    _dedup_node(tree)
    return removed


# ─── 内部辅助函数 ────────────────────────────────────────────

def _find_folder(node: BookmarkItem, path: str) -> Optional[BookmarkItem]:
    """根据路径查找文件夹。"""
    if not path:
        return node
    parts = [p for p in path.split("/") if p]
    current = node
    for part in parts:
        found = False
        for child in current.children:
            if child.name == part and child.is_folder:
                current = child
                found = True
                break
        if not found:
            # 尝试模糊匹配
            for child in current.children:
                if child.name.lower() == part.lower():
                    current = child
                    found = True
                    break
        if not found:
            return None
    return current


def _ensure_folder_path(tree: BookmarkItem, path: str,
                        default_root: BookmarkItem) -> BookmarkItem:
    """确保目标文件夹路径存在，不存在则创建。"""
    if not path:
        return default_root

    parts = [p for p in path.split("/") if p]
    if not parts:
        return default_root

    # 尝试在 tree 中找到根级匹配
    current = None
    root_name = parts[0]
    for child in tree.children:
        if child.name == root_name:
            current = child
            break

    if current is None:
        current = default_root
        start_idx = 0
    else:
        start_idx = 1

    for part in parts[start_idx:]:
        found = False
        for child in current.children:
            if child.name == part:
                current = child
                found = True
                break
        if not found:
            new_folder = BookmarkItem(
                name=part,
                source_path=f"{current.source_path}/{part}",
            )
            current.children.append(new_folder)
            current = new_folder

    return current


def _delete_from_node(node: BookmarkItem, url: str) -> bool:
    """递归删除指定 URL 的书签。"""
    for i, child in enumerate(node.children):
        if child.is_bookmark and _normalize_url(child.url) == _normalize_url(url):
            node.children.pop(i)
            return True
        if child.is_folder:
            if _delete_from_node(child, url):
                return True
    return False

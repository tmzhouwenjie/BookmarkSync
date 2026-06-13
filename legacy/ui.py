"""Tkinter GUI — 书签对比与同步界面。"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Optional, List
import json
import os
import sys
import plistlib
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bookmark import BookmarkItem, flatten_bookmarks
from safari_bm import read_safari_tree, write_safari_bookmarks, get_safari_info
from edge_bm import read_edge_bookmarks, read_edge_tree, write_edge_bookmarks, get_edge_info
from compare import compare, CompareResult, find_duplicates_in_tree
from sync import (
    sync_safari_to_edge, sync_edge_to_safari, sync_all,
    deduplicate_tree, add_bookmark_to_tree, delete_bookmark_from_tree,
    update_bookmark_in_tree, add_folder_to_tree,
)

# ─── 颜色常量 ─────────────────────────────────────────────
COLORS = {
    "safari_only": "#E8A838",   # 橙色 - Safari 独有
    "edge_only": "#5B9BD5",     # 蓝色 - Edge 独有
    "both": "#6AAE6A",          # 绿色 - 两者共有
    "title_diff": "#D67BFF",    # 紫色 - 标题不同
    "folder": "#888888",        # 灰色 - 文件夹
    "duplicate": "#FF6B6B",     # 红色 - 重复项
    "bg_dark": "#1E1E1E",
    "bg_light": "#2D2D2D",
    "fg": "#E0E0E0",
    "accent": "#0078D4",
}


class BookmarkSyncApp:
    """书签同步工具主窗口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bookmark Sync — Safari ↔ Edge 书签同步工具")
        self.root.geometry("1200x750")
        self.root.minsize(900, 600)

        # 数据
        self.safari_tree: Optional[BookmarkItem] = None
        self.edge_tree: Optional[BookmarkItem] = None
        self.diff_result: Optional[CompareResult] = None
        self.safari_url_set: set = set()
        self.edge_url_set: set = set()

        self._setup_styles()
        self._build_ui()
        self._load_data()

    # ─── 样式 ────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Title.TLabel", font=("SF Pro Display", 16, "bold"))
        style.configure("Status.TLabel", font=("SF Pro Text", 11))
        style.configure("Accent.TButton", font=("SF Pro Text", 11, "bold"))
        style.configure("Toolbar.TFrame", background=COLORS["bg_dark"])
        style.configure("Treeview", font=("SF Pro Text", 12), rowheight=28)
        style.configure("Treeview.Heading", font=("SF Pro Text", 12, "bold"))

    # ─── UI 构建 ─────────────────────────────────────────

    def _build_ui(self):
        # 主容器
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── 顶部工具栏 ──
        toolbar = ttk.Frame(main)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        self.btn_refresh = ttk.Button(toolbar, text="🔄 刷新", command=self._load_data)
        self.btn_refresh.pack(side=tk.LEFT, padx=2)

        self.btn_import = ttk.Button(toolbar, text="📂 导入Safari文件",
                                     command=self._import_safari_from_file)
        self.btn_import.pack(side=tk.LEFT, padx=2)

        self.btn_compare = ttk.Button(toolbar, text="🔍 对比", command=self._do_compare)
        self.btn_compare.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_s2e = ttk.Button(toolbar, text="Safari → Edge", command=self._sync_s2e)
        self.btn_s2e.pack(side=tk.LEFT, padx=2)

        self.btn_e2s = ttk.Button(toolbar, text="Edge → Safari", command=self._sync_e2s)
        self.btn_e2s.pack(side=tk.LEFT, padx=2)

        self.btn_sync_all = ttk.Button(toolbar, text="⇄ 双向同步", command=self._sync_all)
        self.btn_sync_all.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_dedup = ttk.Button(toolbar, text="🗑 一键去重", command=self._do_dedup)
        self.btn_dedup.pack(side=tk.LEFT, padx=2)

        self.btn_export = ttk.Button(toolbar, text="💾 导出 HTML", command=self._do_export)
        self.btn_export.pack(side=tk.LEFT, padx=2)

        # ── 信息栏 ──
        info_frame = ttk.Frame(main)
        info_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_safari_info = ttk.Label(info_frame, text="Safari: 加载中...",
                                         style="Status.TLabel")
        self.lbl_safari_info.pack(side=tk.LEFT, padx=8)

        self.lbl_edge_info = ttk.Label(info_frame, text="Edge: 加载中...",
                                       style="Status.TLabel")
        self.lbl_edge_info.pack(side=tk.RIGHT, padx=8)

        # ── 双栏对比区域 ──
        paned = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Safari 面板
        safari_frame = ttk.LabelFrame(paned, text="  Safari 书签  ")
        paned.add(safari_frame, weight=1)

        self.safari_search = ttk.Entry(safari_frame)
        self.safari_search.pack(fill=tk.X, padx=4, pady=4)
        self.safari_search.insert(0, "🔍 搜索...")
        self.safari_search.bind("<FocusIn>", lambda e: self._clear_placeholder(self.safari_search))
        self.safari_search.bind("<KeyRelease>", lambda e: self._filter_tree("safari"))

        self.safari_tree_widget = ttk.Treeview(safari_frame, selectmode="browse", show="tree")
        safari_scroll = ttk.Scrollbar(safari_frame, orient=tk.VERTICAL,
                                      command=self.safari_tree_widget.yview)
        self.safari_tree_widget.configure(yscrollcommand=safari_scroll.set)
        self.safari_tree_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        safari_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=4)

        self.safari_tree_widget.bind("<Button-3>", lambda e: self._show_context_menu(e, "safari"))
        self.safari_tree_widget.bind("<Double-1>", lambda e: self._on_double_click("safari"))

        # Edge 面板
        edge_frame = ttk.LabelFrame(paned, text="  Edge 书签  ")
        paned.add(edge_frame, weight=1)

        self.edge_search = ttk.Entry(edge_frame)
        self.edge_search.pack(fill=tk.X, padx=4, pady=4)
        self.edge_search.insert(0, "🔍 搜索...")
        self.edge_search.bind("<FocusIn>", lambda e: self._clear_placeholder(self.edge_search))
        self.edge_search.bind("<KeyRelease>", lambda e: self._filter_tree("edge"))

        self.edge_tree_widget = ttk.Treeview(edge_frame, selectmode="browse", show="tree")
        edge_scroll = ttk.Scrollbar(edge_frame, orient=tk.VERTICAL,
                                    command=self.edge_tree_widget.yview)
        self.edge_tree_widget.configure(yscrollcommand=edge_scroll.set)
        self.edge_tree_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        edge_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=4)

        self.edge_tree_widget.bind("<Button-3>", lambda e: self._show_context_menu(e, "edge"))
        self.edge_tree_widget.bind("<Double-1>", lambda e: self._on_double_click("edge"))

        # 配置标签颜色
        for tree in (self.safari_tree_widget, self.edge_tree_widget):
            tree.tag_configure("safari_only", foreground=COLORS["safari_only"])
            tree.tag_configure("edge_only", foreground=COLORS["edge_only"])
            tree.tag_configure("both", foreground=COLORS["both"])
            tree.tag_configure("title_diff", foreground=COLORS["title_diff"])
            tree.tag_configure("folder", foreground=COLORS["folder"])
            tree.tag_configure("duplicate", foreground=COLORS["duplicate"])

        # ── 右键菜单 ──
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="✏️ 编辑", command=self._edit_selected)
        self.context_menu.add_command(label="➕ 添加书签", command=self._add_bookmark)
        self.context_menu.add_command(label="📁 添加文件夹", command=self._add_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑 删除", command=self._delete_selected)

        self._context_source = ""

        # ── 底部状态栏 ──
        self.status_var = tk.StringVar(value="就绪 — 点击「对比」查看差异")
        status_bar = ttk.Label(main, textvariable=self.status_var, style="Status.TLabel",
                               relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(4, 0))

    # ─── 数据加载 ─────────────────────────────────────────

    def _load_data(self):
        """加载 Safari 和 Edge 书签数据。"""
        self.root.config(cursor="wait")
        self.root.update()

        try:
            self.safari_tree = read_safari_tree()
            info = self.safari_tree
            self.lbl_safari_info.config(
                text=f"Safari: {info.count_all()} 条书签, {info.folder_count()} 个文件夹"
            )
        except PermissionError as e:
            self.lbl_safari_info.config(text="Safari: ❌ 无权限（需完全磁盘访问权限）")
            self.safari_tree = BookmarkItem(name="Safari")
            messagebox.showwarning("权限不足", str(e))
        except FileNotFoundError:
            self.lbl_safari_info.config(text="Safari: ❌ 书签文件不存在")
            self.safari_tree = BookmarkItem(name="Safari")
        except Exception as e:
            self.lbl_safari_info.config(text=f"Safari: ❌ {e}")
            self.safari_tree = BookmarkItem(name="Safari")

        try:
            self.edge_tree = read_edge_tree()
            info = self.edge_tree
            self.lbl_edge_info.config(
                text=f"Edge: {info.count_all()} 条书签, {info.folder_count()} 个文件夹"
            )
        except FileNotFoundError:
            self.lbl_edge_info.config(text="Edge: ❌ 书签文件不存在")
            self.edge_tree = BookmarkItem(name="Edge")
        except Exception as e:
            self.lbl_edge_info.config(text=f"Edge: ❌ {e}")
            self.edge_tree = BookmarkItem(name="Edge")

        # 填充树
        self._populate_tree(self.safari_tree_widget, self.safari_tree)
        self._populate_tree(self.edge_tree_widget, self.edge_tree)

        # 收集 URL 集合（用于对比高亮）
        self.safari_url_set = self._collect_url_set(self.safari_tree)
        self.edge_url_set = self._collect_url_set(self.edge_tree)

        self.root.config(cursor="")

        # 如果 Safari 为空，提示用户
        if self.safari_tree.count_all() == 0:
            self.status_var.set(
                f"⚠️ Safari 书签为空（可能无权限） — "
                f"请点击「📂 导入Safari文件」手动加载  |  "
                f"Edge {self.edge_tree.count_all()} 条"
            )
        else:
            self.status_var.set(f"已加载 — Safari {self.safari_tree.count_all()} 条 | "
                               f"Edge {self.edge_tree.count_all()} 条")

    def _import_safari_from_file(self):
        """从用户选择的 Bookmarks.plist 文件导入 Safari 书签。"""
        path = filedialog.askopenfilename(
            parent=self.root,
            title="选择 Safari Bookmarks.plist 文件",
            filetypes=[("Plist 文件", "*.plist"), ("所有文件", "*.*")],
            initialdir=str(Path.home() / "Desktop"),
        )
        if not path:
            return

        try:
            from safari_bm import _convert_node
            with open(path, "rb") as f:
                data = plistlib.load(f)
            self.safari_tree = _convert_node(data)
            self.lbl_safari_info.config(
                text=f"Safari: {self.safari_tree.count_all()} 条书签 (从文件导入)"
            )
            # 重新填充和对比
            self.safari_url_set = self._collect_url_set(self.safari_tree)
            self._populate_tree(self.safari_tree_widget, self.safari_tree)
            self.diff_result = None  # 需要重新对比
            self.status_var.set(
                f"✅ 已从文件导入 Safari 书签: {self.safari_tree.count_all()} 条 — "
                f"点击「对比」查看差异"
            )
        except Exception as e:
            messagebox.showerror("导入失败", f"无法解析该文件:\n{e}")

    def _collect_url_set(self, tree: BookmarkItem) -> set:
        """收集书签树中所有 URL。"""
        from compare import _normalize_url
        urls = set()
        flat = flatten_bookmarks(tree)
        for bm in flat:
            urls.add(_normalize_url(bm["url"]))
        return urls

    # ─── 树填充 ───────────────────────────────────────────

    def _populate_tree(self, tree_widget: ttk.Treeview, root_item: BookmarkItem):
        """递归填充 TreeView。"""
        tree_widget.delete(*tree_widget.get_children())

        for child in root_item.children:
            self._add_tree_node(tree_widget, "", child)

    def _add_tree_node(self, tree_widget: ttk.Treeview, parent_id: str,
                       item: BookmarkItem):
        """递归添加节点到 TreeView。"""
        from compare import _normalize_url

        if item.is_folder:
            display = f"📁 {item.name}  ({item.count_all()})"
            tags = ("folder",)
        else:
            display = f"🔗 {item.name}"
            # 根据对比结果设置标签
            norm_url = _normalize_url(item.url)
            in_safari = norm_url in self.safari_url_set
            in_edge = norm_url in self.edge_url_set
            if in_safari and in_edge:
                tags = ("both",)
            elif in_safari and not in_edge:
                tags = ("safari_only",)
            elif not in_safari and in_edge:
                tags = ("edge_only",)
            else:
                tags = ()

        node_id = tree_widget.insert(parent_id, tk.END, text=display, tags=tags)

        # 将数据附加到节点（通过 item 配置）
        tree_widget.item(node_id, values=(item.url, item.name, item.source_path))

        for child in item.children:
            self._add_tree_node(tree_widget, node_id, child)

    # ─── 对比 ─────────────────────────────────────────────

    def _do_compare(self):
        """执行书签对比。"""
        if not self.safari_tree or not self.edge_tree:
            messagebox.showwarning("提示", "请先加载书签数据")
            return

        self.root.config(cursor="wait")
        self.root.update()

        self.diff_result = compare(self.safari_tree, self.edge_tree)

        # 重新填充树（带颜色标记）
        self._populate_tree(self.safari_tree_widget, self.safari_tree)
        self._populate_tree(self.edge_tree_widget, self.edge_tree)

        # 更新状态栏
        dup_info = ""
        if self.diff_result.safari_duplicates:
            dup_info += f" | Safari 重复: {len(self.diff_result.safari_duplicates)} 组"
        if self.diff_result.edge_duplicates:
            dup_info += f" | Edge 重复: {len(self.diff_result.edge_duplicates)} 组"

        self.status_var.set(
            f"对比完成 — {self.diff_result.summary}{dup_info}"
        )

        self.root.config(cursor="")

        # 弹出摘要
        msg = (
            f"Safari 独有: {len(self.diff_result.safari_only)} 条\n"
            f"Edge 独有: {len(self.diff_result.edge_only)} 条\n"
            f"两者共有: {len(self.diff_result.both)} 条\n"
            f"标题不同: {len(self.diff_result.title_diffs)} 条\n"
        )
        if self.diff_result.safari_duplicates:
            msg += f"\nSafari 重复: {len(self.diff_result.safari_duplicates)} 组"
        if self.diff_result.edge_duplicates:
            msg += f"\nEdge 重复: {len(self.diff_result.edge_duplicates)} 组"

        messagebox.showinfo("对比结果", msg)

    # ─── 同步 ─────────────────────────────────────────────

    def _sync_s2e(self):
        """Safari → Edge 同步。"""
        # 检查 Safari 是否有数据
        if self.safari_tree.count_all() == 0:
            messagebox.showwarning(
                "Safari 书签为空",
                "Safari 书签未加载（可能无权限读取）。\n\n"
                "解决方案：\n"
                "1. 去「系统设置 → 隐私与安全性 → 完全磁盘访问权限」授权终端\n"
                "2. 或点击工具栏「📂 导入Safari文件」手动加载 Bookmarks.plist\n\n"
                "提示：你可以用 Finder 将 ~/Library/Safari/Bookmarks.plist\n"
                "复制到桌面，然后通过「导入Safari文件」按钮加载。"
            )
            return

        if not self.diff_result:
            self._do_compare()

        count = len(self.diff_result.safari_only)
        if count == 0:
            messagebox.showinfo("同步", "Safari 没有需要同步到 Edge 的书签，两者已一致。")
            return

        if not messagebox.askyesno("确认同步",
                                    f"确定要将 {count} 条 Safari 独有书签同步到 Edge？\n\n"
                                    "操作前会自动备份。"):
            return

        try:
            sync_safari_to_edge(self.safari_tree, self.edge_tree, self.diff_result)
            self._save_edge()
            self._load_data()
            self.status_var.set(f"✅ 已同步 {count} 条书签: Safari → Edge")
        except Exception as e:
            messagebox.showerror("同步失败", f"Safari → Edge 同步出错:\n{e}")
            import traceback
            traceback.print_exc()

    def _sync_e2s(self):
        """Edge → Safari 同步。"""
        if not self.diff_result:
            self._do_compare()

        count = len(self.diff_result.edge_only)
        if count == 0:
            messagebox.showinfo("同步", "Edge 没有需要同步到 Safari 的书签，两者已一致。")
            return

        if not messagebox.askyesno("确认同步",
                                    f"确定要将 {count} 条 Edge 独有书签同步到 Safari？\n\n"
                                    "操作前会自动备份。"):
            return

        try:
            sync_edge_to_safari(self.edge_tree, self.safari_tree, self.diff_result)
            self._save_safari()
            self._load_data()
            self.status_var.set(f"✅ 已同步 {count} 条书签: Edge → Safari")
        except Exception as e:
            messagebox.showerror("同步失败", f"Edge → Safari 同步出错:\n{e}")
            import traceback
            traceback.print_exc()

    def _sync_all(self):
        """双向同步。"""
        if self.safari_tree.count_all() == 0:
            messagebox.showwarning(
                "Safari 书签为空",
                "Safari 书签未加载，无法进行双向同步。\n"
                "请先通过「📂 导入Safari文件」加载书签。"
            )
            return

        if not self.diff_result:
            self._do_compare()

        s2e = len(self.diff_result.safari_only)
        e2s = len(self.diff_result.edge_only)

        if s2e == 0 and e2s == 0:
            messagebox.showinfo("同步", "两个浏览器的书签已经完全一致")
            return

        if not messagebox.askyesno("确认双向同步",
                                    f"Safari → Edge: {s2e} 条\n"
                                    f"Edge → Safari: {e2s} 条\n\n"
                                    "操作前会自动备份。"):
            return

        try:
            sync_all(self.safari_tree, self.edge_tree, self.diff_result)
            self._save_safari()
            self._save_edge()
            self._load_data()
            self.status_var.set(f"✅ 双向同步完成: Safari→Edge {s2e} 条, Edge→Safari {e2s} 条")
        except Exception as e:
            messagebox.showerror("同步失败", f"双向同步出错:\n{e}")
            import traceback
            traceback.print_exc()

    # ─── 去重 ─────────────────────────────────────────────

    def _do_dedup(self):
        """一键去重。"""
        safari_dups = find_duplicates_in_tree(self.safari_tree)
        edge_dups = find_duplicates_in_tree(self.edge_tree)

        if not safari_dups and not edge_dups:
            messagebox.showinfo("去重", "没有发现重复书签 🎉")
            return

        msg = ""
        if safari_dups:
            msg += f"Safari: {len(safari_dups)} 组重复（共 {sum(len(d) for d in safari_dups)} 条）\n"
        if edge_dups:
            msg += f"Edge: {len(edge_dups)} 组重复（共 {sum(len(d) for d in edge_dups)} 条）\n"
        msg += "\n将保留每组中最早出现的一条，删除其余重复项。\n操作前会自动备份。"

        if not messagebox.askyesno("确认去重", msg):
            return

        removed_s = deduplicate_tree(self.safari_tree) if safari_dups else 0
        removed_e = deduplicate_tree(self.edge_tree) if edge_dups else 0

        if removed_s > 0:
            self._save_safari()
        if removed_e > 0:
            self._save_edge()

        self._load_data()
        self.status_var.set(f"✅ 去重完成: Safari 删除 {removed_s} 条, Edge 删除 {removed_e} 条")

    # ─── 保存 ─────────────────────────────────────────────

    def _save_safari(self):
        """保存 Safari 书签。"""
        try:
            write_safari_bookmarks(self.safari_tree.children)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存 Safari 书签时出错:\n{e}")

    def _save_edge(self):
        """保存 Edge 书签。"""
        try:
            write_edge_bookmarks(self.edge_tree.children)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存 Edge 书签时出错:\n{e}")

    # ─── 右键菜单 ─────────────────────────────────────────

    def _show_context_menu(self, event, source: str):
        """显示右键菜单。"""
        self._context_source = source
        widget = self.safari_tree_widget if source == "safari" else self.edge_tree_widget
        item_id = widget.identify_row(event.y)
        if item_id:
            widget.selection_set(item_id)
            self.context_menu.post(event.x_root, event.y_root)

    def _get_selected_info(self, source: str) -> Optional[dict]:
        """获取当前选中节点的信息。"""
        widget = self.safari_tree_widget if source == "safari" else self.edge_tree_widget
        sel = widget.selection()
        if not sel:
            return None
        item_id = sel[0]
        values = widget.item(item_id, "values")
        text = widget.item(item_id, "text")
        return {
            "id": item_id,
            "url": values[0] if values else "",
            "name": values[1] if len(values) > 1 else "",
            "path": values[2] if len(values) > 2 else "",
            "text": text,
        }

    def _edit_selected(self):
        """编辑选中的书签。"""
        info = self._get_selected_info(self._context_source)
        if not info:
            return
        if not info["url"]:
            messagebox.showinfo("提示", "文件夹不支持编辑 URL，可以右键添加子书签")
            return

        # 弹出编辑对话框
        dialog = EditDialog(self.root, info["name"], info["url"])
        if dialog.result:
            new_name, new_url = dialog.result
            tree = self.safari_tree if self._context_source == "safari" else self.edge_tree
            update_bookmark_in_tree(tree, info["url"], new_name, new_url)
            if self._context_source == "safari":
                self._save_safari()
            else:
                self._save_edge()
            self._load_data()
            self.status_var.set(f"✅ 已更新书签: {new_name}")

    def _add_bookmark(self):
        """添加新书签。"""
        tree = self.safari_tree if self._context_source == "safari" else self.edge_tree

        dialog = EditDialog(self.root, "", "", title="添加书签")
        if dialog.result:
            name, url = dialog.result
            info = self._get_selected_info(self._context_source)
            target_folder = info["path"] if info and info["path"] else ""
            add_bookmark_to_tree(tree, name, url, target_folder)
            if self._context_source == "safari":
                self._save_safari()
            else:
                self._save_edge()
            self._load_data()
            self.status_var.set(f"✅ 已添加书签: {name}")

    def _add_folder(self):
        """添加新文件夹。"""
        tree = self.safari_tree if self._context_source == "safari" else self.edge_tree
        name = simpledialog.askstring("添加文件夹", "请输入文件夹名称:", parent=self.root)
        if name:
            info = self._get_selected_info(self._context_source)
            parent_path = info["path"] if info and info["path"] else ""
            add_folder_to_tree(tree, name, parent_path)
            if self._context_source == "safari":
                self._save_safari()
            else:
                self._save_edge()
            self._load_data()
            self.status_var.set(f"✅ 已添加文件夹: {name}")

    def _delete_selected(self):
        """删除选中的书签。"""
        info = self._get_selected_info(self._context_source)
        if not info:
            return

        display = info["name"] or info["url"]
        if not messagebox.askyesno("确认删除", f"确定要删除「{display}」吗？"):
            return

        tree = self.safari_tree if self._context_source == "safari" else self.edge_tree
        if info["url"]:
            delete_bookmark_from_tree(tree, info["url"])
        else:
            # 删除文件夹 — 通过找到父节点并移除
            self._delete_folder_from_widget(info)

        if self._context_source == "safari":
            self._save_safari()
        else:
            self._save_edge()
        self._load_data()
        self.status_var.set(f"✅ 已删除: {display}")

    def _delete_folder_from_widget(self, info: dict):
        """从树中删除文件夹。"""
        tree = self.safari_tree if self._context_source == "safari" else self.edge_tree
        folder_name = info["name"]
        parent_path = info["path"]
        # 找到父文件夹并删除子文件夹
        from sync import _find_folder
        parent = _find_folder(tree, parent_path)
        if parent:
            for i, child in enumerate(parent.children):
                if child.name == folder_name and child.is_folder:
                    parent.children.pop(i)
                    return

    def _on_double_click(self, source: str):
        """双击编辑书签。"""
        self._context_source = source
        self._edit_selected()

    # ─── 搜索/过滤 ────────────────────────────────────────

    def _clear_placeholder(self, entry: ttk.Entry):
        if entry.get() == "🔍 搜索...":
            entry.delete(0, tk.END)

    def _filter_tree(self, source: str):
        """根据搜索词过滤树。"""
        widget = self.safari_tree_widget if source == "safari" else self.edge_tree_widget
        query = widget.master.winfo_children()[0].get().lower()  # 搜索框

        if not query or query == "🔍 搜索...":
            # 恢复全部
            tree = self.safari_tree if source == "safari" else self.edge_tree
            self._populate_tree(widget, tree)
            return

        # 清除并重新填充，只保留匹配项
        widget.delete(*widget.get_children())
        tree = self.safari_tree if source == "safari" else self.edge_tree
        for child in tree.children:
            self._add_filtered_node(widget, "", child, query)

    def _add_filtered_node(self, tree_widget: ttk.Treeview, parent_id: str,
                           item: BookmarkItem, query: str):
        """递归添加匹配搜索的节点。"""
        matches = query in item.name.lower() or query in item.url.lower()
        has_matching_children = any(
            self._node_matches(child, query) for child in item.children
        )

        if matches or has_matching_children:
            if item.is_folder:
                display = f"📁 {item.name}  ({item.count_all()})"
                tags = ("folder",)
            else:
                display = f"🔗 {item.name}"
                tags = ()

            node_id = tree_widget.insert(parent_id, tk.END, text=display, tags=tags)
            tree_widget.item(node_id, values=(item.url, item.name, item.source_path))

            if matches or has_matching_children:
                tree_widget.item(node_id, open=True)

            for child in item.children:
                self._add_filtered_node(tree_widget, node_id, child, query)

    def _node_matches(self, item: BookmarkItem, query: str) -> bool:
        if query in item.name.lower() or query in item.url.lower():
            return True
        return any(self._node_matches(c, query) for c in item.children)

    # ─── 导出 ─────────────────────────────────────────────

    def _do_export(self):
        """导出书签为 HTML 文件。"""
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出书签为 HTML",
            defaultextension=".html",
            filetypes=[("HTML 文件", "*.html"), ("所有文件", "*.*")],
            initialfile="bookmarks_export.html",
        )
        if not path:
            return

        html = self._generate_html(self.safari_tree, self.edge_tree)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        self.status_var.set(f"✅ 已导出到: {path}")
        messagebox.showinfo("导出完成", f"书签已导出到:\n{path}")

    def _generate_html(self, safari_tree: BookmarkItem, edge_tree: BookmarkItem) -> str:
        """生成 Netscape 书签 HTML 格式。"""
        lines = [
            '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            '<TITLE>Bookmarks</TITLE>',
            '<H1>Bookmarks</H1>',
            '<DL><p>',
        ]

        def _add_node(item: BookmarkItem):
            if item.is_bookmark:
                lines.append(f'    <DT><A HREF="{item.url}">{item.name}</A>')
            elif item.is_folder:
                lines.append(f'    <DT><H3>{item.name}</H3>')
                lines.append('    <DL><p>')
                for child in item.children:
                    _add_node(child)
                lines.append('    </DL><p>')

        for child in safari_tree.children:
            _add_node(child)

        lines.append('</DL><p>')
        return '\n'.join(lines)


class EditDialog:
    """编辑书签对话框。"""

    def __init__(self, parent, name: str, url: str, title: str = "编辑书签"):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x180")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frame = ttk.Frame(self.dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="名称:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.name_var = tk.StringVar(value=name)
        ttk.Entry(frame, textvariable=self.name_var, width=45).grid(row=0, column=1, pady=4)

        ttk.Label(frame, text="URL:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.url_var = tk.StringVar(value=url)
        ttk.Entry(frame, textvariable=self.url_var, width=45).grid(row=1, column=1, pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="确定", command=self._ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side=tk.LEFT, padx=8)

        self.dialog.bind("<Return>", lambda e: self._ok())
        self.dialog.bind("<Escape>", lambda e: self._cancel())

        parent.wait_window(self.dialog)

    def _ok(self):
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        if name or url:
            self.result = (name, url)
        self.dialog.destroy()

    def _cancel(self):
        self.dialog.destroy()


def main():
    root = tk.Tk()

    # macOS 适配
    try:
        root.tk.call("::tk::unsupported::MacWindowStyle", "style", root._w, "document", "closeBox collapseBox")
    except Exception:
        pass

    # 设置应用图标（如果可用）
    try:
        if sys.platform == "darwin":
            root.iconphoto(False, tk.PhotoImage(data=""))
    except Exception:
        pass

    app = BookmarkSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

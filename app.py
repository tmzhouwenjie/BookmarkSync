#!/usr/bin/env python3
"""Bookmark Sync — PyWebView 桌面应用。

自动读取 Safari / Edge 书签，提供可视化对比与一键同步。
需要「完全磁盘访问权限」才能读取 Safari 书签。

用法:
    python3 app.py
"""
import os
import sys
import json
import plistlib
import shutil
import webview
import webbrowser
import threading
import subprocess
import urllib.request
import tempfile
import logging
from pathlib import Path
from datetime import datetime

# ─── 常量 ─────────────────────────────────────────────────
HOME = Path.home()
SAFARI_PLIST = HOME / "Library" / "Safari" / "Bookmarks.plist"
EDGE_BOOKMARKS = HOME / "Library" / "Application Support" / "Microsoft Edge" / "Default" / "Bookmarks"
BACKUP_DIR = HOME / ".bookmark_sync" / "backups"
LOG_DIR = HOME / ".bookmark_sync" / "logs"
LOG_FILE = LOG_DIR / "app.log"
HTML_FILE = Path(__file__).parent / "BookmarkSync.html"
APP_VERSION = '1.1.1'
GITHUB_REPO = 'tmzhouwenjie/BookmarkSync'

# ─── 日志配置 ─────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8',
)
logger = logging.getLogger('BookmarkSync')


class Api:
    """暴露给前端 JS 的 Python API（通过 window.pywebview.api 调用）。"""

    def __init__(self):
        self._dirty = False
        self._update_progress = 0
        self._update_downloading = False
        self._update_dmg_path = ''

    def set_dirty(self, value: bool) -> str:
        """前端通知 Python 端数据已修改/已保存。"""
        self._dirty = bool(value)
        return json.dumps({'ok': True})

    def load_safari(self) -> str:
        """读取 Safari Bookmarks.plist，返回 JSON 字符串。"""
        if not SAFARI_PLIST.exists():
            return json.dumps({"error": "Safari 书签文件不存在"})
        try:
            with open(SAFARI_PLIST, "rb") as f:
                data = plistlib.load(f)
            return json.dumps({"data": _bplist_to_json(data)}, ensure_ascii=False)
        except PermissionError:
            return json.dumps({
                "error": "无权限读取 Safari 书签。请在「系统设置 → 隐私与安全性 → "
                         "完全磁盘访问权限」中授权给此应用，然后重启。"
            })
        except Exception as e:
            return json.dumps({"error": f"读取失败: {e}"})

    def load_edge(self) -> str:
        """读取 Edge Bookmarks JSON，返回 JSON 字符串。"""
        if not EDGE_BOOKMARKS.exists():
            return json.dumps({"error": "Edge 书签文件不存在，请确认已安装 Microsoft Edge"})
        try:
            with open(EDGE_BOOKMARKS, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps({"data": data}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"读取失败: {e}"})

    def save_edge(self, edge_json_str: str) -> str:
        """保存 Edge 书签（自动备份原文件）。"""
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = BACKUP_DIR / "edge" / f"Bookmarks_{ts}.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(EDGE_BOOKMARKS, backup)

            data = json.loads(edge_json_str)
            with open(EDGE_BOOKMARKS, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info('保存 Edge 书签 → %s', backup.name)
            return json.dumps({"ok": True, "backup": str(backup)})
        except Exception as e:
            return json.dumps({"error": f"保存失败: {e}"})

    def save_safari(self, safari_json_str: str) -> str:
        """保存 Safari 书签（自动备份原文件）。"""
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = BACKUP_DIR / "safari" / f"Bookmarks_{ts}.plist"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SAFARI_PLIST, backup)

            data = json.loads(safari_json_str)
            plist_data = _json_to_bplist(data)
            with open(SAFARI_PLIST, "wb") as f:
                plistlib.dump(plist_data, f)
            logger.info('保存 Safari 书签 → %s', backup.name)
            return json.dumps({"ok": True, "backup": str(backup)})
        except Exception as e:
            return json.dumps({"error": f"保存失败: {e}"})

    def save_mapping(self, mapping_json_str: str) -> str:
        """保存文件夹映射到本地文件。"""
        try:
            mapping_file = BACKUP_DIR / "folder_mapping.json"
            mapping_file.parent.mkdir(parents=True, exist_ok=True)
            with open(mapping_file, "w", encoding="utf-8") as f:
                f.write(mapping_json_str)
            logger.info('保存文件夹映射 (%d 条)', len(json.loads(mapping_json_str)))
            return json.dumps({"ok": True, "path": str(mapping_file)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def load_mapping(self) -> str:
        """从本地文件加载文件夹映射。"""
        try:
            mapping_file = BACKUP_DIR / "folder_mapping.json"
            if mapping_file.exists():
                with open(mapping_file, "r", encoding="utf-8") as f:
                    data = f.read()
                return json.dumps({"ok": True, "data": json.loads(data)})
            return json.dumps({"ok": False})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def list_backups(self) -> str:
        """列出所有可用的备份文件。"""
        try:
            backups = []
            if BACKUP_DIR.exists():
                for browser_dir in sorted(BACKUP_DIR.iterdir()):
                    if not browser_dir.is_dir() or browser_dir.name.startswith('.'):
                        continue
                    for f in sorted(browser_dir.iterdir(), reverse=True):
                        if f.is_file() and f.name.startswith('Bookmarks_'):
                            # 从文件名提取时间戳: Bookmarks_20240614_123456.json
                            stem = f.stem.replace('Bookmarks_', '')
                            try:
                                dt = datetime.strptime(stem, '%Y%m%d_%H%M%S')
                                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                date_str = stem
                            browser_name = browser_dir.name.capitalize()
                            ext_label = 'Edge' if f.suffix == '.json' else 'Safari'
                            backups.append({
                                'name': f'{ext_label} 备份 ({browser_name})',
                                'date': date_str,
                                'path': str(f),
                                'browser': browser_dir.name,
                            })
            return json.dumps({'backups': backups}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'backups': [], 'error': str(e)})

    def backup_now(self, browser: str) -> str:
        """手动备份当前书签文件。"""
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            if browser == 'safari':
                if not SAFARI_PLIST.exists():
                    return json.dumps({'error': 'Safari 书签文件不存在'})
                backup = BACKUP_DIR / 'safari' / f'Bookmarks_{ts}.plist'
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SAFARI_PLIST, backup)
                logger.info('手动备份 Safari → %s', backup.name)
                return json.dumps({'ok': True, 'path': str(backup)})
            elif browser == 'edge':
                if not EDGE_BOOKMARKS.exists():
                    return json.dumps({'error': 'Edge 书签文件不存在'})
                backup = BACKUP_DIR / 'edge' / f'Bookmarks_{ts}.json'
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(EDGE_BOOKMARKS, backup)
                logger.info('手动备份 Edge → %s', backup.name)
                return json.dumps({'ok': True, 'path': str(backup)})
            else:
                return json.dumps({'error': f'未知浏览器: {browser}'})
        except Exception as e:
            return json.dumps({'error': f'备份失败: {e}'})

    def restore_backup(self, backup_path: str) -> str:
        """从备份文件恢复书签。"""
        try:
            bp = Path(backup_path)
            if not bp.exists():
                return json.dumps({'error': f'备份文件不存在: {backup_path}'})

            # 先备份当前文件
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')

            if bp.suffix == '.json':
                # Edge 备份恢复
                target = EDGE_BOOKMARKS
                pre_backup = BACKUP_DIR / 'edge' / f'Bookmarks_pre_restore_{ts}.json'
                pre_backup.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.copy2(target, pre_backup)
                shutil.copy2(bp, target)
                logger.info('恢复 Edge 备份 ← %s', bp.name)
                return json.dumps({'ok': True, 'browser': 'edge',
                                   'pre_restore_backup': str(pre_backup)})
            elif bp.suffix == '.plist':
                # Safari 备份恢复
                target = SAFARI_PLIST
                pre_backup = BACKUP_DIR / 'safari' / f'Bookmarks_pre_restore_{ts}.plist'
                pre_backup.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.copy2(target, pre_backup)
                shutil.copy2(bp, target)
                logger.info('恢复 Safari 备份 ← %s', bp.name)
                return json.dumps({'ok': True, 'browser': 'safari',
                                   'pre_restore_backup': str(pre_backup)})
            else:
                return json.dumps({'error': f'未知的备份文件格式: {bp.suffix}'})
        except PermissionError:
            return json.dumps({'error': '无权限写入书签文件，请检查系统权限设置'})
        except Exception as e:
            return json.dumps({'error': f'恢复失败: {e}'})

    def open_url(self, url: str) -> str:
        """在系统浏览器中打开 URL。"""
        try:
            webbrowser.open(url)
            return json.dumps({'ok': True})
        except Exception as e:
            return json.dumps({'error': str(e)})

    # ─── 自动更新 ───────────────────────────────────────────

    def check_github_update(self) -> str:
        """从 GitHub API 检查最新版本。"""
        try:
            url = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'BookmarkSync-Updater',
                'Accept': 'application/vnd.github.v3+json',
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get('tag_name', '').lstrip('v')
            notes = data.get('body', '')
            assets = data.get('assets', [])
            dmg_url = ''
            for a in assets:
                if a.get('browser_download_url', '').endswith('.dmg'):
                    dmg_url = a['browser_download_url']
                    break
            return json.dumps({
                'latest_version': tag,
                'current_version': APP_VERSION,
                'download_url': dmg_url,
                'notes': notes,
                'asset_count': len(assets),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)})

    def download_update(self, url: str) -> str:
        """后台下载 DMG 更新文件。"""
        if self._update_downloading:
            return json.dumps({'error': '下载已在进行中'})
        self._update_downloading = True
        self._update_progress = 0
        self._update_dmg_path = str(Path(tempfile.gettempdir()) / 'BookmarkSync_update.dmg')

        def _dl():
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'BookmarkSync-Updater'})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    total = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    with open(self._update_dmg_path, 'wb') as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self._update_progress = int(downloaded * 100 / total)
                self._update_progress = 100
                self._update_downloading = False
            except Exception as e:
                self._update_downloading = False
                self._update_progress = -1

        threading.Thread(target=_dl, daemon=True).start()
        return json.dumps({'ok': True})

    def get_update_progress(self) -> str:
        """获取下载进度（0-100），-1 表示失败。"""
        return json.dumps({
            'progress': self._update_progress,
            'downloading': self._update_downloading,
        })

    def install_update(self) -> str:
        """挂载 DMG 并将 .app 拷贝到 /Applications，替换当前版本。"""
        try:
            dmg_path = self._update_dmg_path
            if not dmg_path or not Path(dmg_path).exists():
                return json.dumps({'error': '未找到下载的更新文件'})

            mount_point = Path(tempfile.gettempdir()) / 'bs_update_mount'
            mount_point.mkdir(exist_ok=True)

            result = subprocess.run(
                ['hdiutil', 'attach', dmg_path, '-mountpoint', str(mount_point), '-nobrowse', '-quiet'],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return json.dumps({'error': f'挂载 DMG 失败: {result.stderr}'})

            try:
                apps = list(mount_point.glob('*.app'))
                if not apps:
                    return json.dumps({'error': 'DMG 中未找到 .app'})

                new_app = apps[0]
                target = Path('/Applications') / new_app.name

                if target.exists():
                    shutil.rmtree(str(target))
                shutil.copytree(str(new_app), str(target), symlinks=True)
            finally:
                subprocess.run(['hdiutil', 'detach', str(mount_point), '-quiet'], timeout=15)

            # 清理下载的 DMG
            try:
                Path(dmg_path).unlink(missing_ok=True)
            except Exception:
                pass

            return json.dumps({'ok': True, 'installed_to': str(target)})
        except Exception as e:
            logger.error('安装更新失败: %s', e)
            return json.dumps({'error': f'安装失败: {e}'})

    def get_logs(self, lines: int = 200) -> str:
        """读取日志文件最近 N 行。"""
        try:
            if not LOG_FILE.exists():
                return json.dumps({'logs': '', 'path': str(LOG_FILE)})
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return json.dumps({'logs': ''.join(recent), 'path': str(LOG_FILE), 'total': len(all_lines)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'logs': '', 'error': str(e)})

    def clear_logs(self) -> str:
        """清空日志文件。"""
        try:
            if LOG_FILE.exists():
                LOG_FILE.write_text('', encoding='utf-8')
            logger.info('日志已清空')
            return json.dumps({'ok': True})
        except Exception as e:
            return json.dumps({'error': str(e)})


def _bplist_to_json(obj):
    """将 plist 中的 bytes/UID 等类型转为 JSON 兼容格式。"""
    if isinstance(obj, dict):
        return {k: _bplist_to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_bplist_to_json(v) for v in obj]
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, '__class__') and obj.__class__.__name__ == 'UID':
        return str(obj)
    return obj


def _json_to_bplist(obj):
    """将 JS 传来的 JSON 对象转回 plist 兼容格式。"""
    if isinstance(obj, dict):
        return {k: _json_to_bplist(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_to_bplist(v) for v in obj]
    return obj


def main():
    print("=" * 50)
    print("  Bookmark Sync — Safari ↔ Edge 书签同步工具")
    print("=" * 50)

    if not HTML_FILE.exists():
        print(f"❌ HTML 文件不存在: {HTML_FILE}")
        print("请确保 BookmarkSync.html 和本脚本在同一目录下。")
        sys.exit(1)

    print(f"✅ HTML: {HTML_FILE}")
    print(f"✅ Safari: {SAFARI_PLIST} ({'存在' if SAFARI_PLIST.exists() else '不存在'})")
    print(f"✅ Edge:   {EDGE_BOOKMARKS} ({'存在' if EDGE_BOOKMARKS.exists() else '不存在'})")
    print("\n正在启动窗口...")

    logger.info('═══════════════════════════════════════')
    logger.info('BookmarkSync v%s 启动', APP_VERSION)
    logger.info('Safari: %s (%s)', SAFARI_PLIST, '存在' if SAFARI_PLIST.exists() else '不存在')
    logger.info('Edge:   %s (%s)', EDGE_BOOKMARKS, '存在' if EDGE_BOOKMARKS.exists() else '不存在')

    api = Api()
    window = webview.create_window(
        "Bookmark Sync — Safari ↔ Edge",
        url=str(HTML_FILE),
        js_api=api,
        width=1280,
        height=800,
        min_size=(900, 600),
        text_select=True,
    )

    def on_closing():
        """关闭窗口前检查是否有未保存的更改。
        注意：此回调运行在 UI 主线程，绝不能调用 evaluate_js，否则会死锁。
        """
        if api._dirty:
            # 使用 Python 端 tkinter 弹窗（非阻塞 UI 线程）
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                result = messagebox.askyesno(
                    '未保存的更改',
                    '有未保存的更改，确定关闭吗？\n未保存的修改将丢失。'
                )
                root.destroy()
                return result
            except Exception:
                return True
        return True

    window.events.closing += on_closing
    webview.start(debug=False)


if __name__ == "__main__":
    main()

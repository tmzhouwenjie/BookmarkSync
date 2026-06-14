# BookmarkSync

Safari ↔ Edge 书签同步工具 —— 可视化对比、一键同步、去重、批量管理。

![macOS](https://img.shields.io/badge/platform-macOS-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## 功能特性

- **自动加载** — 启动后自动读取 Safari 和 Edge 书签（需「完全磁盘访问权限」）
- **可视化对比** — 双栏树视图展示书签结构，标记 Safari 独有、Edge 独有、共有、标题不同、重复
- **智能同步** — Safari→Edge、Edge→Safari、双向同步，支持文件夹结构同步
- **文件夹映射** — 自定义 Safari 与 Edge 之间的文件夹对应关系，映射持久保存
- **同步勾选项** — 勾选任意书签后一键同步到对侧
- **去重** — 自动检测并清理重复书签
- **勾选删除** — 勾选书签/文件夹后一键删除（含子项级联）
- **排序** — 按名称对书签排序
- **勾选独有** — 一键勾选当前侧独有的书签，便于批量同步或删除
- **一键展开/折叠** — 展开或折叠全部目录树
- **文件夹编辑** — 右键文件夹可重命名
- **备份与恢复** — 自动备份 + 手动备份 + 一键恢复
- **未保存提醒** — 关闭时检测未保存更改，弹窗提醒
- **拖拽导入** — 支持拖拽 plist / json 文件手动导入
- **右键菜单** — 编辑书签/文件夹、添加书签、添加文件夹、删除
- **搜索** — 实时搜索书签名称或 URL
- **暗色主题** — 精心设计的深色 UI

## 安装

### 方式一：DMG 安装包（推荐）

1. 从 [Releases](https://github.com/tmzhouwenjie/BookmarkSync/releases) 下载最新 `.dmg` 文件
2. 双击挂载，将 BookmarkSync.app 拖入 Applications
3. 首次打开需在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」中授权

### 方式二：源码运行

```bash
# 克隆仓库
git clone https://github.com/tmzhouwenjie/BookmarkSync.git
cd BookmarkSync

# 安装依赖
pip install pywebview

# 运行
python3 app.py
# 或双击「启动BookmarkSync.command」
```

## 系统要求

- macOS 12+
- Python 3.10+（源码运行时需要）
- Safari 和 Microsoft Edge 浏览器

## 使用说明

### 基本流程

1. 启动应用，自动加载两侧书签
2. 点击「对比」查看差异
3. 设置「映射」对齐文件夹命名差异
4. 选择同步方向或勾选同步
5. 点击书签栏「保存」写入浏览器

### 文件夹映射

当 Safari 和 Edge 的文件夹名称不同时（如 Safari 的「书签」对应 Edge 的「收藏夹栏」），可通过映射功能指定对应关系。映射设置会自动保存，下次启动时恢复。

### 备份管理

- **自动备份**：每次保存书签前自动备份原文件
- **手动备份**：点击书签栏「备份」按钮即时备份
- **恢复**：点击工具栏「恢复」按钮选择历史备份恢复

备份文件存储在 `~/.bookmark_sync/backups/`。

## 构建 DMG

```bash
# 推荐：使用 uv（快速可靠）
uv venv --python 3.12 .build_env
source .build_env/bin/activate
uv pip install pyinstaller pywebview

# 或用 venv 传统方式
python3 -m venv .build_env
source .build_env/bin/activate
pip install pyinstaller pywebview

# 构建
bash build.sh
```

产物位于 `dist/` 目录：
- `dist/BookmarkSync.app` — 独立应用包
- `dist/BookmarkSync_x.x.x.dmg` — 磁盘镜像

## 发布工作流

跨机器协作（Linux 开发 + Mac 构建）:

```bash
# 同步代码到 Mac
bash workflow.sh sync

# 一键发布新版本（自动：更新版本号 → 同步 → 构建 → 发布）
bash workflow.sh release v1.1.0
```

> **架构说明**: 代码在 Linux 上开发 → `workflow.sh` 通过 rsync 同步到 Mac → Mac 上构建 DMG 并上传 GitHub Release。`gh` CLI 在 Mac 上负责推送代码和发布。

## 项目结构

```
BookmarkSync/
├── app.py                      # PyWebView 后端（Python API）
├── BookmarkSync.html           # 前端界面（纯 HTML/CSS/JS）
├── build.sh                    # DMG 构建脚本
├── 启动BookmarkSync.command     # macOS 双击启动脚本
├── requirements.txt            # Python 依赖
└── dist/                       # 构建产物（不纳入版本控制）
```

## 技术架构

- **后端**：PyWebView（Python + WebKit 原生窗口），通过 `window.pywebview.api` 桥接 JS↔Python
- **前端**：单文件 HTML，内联 CSS/JS，自含 Binary Plist 解析器
- **存储**：书签映射和备份通过 Python 端文件持久化（绕过 WKWebView localStorage 限制）

## 许可证

[MIT License](LICENSE)

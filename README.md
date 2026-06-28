# sharept-dl

Batch download files from SharePoint shared links — pure HTTP, zero browser dependencies.

[中文说明](#中文说明) below.

## Features

- **No browser required** — uses plain HTTP, no Playwright, no Chromium
- **Pre-scan report** — shows file count and total size before downloading
- **Stable TUI** — Rich-powered terminal UI with real-time progress, no flickering
- **Resumable downloads** — interrupted transfers pick up where they left off via HTTP `Range` requests
- **Auto-skip** — already-downloaded files are detected and skipped instantly
- **Preserves folder structure** — subdirectories are recreated locally
- **Safe URL handling** — prevents double-encoding of paths with special/Chinese characters
- **Single file support** — handles `:w:` (Word), `:x:` (Excel), `:p:` (PowerPoint) share links via GUID lookup
- **Multi-language** — auto-detects system locale; displays Chinese or English based on your environment

## Supported share link types

| Type | URL pattern | How it works |
|------|-------------|--------------|
| Folder | `:f:` | Recursively enumerates files & subfolders via REST API |
| Word | `:w:` | Parses `sourcedoc` GUID, resolves via `GetFileById` API |
| Excel | `:x:` | Same as Word |
| PowerPoint | `:p:` | Same as Word |

## How it works

```
Folder share (:f:)
  │
  ├─ [1] HTTP GET → 302 redirect → Set-Cookie (auth)
  ├─ [2] REST API: enumerate files & folders
  └─ [3] Download each file (with Range support for resume)

Single file share (:w:/:x:/:p:)
  │
  ├─ [1] HTTP GET → 302 redirect → Set-Cookie (auth)
  ├─ [2] Extract sourcedoc GUID from URL
  ├─ [3] REST API: GetFileById('<GUID>') → ServerRelativeUrl
  └─ [4] Download via /_layouts/15/download.aspx
```

> **Limitation**: currently only supports "Anyone with the link" sharing links (anonymous access). Organization-internal links require additional OAuth2 authentication.

## Requirements

- Python >= 3.9
- [requests](https://pypi.org/project/requests/)
- [rich](https://pypi.org/project/rich/)

## Installation

### Via pip

```bash
pip install sharept-dl
```

### From source

```bash
git clone <repo-url>
cd sharept-dl
pip install -e .
```

## Usage

```bash
# Folder share
sharept-dl -u 'https://xxx.sharepoint.cn/:f:/g/personal/...'

# Single file share (Word/Excel/PowerPoint)
sharept-dl -u 'https://xxx.sharepoint.cn/:w:/r/personal/.../Doc.aspx?sourcedoc=...&file=....docx'

# Specify output directory
sharept-dl -u '...' -o ./my_files

# Verbose mode
sharept-dl -u '...' -v

# Force re-download everything
sharept-dl -u '...' --no-resume
```

> **⚠️ Important**: Always wrap the URL in **single quotes** `'...'`, NOT double quotes.
> Double quotes allow the shell to interpret `$`, `\`, and other special characters,
> which will break the URL.

### Options

| Argument | Short | Required | Default | Description |
|----------|-------|----------|---------|-------------|
| `--url` | `-u` | Yes | — | SharePoint share link (`:f:` folder type) |
| `--output` | `-o` | No | `.` | Output directory |
| `--timeout` | `-t` | No | `60` | HTTP request timeout in seconds |
| `--delay` | `-d` | No | `0.3` | Delay between file downloads (to avoid rate limits) |
| `--no-resume` | | No | `false` | Disable resume — force re-download all files |
| `--verbose` | `-v` | No | `false` | Verbose logging (prints to stderr) |

### Interrupt & resume

If the download is interrupted (Ctrl+C, network failure, etc.), simply run the same command again. The tool will:

1. Skip all fully-downloaded files (instant)
2. Detect `.part` temporary files and resume from where they left off via HTTP `Range` requests

```bash
# First run — interrupted at file 42/64
sharept-dl -u '...' -o ./downloads
# ... Ctrl+C ...

# Second run — skips 41 complete files, resumes file 42, continues from 43
sharept-dl -u '...' -o ./downloads
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project structure

```
sharept-dl/
├── sharepoint_dl/
│   ├── __init__.py       # Package exports
│   ├── __main__.py       # python -m entry point
│   ├── cli.py            # CLI argument parsing & main loop
│   ├── i18n.py           # Multi-language support (zh/en)
│   ├── session.py        # SharePoint authentication & REST API
│   ├── ui.py             # Rich terminal UI rendering
│   └── utils.py          # Utility functions & safe encoding
├── tests/
│   ├── test_utils.py     # Utility function tests
│   ├── test_session.py   # Session & API tests (mocked HTTP)
│   ├── test_cli.py       # CLI argument parsing tests
│   └── test_i18n.py      # i18n language detection tests
├── main.py               # Legacy entry point (backward compatible)
├── pyproject.toml        # Project metadata & build config
├── requirements.txt      # pip dependency list
├── LICENSE               # MIT license
└── README.md             # This file
```

## Internationalization (i18n)

sharept-dl automatically detects your system language:

- **Chinese** (`zh_CN`, `zh_TW`, etc.) → displays Chinese messages
- **Anything else** → displays English messages

You can override the language in code:

```python
from sharepoint_dl import set_language
set_language("en")  # force English
set_language("zh")  # force Chinese
```

## License

MIT

---

## 中文说明

无需浏览器即可批量下载 SharePoint 分享文件。纯 HTTP 实现，零浏览器依赖。

### 功能特性

- **无需浏览器** — 纯 HTTP 请求，不依赖 Playwright / Chromium
- **预扫描报告** — 下载前展示文件总数和总大小
- **稳定终端界面** — Rich 驱动的 TUI，实时进度不闪烁
- **断点续传** — 中断后重新运行，通过 `.part` 临时文件 + HTTP `Range` 请求自动续传
- **自动跳过** — 已下载完成的文件即时跳过
- **保留目录结构** — 子文件夹按原始层级重建
- **安全编码处理** — 防止特殊字符/中文路径的双重编码问题
- **单文件支持** — 兼容 `:w:`（Word）、`:x:`（Excel）、`:p:`（PowerPoint）分享链接
- **多语言** — 自动检测系统语言，中文环境显示中文，其他显示英文

### 支持的分享链接类型

| 类型 | URL 特征 | 处理方式 |
|------|----------|----------|
| 文件夹 | `:f:` | 通过 REST API 递归枚举文件和子文件夹 |
| Word 文档 | `:w:` | 解析 `sourcedoc` GUID，通过 `GetFileById` API 获取文件路径 |
| Excel 表格 | `:x:` | 同上 |
| PowerPoint | `:p:` | 同上 |

### 原理

访问 SharePoint 分享链接（`?e=...`）后获取认证 cookie，随后通过 SharePoint REST API 获取文件信息并下载。文件夹分享会递归枚举子目录，单文件分享通过 GUID 定位文件。

> **局限**：当前仅支持「任何人可查看」类型的分享链接（匿名访问）。组织内部链接需额外 OAuth2 认证。

### 依赖

- Python >= 3.9
- [requests](https://pypi.org/project/requests/)
- [rich](https://pypi.org/project/rich/)

### 安装与使用

```bash
pip install sharept-dl

# 文件夹分享
sharept-dl -u 'https://xxx.sharepoint.cn/:f:/g/personal/...' -o ./downloads

# 单文件分享
sharept-dl -u 'https://xxx.sharepoint.cn/:w:/r/personal/.../Doc.aspx?sourcedoc=...&file=....docx'

# 详细日志
sharept-dl -u '...' -v

# 禁用断点续传（强制重新下载）
sharept-dl -u '...' --no-resume
```

> **⚠️ 重要**: URL 务必使用**单引号** `'...'` 包裹，不要用双引号。双引号会让 shell 解释 `$`、`\` 等特殊字符，导致 URL 被截断。

### 多语言

工具会根据系统语言自动选择提示语言，中文环境显示中文，其他环境显示英文。也可以通过代码手动设置：

```python
from sharepoint_dl import set_language
set_language("en")  # 强制英文
set_language("zh")  # 强制中文
```

### 中断恢复

下载中断后，再次运行相同命令即可自动续传——已完成的文件直接跳过，未完成的从 `.part` 断点继续。

```bash
# 首次运行 —— 在第 42/64 个文件时中断
sharept-dl -u '...' -o ./downloads

# 重新运行 —— 跳过前 41 个，续传第 42 个，继续下载后续文件
sharept-dl -u '...' -o ./downloads
```

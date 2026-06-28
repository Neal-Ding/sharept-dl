"""终端 UI 渲染 — 基于 Rich 库的稳定界面。"""

from collections import deque
from typing import Optional

from rich import box
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from .i18n import t
from .utils import shorten_path

# ── 状态图标 ──────────────────────────────────────────────────────────────

ICON_DOWNLOADING = "[bold yellow]↓[/]"
ICON_DONE = "[bold green]✓[/]"
ICON_FAILED = "[bold red]✗[/]"
ICON_PENDING = "[dim]⏳[/]"

# (icon, filename, size_str, info_str)
DownloadEntry = tuple[str, str, str, str]


def build_display(
    title: str,
    subtitle: str,
    progress: Progress,
    task_id: TaskID,
    recent: deque,
    pending_preview: list[str],
    stats_text: str,
) -> "Group":  # noqa: F821
    """构建稳定的终端显示布局。

    布局从上到下:
        - 标题（工具名 + 摘要信息）
        - 进度条
        - 最近 10 条下载状态表格
        - 待下载文件预览
        - 底部统计
    """
    from rich.console import Group

    # ── 标题区 ──
    header = Text()
    header.append(title, style="bold white")
    if subtitle:
        header.append("\n")
        header.append(subtitle, style="dim")

    # ── 进度条 ──
    progress_section = Panel(progress, box=box.SIMPLE, padding=(0, 1))

    # ── 最近下载表格 ──
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("", width=2, justify="center")
    table.add_column("文件", ratio=1, no_wrap=True)
    table.add_column("大小", width=10, justify="right")
    table.add_column("状态", width=12)

    for icon, fname, fsize, info in recent:
        table.add_row(icon, shorten_path(fname, 50), fsize, info or "-")

    # 填充空白行以保持 10 行稳定高度
    empty_needed = max(0, 10 - len(recent))
    for _ in range(empty_needed):
        table.add_row("", "", "", "")

    # ── 待处理预览 ──
    if pending_preview:
        pending_text = Text(t("ui_pending"), style="dim")
        pending_text.append(" · ".join(pending_preview[:5]), style="dim")
    else:
        pending_text = Text("")

    # ── 底部统计 ──
    footer = Text(stats_text, style="bold")

    return Group(header, "", progress_section, table, pending_text, "", footer)

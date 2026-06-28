"""CLI 入口 — 命令行参数解析、主流程编排。"""

import argparse
import logging
import os
import signal
import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from .i18n import t
from .session import SharePointSession
from .ui import (
    ICON_DONE,
    ICON_DOWNLOADING,
    ICON_FAILED,
    ICON_PENDING,
    DownloadEntry,
    build_display,
)
from .utils import format_bytes, safe_unquote, setup_logging

logger = logging.getLogger("sharept-dl")


# ── 辅助函数 ──────────────────────────────────────────────────────────────


def _get_local_path(sp: SharePointSession, file_info: dict) -> str:
    """根据分享类型计算文件的本地保存路径。

    文件夹分享:   从完整路径中剥离文件夹前缀
    单文件分享:   直接使用文件名（下载到输出目录根）
    """
    if not sp.is_folder:
        # 单文件 → 直接用文件名，无视服务器路径
        return file_info["name"]

    # 文件夹 → 剥离文件夹前缀，保留子目录结构
    rel = file_info["rel_path"]
    fp = sp.folder_path
    if fp and rel.startswith(fp):
        return rel[len(fp):].lstrip("/")
    return file_info["name"]


# ── 命令行参数 ────────────────────────────────────────────────────────────


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sharept-dl",
        description="批量下载 SharePoint 分享文件，纯 HTTP 实现，无需浏览器。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 文件夹分享
  sharept-dl -u 'https://xxx.sharepoint.cn/:f:/g/personal/...'
  # 单文件分享
  sharept-dl -u 'https://xxx.sharepoint.cn/:w:/r/personal/.../Doc.aspx?sourcedoc=...&file=....docx'
  # 指定输出目录
  sharept-dl -u '...' -o ./my_files
  # 禁用续传
  sharept-dl -u '...' --no-resume

注意:
  URL 请务必使用单引号 '...' 包裹，而不是双引号 "..."。
  双引号会让 shell 解释 $、\\ 等特殊字符，导致 URL 被截断。
        """,
    )
    parser.add_argument(
        "--url",
        "-u",
        required=True,
        help="SharePoint 分享链接，支持文件夹（:f:）和单文件（:w:/:x:/:p:）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=".",
        help="输出目录（默认: 当前目录）",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=60,
        help="HTTP 请求超时秒数（默认: 60）",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0.3,
        help="文件间下载间隔秒数（默认: 0.3）",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="禁用断点续传，强制重新下载所有文件",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="详细日志输出（发送到 stderr）",
    )
    args = parser.parse_args(argv)
    args.resume = not args.no_resume
    return args


# ── 主流程 ────────────────────────────────────────────────────────────────


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 设置信号处理 ──
    interrupted = False

    def on_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, on_interrupt)

    # ── URL 预处理 ──
    raw_url = args.url.strip()

    # 检测可能由 shell 双引号或未引用导致的截断
    if raw_url.count("$") > 0:
        logger.warning(t("cli_shell_warning"))

    # 安全 unquote：仅在 URL 包含 %XX 编码时解码，避免破坏正常 URL
    share_url = safe_unquote(raw_url)
    if share_url != raw_url:
        logger.info(t("cli_url_decoded"))

    # ── 认证 ──
    sp = SharePointSession(share_url, timeout=args.timeout)
    try:
        sp.authenticate()
    except requests.RequestException as e:
        logger.error(t("cli_auth_failed", str(e)))
        logger.error(t("cli_auth_hint"))
        logger.error(t("cli_quote_hint"))
        return 1

    if not sp.base_url:
        logger.error(t("cli_no_site_info"))
        return 1
    if sp.is_folder and not sp.folder_path:
        logger.error(t("cli_no_folder_path"))
        return 1

    # ── 阶段 1: 扫描 ──
    if sp.is_folder:
        logger.info(t("cli_scanning_folder"))
        all_files = sp.collect_all_files(sp.folder_path)
    else:
        logger.info(t("cli_fetching_file"))
        all_files = sp.collect_all_files()
    total_bytes = sum(f["size"] for f in all_files)
    total = len(all_files)

    # 确认已存在文件（断点续传：跳过完整的）
    skipped_files = 0
    skipped_bytes = 0
    for f in all_files:
        sub_path = _get_local_path(sp, f)
        fp = output_dir / sub_path
        if fp.exists() and fp.stat().st_size > 0:
            skipped_files += 1
            skipped_bytes += fp.stat().st_size

    # ── 初始化 Rich 组件 ──
    console = Console()
    progress = Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("({task.percentage:.0f}%)"),
        TimeElapsedColumn(),
        TextColumn("↓ {task.fields[rate]:.1f}/s"),
        console=console,
        expand=False,
    )
    task_id = progress.add_task(
        t("ui_progress_label"),
        total=total,
        completed=skipped_files,
        rate=0.0,
    )

    recent: deque[DownloadEntry] = deque(maxlen=10)
    if sp.is_folder:
        title = "  " + t("ui_title_folder")
        subtitle = "  " + t("ui_files_count", total, format_bytes(total_bytes)) + " · → " + str(output_dir)
    else:
        title = "  " + t("ui_title_file")
        file_label = sp.file_name or (all_files[0]["name"] if all_files else "?")
        subtitle = "  " + file_label + " · " + format_bytes(total_bytes) + " · → " + str(output_dir)

    # ── 预填最近队列 ──
    pending_preview: list[str] = []
    for f in all_files:
        sub_path = _get_local_path(sp, f)
        fp = output_dir / sub_path
        if fp.exists() and fp.stat().st_size > 0:
            recent.append(
                (ICON_DONE, sub_path, format_bytes(f["size"]), t("ui_exists"))
            )
        else:
            pending_preview.append(sub_path)
    # 只保留最近 10 条
    while len(recent) > 10:
        recent.popleft()

    # 初始显示
    stats = t("ui_completed", skipped_files, total) + "  ·  " + t("ui_downloaded", format_bytes(skipped_bytes))
    display = build_display(
        title, subtitle, progress, task_id, recent, pending_preview, stats
    )

    # ── 阶段 2: 下载 ──
    ok_count = 0
    fail_count = 0
    downloaded_bytes = 0
    start_time = time.time()
    rate_samples: list[tuple[float, int]] = []

    with Live(
        display, console=console, refresh_per_second=5, screen=False
    ) as live:
        for i, f in enumerate(all_files):
            # ── 检查中断 ──
            if interrupted:
                console.print()
                console.print(
                    f"\n[bold yellow]{t('cli_interrupted_title')}[/] — "
                    + t("cli_interrupted_msg", ok_count + skipped_files, total, format_bytes(downloaded_bytes + skipped_bytes))
                )
                signal.signal(signal.SIGINT, original_sigint)
                return 0

            rel_path = f["rel_path"]
            sub_path = _get_local_path(sp, f)
            save_path = output_dir / sub_path

            # 跳过已存在
            if save_path.exists() and save_path.stat().st_size > 0:
                continue

            # ── 下载 ──
            part_path = str(save_path) + ".part"
            existing_size = (
                os.path.getsize(part_path)
                if os.path.exists(part_path)
                else 0
            )

            # 使用 session 方法构建 URL（内置防双重编码）
            dl_url = sp.build_download_url(rel_path)
            headers: dict = {}
            if args.resume and existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

            # 添加下载中条目
            size_str = format_bytes(f["size"])
            recent.append(
                (ICON_DOWNLOADING, sub_path, size_str, t("cli_downloading"))
            )
            if sub_path in pending_preview:
                pending_preview.remove(sub_path)

            file_start = time.time()
            file_ok = False

            try:
                r = sp.session.get(
                    dl_url,
                    stream=True,
                    headers=headers,
                    timeout=sp.timeout * 2,
                )

                if r.status_code == 206:
                    mode = "ab"
                elif r.status_code == 200:
                    mode = "wb"
                    existing_size = 0
                    if os.path.exists(part_path):
                        os.remove(part_path)
                else:
                    recent[-1] = (
                        ICON_FAILED,
                        sub_path,
                        size_str,
                        f"HTTP {r.status_code}",
                    )
                    fail_count += 1
                    file_ok = False

                if r.status_code in (200, 206):
                    os.makedirs(
                        os.path.dirname(save_path), exist_ok=True
                    )
                    with open(part_path, mode) as fh:
                        for chunk in r.iter_content(chunk_size=65536):
                            if interrupted:
                                if chunk:
                                    fh.write(chunk)
                                fh.flush()
                                break
                            if chunk:
                                fh.write(chunk)

                    if not interrupted:
                        final_size = os.path.getsize(part_path)
                        os.rename(part_path, str(save_path))
                        elapsed = time.time() - file_start
                        recent[-1] = (
                            ICON_DONE,
                            sub_path,
                            size_str,
                            f"{elapsed:.1f}s",
                        )
                        downloaded_bytes += final_size
                        ok_count += 1
                        file_ok = True
                    else:
                        recent[-1] = (
                            ICON_DOWNLOADING,
                            sub_path,
                            size_str,
                            t("ui_paused"),
                        )
                        pending_preview.insert(0, sub_path)

            except requests.RequestException:
                recent[-1] = (
                    ICON_FAILED, sub_path, size_str, t("ui_network_error")
                )
                fail_count += 1
                file_ok = False
            except OSError:
                recent[-1] = (
                    ICON_FAILED, sub_path, size_str, t("ui_write_error")
                )
                fail_count += 1
                file_ok = False

            # ── 更新进度统计 ──
            progress.advance(task_id)

            # 更新速率（最近 30 秒）
            now = time.time()
            rate_samples.append(
                (now, ok_count + fail_count + skipped_files)
            )
            rate_samples = [
                (ts, c) for ts, c in rate_samples if now - ts <= 30
            ]
            if len(rate_samples) >= 2:
                first_ts, first_c = rate_samples[0]
                duration = now - first_ts
                files_done = rate_samples[-1][1] - first_c
                rate = (
                    files_done / duration if duration > 0 else 0
                )
            else:
                rate = 0.0
            progress.update(task_id, rate=rate)

            # ── 刷新显示 ──
            stats_str = (
                t("ui_completed", ok_count + skipped_files, total)
                + "  ·  "
                + t("ui_downloaded", format_bytes(downloaded_bytes + skipped_bytes))
                + "  ·  "
                + t("ui_failed_count", fail_count)
            )
            display = build_display(
                title,
                subtitle,
                progress,
                task_id,
                recent,
                pending_preview,
                stats_str,
            )
            live.update(display)

            # 限速延迟
            if not interrupted and i < total - 1 and file_ok:
                time.sleep(args.delay)

            # 中断后退出循环
            if interrupted:
                console.print()
                console.print(
                    f"\n[bold yellow]{t('cli_interrupted_title')}[/] — "
                    + t("cli_interrupted_msg", ok_count + skipped_files, total, format_bytes(downloaded_bytes + skipped_bytes))
                )
                signal.signal(signal.SIGINT, original_sigint)
                return 0

    # ── 恢复信号处理 ──
    signal.signal(signal.SIGINT, original_sigint)

    # ── 汇总 ──
    elapsed = time.time() - start_time
    console.print()
    console.print(
        Panel.fit(
            f"[bold]{t('cli_done_title')}[/]\n"
            + t("cli_done_success", ok_count)
            + "  ·  "
            + t("cli_done_skipped", skipped_files)
            + "  ·  "
            + t("cli_done_failed", fail_count)
            + "  ·  "
            + t("cli_done_elapsed", elapsed)
            + "\n"
            + t("cli_done_total", format_bytes(downloaded_bytes + skipped_bytes))
            + "\n"
            + t("cli_done_dir", str(output_dir)),
            border_style="green",
        )
    )

    return 0 if fail_count == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    """程序入口。"""
    args = parse_args(argv)
    setup_logging(verbose=args.verbose)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

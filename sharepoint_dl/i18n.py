"""国际化支持 — 根据系统语言自动选择中文或英文提示。

检测逻辑:
    - 检查 LANGUAGE / LANG / LC_ALL / LC_MESSAGES 环境变量
    - 包含 'zh' 则使用中文，否则使用英文
    - 可通过 set_language() 手动覆盖

用法:
    from .i18n import t
    logger.info(t("scanning_files"))
"""

import locale
import logging
import os

logger = logging.getLogger("sharept-dl")

# ── 语言检测 ────────────────────────────────────────────────────────────

_current_lang: str = "en"


def _detect_language() -> str:
    """检测系统语言，返回 'zh' 或 'en'。"""
    # 1. 检查环境变量
    for var in ("LANGUAGE", "LANG", "LC_ALL", "LC_MESSAGES"):
        val = os.environ.get(var, "")
        if "zh" in val.lower():
            return "zh"

    # 2. 检查 locale（避免使用已废弃的 getdefaultlocale）
    try:
        loc = locale.getlocale()
        if loc and loc[0]:
            lang = loc[0].lower()
            if "zh" in lang:
                return "zh"
    except (ValueError, locale.Error):
        pass

    return "en"


_current_lang = _detect_language()


def set_language(lang: str) -> None:
    """手动设置语言（用于测试或用户偏好覆盖）。

    Parameters
    ----------
    lang : str
        'zh' 或 'en'。
    """
    global _current_lang
    if lang in ("zh", "en"):
        _current_lang = lang
    else:
        logger.warning("不支持的语言 '%s'，保持 '%s'", lang, _current_lang)


def current_language() -> str:
    """返回当前检测到的语言代码。"""
    return _current_lang


# ── 翻译字典 ─────────────────────────────────────────────────────────────

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # ── CLI ──
        "cli_shell_warning": (
            "URL contains '$' character — if running in double quotes, "
            "the shell may have expanded it as a variable. "
            "Please use single quotes '...' around the URL."
        ),
        "cli_url_decoded": "URL has been percent-decoded.",
        "cli_auth_failed": "Authentication failed: %s",
        "cli_auth_hint": (
            "Please verify the share link is still valid and "
            "the network is accessible."
        ),
        "cli_quote_hint": (
            "Tip: If the URL contains &, ?, $ or other special "
            "characters, please wrap it in single quotes."
        ),
        "cli_no_site_info": (
            "Cannot extract SharePoint site info — "
            "please verify the share link is valid."
        ),
        "cli_no_folder_path": (
            "Cannot extract folder path — "
            "please verify the share link is valid."
        ),
        "cli_scanning_folder": "Scanning file tree...",
        "cli_fetching_file": "Fetching file info...",
        "cli_downloading": "Downloading...",
        "cli_interrupted_title": "⚠ Interrupted",
        "cli_interrupted_msg": (
            "Completed %d/%d, downloaded %s.\n"
            "Re-run the same command to resume."
        ),
        "cli_done_title": "Download Complete",
        "cli_done_success": "Success: %d",
        "cli_done_skipped": "Skipped: %d",
        "cli_done_failed": "Failed: %d",
        "cli_done_elapsed": "Elapsed: %.1fs",
        "cli_done_total": "Total: %s",
        "cli_done_dir": "Directory: %s",
        # ── Session ──
        "sess_authenticating": "Accessing share link for authentication...",
        "sess_share_type_folder": "Share type: folder",
        "sess_share_type_file": "Share type: single file",
        "sess_site": "Site: %s",
        "sess_folder": "Folder: %s",
        "sess_file_guid": "File GUID: %s",
        "sess_filename": "Filename: %s",
        "sess_folder_fallback": (
            "Cannot extract folder path from URL, using default: %s"
        ),
        "sess_no_guid": (
            "No sourcedoc GUID found in URL — download may fail"
        ),
        "sess_found_subfolder": "Found subfolder: %s",
        "sess_fetching_metadata": "Fetching file metadata via GUID...",
        "sess_api_fallback": (
            "Cannot fetch file metadata via API, "
            "using filename from URL"
        ),
        "sess_missing_guid": "Missing file GUID, cannot fetch file info.",
        "sess_fallback_download": (
            "Missing file path, trying GUID-based download URL"
        ),
        "sess_no_download_url": (
            "Cannot construct download URL: "
            "missing both file path and GUID"
        ),
        # ── UI ──
        "ui_title_folder": "SharePoint Batch Download",
        "ui_title_file": "SharePoint File Download",
        "ui_files_count": "%d file(s) · %s",
        "ui_progress_label": "Overall Progress",
        "ui_pending": "Pending: ",
        "ui_completed": "Completed %d/%d",
        "ui_downloaded": "Downloaded %s",
        "ui_failed_count": "Failed %d",
        "ui_exists": "Already exists",
        "ui_paused": "Paused",
        "ui_network_error": "Network error",
        "ui_write_error": "Write error",
    },
    "zh": {
        # ── CLI ──
        "cli_shell_warning": (
            "URL 中包含 '$' 字符，如果在双引号中运行，shell 可能已经对其做了"
            "变量展开。请使用单引号 '...' 包裹 URL。"
        ),
        "cli_url_decoded": "URL 已被 percent-decode。",
        "cli_auth_failed": "认证失败: %s",
        "cli_auth_hint": (
            "请确认分享链接是否仍有效，以及网络连接是否正常。"
        ),
        "cli_quote_hint": (
            "提示: URL 中如有 &、?、$ 等特殊字符，请务必用单引号包裹。"
        ),
        "cli_no_site_info": (
            "无法提取 SharePoint 站点信息，请确认分享链接有效。"
        ),
        "cli_no_folder_path": (
            "无法提取文件夹路径，请确认分享链接有效。"
        ),
        "cli_scanning_folder": "正在扫描文件树...",
        "cli_fetching_file": "正在获取文件信息...",
        "cli_downloading": "下载中...",
        "cli_interrupted_title": "⚠ 用户中断",
        "cli_interrupted_msg": (
            "已完成 %d/%d，下载 %s。\n重新运行相同命令即可断点续传。"
        ),
        "cli_done_title": "下载完成",
        "cli_done_success": "成功: %d",
        "cli_done_skipped": "跳过: %d",
        "cli_done_failed": "失败: %d",
        "cli_done_elapsed": "耗时: %.1fs",
        "cli_done_total": "总计: %s",
        "cli_done_dir": "目录: %s",
        # ── Session ──
        "sess_authenticating": "访问分享链接获取认证...",
        "sess_share_type_folder": "分享类型: 文件夹",
        "sess_share_type_file": "分享类型: 单文件",
        "sess_site": "站点: %s",
        "sess_folder": "文件夹: %s",
        "sess_file_guid": "文件 GUID: %s",
        "sess_filename": "文件名: %s",
        "sess_folder_fallback": (
            "无法从 URL 提取文件夹路径，使用默认值: %s"
        ),
        "sess_no_guid": (
            "未从 URL 提取到 sourcedoc GUID，下载可能失败"
        ),
        "sess_found_subfolder": "发现子文件夹: %s",
        "sess_fetching_metadata": "通过 GUID 获取文件元数据...",
        "sess_api_fallback": (
            "无法通过 API 获取文件元数据，使用 URL 中的文件名"
        ),
        "sess_missing_guid": "缺少文件 GUID，无法获取文件信息。",
        "sess_fallback_download": (
            "缺少文件路径，尝试通过 GUID 构造下载链接"
        ),
        "sess_no_download_url": (
            "无法构造下载 URL：缺少文件路径和 GUID"
        ),
        # ── UI ──
        "ui_title_folder": "SharePoint 批量下载",
        "ui_title_file": "SharePoint 文件下载",
        "ui_files_count": "%d 个文件 · %s",
        "ui_progress_label": "整体进度",
        "ui_pending": "待下载: ",
        "ui_completed": "已完成 %d/%d",
        "ui_downloaded": "已下载 %s",
        "ui_failed_count": "失败 %d",
        "ui_exists": "已存在",
        "ui_paused": "已暂停",
        "ui_network_error": "网络错误",
        "ui_write_error": "写入错误",
    },
}


def t(key: str, *args) -> str:
    """获取当前语言的翻译文本，支持 printf 风格格式化。

    用法:
        t("cli_auth_failed", str(error))
        t("ui_files_count", count, size_str)
    """
    lang_dict = _MESSAGES.get(_current_lang, _MESSAGES["en"])
    template = lang_dict.get(key)
    if template is None:
        # 回退到英文
        template = _MESSAGES["en"].get(key, key)
    if args:
        return template % args
    return template

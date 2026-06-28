"""SharePoint 会话管理 — 认证与 API 调用。

支持两种分享链接：
    - :f: 文件夹分享 → 递归枚举子文件和子文件夹
    - :w:/:x:/:p:/:b: 等文件分享 → 通过 sourcedoc GUID 定位单文件
"""

import json
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .i18n import t
from .utils import safe_quote, safe_quote_strict

logger = logging.getLogger("sharept-dl")

# ── HTTP 请求头 ───────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

API_HEADERS = {"Accept": "application/json;odata=verbose"}

# 单文件分享类型标识（非 :f: 的均为文件分享）
_FILE_SHARE_TYPES = frozenset({":w:", ":x:", ":p:", ":b:", ":t:", ":s:"})


def _detect_share_type(share_url: str) -> str:
    """检测分享链接类型。

    Returns
    -------
    str
        'folder' 或 'file'。
    """
    parsed = urlparse(share_url)
    for part in parsed.path.split("/"):
        if part == ":f:":
            return "folder"
        if part in _FILE_SHARE_TYPES:
            return "file"
    # 默认按文件夹处理（向后兼容）
    return "folder"


def _extract_file_guid(share_url: str) -> Optional[str]:
    """从单文件分享 URL 中提取 sourcedoc GUID。

    例如:  sourcedoc=%7B86800104-82B5-4891-A884-F59294D75F25%7D
          → '86800104-82B5-4891-A884-F59294D75F25'
    """
    parsed = urlparse(share_url)
    qs = parse_qs(parsed.query)
    raw = qs.get("sourcedoc", [None])[0]
    if not raw:
        return None
    decoded = unquote(raw)
    return decoded.strip("{}")


def _extract_file_name(share_url: str) -> Optional[str]:
    """从单文件分享 URL 中提取文件名。"""
    parsed = urlparse(share_url)
    qs = parse_qs(parsed.query)
    raw = qs.get("file", [None])[0]
    if raw:
        return unquote(raw)
    return None


# ── SharePointSession ─────────────────────────────────────────────────────


class SharePointSession:
    """封装对 SharePoint 的认证会话和 API 调用。

    Parameters
    ----------
    share_url : str
        SharePoint 分享链接，支持文件夹（:f:）和单文件（:w:/:x:/:p: 等）。
    timeout : int
        HTTP 请求超时秒数（默认 60）。
    """

    def __init__(self, share_url: str, timeout: int = 60):
        self.share_url = share_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.base_url: str = ""
        self.folder_path: str = ""
        self.is_folder: bool = True
        self.file_guid: Optional[str] = None
        self.file_name: Optional[str] = None

    # ── 认证 ──────────────────────────────────────────────────────────

    def authenticate(self) -> None:
        """访问分享链接，沿重定向链获取认证 cookie。"""
        logger.info(t("sess_authenticating"))
        resp = self.session.get(
            self.share_url, allow_redirects=True, timeout=self.timeout
        )
        resp.raise_for_status()
        logger.debug("最终 URL: %s", resp.url)
        self._extract_context(resp)

    def _extract_context(self, resp: requests.Response) -> None:
        """从重定向后的 URL 和页面中提取 SharePoint 上下文。"""
        final_url = resp.url
        parsed = urlparse(final_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        sp_info: dict = {}

        # 尝试从页面中提取 _spPageContextInfo
        sp_match = re.search(
            r"_spPageContextInfo\s*=\s*(\{.*?\});", resp.text, re.DOTALL
        )
        if sp_match:
            try:
                sp_info = json.loads(sp_match.group(1))
                self.base_url = sp_info.get(
                    "webAbsoluteUrl", self.base_url
                )
            except json.JSONDecodeError:
                pass

        # 检测分享类型
        share_type = _detect_share_type(self.share_url)
        self.is_folder = share_type == "folder"

        if self.is_folder:
            self._extract_folder_context(final_url, sp_info)
        else:
            self._extract_file_context(self.share_url)

    def _extract_folder_context(
        self, final_url: str, sp_info: dict
    ) -> None:
        """从文件夹分享链接中提取上下文。"""
        parsed = urlparse(final_url)
        qs = parse_qs(parsed.query)
        raw_id = qs.get("id", [None])[0]
        if raw_id:
            self.folder_path = unquote(raw_id)
        else:
            id_match = re.search(r"id=([^&]+)", final_url)
            if id_match:
                self.folder_path = unquote(id_match.group(1))

        if not self.folder_path:
            web_rel = sp_info.get(
                "webServerRelativeUrl", "/personal"
            )
            self.folder_path = f"{web_rel}/Documents"
            logger.warning(
                t("sess_folder_fallback", self.folder_path)
            )

        logger.info(t("sess_share_type_folder"))
        logger.info(t("sess_site", self.base_url))
        logger.info(t("sess_folder", self.folder_path))

    def _extract_file_context(self, share_url: str) -> None:
        """从单文件分享链接中提取上下文。"""
        self.file_guid = _extract_file_guid(share_url)
        self.file_name = _extract_file_name(share_url)

        logger.info(t("sess_share_type_file"))
        logger.info(t("sess_site", self.base_url))
        if self.file_guid:
            logger.info(t("sess_file_guid", self.file_guid))
        if self.file_name:
            logger.info(t("sess_filename", self.file_name))

        if not self.file_guid:
            logger.warning(t("sess_no_guid"))

    # ── REST API ──────────────────────────────────────────────────────

    def _api_get(self, api_url: str) -> Optional[dict]:
        """发送 REST API GET 请求，返回 JSON。"""
        try:
            r = self.session.get(
                api_url, headers=API_HEADERS, timeout=self.timeout
            )
            if r.status_code == 200:
                return r.json()
            logger.debug("API 返回 %d: %s", r.status_code, api_url)
            return None
        except requests.RequestException as e:
            logger.warning("API 请求失败: %s", e)
            return None

    def _get_file_by_id(self, guid: str) -> Optional[dict]:
        """通过 GUID 获取文件元数据。

        SharePoint REST API: /_api/web/GetFileById('<guid>')
        """
        api = f"{self.base_url}/_api/web/GetFileById('{guid}')"
        return self._api_get(api)

    def _list_files(self, folder_path: str) -> list[dict]:
        """列出文件夹下的所有文件。"""
        encoded = safe_quote(folder_path)
        api = (
            f"{self.base_url}/_api/web/"
            f"GetFolderByServerRelativeUrl('{encoded}')/Files?$top=5000"
        )
        data = self._api_get(api)
        if not data:
            return []
        return [
            {
                "name": f.get("Name", "unknown"),
                "rel_path": f.get("ServerRelativeUrl", ""),
                "size": int(f.get("Length") or 0),
                "folder": folder_path,
            }
            for f in data.get("d", {}).get("results", [])
        ]

    def _list_folders(self, folder_path: str) -> list[dict]:
        """列出文件夹下的所有子文件夹。"""
        encoded = safe_quote(folder_path)
        api = (
            f"{self.base_url}/_api/web/"
            f"GetFolderByServerRelativeUrl('{encoded}')/Folders?$top=5000"
        )
        data = self._api_get(api)
        if not data:
            return []
        return [
            {"name": d["Name"], "rel_path": d["ServerRelativeUrl"]}
            for d in data.get("d", {}).get("results", [])
        ]

    def collect_all_files(self, folder_path: str = "") -> list[dict]:
        """递归收集文件夹下所有文件。

        对于文件夹分享，使用 folder_path；对于单文件分享，忽略参数。
        """
        if not self.is_folder:
            return self._collect_single_file()

        if not folder_path:
            folder_path = self.folder_path

        all_files: list[dict] = []
        all_files.extend(self._list_files(folder_path))
        for sub in self._list_folders(folder_path):
            logger.info("  " + t("sess_found_subfolder", sub["name"]))
            all_files.extend(
                self.collect_all_files(sub["rel_path"])
            )
        return all_files

    def _collect_single_file(self) -> list[dict]:
        """获取单文件分享的文件信息。"""
        if not self.file_guid:
            logger.error(t("sess_missing_guid"))
            return []

        logger.info(t("sess_fetching_metadata"))
        data = self._get_file_by_id(self.file_guid)

        if not data:
            # 回退：尝试用 URL 中的文件名构造基本信息
            if self.file_name:
                logger.warning(t("sess_api_fallback"))
                return [
                    {
                        "name": self.file_name,
                        "rel_path": "",
                        "size": 0,
                        "folder": "",
                    }
                ]
            return []

        file_info = data.get("d", {})
        name = file_info.get("Name", self.file_name or "unknown")
        rel_path = file_info.get("ServerRelativeUrl", "")
        size = int(file_info.get("Length") or 0)

        return [
            {
                "name": name,
                "rel_path": rel_path,
                "size": size,
                "folder": "",
            }
        ]

    def build_download_url(self, server_rel_url: str) -> str:
        """构建下载 URL。

        使用 safe_quote_strict 避免对已编码路径双重编码。
        优先使用 server_rel_url；如果为空（单文件回退场景），
        使用 GUID 构造备选 URL。
        """
        if server_rel_url:
            encoded = safe_quote_strict(server_rel_url)
            return (
                f"{self.base_url}/_layouts/15/download.aspx"
                f"?SourceUrl={encoded}"
            )

        # 回退：使用 sourcedoc GUID 直接下载
        if self.file_guid:
            logger.warning(t("sess_fallback_download"))
            return (
                f"{self.base_url}/_layouts/15/download.aspx"
                f"?sourcedoc={self.file_guid}"
            )

        raise ValueError(t("sess_no_download_url"))

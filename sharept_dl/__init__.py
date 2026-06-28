"""sharept-dl — SharePoint 批量下载工具。

纯 HTTP 实现，通过分享链接 token 换取 cookie，利用 SharePoint REST API
递归枚举文件和下载，无需浏览器、无需登录。
"""

from ._version import __version__  # noqa: E402, F401

__all__ = [
    "SharePointSession",
    "format_bytes",
    "shorten_path",
    "safe_unquote",
    "safe_quote",
    "safe_quote_strict",
    "t",
    "set_language",
    "current_language",
    "main",
]

from .i18n import current_language, set_language, t  # noqa: E402, F401
from .session import SharePointSession  # noqa: E402, F401
from .utils import (  # noqa: E402, F401
    format_bytes,
    safe_quote,
    safe_quote_strict,
    safe_unquote,
    shorten_path,
)


def main():  # noqa: D401
    """快捷入口函数，不需要传 sys.argv。"""
    import sys

    from .cli import main as _main

    sys.exit(_main())

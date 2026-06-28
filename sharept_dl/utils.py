"""工具函数。"""

import logging
import sys
from typing import Optional

logger = logging.getLogger("sharept-dl")


def format_bytes(size: int) -> str:
    """将字节数格式化为可读字符串。"""
    if size == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    n = float(size)
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}" if i > 0 else f"{int(n)} B"


def shorten_path(path: str, max_len: int = 48) -> str:
    """截断过长的文件名，保留首尾。"""
    if len(path) <= max_len:
        return path
    return path[:max_len - 3] + "..."


def setup_logging(verbose: bool = False) -> None:
    """配置日志输出（仅非 rich 消息使用 stderr）。"""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        )
    )
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False


def safe_unquote(text: str) -> str:
    """安全 unquote：仅在文本包含 %XX 格式的编码序列时才做 decode，
    避免对已解码文本产生副作用。"""
    from urllib.parse import unquote

    if "%" not in text:
        return text
    decoded = unquote(text)
    return decoded


def safe_quote(text: str) -> str:
    """安全 quote：先 unquote 再 quote，避免对已编码文本双重编码。

    例如: '/path/%E4%B8%AD%E6%96%87' → 先 decode 为 '/path/中文' → 再 encode。
    如果输入未被编码，unquote 是 no-op，结果等同于直接 quote。
    """
    from urllib.parse import quote, unquote

    if "%" in text:
        text = unquote(text)
    return quote(text)


def safe_quote_strict(text: str) -> str:
    """安全 quote（严格模式）：编码包括 '/' 在内的所有字符。
    用于 SourceUrl 查询参数值。
    """
    from urllib.parse import quote, unquote

    if "%" in text:
        text = unquote(text)
    return quote(text, safe="")

"""测试工具函数。"""

import logging

import pytest

from sharepoint_dl.utils import (
    format_bytes,
    safe_quote,
    safe_quote_strict,
    safe_unquote,
    setup_logging,
    shorten_path,
)


class TestFormatBytes:
    def test_zero(self):
        assert format_bytes(0) == "0 B"

    def test_bytes(self):
        assert format_bytes(500) == "500 B"
        assert format_bytes(1023) == "1023 B"

    def test_kb(self):
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"

    def test_mb(self):
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(2097152) == "2.0 MB"

    def test_gb(self):
        assert format_bytes(1073741824) == "1.0 GB"

    def test_large_int(self):
        assert format_bytes(2 ** 40) == "1024.0 GB"


class TestShortenPath:
    def test_short_path_unchanged(self):
        assert shorten_path("file.txt") == "file.txt"
        assert shorten_path("a" * 48) == "a" * 48

    def test_long_path_shortened(self):
        long_name = "a" * 60
        result = shorten_path(long_name)
        assert len(result) <= 48
        assert result.endswith("...")

    def test_custom_max_len(self):
        result = shorten_path("a" * 30, max_len=20)
        assert len(result) <= 20


class TestSafeUnquote:
    def test_no_percent_unchanged(self):
        """不含 % 的文本原样返回。"""
        url = "https://example.com/path/to/file"
        assert safe_unquote(url) == url

    def test_empty_string(self):
        assert safe_unquote("") == ""

    def test_with_percent_encoding(self):
        """%XX 编码被正确解码。"""
        encoded = "https://example.com/path%20with%20spaces"
        decoded = safe_unquote(encoded)
        assert decoded == "https://example.com/path with spaces"

    def test_with_chinese_url_encoding(self):
        """URL 编码的中文被正确解码。"""
        encoded = "/path/%E4%B8%AD%E6%96%87"
        decoded = safe_unquote(encoded)
        assert decoded == "/path/中文"

    def test_with_percent_character_not_encoding(self):
        """单独的 % 字符（不是有效 %XX 序列）保持原样。"""
        text = "50% off"
        assert safe_unquote(text) == "50% off"

    def test_sharepoint_url_unchanged(self):
        """正常 SharePoint 分享链接不变。"""
        url = (
            "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc123?e=def"
        )
        assert safe_unquote(url) == url


class TestSafeQuote:
    def test_normal_path(self):
        """正常路径被正确编码。"""
        result = safe_quote("/personal/xxx/My Documents")
        assert "%20" in result
        assert "My%20Documents" in result

    def test_chinese_path(self):
        """中文路径被正确编码。"""
        result = safe_quote("/path/答辩证据")
        assert "%E7%AD%94" in result

    def test_no_double_encoding(self):
        """已编码路径不会双重编码。"""
        encoded = "/path/%E4%B8%AD%E6%96%87"
        result = safe_quote(encoded)
        # 应该不是 %25 — 双重编码的标志
        assert "%25" not in result
        # 结果应该与直接编码 decoded 版本相同
        from urllib.parse import unquote

        assert result == safe_quote(unquote(encoded))

    def test_special_chars(self):
        """特殊字符被正确编码。"""
        result = safe_quote("/path/file & stuff")
        assert "%26" in result

    def test_safe_default_preserves_slash(self):
        """默认 safe 保留 /。"""
        result = safe_quote("/a/b/c")
        assert result.startswith("/")
        assert "/" in result


class TestSafeQuoteStrict:
    def test_encodes_slash(self):
        """严格模式也编码 /。"""
        result = safe_quote_strict("/personal/xxx/file.txt")
        assert not result.startswith("/")
        assert "%2F" in result

    def test_no_double_encoding_strict(self):
        """严格模式也不会双重编码。"""
        encoded = "%2Fpersonal%2Fxxx%2Ffile.txt"
        result = safe_quote_strict(encoded)
        assert "%25" not in result

    def test_sharepoint_download_url_format(self):
        """生成 SharePoint 下载 URL 的 SourceUrl 参数格式。"""
        path = "/personal/xxx/Documents/file.txt"
        result = safe_quote_strict(path)
        # 整个路径应该被编码为单一 blob（无 / 前缀）
        assert "%2Fpersonal%2Fxxx%2FDocuments%2Ffile.txt" == result


class TestSetupLogging:
    def test_creates_logger(self):
        logger = logging.getLogger("sharept-dl")
        # 清除已有 handler 后设置
        setup_logging(verbose=False)
        assert len(logger.handlers) >= 1

    def test_verbose_sets_debug(self):
        logger = logging.getLogger("sharept-dl")
        setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_normal_sets_info(self):
        logger = logging.getLogger("sharept-dl")
        setup_logging(verbose=False)
        assert logger.level == logging.INFO

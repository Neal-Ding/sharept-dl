"""测试 CLI 参数解析。"""

import argparse

import pytest

from sharept_dl.cli import _get_local_path, parse_args
from sharept_dl.session import SharePointSession


class TestParseArgs:
    def test_required_url(self):
        args = parse_args(["-u", "https://example.com/share"])
        assert args.url == "https://example.com/share"

    def test_url_with_long_flag(self):
        args = parse_args(
            ["--url", "https://example.com/share"]
        )
        assert args.url == "https://example.com/share"

    def test_default_output(self):
        args = parse_args(["-u", "https://example.com/share"])
        assert args.output == "."

    def test_custom_output(self):
        args = parse_args(
            ["-u", "https://example.com/share", "-o", "./downloads"]
        )
        assert args.output == "./downloads"

    def test_default_timeout(self):
        args = parse_args(["-u", "https://example.com/share"])
        assert args.timeout == 60

    def test_custom_timeout(self):
        args = parse_args(
            ["-u", "https://example.com/share", "-t", "120"]
        )
        assert args.timeout == 120

    def test_default_delay(self):
        args = parse_args(["-u", "https://example.com/share"])
        assert args.delay == 0.3

    def test_custom_delay(self):
        args = parse_args(
            ["-u", "https://example.com/share", "-d", "0.5"]
        )
        assert args.delay == 0.5

    def test_resume_default(self):
        """默认启用断点续传。"""
        args = parse_args(["-u", "https://example.com/share"])
        assert args.resume is True

    def test_no_resume_flag(self):
        args = parse_args(
            ["-u", "https://example.com/share", "--no-resume"]
        )
        assert args.resume is False

    def test_verbose_default(self):
        args = parse_args(["-u", "https://example.com/share"])
        assert args.verbose is False

    def test_verbose_flag(self):
        args = parse_args(
            ["-u", "https://example.com/share", "-v"]
        )
        assert args.verbose is True

    def test_missing_url_raises(self):
        with pytest.raises(SystemExit):
            parse_args([])

    def test_sharepoint_url_format(self):
        """SharePoint 分享链接格式。"""
        url = (
            "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc123"
            "?e=def456"
        )
        args = parse_args(["-u", url])
        assert ":f:" in args.url
        assert "sharepoint.cn" in args.url

    def test_url_with_special_chars_in_quotes(self):
        """URL 中的特殊字符（模拟已在 shell 中正确引用）。"""
        url = (
            "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc"
            "?e=def&download=1"
        )
        args = parse_args(["-u", url])
        assert "&download=1" in args.url
        assert "?" in args.url


class TestParseArgsEdgeCases:
    def test_url_with_spaces(self):
        """URL 编码的空格。"""
        url = "https://example.com/path%20with%20spaces"
        args = parse_args(["-u", url])
        assert args.url == url

    def test_url_with_chinese_in_path(self):
        """路径中的中文字符。"""
        url = (
            "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc"
            "?id=%2Fpersonal%2Fxxx%2F%E8%AF%81%E6%8D%AE"
        )
        args = parse_args(["-u", url])
        assert args.url == url

    def test_all_short_flags(self):
        args = parse_args(
            [
                "-u", "https://example.com/share",
                "-o", "/tmp/out",
                "-t", "30",
                "-d", "0.1",
                "-v",
            ]
        )
        assert args.url == "https://example.com/share"
        assert args.output == "/tmp/out"
        assert args.timeout == 30
        assert args.delay == 0.1
        assert args.verbose is True

    def test_single_file_url(self):
        """单文件分享链接被正确解析。"""
        url = (
            "https://xxx.sharepoint.cn/:w:/r/personal/"
            "user/_layouts/15/Doc.aspx"
            "?sourcedoc=%7Babc-123%7D&file=document.docx"
        )
        args = parse_args(["-u", url])
        assert ":w:" in args.url
        assert "sourcedoc=" in args.url


class TestGetLocalPath:
    """测试 _get_local_path 辅助函数。"""

    def test_folder_share_strips_prefix(self):
        sp = SharePointSession("https://x.com/:f:/g/p/xxx/Eabc")
        sp.is_folder = True
        sp.folder_path = "/personal/xxx/Documents"
        file_info = {
            "name": "report.docx",
            "rel_path": "/personal/xxx/Documents/sub/report.docx",
        }
        result = _get_local_path(sp, file_info)
        assert result == "sub/report.docx"

    def test_folder_share_no_prefix_match(self):
        sp = SharePointSession("https://x.com/:f:/g/p/xxx/Eabc")
        sp.is_folder = True
        sp.folder_path = "/personal/xxx/Documents"
        file_info = {
            "name": "other.docx",
            "rel_path": "/different/path/other.docx",
        }
        result = _get_local_path(sp, file_info)
        assert result == "other.docx"

    def test_single_file_uses_name(self):
        sp = SharePointSession(
            "https://x.com/:w:/r/p/xxx/Doc.aspx?sourcedoc=abc&file=test.docx"
        )
        sp.is_folder = False
        file_info = {
            "name": "test.docx",
            "rel_path": "/personal/xxx/Documents/test.docx",
        }
        result = _get_local_path(sp, file_info)
        assert result == "test.docx"

    def test_single_file_chinese_name(self):
        sp = SharePointSession(
            "https://x.com/:w:/r/p/xxx/Doc.aspx?sourcedoc=abc&file=文件.docx"
        )
        sp.is_folder = False
        file_info = {
            "name": "示例文件.docx",
            "rel_path": "/personal/xxx/Documents/示例文件.docx",
        }
        result = _get_local_path(sp, file_info)
        assert result == "示例文件.docx"

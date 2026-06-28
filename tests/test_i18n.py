"""测试 i18n 国际化模块。"""

import os

import pytest

from sharept_dl.i18n import (
    _detect_language,
    current_language,
    set_language,
    t,
)


class TestDetectLanguage:
    """测试语言检测逻辑（纯函数，不依赖模块级状态）。"""

    def test_zh_detected_from_lang_env(self, monkeypatch):
        monkeypatch.setenv("LANG", "zh_CN.UTF-8")
        monkeypatch.delenv("LANGUAGE", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        assert _detect_language() == "zh"

    def test_zh_detected_from_lc_all(self, monkeypatch):
        monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.delenv("LANGUAGE", raising=False)
        assert _detect_language() == "zh"

    def test_en_when_no_zh_env(self, monkeypatch):
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        monkeypatch.delenv("LANGUAGE", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        # Mock getlocale 以防系统 locale 恰好是中文
        import locale as _locale
        monkeypatch.setattr(_locale, "getlocale", lambda: ("en_US", "UTF-8"))
        assert _detect_language() == "en"

    def test_en_when_no_env_at_all(self, monkeypatch):
        monkeypatch.delenv("LANGUAGE", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        import locale as _locale
        monkeypatch.setattr(_locale, "getlocale", lambda: ("en_US", "UTF-8"))
        assert _detect_language() == "en"


class TestSetLanguage:
    """测试手动设置语言。"""

    def test_set_to_en(self):
        set_language("en")
        assert current_language() == "en"

    def test_set_to_zh(self):
        set_language("zh")
        assert current_language() == "zh"

    def test_invalid_lang_ignored(self):
        set_language("fr")
        # 保持之前设置的语言不变
        assert current_language() in ("en", "zh")


class TestTranslation:
    """测试翻译功能（使用 set_language 精确控制）。"""

    def test_english_translation(self):
        set_language("en")
        assert t("cli_scanning_folder") == "Scanning file tree..."
        assert t("sess_authenticating") == (
            "Accessing share link for authentication..."
        )

    def test_chinese_translation(self):
        set_language("zh")
        assert t("cli_scanning_folder") == "正在扫描文件树..."
        assert t("sess_authenticating") == "访问分享链接获取认证..."

    def test_formatted_string_en(self):
        set_language("en")
        result = t("cli_auth_failed", "Connection refused")
        assert "Connection refused" in result
        assert "Authentication failed" in result

    def test_formatted_string_zh(self):
        set_language("zh")
        result = t("cli_auth_failed", "Connection refused")
        assert "Connection refused" in result
        assert "认证失败" in result

    def test_missing_key_falls_back_to_english(self):
        set_language("zh")
        result = t("nonexistent_key")
        assert result == "nonexistent_key"

    def test_all_keys_in_both_languages(self):
        """验证中英文翻译键表完全一致。"""
        from sharept_dl.i18n import _MESSAGES

        en_keys = set(_MESSAGES["en"].keys())
        zh_keys = set(_MESSAGES["zh"].keys())
        assert en_keys == zh_keys, (
            f"Key mismatch — only in en: {en_keys - zh_keys}, "
            f"only in zh: {zh_keys - en_keys}"
        )

    def test_current_language_returns_string(self):
        lang = current_language()
        assert isinstance(lang, str)
        assert lang in ("en", "zh")

    def test_set_language_then_t(self):
        """切换语言后翻译立即生效。"""
        set_language("en")
        assert "Scanning" in t("cli_scanning_folder")
        set_language("zh")
        assert "扫描" in t("cli_scanning_folder")
        set_language("en")
        assert "Scanning" in t("cli_scanning_folder")

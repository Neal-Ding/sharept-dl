"""测试 SharePointSession — 使用 requests_mock 模拟 HTTP。"""

import pytest
import requests
import requests_mock

from sharepoint_dl.session import (
    SharePointSession,
    _detect_share_type,
    _extract_file_guid,
    _extract_file_name,
)

SHARE_URL = "https://xxx.sharepoint.cn/:f:/g/personal/neal_test/Eabc123?e=def456"
BASE_URL = "https://xxx.sharepoint.cn"
FOLDER_PATH = "/personal/neal_test/Documents"


@pytest.fixture
def mock_sharepoint_page():
    """模拟 SharePoint 认证页面 HTML。"""
    return f"""
    <html>
    <head></head>
    <body>
    <script>
    var _spPageContextInfo = {{
        "webAbsoluteUrl": "{BASE_URL}",
        "webServerRelativeUrl": "/personal/neal_test"
    }};
    </script>
    </body>
    </html>
    """


@pytest.fixture
def session():
    return SharePointSession(SHARE_URL, timeout=30)


class TestInit:
    def test_default_values(self, session):
        assert session.share_url == SHARE_URL
        assert session.timeout == 30
        assert session.base_url == ""
        assert session.folder_path == ""

    def test_custom_timeout(self):
        sp = SharePointSession(SHARE_URL, timeout=120)
        assert sp.timeout == 120

    def test_session_headers_set(self, session):
        assert "User-Agent" in session.session.headers
        assert "Accept-Language" in session.session.headers


class TestAuthenticate:
    def test_basic_redirect_flow(self, session, mock_sharepoint_page):
        """测试基本重定向认证流程。"""
        with requests_mock.Mocker() as m:
            # 模拟分享链接的重定向链
            m.get(
                SHARE_URL,
                text=mock_sharepoint_page,
                status_code=200,
            )
            session.authenticate()
            assert session.base_url == BASE_URL
            assert session.folder_path != ""

    def test_extract_base_url_from_pageinfo(self, session):
        """从 _spPageContextInfo 提取站点 URL。"""
        with requests_mock.Mocker() as m:
            m.get(
                SHARE_URL,
                text=f"""
                <script>
                var _spPageContextInfo = {{
                    "webAbsoluteUrl": "https://custom.sharepoint.cn"
                }};
                </script>
                """,
                status_code=200,
            )
            session.authenticate()
            assert session.base_url == "https://custom.sharepoint.cn"

    def test_extract_folder_from_id_param(self, session):
        """从 URL id 参数提取文件夹路径。"""
        redirect_url = (
            f"{BASE_URL}/:f:/g/personal/neal_test/Eabc123"
            f"?id={FOLDER_PATH}"
        )
        with requests_mock.Mocker() as m:
            m.get(SHARE_URL, text="<html></html>", status_code=200)
            # 模拟最终 URL
            session.authenticate()
            # 注意：这里测试的是 _extract_context 的 URL 解析，
            # 实际 authenticate 会跟随重定向
        # 单独测试 _extract_context
        mock_resp = requests.Response()
        mock_resp.url = redirect_url
        mock_resp._content = b"<html></html>"
        mock_resp.status_code = 200
        session._extract_context(mock_resp)
        assert session.folder_path == FOLDER_PATH

    def test_fallback_folder_path(self, session):
        """无法提取路径时使用默认值。"""
        mock_resp = requests.Response()
        mock_resp.url = f"{BASE_URL}/:f:/g/personal/neal_test/Eabc123"
        mock_resp._content = b"<html></html>"
        mock_resp.status_code = 200
        session._extract_context(mock_resp)
        assert session.folder_path != ""
        assert "Documents" in session.folder_path

    def test_http_error_raises(self, session):
        """HTTP 错误应抛出。"""
        with requests_mock.Mocker() as m:
            m.get(SHARE_URL, status_code=403)
            with pytest.raises(requests.RequestException):
                session.authenticate()


class TestApiCalls:
    def test_list_files_empty(self, session):
        """空文件夹返回空列表。"""
        session.base_url = BASE_URL
        with requests_mock.Mocker() as m:
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Files",
                json={"d": {"results": []}},
                status_code=200,
            )
            result = session._list_files(FOLDER_PATH)
            assert result == []

    def test_list_files_with_results(self, session):
        """正常文件列表解析。"""
        session.base_url = BASE_URL
        api_response = {
            "d": {
                "results": [
                    {
                        "Name": "file1.docx",
                        "ServerRelativeUrl": f"{FOLDER_PATH}/file1.docx",
                        "Length": "102400",
                    },
                    {
                        "Name": "file2.pdf",
                        "ServerRelativeUrl": f"{FOLDER_PATH}/file2.pdf",
                        "Length": "204800",
                    },
                ]
            }
        }
        with requests_mock.Mocker() as m:
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Files",
                json=api_response,
                status_code=200,
            )
            result = session._list_files(FOLDER_PATH)
            assert len(result) == 2
            assert result[0]["name"] == "file1.docx"
            assert result[0]["size"] == 102400
            assert result[1]["name"] == "file2.pdf"

    def test_list_files_api_error(self, session):
        """API 返回非 200 时返回空列表。"""
        session.base_url = BASE_URL
        with requests_mock.Mocker() as m:
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Files",
                status_code=500,
            )
            result = session._list_files(FOLDER_PATH)
            assert result == []

    def test_list_folders(self, session):
        """子文件夹列表解析。"""
        session.base_url = BASE_URL
        api_response = {
            "d": {
                "results": [
                    {
                        "Name": "subfolder1",
                        "ServerRelativeUrl": f"{FOLDER_PATH}/subfolder1",
                    },
                ]
            }
        }
        with requests_mock.Mocker() as m:
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Folders",
                json=api_response,
                status_code=200,
            )
            result = session._list_folders(FOLDER_PATH)
            assert len(result) == 1
            assert result[0]["name"] == "subfolder1"

    def test_collect_all_files_recursive(self, session):
        """递归收集所有文件。"""
        session.base_url = BASE_URL

        with requests_mock.Mocker() as m:
            # 根目录文件
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Files",
                json={
                    "d": {
                        "results": [
                            {
                                "Name": "root.txt",
                                "ServerRelativeUrl": f"{FOLDER_PATH}/root.txt",
                                "Length": "100",
                            }
                        ]
                    }
                },
                status_code=200,
            )
            # 根目录子文件夹
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}')/Folders",
                json={
                    "d": {
                        "results": [
                            {
                                "Name": "sub",
                                "ServerRelativeUrl": f"{FOLDER_PATH}/sub",
                            }
                        ]
                    }
                },
                status_code=200,
            )
            # 子文件夹文件
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}/sub')/Files",
                json={
                    "d": {
                        "results": [
                            {
                                "Name": "sub_file.txt",
                                "ServerRelativeUrl": f"{FOLDER_PATH}/sub/sub_file.txt",
                                "Length": "200",
                            }
                        ]
                    }
                },
                status_code=200,
            )
            # 子文件夹无子文件夹
            m.get(
                f"{BASE_URL}/_api/web/"
                f"GetFolderByServerRelativeUrl('{FOLDER_PATH}/sub')/Folders",
                json={"d": {"results": []}},
                status_code=200,
            )

            result = session.collect_all_files(FOLDER_PATH)
            assert len(result) == 2
            names = {f["name"] for f in result}
            assert names == {"root.txt", "sub_file.txt"}


class TestBuildDownloadUrl:
    def test_normal_path(self, session):
        session.base_url = BASE_URL
        url = session.build_download_url(
            "/personal/xxx/Documents/file.docx"
        )
        assert url.startswith(BASE_URL)
        assert "/_layouts/15/download.aspx" in url
        assert "SourceUrl=" in url

    def test_path_with_special_chars(self, session):
        """特殊字符路径的下载 URL 正确编码。"""
        session.base_url = BASE_URL
        url = session.build_download_url(
            "/personal/xxx/Documents/My File & Stuff.docx"
        )
        # & 应该被编码为 %26，避免破坏 URL 查询参数
        assert "%26" in url.split("SourceUrl=")[1]
        # 不应该包含原始 &
        source_url = url.split("SourceUrl=")[1]
        assert "&" not in source_url

    def test_path_with_chinese_chars(self, session):
        """中文路径的下载 URL 正确编码。"""
        session.base_url = BASE_URL
        url = session.build_download_url(
            "/personal/xxx/答辩证据/文件.docx"
        )
        source_url = url.split("SourceUrl=")[1]
        # 中文字符应被 percent-encode
        assert "%E7%AD%94" in source_url or "%E6%96%87" in source_url

    def test_no_double_encoding(self, session):
        """已编码路径不会双重编码。"""
        session.base_url = BASE_URL
        encoded_path = "/personal/xxx/%E4%B8%AD%E6%96%87.docx"
        url = session.build_download_url(encoded_path)
        # 不应出现 %25（双重编码标志）
        source_url = url.split("SourceUrl=")[1]
        assert "%25" not in source_url


# ── 单文件分享测试 ──────────────────────────────────────────────────────

SINGLE_FILE_URL = (
    "https://tianyuanlaw-my.sharepoint.cn/:w:/r/personal/"
    "cuibin_tylaw_com_cn/_layouts/15/Doc.aspx"
    "?sourcedoc=%7B86800104-82B5-4891-A884-F59294D75F25%7D"
    "&file=%E5%85%B3%E4%BA%8E%E8%B5%B5%E5%9B%BD%E5%AF%8C.docx"
    "&action=default&mobileredirect=true"
)
SINGLE_FILE_GUID = "86800104-82B5-4891-A884-F59294D75F25"


class TestDetectShareType:
    def test_folder_share(self):
        url = "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc"
        assert _detect_share_type(url) == "folder"

    def test_word_share(self):
        url = "https://xxx.sharepoint.cn/:w:/r/personal/xxx/Doc.aspx?sourcedoc=..."
        assert _detect_share_type(url) == "file"

    def test_excel_share(self):
        url = "https://xxx.sharepoint.cn/:x:/g/personal/xxx/Eabc"
        assert _detect_share_type(url) == "file"

    def test_powerpoint_share(self):
        url = "https://xxx.sharepoint.cn/:p:/g/personal/xxx/Eabc"
        assert _detect_share_type(url) == "file"

    def test_unknown_defaults_to_folder(self):
        url = "https://xxx.sharepoint.cn/:z:/g/personal/xxx/Eabc"
        assert _detect_share_type(url) == "folder"


class TestExtractFileGuid:
    def test_extract_guid(self):
        guid = _extract_file_guid(SINGLE_FILE_URL)
        assert guid == SINGLE_FILE_GUID

    def test_no_sourcedoc_returns_none(self):
        url = "https://xxx.sharepoint.cn/:f:/g/personal/xxx/Eabc"
        assert _extract_file_guid(url) is None

    def test_guid_strips_braces(self):
        url = (
            "https://xxx.sharepoint.cn/:w:/g/personal/xxx/"
            "Doc.aspx?sourcedoc=%7Babc-def%7D"
        )
        assert _extract_file_guid(url) == "abc-def"


class TestExtractFileName:
    def test_extract_decoded_filename(self):
        name = _extract_file_name(SINGLE_FILE_URL)
        assert "赵国富" in name
        assert name.endswith(".docx")

    def test_no_file_param_returns_none(self):
        url = "https://xxx.sharepoint.cn/:w:/g/personal/xxx/Doc.aspx?sourcedoc=abc"
        assert _extract_file_name(url) is None


class TestSingleFileSession:
    @pytest.fixture
    def sf_session(self):
        return SharePointSession(SINGLE_FILE_URL, timeout=30)

    def test_is_folder_false_after_init(self, sf_session):
        """初始化后 is_folder 默认为 True，认证后才确定。"""
        assert sf_session.is_folder is True

    def test_detect_type_from_url(self, sf_session):
        """从 URL 检测分享类型。"""
        share_type = _detect_share_type(sf_session.share_url)
        assert share_type == "file"

    def test_authenticate_extracts_file_context(self, sf_session):
        """认证后提取文件上下文。"""
        with requests_mock.Mocker() as m:
            m.get(SINGLE_FILE_URL, text="<html></html>", status_code=200)
            sf_session.authenticate()
            assert sf_session.is_folder is False
            assert sf_session.file_guid == SINGLE_FILE_GUID
            assert sf_session.file_name is not None
            assert "赵国富" in sf_session.file_name

    def test_collect_all_files_single(self, sf_session):
        """单文件 collect_all_files 调用 _collect_single_file。"""
        sf_session.base_url = BASE_URL
        sf_session.is_folder = False
        sf_session.file_guid = SINGLE_FILE_GUID
        sf_session.file_name = "test.docx"

        with requests_mock.Mocker() as m:
            # Mock GetFileById
            m.get(
                f"{BASE_URL}/_api/web/GetFileById('{SINGLE_FILE_GUID}')",
                json={
                    "d": {
                        "Name": "test.docx",
                        "ServerRelativeUrl": "/personal/xxx/Documents/test.docx",
                        "Length": "50000",
                    }
                },
                status_code=200,
            )
            result = sf_session.collect_all_files()
            assert len(result) == 1
            assert result[0]["name"] == "test.docx"
            assert result[0]["size"] == 50000
            assert result[0]["rel_path"] == "/personal/xxx/Documents/test.docx"

    def test_collect_single_file_api_failure_fallback(self, sf_session):
        """API 失败时回退到 URL 中的文件名。"""
        sf_session.base_url = BASE_URL
        sf_session.is_folder = False
        sf_session.file_guid = SINGLE_FILE_GUID
        sf_session.file_name = "fallback.docx"

        with requests_mock.Mocker() as m:
            m.get(
                f"{BASE_URL}/_api/web/GetFileById('{SINGLE_FILE_GUID}')",
                status_code=500,
            )
            result = sf_session.collect_all_files()
            assert len(result) == 1
            assert result[0]["name"] == "fallback.docx"
            assert result[0]["size"] == 0

    def test_collect_single_file_no_guid_no_name(self, sf_session):
        """既无 GUID 也无文件名时返回空列表。"""
        sf_session.is_folder = False
        sf_session.file_guid = None
        sf_session.file_name = None
        result = sf_session.collect_all_files()
        assert result == []

    def test_build_download_url_with_empty_path(self, sf_session):
        """rel_path 为空时回退到 GUID 构造 URL。"""
        sf_session.base_url = BASE_URL
        sf_session.file_guid = SINGLE_FILE_GUID
        url = sf_session.build_download_url("")
        assert "/_layouts/15/download.aspx" in url
        assert f"sourcedoc={SINGLE_FILE_GUID}" in url

    def test_build_download_url_no_path_no_guid_raises(self, sf_session):
        """既无路径也无 GUID 时抛出异常。"""
        sf_session.file_guid = None
        with pytest.raises(ValueError, match=r"Cannot construct download URL|无法构造下载 URL"):
            sf_session.build_download_url("")

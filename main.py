#!/usr/bin/env python3
"""
SharePoint 批量下载工具

纯 HTTP 实现 — 利用分享链接中的 token 换取 cookie，然后通过 SharePoint REST API
递归枚举文件和下载，无需浏览器、无需登录。

特性:
    - 预扫描报告（文件数 + 总大小）
    - 稳定终端界面（不滚动、不闪烁），展示最近 10 条下载状态
    - 断点续传（HTTP Range 请求 + .part 临时文件）
    - 友好中断处理（Ctrl+C 无 Traceback）
    - 自动跳过已完整下载的文件
    - 安全处理 URL 编码与特殊字符路径

依赖: requests, rich

使用:
    python main.py -u 'https://xxx.sharepoint.cn/:f:/g/personal/...' -o ./downloads

注意:
    URL 请务必使用单引号 '...' 包裹，双引号会导致 shell 解释特殊字符。
"""

if __name__ == "__main__":
    import sys

    from sharepoint_dl.cli import main

    sys.exit(main())

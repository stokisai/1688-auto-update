"""
动态获取 Chrome 浏览器版本，用于生成匹配的 User-Agent。
"""

import subprocess
import re
import sys


def get_chrome_version() -> str:
    """
    获取本机安装的 Chrome 浏览器版本号。

    Returns:
        版本号字符串，如 "146.0.7680.80"；获取失败时返回 None。
    """
    if sys.platform == "win32":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in paths:
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     f"(Get-Item '{path}').VersionInfo.FileVersion"],
                    capture_output=True, text=True, timeout=10
                )
                version = result.stdout.strip()
                if re.match(r"\d+\.\d+\.\d+\.\d+", version):
                    return version
            except Exception:
                continue
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                capture_output=True, text=True, timeout=10
            )
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
        except Exception:
            pass
    else:
        for cmd in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
            except Exception:
                continue
    return None


def get_user_agent(chrome_version: str = None) -> str:
    """
    生成与本机 Chrome 版本匹配的 User-Agent 字符串。

    Args:
        chrome_version: 可选，手动指定版本号。为 None 时自动检测。

    Returns:
        User-Agent 字符串。
    """
    if chrome_version is None:
        chrome_version = get_chrome_version()
    if chrome_version is None:
        chrome_version = "130.0.0.0"  # 安全的回退版本
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_version} Safari/537.36"
    )

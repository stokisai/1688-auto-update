# -*- coding: utf-8 -*-
"""
一键发版脚本

用法:
    python release.py <版本号> <更新说明>

示例:
    python release.py 2.3.8 "修复Chrome浏览器启动问题"

流程:
    1. 更新 version.json (版本号、下载URL、changelog)
    2. PyInstaller 打包
    3. 创建 release zip
    4. Git commit & push
    5. 创建 GitHub Release 并上传 zip
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
VERSION_FILE = PROJECT_DIR / "version.json"
REPO = "stokisai/1688-auto-update"


def run(cmd, check=True, capture=False):
    """执行命令并打印"""
    print(f"  > {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=str(PROJECT_DIR),
        capture_output=capture, text=True,
    )
    if check and result.returncode != 0:
        if capture:
            print(f"  STDERR: {result.stderr}")
        print(f"  命令失败，退出码: {result.returncode}")
        sys.exit(1)
    return result


def main():
    if len(sys.argv) < 3:
        print("用法: python release.py <版本号> <更新说明>")
        print('示例: python release.py 2.3.8 "修复Chrome浏览器启动问题"')
        sys.exit(1)

    version = sys.argv[1]
    changelog = sys.argv[2]
    tag = f"v{version}"
    zip_name = f"AI_v{version}.zip"
    zip_path = PROJECT_DIR / "dist" / zip_name
    download_url = f"https://github.com/{REPO}/releases/download/{tag}/{zip_name}"

    print(f"\n{'='*50}")
    print(f"  发版: {tag}")
    print(f"  说明: {changelog}")
    print(f"  文件: {zip_name}")
    print(f"{'='*50}\n")

    # 1. 更新 version.json
    print("[1/5] 更新 version.json")
    version_info = {
        "version": version,
        "app_name": "AI绘画工具",
        "download_url": download_url,
        "changelog": f"{version} - {changelog}",
    }
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(version_info, f, ensure_ascii=False, indent=2)
    print(f"  版本号: {version}")
    print(f"  下载URL: {download_url}\n")

    # 2. PyInstaller 打包
    print("[2/5] PyInstaller 打包")
    run("python -m PyInstaller build.spec --noconfirm")
    app_dir = PROJECT_DIR / "dist" / "AI_Drawing_Tool"
    if not app_dir.exists():
        print(f"  错误: 打包目录不存在 {app_dir}")
        sys.exit(1)
    print("  打包完成\n")

    # 3. 创建 release zip
    print("[3/5] 创建 release zip")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    run("python create_release_zip.py")
    if not zip_path.exists():
        print(f"  错误: zip文件不存在 {zip_path}")
        sys.exit(1)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"  文件大小: {size_mb:.1f} MB\n")

    # 4. Git commit & push
    print("[4/5] Git commit & push")
    run("git add version.json")
    run(f'git commit -m "{tag} - {changelog}"')
    run("git push origin main")
    print("  推送完成\n")

    # 5. 创建 GitHub Release
    print("[5/5] 创建 GitHub Release")
    notes = f"## {tag} - {changelog}"
    run(f'gh release create {tag} "{zip_path}" --title "{tag}" --notes "{notes}"')

    # 验证
    result = run(f"gh release view {tag} --json assets --jq \".assets[].name\"", capture=True)
    print(f"  Release 文件: {result.stdout.strip()}")

    print(f"\n{'='*50}")
    print(f"  发版完成! {tag}")
    print(f"  https://github.com/{REPO}/releases/tag/{tag}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

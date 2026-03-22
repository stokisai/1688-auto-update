"""
将更新包上传到阿里云 OSS

使用方法:
    python upload_to_oss.py <zip文件路径> <版本号>

示例:
    python upload_to_oss.py ./dist/AI_Drawing_Tool.zip 2.2.0

环境变量 (从 GitHub Secrets 或 Railway Variables 获取):
    OSS_KEY      - 阿里云 AccessKey ID
    OSS_SECRET   - 阿里云 AccessKey Secret
    OSS_BUCKET   - Bucket 名称 (默认: n8n-labels-923847)
    OSS_ENDPOINT - Endpoint (默认: https://oss-cn-hongkong.aliyuncs.com)
"""

import json
import os
import sys

import oss2


OSS_KEY = os.environ.get("OSS_KEY", "")
OSS_SECRET = os.environ.get("OSS_SECRET", "")
OSS_BUCKET = os.environ.get("OSS_BUCKET", "n8n-labels-923847")
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "https://oss-cn-hongkong.aliyuncs.com")
OSS_CUSTOM_DOMAIN = os.environ.get("OSS_CUSTOM_DOMAIN", "labels.stokisai.com")
OSS_PREFIX = "comfyui-app"


def upload_update(zip_path: str, version: str, changelog: str = ""):
    """上传更新包和 version.json 到 OSS"""

    if not OSS_KEY or not OSS_SECRET:
        print("错误: 请设置 OSS_KEY 和 OSS_SECRET 环境变量")
        sys.exit(1)

    if not os.path.exists(zip_path):
        print(f"错误: 文件不存在: {zip_path}")
        sys.exit(1)

    auth = oss2.Auth(OSS_KEY, OSS_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)

    # 上传 zip 文件
    zip_filename = f"AI_v{version}.zip"
    zip_key = f"{OSS_PREFIX}/{zip_filename}"

    print(f"[1] 正在上传更新包: {zip_path} -> {zip_key}")
    with open(zip_path, "rb") as f:
        bucket.put_object(zip_key, f)
    print(f"    上传成功!")

    # 生成 version.json
    download_url = f"http://{OSS_CUSTOM_DOMAIN}/{zip_key}"
    version_info = {
        "version": version,
        "app_name": "AI绘画工具",
        "download_url": download_url,
        "changelog": changelog or f"v{version} 更新",
    }

    version_key = f"{OSS_PREFIX}/version.json"
    print(f"[2] 正在上传 version.json -> {version_key}")
    bucket.put_object(
        version_key,
        json.dumps(version_info, ensure_ascii=False, indent=2).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"    上传成功!")

    print(f"\n=== 发布完成 ===")
    print(f"版本: v{version}")
    print(f"更新检查地址: http://{OSS_CUSTOM_DOMAIN}/{version_key}")
    print(f"下载地址: {download_url}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python upload_to_oss.py <zip文件路径> <版本号> [更新日志]")
        print("示例: python upload_to_oss.py ./dist/AI_v2.2.0.zip 2.2.0 \"修复了某某问题\"")
        sys.exit(1)

    zip_file = sys.argv[1]
    ver = sys.argv[2]
    log = sys.argv[3] if len(sys.argv) > 3 else ""
    upload_update(zip_file, ver, log)

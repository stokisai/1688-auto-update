# -*- coding: utf-8 -*-
"""
创建发布 zip 包的脚本

使用方法：
1. 先运行 PyInstaller 打包: pyinstaller build.spec
2. 然后运行此脚本: python create_release_zip.py

这个脚本会：
1. 读取 version.json 获取版本号
2. 创建正确编码的 zip 文件
3. 输出到 dist 目录
"""

import os
import sys
import json
import zipfile
from pathlib import Path


class UTF8ZipFile(zipfile.ZipFile):
    """支持 UTF-8 文件名的 ZipFile"""
    def _encodeFilenameFlags(self):
        return self.filename.encode('utf-8'), self.flag_bits | 0x800


def create_release_zip():
    """创建发布 zip 包"""
    # 项目根目录
    project_dir = Path(__file__).parent
    dist_dir = project_dir / "dist"
    app_dir = dist_dir / "AI_Drawing_Tool"

    # 检查打包目录是否存在
    if not app_dir.exists():
        print(f"错误: 找不到打包目录 {app_dir}")
        print("请先运行: pyinstaller build.spec")
        return False

    # 读取版本号
    version_file = project_dir / "version.json"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            version_info = json.load(f)
            version = version_info.get("version", "unknown")
    else:
        version = "unknown"

    # 输出文件名
    zip_filename = f"AI_v{version}.zip"
    zip_path = dist_dir / zip_filename

    print(f"正在创建发布包: {zip_filename}")
    print(f"源目录: {app_dir}")
    print(f"版本: {version}")

    # 创建 zip 文件（使用 UTF-8 编码）
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 遍历打包目录
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                file_path = Path(root) / file
                # 计算相对路径（相对于 app_dir）
                arcname = str(file_path.relative_to(app_dir))
                # 确保使用正斜杠
                arcname = arcname.replace('\\', '/')
                print(f"  添加: {arcname}")

                # 创建 ZipInfo 对象并设置 UTF-8 标志
                info = zipfile.ZipInfo(arcname)
                info.flag_bits |= 0x800  # 设置 UTF-8 文件名标志
                info.compress_type = zipfile.ZIP_DEFLATED

                # 读取文件内容并写入
                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())

    print(f"\n完成! 输出文件: {zip_path}")
    print(f"文件大小: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")

    # 验证 zip 文件
    print("\n验证 zip 文件内容:")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        print(f"  文件数量: {len(names)}")
        # 显示关键文件
        key_files = [n for n in names if 'version.json' in n or '.exe' in n]
        for f in key_files[:10]:
            print(f"  - {f}")

    return True


if __name__ == "__main__":
    success = create_release_zip()
    sys.exit(0 if success else 1)

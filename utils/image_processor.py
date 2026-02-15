"""
图片处理工具模块

提供裁剪、缩放、旋转等图片编辑功能。
支持中文路径，处理后覆盖原文件。
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Tuple


def _read_image(path: str) -> np.ndarray:
    """Unicode 安全读取图片

    使用 np.fromfile + cv2.imdecode 支持中文路径

    Args:
        path: 图片文件路径

    Returns:
        numpy array (BGR格式)

    Raises:
        ValueError: 读取失败
    """
    try:
        # 使用 numpy 读取文件字节
        file_bytes = np.fromfile(path, dtype=np.uint8)
        # 解码为图片
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法解码图片: {path}")
        return img
    except Exception as e:
        raise ValueError(f"读取图片失败: {path}, 错误: {e}")


def _write_image(path: str, img: np.ndarray) -> None:
    """Unicode 安全写入图片

    使用 cv2.imencode + tofile 支持中文路径

    Args:
        path: 图片文件路径
        img: numpy array (BGR格式)

    Raises:
        ValueError: 写入失败
    """
    try:
        # 获取文件扩展名
        ext = Path(path).suffix.lower()
        if not ext:
            ext = '.jpg'

        # 编码图片
        success, encoded = cv2.imencode(ext, img)
        if not success:
            raise ValueError(f"无法编码图片: {path}")

        # 写入文件
        encoded.tofile(path)
    except Exception as e:
        raise ValueError(f"写入图片失败: {path}, 错误: {e}")


def crop_image(path: str, x: int, y: int, w: int, h: int) -> None:
    """裁剪图片

    从 (x, y) 开始，宽 w 高 h，自动 clamp 到图片边界。
    处理后覆盖原文件。

    Args:
        path: 图片文件路径
        x: 起始 x 坐标
        y: 起始 y 坐标
        w: 裁剪宽度
        h: 裁剪高度

    Raises:
        ValueError: 处理失败
    """
    img = _read_image(path)
    ih, iw = img.shape[:2]

    # Clamp 到图片边界
    x = max(0, min(x, iw - 1))
    y = max(0, min(y, ih - 1))
    w = max(1, min(w, iw - x))
    h = max(1, min(h, ih - y))

    # 裁剪
    cropped = img[y:y+h, x:x+w].copy()
    _write_image(path, cropped)


def resize_image(path: str, width: int, height: int) -> None:
    """缩放图片

    使用 LANCZOS4 插值到指定宽高。
    处理后覆盖原文件。

    Args:
        path: 图片文件路径
        width: 目标宽度
        height: 目标高度

    Raises:
        ValueError: 处理失败
    """
    img = _read_image(path)

    # 确保尺寸有效
    width = max(1, width)
    height = max(1, height)

    # 缩放
    resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
    _write_image(path, resized)


def rotate_image(path: str, angle: float) -> None:
    """旋转图片

    使用 PIL rotate，expand=True 扩展画布，支持任意角度。
    处理后覆盖原文件。

    Args:
        path: 图片文件路径
        angle: 旋转角度（逆时针为正）

    Raises:
        ValueError: 处理失败
    """
    img = _read_image(path)

    # 转换为 PIL Image (RGB)
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    # 旋转（PIL 的 rotate 是逆时针，所以取负）
    rotated = pil_img.rotate(-angle, expand=True, resample=Image.BICUBIC)

    # 转换回 cv2 格式 (BGR)
    rotated_cv = cv2.cvtColor(np.array(rotated), cv2.COLOR_RGB2BGR)
    _write_image(path, rotated_cv)

"""
可复用缩略图网格 - 支持选择、点击预览
"""

from pathlib import Path
from typing import Callable
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QLabel,
    QCheckBox, QVBoxLayout, QFrame,
)

from ..theme import Theme

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class GalleryGrid(QWidget):
    """缩略图网格，支持复选框选择和点击信号。"""

    image_clicked = Signal(str)   # 点击图片路径
    selection_changed = Signal()  # 选择变化

    def __init__(
        self,
        parent=None,
        columns: int = 4,
        thumb_size: int = 140,
        checkable: bool = True,
        max_images: int = 0,
    ):
        super().__init__(parent)
        self._columns = columns
        self._thumb_size = thumb_size
        self._checkable = checkable
        self._max_images = max_images

        self._items: list[str] = []
        self._checks: dict[str, QCheckBox] = {}

        # 滚动区域
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._scroll)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(8)
        self._scroll.setWidget(self._container)

    # ── 公共 API ──

    def load_directory(self, directory: str, pattern: str = "*"):
        """从目录加载图片。"""
        d = Path(directory)
        if not d.is_dir():
            return
        files = sorted(
            [f for f in d.iterdir() if f.suffix.lower() in _IMAGE_EXTS],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if self._max_images > 0:
            files = files[: self._max_images]
        self.set_images([str(f) for f in files])

    def set_images(self, paths: list[str]):
        """设置图片列表。"""
        self._clear_grid()
        self._items = list(paths)
        for i, path in enumerate(paths):
            self._add_thumb(i, path)

    def selected_paths(self) -> list[str]:
        """返回已勾选的图片路径。"""
        return [p for p, cb in self._checks.items() if cb.isChecked()]

    def select_all(self):
        for cb in self._checks.values():
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self._checks.values():
            cb.setChecked(False)

    def all_paths(self) -> list[str]:
        return list(self._items)

    def wheelEvent(self, event: QWheelEvent):
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().value() - event.angleDelta().y()
        )
        event.accept()

    # ── 内部 ──

    def _clear_grid(self):
        self._items.clear()
        self._checks.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_thumb(self, index: int, path: str):
        row, col = divmod(index, self._columns)

        card = QFrame()
        card.setStyleSheet(
            f"background-color: {Theme.COLOR_INPUT_BG}; border-radius: 6px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        # 缩略图
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(self._thumb_size, self._thumb_size)
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)

        pm = QPixmap(path)
        if not pm.isNull():
            pm = pm.scaled(
                self._thumb_size, self._thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        lbl.setPixmap(pm)
        # 点击图片时切换选中状态（如果有复选框）
        if self._checkable:
            lbl.mousePressEvent = lambda e, p=path: self._toggle_selection(p)
        else:
            lbl.mousePressEvent = lambda e, p=path: self.image_clicked.emit(p)
        card_layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # 文件名
        name_lbl = QLabel(Path(path).name)
        name_lbl.setFont(Theme.font_small())
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumWidth(self._thumb_size)
        card_layout.addWidget(name_lbl)

        # 图片详细信息 - 分两行显示，不同颜色
        dimensions, size_str = self._get_image_info(path)
        if dimensions:
            # 尺寸 - 蓝色
            dim_lbl = QLabel(dimensions)
            dim_lbl.setFont(Theme.font_small())
            dim_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dim_lbl.setMaximumWidth(self._thumb_size)
            dim_lbl.setStyleSheet("color: #2196F3;")  # 蓝色
            card_layout.addWidget(dim_lbl)

        if size_str:
            # 文件大小 - 绿色
            size_lbl = QLabel(size_str)
            size_lbl.setFont(Theme.font_small())
            size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            size_lbl.setMaximumWidth(self._thumb_size)
            size_lbl.setStyleSheet("color: #4CAF50;")  # 绿色
            card_layout.addWidget(size_lbl)

        # 复选框
        if self._checkable:
            cb = QCheckBox()
            cb.stateChanged.connect(lambda: self.selection_changed.emit())
            card_layout.addWidget(cb, alignment=Qt.AlignmentFlag.AlignCenter)
            self._checks[path] = cb

        self._grid.addWidget(card, row, col)

    def _toggle_selection(self, path: str):
        """切换图片的选中状态"""
        if path in self._checks:
            cb = self._checks[path]
            cb.setChecked(not cb.isChecked())

    def _get_image_info(self, path: str) -> tuple[str, str]:
        """获取图片详细信息，返回 (尺寸, 文件大小)"""
        try:
            p = Path(path)
            if not p.exists():
                return ("", "")

            # 文件大小
            size_bytes = p.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1000:
                size_str = f"{size_bytes / 1024:.1f}KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f}MB"

            # 图片尺寸
            pm = QPixmap(path)
            if not pm.isNull():
                dimensions = f"{pm.width()}x{pm.height()}"
            else:
                dimensions = "未知"

            return (dimensions, size_str)
        except Exception:
            return ("", "")

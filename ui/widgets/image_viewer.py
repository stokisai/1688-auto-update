"""
可复用图片预览组件 — QLabel + QPixmap，支持拖放 + 自适应缩放 + 元数据显示
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ..theme import Theme

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class ImageViewer(QWidget):
    """图片预览组件，支持自适应缩放、拖放和元数据显示。"""

    file_dropped = Signal(str)  # 拖放文件路径

    def __init__(
        self,
        parent=None,
        placeholder: str = "暂无图片",
        accept_drop: bool = False,
        max_size: int = 350,
    ):
        super().__init__(parent)
        self._placeholder = placeholder
        self._max = max_size
        self._path: str | None = None
        self._original_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 图片显示标签
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(200, 200)
        self._image_label.setStyleSheet(
            f"background-color: {Theme.COLOR_INPUT_BG}; "
            "border-radius: 8px; padding: 8px;"
        )
        self._image_label.setText(placeholder)
        self._image_label.setFont(Theme.font_body())
        layout.addWidget(self._image_label, stretch=1)

        # 元数据标签
        self._meta_label = QLabel("")
        self._meta_label.setFont(Theme.font_small())
        self._meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._meta_label.setStyleSheet(f"color: {Theme.COLOR_TEXT_GRAY}; padding: 2px;")
        self._meta_label.setWordWrap(True)
        layout.addWidget(self._meta_label)

        if accept_drop:
            self.setAcceptDrops(True)

    # ── 公共 API ──

    def set_image(self, path: str | None, max_size: int | None = None):
        """加载并显示图片。path 为 None 时恢复占位文字。"""
        if path is None or not Path(path).exists():
            self._path = None
            self._original_pixmap = None
            self._image_label.setPixmap(QPixmap())
            self._image_label.setText(self._placeholder)
            self._meta_label.setText("")
            return

        self._path = path
        self._max = max_size or self._max
        self._original_pixmap = QPixmap(path)
        self._update_scaled_pixmap()
        self._image_label.setText("")  # 清除占位文字
        self._update_meta(path)

    def current_path(self) -> str | None:
        return self._path

    def clear_image(self):
        self.set_image(None)

    # ── 自适应缩放 ──

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original_pixmap and not self._original_pixmap.isNull():
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if not self._original_pixmap or self._original_pixmap.isNull():
            return
        # 使用容器 90% 的可用空间
        avail_w = int(self._image_label.width() * 0.9) or self._max
        avail_h = int(self._image_label.height() * 0.9) or self._max
        target = min(avail_w, avail_h, self._max * 2)  # 不超过 2x max_size
        target = max(target, 150)  # 最小 150px
        pm = self._original_pixmap.scaled(
            target, target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(pm)

    def _update_meta(self, path: str):
        """更新元数据显示：文件名、尺寸、文件大小。"""
        p = Path(path)
        if not p.exists():
            self._meta_label.setText("")
            return
        size_kb = p.stat().st_size / 1024
        if self._original_pixmap and not self._original_pixmap.isNull():
            w = self._original_pixmap.width()
            h = self._original_pixmap.height()
            self._meta_label.setText(f"{p.name}  |  {w}x{h}  |  {size_kb:.0f}KB")
        else:
            self._meta_label.setText(f"{p.name}  |  {size_kb:.0f}KB")

    # ── 兼容旧接口 (QLabel 方法代理) ──

    def setPixmap(self, pm):
        self._image_label.setPixmap(pm)

    def setText(self, text):
        self._image_label.setText(text)

    def setFont(self, font):
        self._image_label.setFont(font)

    def text(self):
        return self._image_label.text()

    # ── 拖放 ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in _IMAGE_EXTS:
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in _IMAGE_EXTS:
                self.set_image(path)
                self.file_dropped.emit(path)
                return

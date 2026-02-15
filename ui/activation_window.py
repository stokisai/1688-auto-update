"""
激活对话框 — 首次启动时显示
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QApplication,
)

from .theme import Theme

# 导入激活码验证模块
try:
    from license.license_manager import get_license_manager
    from license.device_fingerprint import get_device_id
    LICENSE_AVAILABLE = True
except ImportError:
    LICENSE_AVAILABLE = False
    get_license_manager = None
    get_device_id = None


class ActivationWindow(QDialog):
    """激活窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件激活 - AI绘画工具")
        self.setFixedSize(500, 450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._activated = False
        self._build_ui()
        self._center()

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 标题
        title = QLabel("软件激活")
        title.setFont(Theme.font_header())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(title)

        subtitle = QLabel("请输入激活码以继续使用")
        subtitle.setFont(Theme.font_body())
        subtitle.setProperty("class", "gray")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        # 设备ID
        device_frame = QFrame()
        device_frame.setFrameShape(QFrame.Shape.StyledPanel)
        df_layout = QVBoxLayout(device_frame)

        df_layout.addWidget(QLabel("您的设备ID:"))

        device_id = get_device_id() if LICENSE_AVAILABLE else "无法获取"
        self._device_entry = QLineEdit(device_id)
        self._device_entry.setReadOnly(True)
        self._device_entry.setFont(Theme.font_log())
        df_layout.addWidget(self._device_entry)

        copy_btn = QPushButton("复制设备ID")
        copy_btn.setFixedWidth(120)
        copy_btn.clicked.connect(self._copy_device_id)
        df_layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(device_frame)

        # 激活码输入
        license_frame = QFrame()
        license_frame.setFrameShape(QFrame.Shape.StyledPanel)
        lf_layout = QVBoxLayout(license_frame)

        lf_layout.addWidget(QLabel("请输入激活码:"))

        self._license_entry = QLineEdit()
        self._license_entry.setPlaceholderText("请输入16位激活码")
        self._license_entry.setFont(Theme.font_log())
        self._license_entry.setMinimumHeight(40)
        self._license_entry.returnPressed.connect(self._activate)
        lf_layout.addWidget(self._license_entry)

        layout.addWidget(license_frame)

        # 状态
        self._status = QLabel("")
        self._status.setFont(Theme.font_body())
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        # 激活按钮
        activate_btn = QPushButton("激活")
        activate_btn.setFont(Theme.font_title())
        activate_btn.setFixedSize(200, 45)
        activate_btn.clicked.connect(self._activate)
        layout.addWidget(activate_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 提示
        hint = QLabel("请将设备ID发送给老师获取激活码")
        hint.setFont(Theme.font_small())
        hint.setProperty("class", "gray")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch()

    def _copy_device_id(self):
        QApplication.clipboard().setText(self._device_entry.text())
        self._status.setText("设备ID已复制到剪贴板")
        self._status.setStyleSheet(f"color: {Theme.COLOR_SUCCESS};")

    def _activate(self):
        if not LICENSE_AVAILABLE:
            self._status.setText("激活模块不可用")
            self._status.setStyleSheet(f"color: {Theme.COLOR_DANGER};")
            return

        key = self._license_entry.text().strip()
        if not key:
            self._status.setText("请输入激活码")
            self._status.setStyleSheet(f"color: {Theme.COLOR_WARNING};")
            return

        manager = get_license_manager()
        success, message = manager.activate(key)

        if success:
            self._status.setText(message)
            self._status.setStyleSheet(f"color: {Theme.COLOR_SUCCESS};")
            self._activated = True
            QTimer.singleShot(1000, self.accept)
        else:
            self._status.setText(message)
            self._status.setStyleSheet(f"color: {Theme.COLOR_DANGER};")

    def is_activated(self) -> bool:
        return self._activated


def check_and_activate() -> bool:
    """检查激活状态，未激活则弹出激活窗口。返回是否已激活。"""
    if not LICENSE_AVAILABLE:
        print("[警告] 激活模块不可用，跳过激活检查")
        return True

    manager = get_license_manager()
    if manager.is_activated():
        print("[信息] 软件已激活")
        return True

    print("[信息] 软件未激活，显示激活窗口")
    dlg = ActivationWindow()
    dlg.exec()
    return manager.is_activated()

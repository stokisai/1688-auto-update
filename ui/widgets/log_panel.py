"""
可复用日志面板 — 带颜色标签的日志输出区域 + critical 脉冲效果
"""

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from ..theme import Theme


class LogPanel(QWidget):
    """带颜色标签的日志面板，支持 critical 脉冲闪烁。"""

    LEVEL_COLORS = {
        "info":     "#FFFFFF",
        "success":  "#4CAF50",
        "warning":  "#FFA726",
        "error":    "#FF5252",
        "step":     "#42A5F5",
        "critical": "#FF1744",
    }

    def __init__(self, parent=None, min_height: int = 120):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(Theme.font_log())
        self._text.setMinimumHeight(min_height)
        layout.addWidget(self._text)

        # Critical 脉冲闪烁
        self._pulse_timer: QTimer | None = None
        self._pulse_state = False
        self._pulse_count = 0

    @Slot(str, str)
    def append(self, message: str, level: str = "info"):
        """追加一条日志。level: info/success/warning/error/step/critical"""
        color = self.LEVEL_COLORS.get(level, self.LEVEL_COLORS["info"])
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))

        # Bold for error/critical
        if level in ("error", "critical"):
            fmt.setFontWeight(QFont.Weight.Bold)

        cursor = self._text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + "\n", fmt)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

        # 败发 critical 脉冲
        if level == "critical":
            self._start_pulse()

    def clear(self):
        self._text.clear()
        self._stop_pulse()

    def get_text(self) -> str:
        return self._text.toPlainText()

    # ── Critical 脉冲闪烁 ──

    def _start_pulse(self):
        """启动背景色脉冲闪烁（红色交替），闪烁 6 次后停止。"""
        self._pulse_count = 0
        if self._pulse_timer:
            self._pulse_timer.stop()
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_timer.start(300)

    def _pulse_tick(self):
        self._pulse_state = not self._pulse_state
        self._pulse_count += 1
        if self._pulse_state:
            self._text.setStyleSheet(
                f"background-color: #3D1111; border: 1px solid {Theme.LOG_CRITICAL};"
            )
        else:
            self._text.setStyleSheet("")
        if self._pulse_count >= 12:  # 6 次闪烁
            self._stop_pulse()

    def _stop_pulse(self):
        if self._pulse_timer:
            self._pulse_timer.stop()
            self._pulse_timer = None
        self._pulse_state = False
        self._text.setStyleSheet("")

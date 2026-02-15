"""
自定义消息框 — 带复制按钮
"""

from PySide6.QtWidgets import (
    QMessageBox, QPushButton, QApplication,
)


def show_message_with_copy(
    parent, title: str, message: str, icon: str = "info"
):
    """
    显示消息框；warning/error 提供"复制"按钮。
    icon: "info" | "warning" | "error" | "check"
    """
    icon_map = {
        "info":    QMessageBox.Icon.Information,
        "check":   QMessageBox.Icon.Information,
        "warning": QMessageBox.Icon.Warning,
        "error":   QMessageBox.Icon.Critical,
    }
    qt_icon = icon_map.get(icon, QMessageBox.Icon.Information)

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(qt_icon)

    if icon in ("warning", "error"):
        copy_btn = box.addButton("复制", QMessageBox.ButtonRole.ActionRole)
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() == copy_btn:
            QApplication.clipboard().setText(message)
            QMessageBox.information(parent, "提示", "报错信息已复制到剪贴板。")
    else:
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        box.exec()

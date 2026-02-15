"""
文囨识别别页?—输取叆商别品文囨 →AI 分析析卖点点 + 生成成绘画画提愮示识?
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QApplication,
)

from ..theme import Theme, Icons
from ..widgets.log_panel import LogPanel
from ..workers.recognition_worker import RecognitionWorker


class CopywritingPage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._sp_worker = None
        self._build_ui()

    # ── UI ──

    def _build_ui(self):
        root = QGridLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 1)
        root.setRowStretch(1, 3)
        root.setRowStretch(2, 1)

        # 鏍囬
        title = QLabel("1688 文囨识别别")
        title.setFont(Theme.font_header())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title, 0, 0, 1, 2)

        # ── 左侧：输入区 ──
        input_card = self._card()
        il = QVBoxLayout(input_card)
        il.setSpacing(12)

        il.addWidget(self._section_label("原始文囨"))

        btn_row = QHBoxLayout()
        sync_btn = QPushButton("同步抓取取文囨")
        sync_btn.setIcon(Icons.sync())
        sync_btn.setFixedWidth(160)
        sync_btn.clicked.connect(self._sync_scraped_text)
        btn_row.addWidget(sync_btn)

        paste_btn = QPushButton("粘贴贴")
        paste_btn.setIcon(Icons.paste())
        paste_btn.setFixedWidth(100)
        paste_btn.clicked.connect(self._paste_text)
        btn_row.addWidget(paste_btn)
        btn_row.addStretch()
        il.addLayout(btn_row)

        self._input_text = QTextEdit()
        self._input_text.setFont(Theme.font_body())
        il.addWidget(self._input_text, stretch=1)

        root.addWidget(input_card, 1, 0)

        # ── 卖点分析区──
        sp_card = self._card()
        sl = QVBoxLayout(sp_card)
        sl.setSpacing(12)

        sl.addWidget(self._section_label("产品卖点分析"))

        sp_btn = QPushButton("分析产品卖点")
        sp_btn.setIcon(Icons.analyze())
        sp_btn.setProperty("class", "danger")
        sp_btn.setFixedWidth(180)
        sp_btn.clicked.connect(self._analyze_selling_points)
        sl.addWidget(sp_btn)

        self._sp_text = QTextEdit()
        self._sp_text.setFont(Theme.font_body())
        sl.addWidget(self._sp_text, stretch=1)

        copy_sp_btn = QPushButton("复制卖点")
        copy_sp_btn.setIcon(Icons.copy())
        copy_sp_btn.setProperty("class", "warning")
        copy_sp_btn.setFixedWidth(140)
        copy_sp_btn.clicked.connect(self._copy_selling_points)
        sl.addWidget(copy_sp_btn)

        root.addWidget(sp_card, 2, 0)

        # ── 中间操作作鍖?──
        action_row = QHBoxLayout()
        self._analyze_btn = QPushButton("开始分析并生成提示词")
        self._analyze_btn.setIcon(Icons.play())
        self._analyze_btn.setFont(Theme.font_subheader())
        self._analyze_btn.setFixedHeight(50)
        self._analyze_btn.setFixedWidth(320)
        self._analyze_btn.setProperty("class", "success")
        self._analyze_btn.clicked.connect(self._start_analysis)
        action_row.addStretch()
        action_row.addWidget(self._analyze_btn)
        action_row.addStretch()

        action_widget = QWidget()
        aw_layout = QVBoxLayout(action_widget)
        aw_layout.setContentsMargins(0, 0, 0, 0)
        aw_layout.addLayout(action_row)

        self._status = QLabel("就绪")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setProperty("class", "gray")
        self._status.setFont(Theme.font_body())
        aw_layout.addWidget(self._status)

        root.addWidget(action_widget, 3, 0, 1, 2)

        # ── 右侧：输出区 ──
        output_card = self._card()
        ol = QVBoxLayout(output_card)
        ol.setSpacing(12)

        ol.addWidget(self._section_label("生成成结果 (AI绘画画提愮示识?"))

        self._output_text = QTextEdit()
        self._output_text.setFont(Theme.font_body())
        ol.addWidget(self._output_text, stretch=1)

        copy_btn = QPushButton("复制结果")
        copy_btn.setIcon(Icons.copy())
        copy_btn.setProperty("class", "warning")
        copy_btn.setFixedWidth(140)
        copy_btn.clicked.connect(self._copy_result)
        ol.addWidget(copy_btn)

        root.addWidget(output_card, 1, 1, 2, 1)

    # ── 输助助 ──

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.StyledPanel)
        return f

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(Theme.font_title())
        return lbl

    # ── 同步 / 粘贴贴 / 复制制 ──

    def _sync_scraped_text(self):
        try:
            p = Path("./output/product_info.txt")
            if p.exists():
                self._input_text.setPlainText(p.read_text(encoding="utf-8"))
                self._set_status("已同步最新抓取文案", "success")
            else:
                self._set_status("未找到抓取文案记录", "warning")
        except Exception as e:
            self._set_status(f"同步失败: {e}", "danger")

    def _paste_text(self):
        clip = QApplication.clipboard().text()
        if clip:
            self._input_text.insertPlainText(clip)

    def _copy_result(self):
        text = self._output_text.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._set_status("结果已复制", "success")

    def _copy_selling_points(self):
        text = self._sp_text.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._set_status("卖点已复制", "success")

    # ── 卖点点分析析 ──

    def _analyze_selling_points(self):
        raw = self._input_text.toPlainText().strip()
        if not raw:
            self._set_status("请输入或同步文案", "danger")
            return

        api_key = getattr(self.config.api_keys, "openrouter_api_key", "")
        if not api_key:
            self._set_status("请先在配置页设置 OpenRouter API Key", "danger")
            return

        self._set_status("正在分析卖点...", "info")
        self._sp_worker = RecognitionWorker(api_key, raw, mode="selling_points")
        self._sp_worker.finished.connect(self._on_sp_done)
        self._sp_worker.error.connect(lambda e: self._set_status(f"分析失败: {e}", "danger"))
        self._sp_worker.start()

    def _on_sp_done(self, result: str):
        self._sp_text.setPlainText(result)
        self._set_status("卖点分析完成", "success")
        self._save_file("selling_points.txt", result)

    # ── 提愮示识种敓成?──

    def _start_analysis(self):
        raw = self._input_text.toPlainText().strip()
        if not raw:
            self._set_status("请输入或同步文案", "danger")
            return

        api_key = getattr(self.config.api_keys, "openrouter_api_key", "")
        if not api_key:
            self._set_status("请先在配置页设置 OpenRouter API Key", "danger")
            return

        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("分析中...")
        self._set_status("正在分析文案...", "info")

        self._worker = RecognitionWorker(api_key, raw, mode="prompt")
        self._worker.finished.connect(self._on_prompt_done)
        self._worker.error.connect(self._on_prompt_error)
        self._worker.start()

    def _on_prompt_done(self, result: str):
        self._output_text.setPlainText(result)
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("开始分析并生成提示词")
        self._analyze_btn.setIcon(Icons.play())
        self._set_status("生成成功!", "success")
        self._save_file("ai_prompt.txt", result)

    def _on_prompt_error(self, err: str):
        self._set_status(f"閿欒: {err}", "danger")
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("开始分析并生成提示词")
        self._analyze_btn.setIcon(Icons.play())

    # ── 左具具 ──

    def _set_status(self, text: str, cls: str = "gray"):
        self._status.setText(text)
        color_map = {
            "success": Theme.COLOR_SUCCESS,
            "warning": Theme.COLOR_WARNING,
            "danger":  Theme.COLOR_DANGER,
            "info":    Theme.COLOR_PRIMARY,
            "gray":    Theme.COLOR_TEXT_GRAY,
        }
        self._status.setStyleSheet(f"color: {color_map.get(cls, Theme.COLOR_TEXT_GRAY)};")

    @staticmethod
    def _save_file(name: str, content: str):
        try:
            d = Path("./output")
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[保存] {name} 失败: {e}")


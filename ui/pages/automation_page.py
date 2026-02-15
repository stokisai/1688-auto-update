"""
自动化页 — URL → 一键完成采集+识别+生成的4步流水线
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QFrame, QSplitter,
    QProgressBar,
)

from ..theme import Theme, Icons
from ..widgets.image_viewer import ImageViewer
from ..widgets.log_panel import LogPanel
from ..widgets.gallery_grid import GalleryGrid
from ..workers.automation_worker import AutomationWorker


class AutomationPage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)

        title = QLabel("智能自动化")
        title.setFont(Theme.font_header())
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # ── 左侧：图片展示 ──
        left = QFrame()
        left.setFrameShape(QFrame.Shape.StyledPanel)
        ll = QVBoxLayout(left)
        ll.setSpacing(12)

        main_lbl = QLabel("AI选择的主图")
        main_lbl.setFont(Theme.font_title())
        ll.addWidget(main_lbl)
        self._main_preview = ImageViewer(placeholder="等待AI识别主图...", max_size=300)
        ll.addWidget(self._main_preview)

        prompt_lbl = QLabel("API提示词")
        prompt_lbl.setFont(Theme.font_title())
        ll.addWidget(prompt_lbl)
        self._prompt_display = QTextEdit()
        self._prompt_display.setReadOnly(True)
        self._prompt_display.setMaximumHeight(120)
        ll.addWidget(self._prompt_display)

        result_lbl = QLabel("生成结果图")
        result_lbl.setFont(Theme.font_title())
        ll.addWidget(result_lbl)
        self._result_preview = ImageViewer(placeholder="等待生成...", max_size=400)
        ll.addWidget(self._result_preview, stretch=1)

        # 结果操作
        res_btns = QHBoxLayout()
        dl_btn = QPushButton("下载")
        dl_btn.setIcon(Icons.download())
        dl_btn.setFixedWidth(100)
        dl_btn.clicked.connect(self._download_result)
        res_btns.addWidget(dl_btn)
        open_btn = QPushButton("打开文件夹")
        open_btn.setIcon(Icons.folder_open())
        open_btn.setFixedWidth(140)
        open_btn.clicked.connect(lambda: os.startfile("./output/generated") if Path("./output/generated").exists() else None)
        res_btns.addWidget(open_btn)
        res_btns.addStretch()
        ll.addLayout(res_btns)

        splitter.addWidget(left)

        # ── 右侧：配置 + 日志 ──
        right = QFrame()
        right.setFrameShape(QFrame.Shape.StyledPanel)
        rl = QVBoxLayout(right)
        rl.setSpacing(12)

        # 1. URL
        step1_lbl = QLabel("1. 产品链接")
        step1_lbl.setFont(Theme.font_title())
        rl.addWidget(step1_lbl)
        self._url_entry = QLineEdit()
        self._url_entry.setPlaceholderText("1688商品链接...")
        self._url_entry.setMinimumHeight(40)
        self._url_entry.setMaximumWidth(600)
        rl.addWidget(self._url_entry)

        # 2. 引擎
        step2_lbl = QLabel("2. 生成引擎")
        step2_lbl.setFont(Theme.font_title())
        rl.addWidget(step2_lbl)
        eng_row = QHBoxLayout()
        self._engine_map = {"ComfyUI": "comfyui", "Nano": "nano_banana", "Nano Pro": "nano_banana_pro"}
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(list(self._engine_map.keys()))
        self._engine_combo.setMinimumWidth(200)
        eng_row.addWidget(self._engine_combo)
        eng_row.addStretch()
        rl.addLayout(eng_row)

        # 3. 手动提示词
        step3_lbl = QLabel("3. 手动提示词 (可选，留空则AI自动生成)")
        step3_lbl.setFont(Theme.font_title())
        rl.addWidget(step3_lbl)
        self._manual_prompt = QTextEdit()
        self._manual_prompt.setMaximumHeight(80)
        rl.addWidget(self._manual_prompt)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 4)
        self._progress.setValue(0)
        rl.addWidget(self._progress)

        self._step_label = QLabel("就绪")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setFont(Theme.font_body())
        rl.addWidget(self._step_label)

        # 操作按钮
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("开始自动化")
        self._start_btn.setIcon(Icons.play())
        self._start_btn.setFont(Theme.font_subheader())
        self._start_btn.setFixedHeight(50)
        self._start_btn.setFixedWidth(220)
        self._start_btn.setProperty("class", "success")
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setIcon(Icons.stop())
        self._stop_btn.setProperty("class", "danger")
        self._stop_btn.setFixedHeight(50)
        self._stop_btn.setFixedWidth(120)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)

        # 日志
        log_lbl = QLabel("日志")
        log_lbl.setFont(Theme.font_title())
        rl.addWidget(log_lbl)
        self._log = LogPanel(min_height=120)
        rl.addWidget(self._log, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

    # ── 操作 ──

    def _start(self):
        url = self._url_entry.text().strip()
        if not url:
            self._log.append("请输入商品链接", "warning")
            return

        engine = self._engine_map.get(self._engine_combo.currentText(), "comfyui")
        prompt = self._manual_prompt.toPlainText().strip()
        wf = self.config.comfyui.current_workflow if engine == "comfyui" else ""

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setValue(0)
        self._log.clear()

        self._worker = AutomationWorker(url, engine, self.config, prompt, wf)
        self._worker.progress.connect(self._log.append)
        self._worker.step_changed.connect(self._on_step)
        self._worker.main_image.connect(lambda p: self._main_preview.set_image(p))
        self._worker.result_image.connect(lambda p: self._result_preview.set_image(p, max_size=500))
        self._worker.prompt_ready.connect(lambda t: self._prompt_display.setPlainText(t))
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._log.append("正在停止...", "warning")

    def _on_step(self, step: int, name: str):
        self._progress.setValue(step)
        self._step_label.setText(f"步骤 {step}/4: {name}")

    def _on_done(self, success: bool):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        if success:
            self._progress.setValue(4)
            self._step_label.setText("完成!")

    def _on_error(self, err: str):
        self._log.append(f"错误: {err}", "error")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _download_result(self):
        path = self._result_preview.current_path()
        if path and Path(path).exists():
            os.startfile(path)

"""
采集页 - 输入 1688 链接 -> 采集商品 -> 预览图片和文案
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QFrame, QSplitter,
    QScrollArea, QListWidget, QListWidgetItem,
)

from ..theme import Theme, Icons
from ..widgets.image_viewer import ImageViewer
from ..widgets.log_panel import LogPanel
from ..workers.scrape_worker import ScrapeWorker, LoginWorker

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class ScrapePage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._login_worker = None
        self._image_paths: list[str] = []
        self._current_idx = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)

        # 标题
        title = QLabel("1688 商品采集")
        title.setFont(Theme.font_header())
        root.addWidget(title)

        # URL 输入行
        url_row = QHBoxLayout()
        lbl = QLabel("商品链接:")
        lbl.setFont(Theme.font_body())
        url_row.addWidget(lbl)
        self._url_entry = QLineEdit()
        self._url_entry.setPlaceholderText("输入 1688 商品链接...")
        self._url_entry.setMinimumHeight(40)
        self._url_entry.setMaximumWidth(600)
        self._url_entry.returnPressed.connect(self._start_scrape)
        url_row.addWidget(self._url_entry, stretch=1)

        # 引擎选择
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["Selenium (自动)", "SerpAPI", "RapidAPI"])
        self._engine_combo.setFixedWidth(180)
        url_row.addWidget(self._engine_combo)

        self._scrape_btn = QPushButton("开始采集")
        self._scrape_btn.setIcon(Icons.search())
        self._scrape_btn.setProperty("class", "success")
        self._scrape_btn.setFixedHeight(40)
        self._scrape_btn.setFixedWidth(160)
        self._scrape_btn.clicked.connect(self._start_scrape)
        url_row.addWidget(self._scrape_btn)

        self._login_btn = QPushButton("登录1688")
        self._login_btn.setIcon(Icons.key())
        self._login_btn.setFixedWidth(140)
        self._login_btn.clicked.connect(self._login_1688)
        url_row.addWidget(self._login_btn)

        # 启动时检查是否已有cookies
        from pathlib import Path
        if Path("./config/1688_cookies.json").exists():
            self._login_btn.setText("已登录 ✓")
        url_row.addStretch()
        root.addLayout(url_row)

        # 主内容区
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # ── 左侧：缩略图列表 ──
        left = QFrame()
        left.setFrameShape(QFrame.Shape.StyledPanel)
        left.setFixedWidth(220)
        ll = QVBoxLayout(left)
        ll.setSpacing(8)
        img_list_lbl = QLabel("图片列表")
        img_list_lbl.setFont(Theme.font_title())
        ll.addWidget(img_list_lbl)

        self._thumb_list = QListWidget()
        self._thumb_list.setIconSize(QSize(60, 60))
        self._thumb_list.currentRowChanged.connect(self._show_preview)
        ll.addWidget(self._thumb_list)

        splitter.addWidget(left)

        # ── 中间：大图预览 ──
        center = QFrame()
        center.setFrameShape(QFrame.Shape.StyledPanel)
        cl = QVBoxLayout(center)
        cl.setSpacing(8)
        preview_lbl = QLabel("图片预览")
        preview_lbl.setFont(Theme.font_title())
        cl.addWidget(preview_lbl)

        self._preview = ImageViewer(placeholder="采集后图片将显示在这里", max_size=500)
        cl.addWidget(self._preview, stretch=2)

        # 导航按钮
        nav_row = QHBoxLayout()
        prev_btn = QPushButton("上一张")
        prev_btn.setIcon(Icons.prev())
        prev_btn.setFixedWidth(120)
        prev_btn.clicked.connect(lambda: self._navigate(-1))
        nav_row.addWidget(prev_btn)
        self._nav_label = QLabel("0 / 0")
        self._nav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nav_label.setFont(Theme.font_body())
        nav_row.addWidget(self._nav_label)
        next_btn = QPushButton("下一张")
        next_btn.setIcon(Icons.next())
        next_btn.setFixedWidth(120)
        next_btn.clicked.connect(lambda: self._navigate(1))
        nav_row.addWidget(next_btn)
        cl.addLayout(nav_row)

        splitter.addWidget(center)

        # ── 右侧：文案 + 日志 ──
        right = QFrame()
        right.setFrameShape(QFrame.Shape.StyledPanel)
        rl = QVBoxLayout(right)
        rl.setSpacing(12)

        text_lbl = QLabel("商品文案")
        text_lbl.setFont(Theme.font_title())
        rl.addWidget(text_lbl)
        self._text_area = QTextEdit()
        self._text_area.setFont(Theme.font_body())
        self._text_area.setReadOnly(True)
        rl.addWidget(self._text_area, stretch=1)

        # 文案操作
        text_btns = QHBoxLayout()
        copy_btn = QPushButton("复制文案")
        copy_btn.setIcon(Icons.copy())
        copy_btn.setFixedWidth(140)
        copy_btn.clicked.connect(self._copy_text)
        text_btns.addWidget(copy_btn)

        open_btn = QPushButton("打开输出文件夹")
        open_btn.setIcon(Icons.folder_open())
        open_btn.setFixedWidth(180)
        open_btn.clicked.connect(lambda: os.startfile("./output") if Path("./output").exists() else None)
        text_btns.addWidget(open_btn)
        text_btns.addStretch()
        rl.addLayout(text_btns)

        log_lbl = QLabel("日志")
        log_lbl.setFont(Theme.font_title())
        rl.addWidget(log_lbl)
        self._log = LogPanel(min_height=100)
        rl.addWidget(self._log)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

    # ── 采集 ──

    def _start_scrape(self):
        url = self._url_entry.text().strip()
        if not url:
            self._log.append("请输入商品链接", "warning")
            return

        engine_map = {"Selenium (自动)": "selenium", "SerpAPI": "serpapi", "RapidAPI": "rapidapi"}
        engine = engine_map.get(self._engine_combo.currentText(), "selenium")

        self._scrape_btn.setEnabled(False)
        self._scrape_btn.setText("采集中...")
        self._log.clear()
        self._log.append(f"开始采集: {url[:60]}...", "step")

        self._worker = ScrapeWorker(url, engine, self.config)
        self._worker.progress.connect(self._log.append)
        self._worker.images_ready.connect(self._on_images_ready)
        self._worker.text_ready.connect(self._on_text_ready)
        self._worker.finished.connect(self._on_scrape_done)
        self._worker.error.connect(self._on_scrape_error)
        self._worker.start()

    def _on_images_ready(self, paths: list):
        self._image_paths = paths
        self._thumb_list.clear()
        for p in paths:
            item = QListWidgetItem(Path(p).name)
            self._thumb_list.addItem(item)
        if paths:
            self._thumb_list.setCurrentRow(0)
            self._show_preview(0)

    def _on_text_ready(self, text: str):
        self._text_area.setPlainText(text)

    def _on_scrape_done(self, product):
        self._scrape_btn.setEnabled(True)
        self._scrape_btn.setText("开始采集")
        self._scrape_btn.setIcon(Icons.search())
        self._log.append("采集完成!", "success")

    def _on_scrape_error(self, err: str):
        self._scrape_btn.setEnabled(True)
        self._scrape_btn.setText("开始采集")
        self._scrape_btn.setIcon(Icons.search())
        self._log.append(f"采集失败: {err}", "error")

    # ── 预览 ──

    def _show_preview(self, index: int):
        if 0 <= index < len(self._image_paths):
            self._current_idx = index
            self._preview.set_image(self._image_paths[index], max_size=500)
            self._nav_label.setText(f"{index + 1} / {len(self._image_paths)}")

    def _navigate(self, delta: int):
        if not self._image_paths:
            return
        new_idx = (self._current_idx + delta) % len(self._image_paths)
        self._thumb_list.setCurrentRow(new_idx)

    # ── 登录 ──

    def _login_1688(self):
        self._log.append("正在打开登录页面...", "step")
        self._login_btn.setEnabled(False)
        self._login_btn.setText("登录中...")
        username = getattr(self.config, 'alibaba_username', '') or ''
        password = getattr(self.config, 'alibaba_password', '') or ''
        self._login_worker = LoginWorker(username=username, password=password)
        self._login_worker.progress.connect(self._log.append)
        self._login_worker.finished.connect(self._on_login_finished)
        self._login_worker.error.connect(lambda e: self._on_login_error(e))
        self._login_worker.start()

    def _on_login_finished(self, ok):
        if ok:
            self._log.append("登录成功!", "success")
            self._login_btn.setText("已登录 ✓")
            self._login_btn.setEnabled(True)
        else:
            self._log.append("登录失败", "error")
            self._login_btn.setText("登录1688")
            self._login_btn.setEnabled(True)

    def _on_login_error(self, e):
        self._log.append(f"登录错误: {e}", "error")
        self._login_btn.setText("登录1688")
        self._login_btn.setEnabled(True)

    # ── 工具 ──

    def _copy_text(self):
        from PySide6.QtWidgets import QApplication
        text = self._text_area.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._log.append("文案已复制", "success")

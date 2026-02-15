"""
文生图页 — 输入提示词 → 选择引擎 → 生成图片 → 图库管理
"""

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QComboBox, QFrame,
    QFileDialog, QApplication, QSplitter,
)

from ..theme import Theme, Icons
from ..widgets.image_viewer import ImageViewer
from ..widgets.gallery_grid import GalleryGrid
from ..widgets.log_panel import LogPanel
from ..workers.generate_worker import GenerateWorker


class Text2ImagePage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._output_dir = Path("output/text2image")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._worker = None
        self._result_path = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)

        # 标题行
        header = QHBoxLayout()
        title = QLabel("文生图")
        title.setFont(Theme.font_header())
        header.addWidget(title)
        header.addStretch()
        open_btn = QPushButton("打开输出文件夹")
        open_btn.setIcon(Icons.folder_open())
        open_btn.setFixedWidth(180)
        open_btn.clicked.connect(self._open_output_folder)
        header.addWidget(open_btn)
        root.addLayout(header)

        # 主区域 splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # ── 左侧：输入 + 预览 ──
        left = QFrame()
        left.setFrameShape(QFrame.Shape.StyledPanel)
        ll = QVBoxLayout(left)
        ll.setSpacing(12)

        prompt_lbl = QLabel("输入提示词")
        prompt_lbl.setFont(Theme.font_title())
        ll.addWidget(prompt_lbl)
        hint = QLabel("描述你想生成的图片内容（支持中英文）")
        hint.setProperty("class", "gray")
        hint.setFont(Theme.font_small())
        ll.addWidget(hint)

        self._prompt = QTextEdit()
        self._prompt.setFont(Theme.font_body())
        self._prompt.setMaximumHeight(130)
        self._prompt.setPlainText("A beautiful sunset over the ocean, with orange and purple clouds")
        ll.addWidget(self._prompt)

        # 引擎选择
        eng_row = QHBoxLayout()
        eng_lbl = QLabel("生成引擎")
        eng_lbl.setFont(Theme.font_body())
        eng_row.addWidget(eng_lbl)
        self._engine_map = {
            "Nano Banana 标准": "nano_banana",
            "Nano Banana Pro": "nano_banana_pro",
            "ComfyUI 工作流": "comfyui",
        }
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(list(self._engine_map.keys()))
        self._engine_combo.setMinimumWidth(220)
        eng_row.addWidget(self._engine_combo)
        eng_row.addStretch()
        ll.addLayout(eng_row)

        # 生成按钮
        gen_row = QHBoxLayout()
        self._gen_btn = QPushButton("开始生成")
        self._gen_btn.setIcon(Icons.palette())
        self._gen_btn.setFont(Theme.font_subheader())
        self._gen_btn.setFixedHeight(50)
        self._gen_btn.setFixedWidth(250)
        self._gen_btn.setProperty("class", "success")
        self._gen_btn.clicked.connect(self._start_generate)
        gen_row.addWidget(self._gen_btn)
        gen_row.addStretch()
        ll.addLayout(gen_row)

        # 预览
        preview_lbl = QLabel("生成结果预览")
        preview_lbl.setFont(Theme.font_title())
        ll.addWidget(preview_lbl)
        self._preview = ImageViewer(placeholder="生成的图片将显示在这里", max_size=400)
        ll.addWidget(self._preview, stretch=2)

        # 操作按钮
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("另存为")
        self._save_btn.setIcon(Icons.save())
        self._save_btn.setFixedWidth(120)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_result)
        btn_row.addWidget(self._save_btn)
        self._open_result_btn = QPushButton("打开")
        self._open_result_btn.setIcon(Icons.folder_open())
        self._open_result_btn.setFixedWidth(100)
        self._open_result_btn.setEnabled(False)
        self._open_result_btn.clicked.connect(self._open_result)
        btn_row.addWidget(self._open_result_btn)
        btn_row.addStretch()
        ll.addLayout(btn_row)

        splitter.addWidget(left)

        # ── 右侧：图库 + 日志 ──
        right = QFrame()
        right.setFrameShape(QFrame.Shape.StyledPanel)
        rl = QVBoxLayout(right)
        rl.setSpacing(12)

        # 图库
        gallery_header = QHBoxLayout()
        gallery_title = QLabel("历史图库")
        gallery_title.setFont(Theme.font_title())
        gallery_header.addWidget(gallery_title)
        self._gallery_info = QLabel("0 张")
        self._gallery_info.setProperty("class", "gray")
        gallery_header.addWidget(self._gallery_info)
        gallery_header.addStretch()

        sel_all_btn = QPushButton("全选")
        sel_all_btn.setIcon(Icons.select_all())
        sel_all_btn.setProperty("class", "flat")
        sel_all_btn.setFixedWidth(80)
        sel_all_btn.clicked.connect(lambda: self._gallery.select_all())
        gallery_header.addWidget(sel_all_btn)

        desel_btn = QPushButton("取消")
        desel_btn.setIcon(Icons.deselect())
        desel_btn.setProperty("class", "flat")
        desel_btn.setFixedWidth(80)
        desel_btn.clicked.connect(lambda: self._gallery.deselect_all())
        gallery_header.addWidget(desel_btn)

        del_btn = QPushButton("删除选中")
        del_btn.setIcon(Icons.delete())
        del_btn.setProperty("class", "danger")
        del_btn.setFixedWidth(130)
        del_btn.clicked.connect(self._delete_selected)
        gallery_header.addWidget(del_btn)

        rl.addLayout(gallery_header)

        self._gallery = GalleryGrid(columns=4, thumb_size=120, checkable=True, max_images=30)
        self._gallery.image_clicked.connect(self._preview_gallery_image)
        rl.addWidget(self._gallery, stretch=1)

        # 日志
        log_lbl = QLabel("日志")
        log_lbl.setFont(Theme.font_title())
        rl.addWidget(log_lbl)
        self._log = LogPanel(min_height=80)
        rl.addWidget(self._log)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)

        # 加载图库
        self._refresh_gallery()

    # ── 生成 ──

    def _start_generate(self):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._log.append("请输入提示词", "warning")
            return

        engine_key = self._engine_map.get(self._engine_combo.currentText(), "nano_banana")
        wf_name = self.config.comfyui.current_workflow if engine_key == "comfyui" else ""

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("生成中...")
        self._log.append(f"开始生成 [{self._engine_combo.currentText()}]", "step")

        self._worker = GenerateWorker(
            config=self.config,
            engine=engine_key,
            prompt=prompt,
            source_image=None,
            output_dir=str(self._output_dir),
            workflow_name=wf_name,
        )
        self._worker.progress.connect(self._log.append)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, path: str):
        self._result_path = path
        self._preview.set_image(path, max_size=500)
        self._save_btn.setEnabled(True)
        self._open_result_btn.setEnabled(True)
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("开始生成")
        self._gen_btn.setIcon(Icons.palette())
        self._log.append(f"生成完成: {Path(path).name}", "success")
        self._refresh_gallery()

    def _on_error(self, err: str):
        self._log.append(f"错误: {err}", "error")
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("开始生成")
        self._gen_btn.setIcon(Icons.palette())

    # ── 图库 ──

    def _refresh_gallery(self):
        self._gallery.load_directory(str(self._output_dir))
        count = len(self._gallery.all_paths())
        self._gallery_info.setText(f"{count} 张")

    def _preview_gallery_image(self, path: str):
        self._preview.set_image(path, max_size=500)
        self._result_path = path
        self._save_btn.setEnabled(True)
        self._open_result_btn.setEnabled(True)

    def _delete_selected(self):
        paths = self._gallery.selected_paths()
        if not paths:
            return
        for p in paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        self._refresh_gallery()

    # ── 文件操作 ──

    def _save_result(self):
        if not self._result_path:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "另存为", Path(self._result_path).name,
            "Images (*.png *.jpg *.webp);;All Files (*.*)"
        )
        if dest:
            shutil.copy2(self._result_path, dest)

    def _open_result(self):
        if self._result_path and Path(self._result_path).exists():
            os.startfile(self._result_path)

    def _open_output_folder(self):
        self._output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self._output_dir))

"""
图库页 — 浏览采集图片 + 批量 ComfyUI 生成 + 结果管理
"""

import os
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QFrame, QSplitter,
    QMessageBox, QFileDialog, QDialog, QCheckBox, QScrollArea,
    QSpinBox, QStackedWidget, QRadioButton, QProgressBar, QGridLayout,
)
from PySide6.QtGui import QPixmap, QImage

from ..theme import Theme, Icons
from ..widgets.gallery_grid import GalleryGrid
from ..widgets.image_viewer import ImageViewer
from ..widgets.log_panel import LogPanel
from utils.logger import log_info, log_warning, log_error

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class _BatchWorker(QThread):
    """批量 ComfyUI 生成 worker。"""
    progress = Signal(str, str)
    image_done = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, config, paths, prompt, workflow, parent=None):
        super().__init__(parent)
        self._config = config
        self._paths = paths
        self._prompt = prompt
        self._workflow = workflow
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            from image_generation import ComfyUIFluxKontextClient
            url = self._config.comfyui.get_effective_server_url()
            if not url:
                self.error.emit("请先配置 ComfyUI 服务器地址")
                return
            client = ComfyUIFluxKontextClient(url)
            if self._workflow:
                wf = self._config.comfyui.get_workflow(self._workflow)
                if wf:
                    client.set_workflow(wf.get("json", {}), wf.get("prompt_node_id", "6"), wf.get("prompt_param_path", "inputs.text"),
                                       image_node_id=wf.get("image_node_id"), image_param_path=wf.get("image_param_path"))
            if not client.test_connection():
                self.error.emit(f"无法连接 ComfyUI: {url}")
                return
            output_dir = "./output/generated"
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            for i, p in enumerate(self._paths):
                if self._stop:
                    break
                self.progress.emit(f"生成 {i+1}/{len(self._paths)}: {Path(p).name}", "step")
                result = client.image_to_image(p, self._prompt, output_dir=output_dir)
                if result:
                    self.image_done.emit(result)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class GalleryPage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)

        title = QLabel("我的图库")
        title.setFont(Theme.font_header())
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(splitter, stretch=1)

        # ── 上方：采集图库 ──
        top = QFrame()
        top.setFrameShape(QFrame.Shape.StyledPanel)
        tl = QVBoxLayout(top)
        tl.setSpacing(12)

        header = QHBoxLayout()
        src_lbl = QLabel("采集图库 (选择图片进行批量生成)")
        src_lbl.setFont(Theme.font_title())
        header.addWidget(src_lbl)
        header.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setIcon(Icons.refresh())
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self._refresh_source)
        header.addWidget(refresh_btn)

        sel_all = QPushButton("全选")
        sel_all.setIcon(Icons.select_all())
        sel_all.setProperty("class", "flat")
        sel_all.setFixedWidth(80)
        sel_all.clicked.connect(lambda: self._source_grid.select_all())
        header.addWidget(sel_all)

        desel = QPushButton("取消")
        desel.setIcon(Icons.deselect())
        desel.setProperty("class", "flat")
        desel.setFixedWidth(80)
        desel.clicked.connect(lambda: self._source_grid.deselect_all())
        header.addWidget(desel)

        del_src = QPushButton("删除选中")
        del_src.setIcon(Icons.delete())
        del_src.setProperty("class", "danger")
        del_src.setFixedWidth(110)
        del_src.clicked.connect(self._delete_source_selected)
        header.addWidget(del_src)
        tl.addLayout(header)

        self._source_grid = GalleryGrid(columns=6, thumb_size=150, checkable=True)
        self._source_grid.image_clicked.connect(self._preview_source)
        tl.addWidget(self._source_grid, stretch=1)

        # ComfyUI 批量生成控制
        ctrl = QHBoxLayout()
        wf_lbl = QLabel("工作流:")
        wf_lbl.setFont(Theme.font_body())
        ctrl.addWidget(wf_lbl)
        self._wf_combo = QComboBox()
        wf_list = self.config.comfyui.list_workflows()
        self._wf_combo.addItems(wf_list if wf_list else ["请先配置工作流"])
        self._wf_combo.setMinimumWidth(200)
        ctrl.addWidget(self._wf_combo)

        prompt_lbl = QLabel("提示词:")
        prompt_lbl.setFont(Theme.font_body())
        ctrl.addWidget(prompt_lbl)
        self._prompt_entry = QLineEdit()
        self._prompt_entry.setPlaceholderText("可选提示词...")
        self._prompt_entry.setMaximumWidth(400)
        ctrl.addWidget(self._prompt_entry, stretch=1)

        self._batch_btn = QPushButton("用已选图片做图")
        self._batch_btn.setIcon(Icons.palette())
        self._batch_btn.setProperty("class", "success")
        self._batch_btn.setFixedWidth(180)
        self._batch_btn.clicked.connect(self._start_batch)
        ctrl.addWidget(self._batch_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setIcon(Icons.stop())
        self._stop_btn.setProperty("class", "danger")
        self._stop_btn.setFixedWidth(100)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_batch)
        ctrl.addWidget(self._stop_btn)

        self._batch_status = QLabel("")
        self._batch_status.setFont(Theme.font_small())
        ctrl.addWidget(self._batch_status)
        tl.addLayout(ctrl)

        splitter.addWidget(top)

        # ── 下方：结果图库 ──
        bottom = QFrame()
        bottom.setFrameShape(QFrame.Shape.StyledPanel)
        bl = QVBoxLayout(bottom)
        bl.setSpacing(12)

        res_header = QHBoxLayout()
        res_lbl = QLabel("生成结果")
        res_lbl.setFont(Theme.font_title())
        res_header.addWidget(res_lbl)
        res_header.addStretch()

        res_sel_all = QPushButton("全选")
        res_sel_all.setIcon(Icons.select_all())
        res_sel_all.setProperty("class", "flat")
        res_sel_all.setFixedWidth(80)
        res_sel_all.clicked.connect(lambda: self._result_grid.select_all())
        res_header.addWidget(res_sel_all)

        res_desel = QPushButton("取消")
        res_desel.setIcon(Icons.deselect())
        res_desel.setProperty("class", "flat")
        res_desel.setFixedWidth(80)
        res_desel.clicked.connect(lambda: self._result_grid.deselect_all())
        res_header.addWidget(res_desel)

        edit_btn = QPushButton("编辑")
        edit_btn.setIcon(Icons.palette())
        edit_btn.setFixedWidth(100)
        edit_btn.clicked.connect(self._edit_selected)
        res_header.addWidget(edit_btn)

        reprocess_btn = QPushButton("重处理")
        reprocess_btn.setIcon(Icons.play())
        reprocess_btn.setProperty("class", "primary")
        reprocess_btn.setFixedWidth(110)
        reprocess_btn.clicked.connect(self._reprocess_selected)
        res_header.addWidget(reprocess_btn)

        dl_sel = QPushButton("下载选中")
        dl_sel.setIcon(Icons.download())
        dl_sel.setFixedWidth(130)
        dl_sel.clicked.connect(self._download_selected)
        res_header.addWidget(dl_sel)

        del_sel = QPushButton("删除选中")
        del_sel.setIcon(Icons.delete())
        del_sel.setProperty("class", "danger")
        del_sel.setFixedWidth(130)
        del_sel.clicked.connect(self._delete_selected)
        res_header.addWidget(del_sel)
        bl.addLayout(res_header)

        self._result_grid = GalleryGrid(columns=5, thumb_size=170, checkable=True)
        self._result_grid.image_clicked.connect(self._preview_result)
        bl.addWidget(self._result_grid, stretch=1)

        # 日志面板
        self._log_panel = LogPanel()
        bl.addWidget(self._log_panel)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self._refresh_source()
        self._refresh_results()

    # ── 刷新 ──

    def _refresh_source(self):
        self._source_grid.load_directory("./output/images")

    def _refresh_results(self):
        self._result_grid.load_directory("./output/generated")

    # ── 预览 ──

    def _preview_source(self, path: str):
        dlg = _PreviewDialog(path, self)
        dlg.exec()

    def _preview_result(self, path: str):
        dlg = _PreviewDialog(path, self)
        dlg.exec()

    # ── 批量生成 ──

    def _start_batch(self):
        paths = self._source_grid.selected_paths()
        if not paths:
            self._batch_status.setText("请先选择图片")
            return

        wf = self._wf_combo.currentText()
        prompt = self._prompt_entry.text().strip()

        self._batch_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._batch_status.setText(f"生成中... 0/{len(paths)}")

        self._done_count = 0
        self._total_count = len(paths)

        self._worker = _BatchWorker(self.config, paths, prompt, wf)
        self._worker.progress.connect(lambda m, l: self._batch_status.setText(m))
        self._worker.image_done.connect(self._on_image_done)
        self._worker.finished.connect(self._on_batch_done)
        self._worker.error.connect(self._on_batch_error)
        self._worker.start()

    def _stop_batch(self):
        if self._worker:
            self._worker.stop()

    def _on_image_done(self, path: str):
        self._done_count += 1
        self._batch_status.setText(f"生成中... {self._done_count}/{self._total_count}")

    def _on_batch_done(self):
        self._batch_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._batch_status.setText(f"完成! {self._done_count}/{self._total_count}")
        self._refresh_results()

    def _on_batch_error(self, err: str):
        self._batch_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._batch_status.setText(f"错误: {err}")

    # ── 采集图库操作 ──

    def _delete_source_selected(self):
        paths = self._source_grid.selected_paths()
        if not paths:
            return
        reply = QMessageBox.question(self, "确认删除", f"确定删除采集图库中 {len(paths)} 张图片?")
        if reply == QMessageBox.StandardButton.Yes:
            for p in paths:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
            self._refresh_source()

    # ── 结果操作 ──

    def _download_selected(self):
        paths = self._result_grid.selected_paths()
        if not paths:
            return
        dest = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if dest:
            for p in paths:
                try:
                    shutil.copy2(p, dest)
                except Exception:
                    pass

    def _delete_selected(self):
        paths = self._result_grid.selected_paths()
        if not paths:
            return
        reply = QMessageBox.question(self, "确认删除", f"确定删除 {len(paths)} 张图片?")
        if reply == QMessageBox.StandardButton.Yes:
            for p in paths:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
            self._refresh_results()

    # ── 编辑功能 ──

    def _edit_selected(self):
        """编辑选中的图片"""
        paths = self._result_grid.selected_paths()
        if not paths:
            self._log_panel.log("请先选择要编辑的图片", "warning")
            return

        if len(paths) == 1:
            # 单图编辑
            self._edit_single_image(paths[0])
        else:
            # 批量编辑
            self._edit_batch_images(paths)

    def _edit_single_image(self, path: str):
        """单图编辑器"""
        dlg = ImageEditorDialog(path, self)
        dlg.image_saved.connect(self._on_image_edited)
        dlg.exec()

    def _edit_batch_images(self, paths: list):
        """批量编辑"""
        dlg = BatchEditDialog(paths, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            operation, params = dlg.get_operation_and_params()
            if operation:
                self._start_batch_edit(paths, operation, params)

    def _start_batch_edit(self, paths: list, operation: str, params: dict):
        """启动批量编辑"""
        self._log_panel.log(f"开始批量编辑 {len(paths)} 张图片...", "step")

        self._edit_worker = BatchEditWorkerThread(paths, operation, params)
        self._edit_worker.progress_updated.connect(self._on_edit_progress)
        self._edit_worker.all_done.connect(self._on_edit_done)
        self._edit_worker.start()

    def _on_edit_progress(self, current: int, total: int, filename: str):
        """编辑进度更新"""
        self._log_panel.log(f"编辑中 {current}/{total}: {filename}", "info")

    def _on_edit_done(self, success: bool):
        """编辑完成"""
        if success:
            self._log_panel.log("批量编辑完成", "success")
        else:
            self._log_panel.log("批量编辑完成（部分失败）", "warning")
        self._refresh_results()

    def _on_image_edited(self, path: str):
        """单图编辑完成"""
        self._log_panel.log(f"图片已保存: {Path(path).name}", "success")
        # 刷新该图片的缩略图
        self._result_grid.load_directory("./output/generated")

    # ── 重处理功能 ──

    def _reprocess_selected(self):
        """重处理选中的图片"""
        paths = self._result_grid.selected_paths()
        if not paths:
            self._log_panel.log("请先选择要重处理的图片", "warning")
            return

        wf = self._wf_combo.currentText()
        if not wf or wf == "请先配置工作流":
            self._log_panel.log("请先选择工作流", "warning")
            return

        reply = QMessageBox.question(
            self,
            "确认重处理",
            f"将使用工作流 '{wf}' 重新处理 {len(paths)} 张图片，原文件将被覆盖。\n\n是否继续？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._start_reprocess(paths, wf)

    def _start_reprocess(self, paths: list, workflow: str):
        """启动重处理"""
        self._log_panel.log(f"开始重处理 {len(paths)} 张图片，使用工作流: {workflow}", "step")

        self._reprocess_worker = ReprocessWorkerThread(self.config, paths, workflow)
        self._reprocess_worker.progress_updated.connect(self._on_reprocess_progress)
        self._reprocess_worker.all_done.connect(self._on_reprocess_done)
        self._reprocess_worker.error_occurred.connect(self._on_reprocess_error)
        self._reprocess_worker.start()

    def _on_reprocess_progress(self, current: int, total: int, filename: str):
        """重处理进度更新"""
        self._log_panel.log(f"重处理中 {current}/{total}: {filename}", "info")

    def _on_reprocess_done(self, success_count: int, total_count: int):
        """重处理完成"""
        self._log_panel.log(f"重处理完成: {success_count}/{total_count} 张成功", "success")
        # 刷新结果图库
        self._result_grid.load_directory("./output/generated")

    def _on_reprocess_error(self, error: str):
        """重处理错误"""
        self._log_panel.log(f"重处理错误: {error}", "error")


class _PreviewDialog(QWidget):
    """简单的图片预览弹窗。"""
    def __init__(self, path, parent=None):
        from PySide6.QtWidgets import QDialog
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle(Path(path).name)
        self._dlg.resize(900, 700)
        layout = QVBoxLayout(self._dlg)
        viewer = ImageViewer(max_size=800)
        viewer.set_image(path, max_size=800)
        layout.addWidget(viewer)

    def exec(self):
        self._dlg.exec()


# ══════════════════════════════════════════════════════════════
# Helper Classes - Image Editing and Reprocessing
# ══════════════════════════════════════════════════════════════

class ImageEditorDialog(QDialog):
    """单图编辑器对话框 - 裁剪/缩放/旋转"""

    image_saved = Signal(str)  # 图片保存后发射信号

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._original = None  # 原始图片（numpy array）
        self._current = None   # 当前编辑中的图片

        self.setWindowTitle(f"编辑图片 - {Path(image_path).name}")
        self.setMinimumSize(1000, 700)
        self._load_image()
        self._build_ui()
        log_info(f"[图片编辑器] 打开编辑器: {Path(image_path).name}")

    def _load_image(self):
        """加载图片到内存"""
        try:
            from utils.image_processor import _read_image
            self._original = _read_image(self._image_path)
            self._current = self._original.copy()
        except Exception as e:
            log_error(f"[图片编辑器] 加载图片失败: {e}")
            QMessageBox.critical(self, "错误", f"加载图片失败: {e}")
            self.reject()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel(f"编辑: {Path(self._image_path).name}")
        title.setFont(Theme.font_header())
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        self._tool_buttons = []

        crop_btn = QPushButton("裁剪")
        crop_btn.setIcon(Icons.palette())
        crop_btn.setCheckable(True)
        crop_btn.setChecked(True)
        crop_btn.clicked.connect(lambda: self._select_tool(0))
        self._tool_buttons.append(crop_btn)
        toolbar.addWidget(crop_btn)

        resize_btn = QPushButton("缩放")
        resize_btn.setIcon(Icons.palette())
        resize_btn.setCheckable(True)
        resize_btn.clicked.connect(lambda: self._select_tool(1))
        self._tool_buttons.append(resize_btn)
        toolbar.addWidget(resize_btn)

        rotate_btn = QPushButton("旋转")
        rotate_btn.setIcon(Icons.palette())
        rotate_btn.setCheckable(True)
        rotate_btn.clicked.connect(lambda: self._select_tool(2))
        self._tool_buttons.append(rotate_btn)
        toolbar.addWidget(rotate_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 主内容区域：左侧预览 + 右侧参数
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：图片预览
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_layout = QVBoxLayout(preview_frame)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background-color: #2D2D2D;")
        preview_scroll.setWidget(self._preview_label)
        preview_layout.addWidget(preview_scroll)

        content_splitter.addWidget(preview_frame)

        # 右侧：参数面板（QStackedWidget）
        params_frame = QFrame()
        params_frame.setFrameShape(QFrame.Shape.StyledPanel)
        params_frame.setFixedWidth(350)
        params_layout = QVBoxLayout(params_frame)

        # 当前尺寸显示
        self._size_label = QLabel()
        self._size_label.setFont(Theme.font_body())
        params_layout.addWidget(self._size_label)

        # 参数面板堆栈
        self._params_stack = QStackedWidget()

        # 裁剪面板
        crop_panel = self._build_crop_panel()
        self._params_stack.addWidget(crop_panel)

        # 缩放面板
        resize_panel = self._build_resize_panel()
        self._params_stack.addWidget(resize_panel)

        # 旋转面板
        rotate_panel = self._build_rotate_panel()
        self._params_stack.addWidget(rotate_panel)

        params_layout.addWidget(self._params_stack)
        params_layout.addStretch()

        content_splitter.addWidget(params_frame)
        layout.addWidget(content_splitter, stretch=1)

        # 底部按钮
        btn_row = QHBoxLayout()

        reset_btn = QPushButton("重置原图")
        reset_btn.setIcon(Icons.refresh())
        reset_btn.setFixedWidth(120)
        reset_btn.clicked.connect(self._reset_image)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存关闭")
        save_btn.setIcon(Icons.save())
        save_btn.setProperty("class", "success")
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # 初始化预览
        self._update_preview()
        self._select_tool(0)




    def _build_crop_panel(self) -> QWidget:
        """构建裁剪参数面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("从各边裁掉像素:")
        title.setFont(Theme.font_title())
        layout.addWidget(title)

        # 上边
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("上边:"))
        self._crop_top = QSpinBox()
        self._crop_top.setRange(0, 10000)
        self._crop_top.setSuffix(" px")
        top_row.addWidget(self._crop_top)
        layout.addLayout(top_row)

        # 下边
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("下边:"))
        self._crop_bottom = QSpinBox()
        self._crop_bottom.setRange(0, 10000)
        self._crop_bottom.setSuffix(" px")
        bottom_row.addWidget(self._crop_bottom)
        layout.addLayout(bottom_row)

        # 左边
        left_row = QHBoxLayout()
        left_row.addWidget(QLabel("左边:"))
        self._crop_left = QSpinBox()
        self._crop_left.setRange(0, 10000)
        self._crop_left.setSuffix(" px")
        left_row.addWidget(self._crop_left)
        layout.addLayout(left_row)

        # 右边
        right_row = QHBoxLayout()
        right_row.addWidget(QLabel("右边:"))
        self._crop_right = QSpinBox()
        self._crop_right.setRange(0, 10000)
        self._crop_right.setSuffix(" px")
        right_row.addWidget(self._crop_right)
        layout.addLayout(right_row)

        # 应用按钮
        apply_btn = QPushButton("应用裁剪")
        apply_btn.setIcon(Icons.play())
        apply_btn.setProperty("class", "success")
        apply_btn.clicked.connect(self._apply_crop)
        layout.addWidget(apply_btn)

        layout.addStretch()
        return panel

    def _build_resize_panel(self) -> QWidget:
        """构建缩放参数面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("缩放尺寸:")
        title.setFont(Theme.font_title())
        layout.addWidget(title)

        # 宽度
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("宽度:"))
        self._resize_width = QSpinBox()
        self._resize_width.setRange(1, 10000)
        self._resize_width.setSuffix(" px")
        self._resize_width.valueChanged.connect(self._on_resize_width_changed)
        width_row.addWidget(self._resize_width)
        layout.addLayout(width_row)

        # 高度
        height_row = QHBoxLayout()
        height_row.addWidget(QLabel("高度:"))
        self._resize_height = QSpinBox()
        self._resize_height.setRange(1, 10000)
        self._resize_height.setSuffix(" px")
        self._resize_height.valueChanged.connect(self._on_resize_height_changed)
        height_row.addWidget(self._resize_height)
        layout.addLayout(height_row)

        # 保持比例
        self._keep_aspect = QCheckBox("保持比例")
        self._keep_aspect.setChecked(True)
        layout.addWidget(self._keep_aspect)

        # 应用按钮
        apply_btn = QPushButton("应用缩放")
        apply_btn.setIcon(Icons.play())
        apply_btn.setProperty("class", "success")
        apply_btn.clicked.connect(self._apply_resize)
        layout.addWidget(apply_btn)

        layout.addStretch()
        return panel

    def _build_rotate_panel(self) -> QWidget:
        """构建旋转参数面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("旋转角度:")
        title.setFont(Theme.font_title())
        layout.addWidget(title)

        # 角度输入
        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("角度:"))
        self._rotate_angle = QSpinBox()
        self._rotate_angle.setRange(-360, 360)
        self._rotate_angle.setSuffix(" °")
        angle_row.addWidget(self._rotate_angle)
        layout.addLayout(angle_row)

        # 快捷按钮
        quick_row = QHBoxLayout()
        btn_90 = QPushButton("90°")
        btn_90.clicked.connect(lambda: self._rotate_angle.setValue(90))
        quick_row.addWidget(btn_90)

        btn_180 = QPushButton("180°")
        btn_180.clicked.connect(lambda: self._rotate_angle.setValue(180))
        quick_row.addWidget(btn_180)

        btn_270 = QPushButton("270°")
        btn_270.clicked.connect(lambda: self._rotate_angle.setValue(270))
        quick_row.addWidget(btn_270)
        layout.addLayout(quick_row)

        # 应用按钮
        apply_btn = QPushButton("应用旋转")
        apply_btn.setIcon(Icons.play())
        apply_btn.setProperty("class", "success")
        apply_btn.clicked.connect(self._apply_rotate)
        layout.addWidget(apply_btn)

        layout.addStretch()
        return panel

    def _select_tool(self, index: int):
        """切换工具"""
        # 更新按钮状态
        for i, btn in enumerate(self._tool_buttons):
            btn.setChecked(i == index)

        # 切换参数面板
        self._params_stack.setCurrentIndex(index)

        # 更新尺寸显示
        if self._current is not None:
            h, w = self._current.shape[:2]
            self._size_label.setText(f"当前尺寸: {w} × {h} 像素")

            # 更新缩放面板的默认值
            if index == 1:  # 缩放工具
                self._resize_width.blockSignals(True)
                self._resize_height.blockSignals(True)
                self._resize_width.setValue(w)
                self._resize_height.setValue(h)
                self._resize_width.blockSignals(False)
                self._resize_height.blockSignals(False)

    def _update_preview(self):
        """更新图片预览"""
        if self._current is None:
            return

        # 转换为 QPixmap
        h, w, ch = self._current.shape
        bytes_per_line = ch * w
        rgb_image = cv2.cvtColor(self._current, cv2.COLOR_BGR2RGB)
        q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        # 缩放显示（最大 640x480）
        scaled = pixmap.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._preview_label.setPixmap(scaled)

        # 更新尺寸显示
        self._size_label.setText(f"当前尺寸: {w} × {h} 像素")

    def _on_resize_width_changed(self, value: int):
        """宽度改变时，如果保持比例则更新高度"""
        if self._keep_aspect.isChecked() and self._current is not None:
            h, w = self._current.shape[:2]
            aspect = h / w
            new_height = int(value * aspect)
            self._resize_height.blockSignals(True)
            self._resize_height.setValue(new_height)
            self._resize_height.blockSignals(False)

    def _on_resize_height_changed(self, value: int):
        """高度改变时，如果保持比例则更新宽度"""
        if self._keep_aspect.isChecked() and self._current is not None:
            h, w = self._current.shape[:2]
            aspect = w / h
            new_width = int(value * aspect)
            self._resize_width.blockSignals(True)
            self._resize_width.setValue(new_width)
            self._resize_width.blockSignals(False)

    def _apply_crop(self):
        """应用裁剪"""
        if self._current is None:
            return

        h, w = self._current.shape[:2]
        t = self._crop_top.value()
        b = self._crop_bottom.value()
        l = self._crop_left.value()
        r = self._crop_right.value()

        # 检查有效性
        if t + b >= h or l + r >= w:
            QMessageBox.warning(self, "错误", "裁剪区域无效")
            return

        # 裁剪
        self._current = self._current[t:h-b, l:w-r].copy()
        self._update_preview()
        log_info(f"[图片编辑器] 应用裁剪: 上{t} 下{b} 左{l} 右{r}")

    def _apply_resize(self):
        """应用缩放"""
        if self._current is None:
            return

        nw = self._resize_width.value()
        nh = self._resize_height.value()

        # 缩放
        self._current = cv2.resize(self._current, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
        self._update_preview()
        log_info(f"[图片编辑器] 应用缩放: {nw}x{nh}")

    def _apply_rotate(self):
        """应用旋转"""
        if self._current is None:
            return

        angle = self._rotate_angle.value()
        if angle == 0:
            return

        # 转换为 PIL Image
        pil_img = Image.fromarray(cv2.cvtColor(self._current, cv2.COLOR_BGR2RGB))

        # 旋转（PIL 的 rotate 是逆时针，所以取负）
        rotated = pil_img.rotate(-angle, expand=True, resample=Image.BICUBIC)

        # 转换回 cv2 格式
        self._current = cv2.cvtColor(np.array(rotated), cv2.COLOR_RGB2BGR)
        self._update_preview()
        log_info(f"[图片编辑器] 应用旋转: {angle}°")

    def _reset_image(self):
        """重置为原图"""
        if self._original is not None:
            self._current = self._original.copy()
            self._update_preview()
            log_info("[图片编辑器] 重置为原图")

    def _save_and_close(self):
        """保存并关闭"""
        if self._current is None:
            self.reject()
            return

        try:
            from utils.image_processor import _write_image
            _write_image(self._image_path, self._current)
            log_info(f"[图片编辑器] 保存图片: {Path(self._image_path).name}")
            self.image_saved.emit(self._image_path)
            self.accept()
        except Exception as e:
            log_error(f"[图片编辑器] 保存失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

class BatchEditWorkerThread(QThread):
    """批量编辑工作线程"""

    progress_updated = Signal(int, int, str)  # current, total, filename
    all_done = Signal(bool)  # success

    def __init__(self, paths, operation, params, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._operation = operation  # "crop", "resize", "rotate"
        self._params = params
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            from utils.image_processor import crop_image, resize_image, rotate_image, _read_image

            total = len(self._paths)
            success_count = 0

            for i, path in enumerate(self._paths):
                if self._stop:
                    break

                filename = Path(path).name
                self.progress_updated.emit(i + 1, total, filename)

                try:
                    if self._operation == "crop":
                        # 边距裁剪模式
                        img = _read_image(path)
                        h, w = img.shape[:2]
                        t = self._params.get("top", 0)
                        b = self._params.get("bottom", 0)
                        l = self._params.get("left", 0)
                        r = self._params.get("right", 0)

                        # 计算裁剪区域
                        x = l
                        y = t
                        crop_w = w - l - r
                        crop_h = h - t - b

                        if crop_w > 0 and crop_h > 0:
                            crop_image(path, x, y, crop_w, crop_h)
                            success_count += 1
                        else:
                            log_warning(f"[批量编辑] 跳过 {filename}: 裁剪区域无效")

                    elif self._operation == "resize":
                        if self._params.get("use_percentage", False):
                            # 百分比模式
                            img = _read_image(path)
                            h, w = img.shape[:2]
                            ratio = self._params.get("percentage", 100) / 100.0
                            new_w = int(w * ratio)
                            new_h = int(h * ratio)
                            resize_image(path, new_w, new_h)
                        else:
                            # 固定尺寸模式
                            new_w = self._params.get("width", 100)
                            new_h = self._params.get("height", 100)
                            resize_image(path, new_w, new_h)
                        success_count += 1

                    elif self._operation == "rotate":
                        angle = self._params.get("angle", 0)
                        if angle != 0:
                            rotate_image(path, angle)
                            success_count += 1

                except Exception as e:
                    log_error(f"[批量编辑] 处理失败 {filename}: {e}")

            log_info(f"[批量编辑] 完成: {success_count}/{total} 张成功")
            self.all_done.emit(success_count == total)

        except Exception as e:
            log_error(f"[批量编辑] 线程错误: {e}")
            self.all_done.emit(False)


class BatchEditDialog(QDialog):
    """批量编辑参数对话框"""

    def __init__(self, selected_paths, parent=None):
        super().__init__(parent)
        self._selected_paths = selected_paths
        self._first_image_size = None

        self.setWindowTitle("批量编辑")
        self.setMinimumSize(500, 400)
        self._load_first_image_size()
        self._build_ui()

    def _load_first_image_size(self):
        """加载第一张图片的尺寸"""
        if self._selected_paths:
            try:
                from utils.image_processor import _read_image
                img = _read_image(self._selected_paths[0])
                h, w = img.shape[:2]
                self._first_image_size = (w, h)
            except Exception as e:
                log_error(f"[批量编辑] 加载图片尺寸失败: {e}")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel(f"批量编辑 - 选中 {len(self._selected_paths)} 张图片")
        title.setFont(Theme.font_header())
        layout.addWidget(title)

        if self._first_image_size:
            size_label = QLabel(f"首张尺寸: {self._first_image_size[0]} × {self._first_image_size[1]} 像素")
            size_label.setFont(Theme.font_body())
            layout.addWidget(size_label)

        # 操作类型选择
        type_row = QHBoxLayout()
        self._crop_radio = QRadioButton("裁剪")
        self._crop_radio.toggled.connect(lambda checked: self._on_type_changed(0) if checked else None)
        type_row.addWidget(self._crop_radio)

        self._resize_radio = QRadioButton("缩放")
        self._resize_radio.setChecked(True)
        self._resize_radio.toggled.connect(lambda checked: self._on_type_changed(1) if checked else None)
        type_row.addWidget(self._resize_radio)

        self._rotate_radio = QRadioButton("旋转")
        self._rotate_radio.toggled.connect(lambda checked: self._on_type_changed(2) if checked else None)
        type_row.addWidget(self._rotate_radio)

        type_row.addStretch()
        layout.addLayout(type_row)

        # 参数面板堆栈
        self._params_stack = QStackedWidget()

        # 裁剪面板
        crop_panel = self._build_batch_crop_panel()
        self._params_stack.addWidget(crop_panel)

        # 缩放面板
        resize_panel = self._build_batch_resize_panel()
        self._params_stack.addWidget(resize_panel)

        # 旋转面板
        rotate_panel = self._build_batch_rotate_panel()
        self._params_stack.addWidget(rotate_panel)

        layout.addWidget(self._params_stack, stretch=1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QPushButton("应用")
        apply_btn.setProperty("class", "success")
        apply_btn.setFixedWidth(100)
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(apply_btn)

        layout.addLayout(btn_row)

        # 初始化
        self._on_type_changed(1)

    def _build_batch_crop_panel(self) -> QWidget:
        """构建批量裁剪面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("从各边裁掉像素（每张图按自身尺寸计算）:")
        title.setFont(Theme.font_title())
        layout.addWidget(title)

        # 上边
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("上边:"))
        self._batch_crop_top = QSpinBox()
        self._batch_crop_top.setRange(0, 10000)
        self._batch_crop_top.setSuffix(" px")
        top_row.addWidget(self._batch_crop_top)
        layout.addLayout(top_row)

        # 下边
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("下边:"))
        self._batch_crop_bottom = QSpinBox()
        self._batch_crop_bottom.setRange(0, 10000)
        self._batch_crop_bottom.setSuffix(" px")
        bottom_row.addWidget(self._batch_crop_bottom)
        layout.addLayout(bottom_row)

        # 左边
        left_row = QHBoxLayout()
        left_row.addWidget(QLabel("左边:"))
        self._batch_crop_left = QSpinBox()
        self._batch_crop_left.setRange(0, 10000)
        self._batch_crop_left.setSuffix(" px")
        left_row.addWidget(self._batch_crop_left)
        layout.addLayout(left_row)

        # 右边
        right_row = QHBoxLayout()
        right_row.addWidget(QLabel("右边:"))
        self._batch_crop_right = QSpinBox()
        self._batch_crop_right.setRange(0, 10000)
        self._batch_crop_right.setSuffix(" px")
        right_row.addWidget(self._batch_crop_right)
        layout.addLayout(right_row)

        layout.addStretch()
        return panel

    def _build_batch_resize_panel(self) -> QWidget:
        """构建批量缩放面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        # 百分比模式
        self._percentage_cb = QCheckBox("百分比模式")
        self._percentage_cb.setChecked(False)
        self._percentage_cb.toggled.connect(self._on_percentage_toggled)
        layout.addWidget(self._percentage_cb)

        # 百分比输入
        pct_row = QHBoxLayout()
        pct_row.addWidget(QLabel("比例:"))
        self._percentage_spin = QSpinBox()
        self._percentage_spin.setRange(1, 1000)
        self._percentage_spin.setValue(50)
        self._percentage_spin.setSuffix(" %")
        self._percentage_spin.setEnabled(False)
        pct_row.addWidget(self._percentage_spin)
        layout.addLayout(pct_row)

        # 分隔线
        sep = QLabel("— 或 —")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        # 固定尺寸
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("宽度:"))
        self._batch_resize_width = QSpinBox()
        self._batch_resize_width.setRange(1, 10000)
        if self._first_image_size:
            self._batch_resize_width.setValue(self._first_image_size[0])
        self._batch_resize_width.setSuffix(" px")
        self._batch_resize_width.valueChanged.connect(self._on_batch_width_changed)
        width_row.addWidget(self._batch_resize_width)
        layout.addLayout(width_row)

        height_row = QHBoxLayout()
        height_row.addWidget(QLabel("高度:"))
        self._batch_resize_height = QSpinBox()
        self._batch_resize_height.setRange(1, 10000)
        if self._first_image_size:
            self._batch_resize_height.setValue(self._first_image_size[1])
        self._batch_resize_height.setSuffix(" px")
        self._batch_resize_height.valueChanged.connect(self._on_batch_height_changed)
        height_row.addWidget(self._batch_resize_height)
        layout.addLayout(height_row)

        self._batch_keep_aspect = QCheckBox("保持比例")
        self._batch_keep_aspect.setChecked(True)
        layout.addWidget(self._batch_keep_aspect)

        layout.addStretch()
        return panel

    def _build_batch_rotate_panel(self) -> QWidget:
        """构建批量旋转面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("旋转角度:")
        title.setFont(Theme.font_title())
        layout.addWidget(title)

        # 角度输入
        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("角度:"))
        self._batch_rotate_angle = QSpinBox()
        self._batch_rotate_angle.setRange(-360, 360)
        self._batch_rotate_angle.setSuffix(" °")
        angle_row.addWidget(self._batch_rotate_angle)
        layout.addLayout(angle_row)

        # 快捷按钮
        quick_row = QHBoxLayout()
        btn_90 = QPushButton("90°")
        btn_90.clicked.connect(lambda: self._batch_rotate_angle.setValue(90))
        quick_row.addWidget(btn_90)

        btn_180 = QPushButton("180°")
        btn_180.clicked.connect(lambda: self._batch_rotate_angle.setValue(180))
        quick_row.addWidget(btn_180)

        btn_270 = QPushButton("270°")
        btn_270.clicked.connect(lambda: self._batch_rotate_angle.setValue(270))
        quick_row.addWidget(btn_270)
        layout.addLayout(quick_row)

        layout.addStretch()
        return panel

    def _on_type_changed(self, index: int):
        """操作类型改变"""
        self._params_stack.setCurrentIndex(index)

    def _on_percentage_toggled(self, checked: bool):
        """百分比模式切换"""
        self._percentage_spin.setEnabled(checked)
        self._batch_resize_width.setEnabled(not checked)
        self._batch_resize_height.setEnabled(not checked)
        self._batch_keep_aspect.setEnabled(not checked)

    def _on_batch_width_changed(self, value: int):
        """宽度改变时，如果保持比例则更新高度"""
        if self._batch_keep_aspect.isChecked() and self._first_image_size:
            w, h = self._first_image_size
            aspect = h / w
            new_height = int(value * aspect)
            self._batch_resize_height.blockSignals(True)
            self._batch_resize_height.setValue(new_height)
            self._batch_resize_height.blockSignals(False)

    def _on_batch_height_changed(self, value: int):
        """高度改变时，如果保持比例则更新宽度"""
        if self._batch_keep_aspect.isChecked() and self._first_image_size:
            w, h = self._first_image_size
            aspect = w / h
            new_width = int(value * aspect)
            self._batch_resize_width.blockSignals(True)
            self._batch_resize_width.setValue(new_width)
            self._batch_resize_width.blockSignals(False)

    def get_operation_and_params(self):
        """获取操作类型和参数"""
        if self._crop_radio.isChecked():
            return "crop", {
                "top": self._batch_crop_top.value(),
                "bottom": self._batch_crop_bottom.value(),
                "left": self._batch_crop_left.value(),
                "right": self._batch_crop_right.value(),
            }
        elif self._resize_radio.isChecked():
            if self._percentage_cb.isChecked():
                return "resize", {
                    "use_percentage": True,
                    "percentage": self._percentage_spin.value(),
                }
            else:
                return "resize", {
                    "use_percentage": False,
                    "width": self._batch_resize_width.value(),
                    "height": self._batch_resize_height.value(),
                }
        elif self._rotate_radio.isChecked():
            return "rotate", {
                "angle": self._batch_rotate_angle.value(),
            }
        return None, {}

class ReprocessWorkerThread(QThread):
    """重处理工作线程 - 使用新工作流重新处理图片"""

    progress_updated = Signal(int, int, str)  # current, total, filename
    all_done = Signal(int, int)  # success_count, total_count
    error_occurred = Signal(str)

    def __init__(self, config, paths, workflow, parent=None):
        super().__init__(parent)
        self._config = config
        self._paths = paths
        self._workflow = workflow
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            from image_generation import ComfyUIFluxKontextClient

            url = self._config.comfyui.get_effective_server_url()
            if not url:
                self.error_occurred.emit("请先配置 ComfyUI 服务器地址")
                return

            client = ComfyUIFluxKontextClient(url)

            # 加载工作流
            if self._workflow:
                wf = self._config.comfyui.get_workflow(self._workflow)
                if wf:
                    client.set_workflow(
                        wf.get("json", {}),
                        wf.get("prompt_node_id", "6"),
                        wf.get("prompt_param_path", "inputs.text"),
                        image_node_id=wf.get("image_node_id"),
                        image_param_path=wf.get("image_param_path")
                    )

            if not client.test_connection():
                self.error_occurred.emit(f"无法连接 ComfyUI: {url}")
                return

            total = len(self._paths)
            success_count = 0

            for i, path in enumerate(self._paths):
                if self._stop:
                    break

                filename = Path(path).name
                self.progress_updated.emit(i + 1, total, filename)

                try:
                    # 重新处理图片（覆盖原文件）
                    result = client.image_to_image(path, None, output_dir=str(Path(path).parent))
                    if result:
                        # 如果生成的文件名不同，需要重命名
                        if result != path:
                            import shutil
                            shutil.move(result, path)
                        success_count += 1
                        log_info(f"[重处理] 成功: {filename}")
                    else:
                        log_error(f"[重处理] 失败: {filename}")
                except Exception as e:
                    log_error(f"[重处理] 错误 {filename}: {e}")

            log_info(f"[重处理] 完成: {success_count}/{total} 张成功")
            self.all_done.emit(success_count, total)

        except Exception as e:
            log_error(f"[重处理] 线程错误: {e}")
            self.error_occurred.emit(str(e))

class OSSUploadWorkerThread(QThread):
    """OSS 上传工作线程"""

    progress_updated = Signal(int, int, str)  # current, total, filename
    all_done = Signal(bool, str)  # success, excel_path
    error_occurred = Signal(str)

    def __init__(self, config, image_paths, output_dir, parent=None):
        super().__init__(parent)
        self._config = config
        self._image_paths = image_paths
        self._output_dir = output_dir
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            from utils.oss_uploader import OSSUploader
            from utils.excel_reporter import generate_simple_excel_report

            # 初始化 OSS 上传器
            uploader = OSSUploader(self._config)
            if not uploader.authenticate():
                self.error_occurred.emit("OSS 连接失败，请检查配置")
                return

            # 贴建文件夹前缀
            folder_name = Path(self._output_dir).name
            folder_prefix = uploader.create_folder(folder_name)

            # 上传图片
            total = len(self._image_paths)
            upload_results = []

            for i, path in enumerate(self._image_paths):
                if self._stop:
                    break

                filename = Path(path).name
                self.progress_updated.emit(i + 1, total, filename)

                result = uploader.upload_file(path, folder_prefix)
                if result:
                    upload_results.append(result)

            # 生成 Excel 报告
            if upload_results:
                excel_path = str(Path(self._output_dir) / f"upload_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                if generate_simple_excel_report(upload_results, excel_path):
                    log_info(f"[OSS] 上传完成: {len(upload_results)}/{total} 张成功")
                    self.all_done.emit(True, excel_path)
                else:
                    self.all_done.emit(True, "")
            else:
                self.error_occurred.emit("没有成功上传任何图片")

        except Exception as e:
            log_error(f"[OSS] 上传线程错误: {e}")
            self.error_occurred.emit(str(e))

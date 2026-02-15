"""
本地图生文生图页 — 本地文件夹浏览 → 递归扫描 → ComfyUI 批量处理 → 图库编辑
"""

import os
import shutil
import re
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QFrame, QSplitter,
    QMessageBox, QFileDialog, QCheckBox, QScrollArea,
    QDialog, QGridLayout, QProgressBar, QSpinBox,
    QStackedWidget, QRadioButton,
)
from PySide6.QtGui import QPixmap, QImage

from ..theme import Theme, Icons
from ..widgets.gallery_grid import GalleryGrid
from ..widgets.log_panel import LogPanel
from utils.logger import log_info, log_warning, log_error

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _detect_language(text: str) -> str:
    """检测文本语言（简单实现）"""
    if not text:
        return "unknown"
    # 检测是否包含中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    if chinese_pattern.search(text):
        return "zh"
    return "en"


class TranslateWorker(QThread):
    """翻译工作线程"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, source_lang, target_lang, config, parent=None):
        super().__init__(parent)
        self._text = text
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._config = config

    def run(self):
        try:
            # 优先使用 OpenRouter API
            api_key = self._config.openrouter.api_key
            if api_key:
                result = self._translate_with_openrouter(self._text, self._target_lang)
                if result:
                    self.finished.emit(result)
                    return

            # 备选：智谱 API（暂未实现）
            # TODO: 实现智谱 API 翻译
            self.error.emit("翻译失败：未配置有效的 API")

        except Exception as e:
            self.error.emit(f"翻译错误: {str(e)}")

    def _translate_with_openrouter(self, text: str, target_lang: str) -> str:
        """使用 OpenRouter API 翻译"""
        try:
            import requests

            api_key = self._config.openrouter.api_key
            if not api_key:
                return None

            # 构建翻译提示
            if target_lang == "en":
                prompt = f"Translate the following Chinese text to English. Only return the translated text, no explanations:\n\n{text}"
            else:
                prompt = f"Translate the following English text to Chinese. Only return the translated text, no explanations:\n\n{text}"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                translated = result["choices"][0]["message"]["content"].strip()
                return translated
            else:
                return None

        except Exception:
            return None


class PromptEditorDialog(QDialog):
    """提示词编辑对话框，支持翻译功能"""

    def __init__(self, initial_prompt: str, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._prompt = initial_prompt
        self._translated = ""
        self._translate_worker = None

        self.setWindowTitle("提示词编辑")
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel("编辑提示词")
        title.setFont(Theme.font_header())
        layout.addWidget(title)

        # 提示词输入区
        prompt_lbl = QLabel("提示词:")
        prompt_lbl.setFont(Theme.font_title())
        layout.addWidget(prompt_lbl)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlaceholderText("输入提示词...")
        self._prompt_edit.setFont(Theme.font_body())
        self._prompt_edit.setText(self._prompt)
        layout.addWidget(self._prompt_edit, stretch=2)

        # 翻译按钮
        translate_row = QHBoxLayout()
        self._translate_btn = QPushButton("翻译")
        self._translate_btn.setIcon(Icons.translate())
        self._translate_btn.setFixedWidth(120)
        self._translate_btn.clicked.connect(self._translate)
        translate_row.addWidget(self._translate_btn)

        self._translating_lbl = QLabel("")
        self._translating_lbl.setFont(Theme.font_body())
        translate_row.addWidget(self._translating_lbl)
        translate_row.addStretch()
        layout.addLayout(translate_row)

        # 翻译结果区
        result_lbl = QLabel("翻译结果:")
        result_lbl.setFont(Theme.font_title())
        layout.addWidget(result_lbl)

        self._result_edit = QTextEdit()
        self._result_edit.setPlaceholderText("翻译结果将显示在这里...")
        self._result_edit.setFont(Theme.font_body())
        self._result_edit.setReadOnly(True)
        layout.addWidget(self._result_edit, stretch=2)

        # 替换按钮（仅在中文→英文时显示）
        replace_row = QHBoxLayout()
        self._replace_btn = QPushButton("替换为翻译结果")
        self._replace_btn.setIcon(Icons.sync())
        self._replace_btn.setProperty("class", "success")
        self._replace_btn.setFixedWidth(150)
        self._replace_btn.clicked.connect(self._replace_with_translation)
        self._replace_btn.setVisible(False)
        replace_row.addWidget(self._replace_btn)
        replace_row.addStretch()
        layout.addLayout(replace_row)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setProperty("class", "success")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _translate(self):
        """翻译提示词"""
        text = self._prompt_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        # 检测语言
        source_lang = _detect_language(text)
        if source_lang == "unknown":
            QMessageBox.warning(self, "提示", "无法检测语言")
            return

        # 确定目标语言
        target_lang = "en" if source_lang == "zh" else "zh"

        log_info(f"[提示词编辑器] 开始翻译: {source_lang} → {target_lang}, 长度: {len(text)}")

        # 显示翻译状态
        self._translate_btn.setEnabled(False)
        self._translating_lbl.setText("翻译中...")
        self._result_edit.clear()
        self._replace_btn.setVisible(False)

        # 启动翻译线程
        self._translate_worker = TranslateWorker(text, source_lang, target_lang, self.config)
        self._translate_worker.finished.connect(lambda result: self._on_translate_finished(result, source_lang))
        self._translate_worker.error.connect(self._on_translate_error)
        self._translate_worker.start()

    def _on_translate_finished(self, result: str, source_lang: str):
        """翻译完成"""
        self._translate_btn.setEnabled(True)
        self._translating_lbl.setText("翻译完成")
        self._result_edit.setText(result)
        self._translated = result

        log_info(f"[提示词编辑器] 翻译完成: {source_lang} → {'en' if source_lang == 'zh' else 'zh'}")

        # 仅在中文→英文时显示替换按钮
        if source_lang == "zh":
            self._replace_btn.setVisible(True)

    def _on_translate_error(self, error: str):
        """翻译错误"""
        self._translate_btn.setEnabled(True)
        self._translating_lbl.setText("")
        log_error(f"[提示词编辑器] 翻译失败: {error}")
        QMessageBox.critical(self, "翻译错误", error)

    def _replace_with_translation(self):
        """用翻译结果替换原提示词"""
        if self._translated:
            self._prompt_edit.setText(self._translated)
            self._replace_btn.setVisible(False)
            log_info(f"[提示词编辑器] 已替换为翻译结果: {self._translated[:50]}...")
            QMessageBox.information(self, "提示", "已替换为翻译结果")

    def get_prompt(self) -> str:
        """获取最终提示词"""
        return self._prompt_edit.toPlainText().strip()


def _scan_folder_recursive(folder: Path, recursive: bool = True) -> list[Path]:
    """递归扫描文件夹中的所有图片

    根据 imag2imag-fileviewer-comfyui skill 的规范：
    - 有效扩展名: .jpg, .jpeg, .png
    - 过滤规则: 排除 "副本"、"copy"、"._" 前缀、"$" 前缀
    - 深度优先递归，保持文件夹结构
    """
    exclude_patterns = ["副本", "copy", "._", "$"]
    images = []

    if recursive:
        for file in folder.rglob("*"):
            if file.is_file() and file.suffix.lower() in _IMAGE_EXTS:
                if not any(pattern in file.name for pattern in exclude_patterns):
                    images.append(file)
    else:
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in _IMAGE_EXTS:
                if not any(pattern in file.name for pattern in exclude_patterns):
                    images.append(file)

    return sorted(images, key=lambda f: f.stat().st_mtime, reverse=True)


class _LocalBatchWorker(QThread):
    """本地文件夹批量处理 worker，保持目录结构

    根据 imag2imag-fileviewer-comfyui skill 的规范：
    - 文件名特殊规则：
      - a.jpg（不含扩展名为 a）→ 完全跳过，不处理不输出
      - b.jpg（不含扩展名为 b）→ 跳过 ComfyUI，直接复制原图到输出
      - 其他 → 正常走 ComfyUI 图生图
    - 保持源文件夹的相对路径结构
    """
    progress = Signal(str, str)
    image_done = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, config, paths, source_root, output_root, prompt, workflow, parent=None):
        super().__init__(parent)
        self._config = config
        self._paths = paths
        self._source_root = Path(source_root)
        self._output_root = Path(output_root)
        self._prompt = prompt
        self._workflow = workflow
        self._stop = False
        self._stage1_results = {}

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
                    client.set_workflow(
                        wf.get("json", {}),
                        wf.get("prompt_node_id", "6"),
                        wf.get("prompt_param_path", "inputs.text"),
                        image_node_id=wf.get("image_node_id"),
                        image_param_path=wf.get("image_param_path")
                    )

            if not client.test_connection():
                self.error.emit(f"无法连接 ComfyUI: {url}")
                return

            for i, source_path in enumerate(self._paths):
                if self._stop:
                    break

                rel_path = Path(source_path).relative_to(self._source_root)
                output_path = self._output_root / rel_path
                output_path.parent.mkdir(parents=True, exist_ok=True)

                stem = Path(source_path).stem

                if stem == "a":
                    self.progress.emit(f"跳过 {i+1}/{len(self._paths)}: {Path(source_path).name} (规则: a.jpg)", "info")
                    continue

                elif stem == "b":
                    shutil.copy2(source_path, output_path)
                    self.progress.emit(f"复制 {i+1}/{len(self._paths)}: {Path(source_path).name} (规则: b.jpg)", "info")
                    self.image_done.emit(str(output_path))
                    self._stage1_results[str(source_path)] = {"output": str(output_path), "task": "copy"}

                else:
                    self.progress.emit(f"生成 {i+1}/{len(self._paths)}: {Path(source_path).name}", "step")
                    # 只有当提示词不为空时才传递，否则使用工作流中的默认提示词
                    prompt_to_use = self._prompt if self._prompt and self._prompt.strip() else None
                    result = client.image_to_image(source_path, prompt_to_use, output_dir=str(output_path.parent))
                    if result:
                        self.image_done.emit(result)
                        self._stage1_results[str(source_path)] = {"output": result, "task": "comfyui"}

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class LocalBrowsePage(QWidget):
    """本地图生文生图页面"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._scanned_images = []
        self._output_images = []
        self._build_ui()
        self._log_and_display("本地图生文生图页面已加载", "info")

    def _log_and_display(self, msg: str, level: str = "info"):
        """同时记录到 LogPanel 和全局日志"""
        # 显示在页面日志
        if hasattr(self, '_log'):
            self._log.append(msg, level)

        # 记录到全局日志
        if level == "error":
            log_error(f"[本地图生文生图] {msg}")
        elif level == "warning":
            log_warning(f"[本地图生文生图] {msg}")
        else:
            log_info(f"[本地图生文生图] {msg}")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(16)

        title = QLabel("本地图生文生图")
        title.setFont(Theme.font_header())
        root.addWidget(title)

        # 文件夹配置区
        folder_frame = QFrame()
        folder_frame.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QVBoxLayout(folder_frame)
        fl.setSpacing(12)

        # 源文件夹
        src_row = QHBoxLayout()
        src_lbl = QLabel("源文件夹:")
        src_lbl.setFont(Theme.font_body())
        src_lbl.setFixedWidth(100)
        src_row.addWidget(src_lbl)

        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("选择包含图片的文件夹")
        self._source_input.setFixedWidth(400)
        src_row.addWidget(self._source_input)

        src_btn = QPushButton("浏览...")
        src_btn.setIcon(Icons.folder_open())
        src_btn.setFixedWidth(100)
        src_btn.clicked.connect(self._select_source_folder)
        src_row.addWidget(src_btn)

        self._recursive_cb = QCheckBox("递归扫描子文件夹")
        self._recursive_cb.setChecked(True)
        src_row.addWidget(self._recursive_cb)
        src_row.addStretch()
        fl.addLayout(src_row)

        # 输出文件夹
        out_row = QHBoxLayout()
        out_lbl = QLabel("输出文件夹:")
        out_lbl.setFont(Theme.font_body())
        out_lbl.setFixedWidth(100)
        out_row.addWidget(out_lbl)

        self._output_input = QLineEdit()
        self._output_input.setPlaceholderText("选择输出文件夹")
        self._output_input.setFixedWidth(400)
        out_row.addWidget(self._output_input)

        out_btn = QPushButton("浏览...")
        out_btn.setIcon(Icons.folder_open())
        out_btn.setFixedWidth(100)
        out_btn.clicked.connect(self._select_output_folder)
        out_row.addWidget(out_btn)

        clear_btn = QPushButton("清除")
        clear_btn.setIcon(Icons.delete())
        clear_btn.setProperty("class", "danger")
        clear_btn.setFixedWidth(100)
        clear_btn.clicked.connect(self._clear_output_folder)
        out_row.addWidget(clear_btn)

        out_row.addStretch()
        fl.addLayout(out_row)

        # 工作流和提示词
        wf_row = QHBoxLayout()
        wf_lbl = QLabel("工作流:")
        wf_lbl.setFont(Theme.font_body())
        wf_lbl.setFixedWidth(100)
        wf_row.addWidget(wf_lbl)

        self._workflow_combo = QComboBox()
        self._workflow_combo.setFixedWidth(200)
        self._load_workflows()
        wf_row.addWidget(self._workflow_combo)

        prompt_lbl = QLabel("提示词:")
        prompt_lbl.setFont(Theme.font_body())
        wf_row.addWidget(prompt_lbl)

        self._prompt_input = QLineEdit()
        self._prompt_input.setPlaceholderText("点击编辑提示词（可选）")
        self._prompt_input.setFixedWidth(300)
        self._prompt_input.setReadOnly(True)
        self._prompt_input.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prompt_input.mousePressEvent = lambda e: self._open_prompt_editor()
        wf_row.addWidget(self._prompt_input)

        edit_prompt_btn = QPushButton("编辑")
        edit_prompt_btn.setIcon(Icons.palette())
        edit_prompt_btn.setFixedWidth(80)
        edit_prompt_btn.clicked.connect(self._open_prompt_editor)
        wf_row.addWidget(edit_prompt_btn)

        scan_btn = QPushButton("扫描并处理")
        scan_btn.setIcon(Icons.play())
        scan_btn.setProperty("class", "success")
        scan_btn.setFixedWidth(150)
        scan_btn.clicked.connect(self._scan_and_process)
        wf_row.addWidget(scan_btn)
        wf_row.addStretch()
        fl.addLayout(wf_row)

        root.addWidget(folder_frame)

        # 待处理图片网格
        grid_frame = QFrame()
        grid_frame.setFrameShape(QFrame.Shape.StyledPanel)
        gl = QVBoxLayout(grid_frame)
        gl.setSpacing(12)

        grid_header = QHBoxLayout()
        self._grid_title = QLabel("待处理图片 (共 0 张)")
        self._grid_title.setFont(Theme.font_title())
        grid_header.addWidget(self._grid_title)

        select_all_btn = QPushButton("全选")
        select_all_btn.setIcon(Icons.select_all())
        select_all_btn.setFixedWidth(100)
        select_all_btn.clicked.connect(self._select_all)
        grid_header.addWidget(select_all_btn)

        deselect_btn = QPushButton("取消")
        deselect_btn.setIcon(Icons.deselect())
        deselect_btn.setFixedWidth(100)
        deselect_btn.clicked.connect(self._deselect_all)
        grid_header.addWidget(deselect_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setIcon(Icons.refresh())
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self._refresh_scan)
        grid_header.addWidget(refresh_btn)
        grid_header.addStretch()
        gl.addLayout(grid_header)

        self._gallery_grid = GalleryGrid(columns=4, thumb_size=200, checkable=True, max_images=0)
        gl.addWidget(self._gallery_grid, stretch=1)

        # 批量处理按钮
        batch_row = QHBoxLayout()
        self._start_btn = QPushButton("开始批量处理")
        self._start_btn.setIcon(Icons.play())
        self._start_btn.setProperty("class", "success")
        self._start_btn.setFixedWidth(150)
        self._start_btn.clicked.connect(self._start_batch)
        self._start_btn.setEnabled(False)
        self._start_btn.setToolTip("请先点击'扫描并处理'按钮扫描图片")
        batch_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setIcon(Icons.stop())
        self._stop_btn.setProperty("class", "danger")
        self._stop_btn.setFixedWidth(100)
        self._stop_btn.clicked.connect(self._stop_batch)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("批量处理开始后可点击停止")
        batch_row.addWidget(self._stop_btn)

        self._status_lbl = QLabel("状态: 就绪")
        self._status_lbl.setFont(Theme.font_body())
        batch_row.addWidget(self._status_lbl)
        batch_row.addStretch()
        gl.addLayout(batch_row)

        root.addWidget(grid_frame, stretch=2)

        # 日志面板
        log_lbl = QLabel("进度日志:")
        log_lbl.setFont(Theme.font_title())
        root.addWidget(log_lbl)

        self._log = LogPanel()
        root.addWidget(self._log, stretch=1)

    def _load_workflows(self):
        """加载工作流列表"""
        self._workflow_combo.clear()
        self._workflow_combo.addItem("默认", None)
        workflows = self.config.comfyui.list_workflows()
        if workflows:
            for wf_name in workflows:
                self._workflow_combo.addItem(wf_name, wf_name)

    def _select_source_folder(self):
        """选择源文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择源文件夹")
        if folder:
            self._source_input.setText(folder)
            self._log_and_display(f"已选择源文件夹: {folder}", "info")

    def _select_output_folder(self):
        """选择输出文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self._output_input.setText(folder)
            self._log_and_display(f"已选择输出文件夹: {folder}", "info")

    def _clear_output_folder(self):
        """清空输出文件夹中的所有图片"""
        output = self._output_input.text().strip()
        if not output:
            QMessageBox.warning(self, "提示", "请先选择输出文件夹")
            return

        output_path = Path(output)
        if not output_path.exists() or not output_path.is_dir():
            QMessageBox.warning(self, "错误", "输出文件夹不存在")
            return

        # 统计图片数量
        image_files = []
        for ext in _IMAGE_EXTS:
            image_files.extend(output_path.rglob(f"*{ext}"))

        if not image_files:
            QMessageBox.information(self, "提示", "输出文件夹中没有图片文件")
            self._log_and_display("输出文件夹中没有图片文件", "info")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认清除",
            f"确定要删除输出文件夹中的所有图片吗？\n\n"
            f"文件夹: {output}\n"
            f"图片数量: {len(image_files)} 张\n\n"
            f"此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            self._log_and_display("用户取消清除操作", "info")
            return

        # 删除图片
        deleted_count = 0
        failed_count = 0

        self._log_and_display("=" * 50, "info")
        self._log_and_display(f"开始清除输出文件夹: {output}", "step")

        for img_file in image_files:
            try:
                img_file.unlink()
                deleted_count += 1
                self._log_and_display(f"✓ 已删除: {img_file.name}", "info")
            except Exception as e:
                failed_count += 1
                self._log_and_display(f"✗ 删除失败: {img_file.name} - {str(e)}", "error")

        self._log_and_display("=" * 50, "info")
        self._log_and_display(
            f"清除完成 - 成功: {deleted_count} 张, 失败: {failed_count} 张",
            "success" if failed_count == 0 else "warning"
        )

        if failed_count == 0:
            QMessageBox.information(self, "完成", f"已成功删除 {deleted_count} 张图片")
        else:
            QMessageBox.warning(
                self, "部分失败",
                f"成功删除 {deleted_count} 张图片\n失败 {failed_count} 张图片\n\n请查看日志了解详情"
            )

    def _open_prompt_editor(self):
        """打开提示词编辑对话框"""
        current_prompt = self._prompt_input.text()
        self._log_and_display("打开提示词编辑器", "info")
        dialog = PromptEditorDialog(current_prompt, self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_prompt = dialog.get_prompt()
            self._prompt_input.setText(new_prompt)
            if new_prompt:
                self._log_and_display(f"已设置提示词: {new_prompt[:50]}{'...' if len(new_prompt) > 50 else ''}", "info")
            else:
                self._log_and_display("已清空提示词（将使用工作流默认提示词）", "info")

    def _scan_and_process(self):
        """扫描文件夹并准备处理"""
        source = self._source_input.text().strip()
        if not source:
            QMessageBox.warning(self, "错误", "请选择源文件夹")
            return

        source_path = Path(source)
        if not source_path.exists() or not source_path.is_dir():
            QMessageBox.warning(self, "错误", "源文件夹不存在")
            return

        recursive = self._recursive_cb.isChecked()
        self._log_and_display(f"开始扫描文件夹: {source} (递归: {'是' if recursive else '否'})", "step")

        self._scanned_images = _scan_folder_recursive(source_path, recursive)

        if not self._scanned_images:
            QMessageBox.information(self, "提示", "未找到任何图片文件")
            self._log_and_display("未找到任何图片文件", "warning")
            return

        self._grid_title.setText(f"待处理图片 (共 {len(self._scanned_images)} 张)")
        self._gallery_grid.set_images([str(p) for p in self._scanned_images])
        self._start_btn.setEnabled(True)
        self._log_and_display(f"扫描完成，找到 {len(self._scanned_images)} 张图片", "success")

    def _select_all(self):
        """全选"""
        self._gallery_grid.select_all()
        count = len(self._scanned_images)
        self._log_and_display(f"已全选 {count} 张图片", "info")

    def _deselect_all(self):
        """取消全选"""
        self._gallery_grid.deselect_all()
        self._log_and_display("已取消全选", "info")

    def _refresh_scan(self):
        """刷新扫描"""
        self._log_and_display("刷新扫描", "info")
        self._scan_and_process()

    def _start_batch(self):
        """开始批量处理"""
        source = self._source_input.text().strip()
        output = self._output_input.text().strip()

        if not output:
            QMessageBox.warning(self, "错误", "请选择输出文件夹")
            return

        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)

        selected = self._gallery_grid.selected_paths()
        if not selected:
            QMessageBox.warning(self, "错误", "请至少选择一张图片")
            return

        prompt = self._prompt_input.text().strip()
        workflow = self._workflow_combo.currentData()

        self._log_and_display("=" * 50, "info")
        self._log_and_display("开始批量处理", "step")
        self._log_and_display(f"源文件夹: {source}", "info")
        self._log_and_display(f"输出文件夹: {output}", "info")
        self._log_and_display(f"选中图片数: {len(selected)}", "info")
        self._log_and_display(f"工作流: {workflow if workflow else '默认'}", "info")
        self._log_and_display(f"提示词: {prompt if prompt else '使用工作流默认'}", "info")
        self._log_and_display("=" * 50, "info")

        self._output_images = []
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_lbl.setText(f"状态: 处理中 0/{len(selected)}")

        self._worker = _LocalBatchWorker(
            self.config, selected, source, output, prompt, workflow
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.image_done.connect(self._on_image_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_batch(self):
        """停止批量处理"""
        if self._worker:
            self._worker.stop()
            self._stop_btn.setEnabled(False)
            self._log_and_display("用户停止批量处理", "warning")

    def _on_progress(self, msg: str, level: str):
        """处理进度"""
        self._log_and_display(msg, level)

    def _on_image_done(self, path: str):
        """图片处理完成"""
        self._output_images.append(path)
        selected_count = len(self._gallery_grid.selected_paths())
        self._status_lbl.setText(f"状态: 处理中 {len(self._output_images)}/{selected_count}")
        self._log_and_display(f"✓ 完成: {Path(path).name}", "success")

    def _on_finished(self):
        """批量处理完成"""
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText(f"状态: 完成 {len(self._output_images)} 张")
        self._log_and_display("=" * 50, "info")
        self._log_and_display(f"批量处理完成，共生成 {len(self._output_images)} 张图片", "success")
        self._log_and_display("=" * 50, "info")

        if self._output_images:
            reply = QMessageBox.question(
                self, "处理完成",
                f"已完成 {len(self._output_images)} 张图片的处理\n\n是否打开图库查看结果？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._log_and_display("打开图库查看结果", "info")
                self._open_gallery()

    def _on_error(self, msg: str):
        """处理错误"""
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText("状态: 错误")
        self._log_and_display(f"错误: {msg}", "error")
        QMessageBox.critical(self, "错误", msg)

    def _open_gallery(self):
        """打开图库对话框"""
        if not self._output_images:
            return

        dialog = ImageGalleryDialog(self._output_images, self.config, self)
        dialog.exec()


class ThumbnailLoader(QThread):
    """异步缩略图加载线程"""
    thumbnail_loaded = Signal(str, QPixmap)
    finished = Signal()

    def __init__(self, image_paths, size=280, parent=None):
        super().__init__(parent)
        self._paths = image_paths
        self._size = size
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for path in self._paths:
            if self._stop:
                break
            try:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self._size, self._size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.thumbnail_loaded.emit(path, scaled)
            except Exception:
                pass
        self.finished.emit()


class ClickableLabel(QLabel):
    """可点击的图片标签"""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageGalleryDialog(QDialog):
    """图库对话框 - 显示处理结果，支持重处理和编辑"""

    def __init__(self, image_paths, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._image_paths = image_paths
        self._thumbnails = {}
        self._selected = set()
        self._loader = None
        self._reprocess_worker = None
        self._oss_worker = None

        self.setWindowTitle("图库 - 处理结果")
        self.setMinimumSize(1200, 800)
        self._build_ui()
        self._load_thumbnails()
        log_info(f"[图库] 打开图库，共 {len(image_paths)} 张图片")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()

        self._count_lbl = QLabel(f"共 {len(self._image_paths)} 张")
        self._count_lbl.setFont(Theme.font_title())
        toolbar.addWidget(self._count_lbl)

        self._selected_lbl = QLabel("已选择: 0 张")
        self._selected_lbl.setFont(Theme.font_body())
        toolbar.addWidget(self._selected_lbl)

        select_all_btn = QPushButton("全选")
        select_all_btn.setIcon(Icons.select_all())
        select_all_btn.setFixedWidth(100)
        select_all_btn.clicked.connect(self._select_all)
        toolbar.addWidget(select_all_btn)

        deselect_btn = QPushButton("取消全选")
        deselect_btn.setIcon(Icons.deselect())
        deselect_btn.setFixedWidth(120)
        deselect_btn.clicked.connect(self._deselect_all)
        toolbar.addWidget(deselect_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 重处理工具栏
        reprocess_row = QHBoxLayout()
        wf_lbl = QLabel("工作流:")
        wf_lbl.setFont(Theme.font_body())
        reprocess_row.addWidget(wf_lbl)

        self._workflow_combo = QComboBox()
        self._workflow_combo.setFixedWidth(200)
        self._load_workflows()
        reprocess_row.addWidget(self._workflow_combo)

        self._reprocess_btn = QPushButton("重新处理选中图片 (0 张)")
        self._reprocess_btn.setIcon(Icons.refresh())
        self._reprocess_btn.setProperty("class", "success")
        self._reprocess_btn.setFixedWidth(220)
        self._reprocess_btn.clicked.connect(self._reprocess_selected)
        self._reprocess_btn.setEnabled(False)
        reprocess_row.addWidget(self._reprocess_btn)
        reprocess_row.addStretch()
        layout.addLayout(reprocess_row)

        # 批量编辑和 OSS 上传按钮
        edit_row = QHBoxLayout()
        self._batch_edit_btn = QPushButton("批量编辑")
        self._batch_edit_btn.setIcon(Icons.palette())
        self._batch_edit_btn.setFixedWidth(120)
        self._batch_edit_btn.clicked.connect(self._batch_edit)
        self._batch_edit_btn.setEnabled(False)
        edit_row.addWidget(self._batch_edit_btn)

        self._upload_oss_btn = QPushButton("上传到 OSS")
        self._upload_oss_btn.setIcon(Icons.sync())
        self._upload_oss_btn.setProperty("class", "success")
        self._upload_oss_btn.setFixedWidth(150)
        self._upload_oss_btn.clicked.connect(self._upload_to_oss)
        edit_row.addWidget(self._upload_oss_btn)

        edit_row.addStretch()
        layout.addLayout(edit_row)

        # 缩略图网格 + 详细信息
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：缩略图网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        grid_widget = QWidget()
        self._grid_layout = QGridLayout(grid_widget)
        self._grid_layout.setSpacing(10)
        scroll.setWidget(grid_widget)
        content_splitter.addWidget(scroll)

        # 右侧：图片详细信息
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setFixedWidth(350)
        info_layout = QVBoxLayout(info_frame)

        info_title = QLabel("图片详细信息:")
        info_title.setFont(Theme.font_title())
        info_layout.addWidget(info_title)

        self._info_label = QLabel("请选择一张图片查看详细信息")
        self._info_label.setFont(Theme.font_body())
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(self._info_label, stretch=1)

        content_splitter.addWidget(info_frame)
        layout.addWidget(content_splitter, stretch=1)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setFont(Theme.font_body())
        self._progress_lbl.setVisible(False)
        layout.addWidget(self._progress_lbl)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton("保存关闭")
        close_btn.setIcon(Icons.save())
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_workflows(self):
        """加载工作流列表"""
        self._workflow_combo.clear()
        self._workflow_combo.addItem("默认", None)
        workflows = self.config.comfyui.list_workflows()
        if workflows:
            for wf_name in workflows:
                self._workflow_combo.addItem(wf_name, wf_name)

    def _load_thumbnails(self):
        """异步加载缩略图"""
        self._loader = ThumbnailLoader(self._image_paths, size=280)
        self._loader.thumbnail_loaded.connect(self._on_thumbnail_loaded)
        self._loader.finished.connect(self._on_thumbnails_finished)
        self._loader.start()

    def _on_thumbnail_loaded(self, path: str, pixmap: QPixmap):
        """缩略图加载完成"""
        row = len(self._thumbnails) // 3
        col = len(self._thumbnails) % 3

        cell_widget = QWidget()
        cell_layout = QVBoxLayout(cell_widget)
        cell_layout.setSpacing(5)
        cell_layout.setContentsMargins(5, 5, 5, 5)

        # 复选框
        checkbox = QCheckBox()
        checkbox.stateChanged.connect(lambda state, p=path: self._on_checkbox_changed(p, state))
        cell_layout.addWidget(checkbox, alignment=Qt.AlignmentFlag.AlignLeft)

        # 图片标签
        img_label = ClickableLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(280, 280)
        img_label.setStyleSheet("border: 1px solid #444; background-color: #2D2D2D;")
        img_label.clicked.connect(lambda p=path: self._show_image_info(p))
        cell_layout.addWidget(img_label)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setIcon(Icons.palette())
        edit_btn.setFixedWidth(100)
        edit_btn.clicked.connect(lambda checked=False, p=path: self._edit_single(p))
        cell_layout.addWidget(edit_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 文件名
        name_label = QLabel(Path(path).name)
        name_label.setFont(Theme.font_small())
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        cell_layout.addWidget(name_label)

        self._grid_layout.addWidget(cell_widget, row, col)
        self._thumbnails[path] = {"checkbox": checkbox, "widget": cell_widget}

    def _on_thumbnails_finished(self):
        """所有缩略图加载完成"""
        pass

    def _on_checkbox_changed(self, path: str, state: int):
        """复选框状态改变"""
        if state == Qt.CheckState.Checked.value:
            self._selected.add(path)
        else:
            self._selected.discard(path)

        self._selected_lbl.setText(f"已选择: {len(self._selected)} 张")
        self._reprocess_btn.setText(f"重新处理选中图片 ({len(self._selected)} 张)")
        self._reprocess_btn.setEnabled(len(self._selected) > 0)
        self._batch_edit_btn.setEnabled(len(self._selected) > 0)

    def _select_all(self):
        """全选"""
        for path, data in self._thumbnails.items():
            data["checkbox"].setChecked(True)
        log_info(f"[图库] 全选图片，共 {len(self._thumbnails)} 张")

    def _deselect_all(self):
        """取消全选"""
        for path, data in self._thumbnails.items():
            data["checkbox"].setChecked(False)
        log_info("[图库] 取消全选")

    def _show_image_info(self, image_path: str):
        """显示图片详细信息"""
        log_info(f"[图库] 查看图片详细信息: {Path(image_path).name}")
        try:
            from PIL import Image

            path = Path(image_path)

            # 读取图片尺寸
            with Image.open(image_path) as img:
                width, height = img.size

            # 文件大小
            size_bytes = path.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.2f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"

            # 文件类型
            file_type = path.suffix.upper().lstrip(".")

            # 贴建时间
            create_time = datetime.fromtimestamp(path.stat().st_ctime)
            time_str = create_time.strftime("%Y-%m-%d %H:%M:%S")

            # 更新信息面板
            info_text = f"""• 尺寸: {width} × {height} 像素
• 文件大小: {size_str}
• 文件类型: {file_type}
• 贴建时间: {time_str}
• 文件名: {path.name}
• 文件路径: {str(path)}"""

            self._info_label.setText(info_text)
        except Exception as e:
            self._info_label.setText(f"无法读取图片信息: {str(e)}")

    def _reprocess_selected(self):
        """重新处理选中的图片"""
        if not self._selected:
            return

        workflow = self._workflow_combo.currentData()
        log_info(f"[图库] 请求重处理 {len(self._selected)} 张图片，工作流: {workflow if workflow else '默认'}")

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认重处理",
            f"确定要重新处理选中的 {len(self._selected)} 张图片吗？\n\n"
            f"工作流: {workflow if workflow else '默认'}\n\n"
            f"注意：处理后将覆盖原文件！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 显示进度条
        self._progress_bar.setVisible(True)
        self._progress_lbl.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("重处理中...")

        # 禁用重处理按钮
        self._reprocess_btn.setEnabled(False)

        # 启动重处理线程
        self._reprocess_worker = ReprocessWorkerThread(self.config, list(self._selected), workflow)
        self._reprocess_worker.progress_updated.connect(self._on_reprocess_progress)
        self._reprocess_worker.all_done.connect(self._on_reprocess_done)
        self._reprocess_worker.error_occurred.connect(self._on_reprocess_error)
        self._reprocess_worker.start()

    def _on_reprocess_progress(self, current: int, total: int, filename: str):
        """重处理进度更新"""
        progress = int((current / total) * 100)
        self._progress_bar.setValue(progress)
        self._progress_lbl.setText(f"重处理中: {current}/{total} - {filename}")

    def _on_reprocess_done(self, success_count: int, total_count: int):
        """重处理完成"""
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        self._reprocess_btn.setEnabled(True)

        if success_count == total_count:
            log_info(f"[图库] 重处理完成: {success_count}/{total_count} 张成功")
            QMessageBox.information(self, "完成", f"重处理完成！\n成功: {success_count}/{total_count} 张\n\n请关闭图库后重新打开查看更新")
        else:
            log_warning(f"[图库] 重处理部分失败: {success_count}/{total_count} 张成功")
            QMessageBox.warning(self, "完成", f"重处理完成，但部分图片处理失败\n成功: {success_count}/{total_count} 张\n\n请查看日志了解详情")

    def _on_reprocess_error(self, error_msg: str):
        """重处理错误"""
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        self._reprocess_btn.setEnabled(True)

        log_error(f"[图库] 重处理错误: {error_msg}")
        QMessageBox.critical(self, "错误", f"重处理失败:\n{error_msg}")

    def _batch_edit(self):
        """批量编辑"""
        if not self._selected:
            return

        log_info(f"[图库] 请求批量编辑 {len(self._selected)} 张图片")

        # 打开批量编辑对话框
        dialog = BatchEditDialog(list(self._selected), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # 获取操作和参数
        operation, params = dialog.get_operation_and_params()
        if not operation:
            return

        log_info(f"[图库] 开始批量编辑: {operation}, 参数: {params}")

        # 显示进度条
        self._progress_bar.setVisible(True)
        self._progress_lbl.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("批量编辑中...")

        # 启动批量编辑线程
        self._batch_worker = BatchEditWorkerThread(list(self._selected), operation, params)
        self._batch_worker.progress_updated.connect(self._on_batch_progress)
        self._batch_worker.all_done.connect(self._on_batch_done)
        self._batch_worker.start()

    def _on_batch_progress(self, current: int, total: int, filename: str):
        """批量编辑进度更新"""
        progress = int((current / total) * 100)
        self._progress_bar.setValue(progress)
        self._progress_lbl.setText(f"批量编辑中: {current}/{total} - {filename}")

    def _on_batch_done(self, success: bool):
        """批量编辑完成"""
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)

        if success:
            log_info("[图库] 批量编辑完成")
            QMessageBox.information(self, "完成", "批量编辑完成！\n请关闭图库后重新打开查看更新")
        else:
            log_warning("[图库] 批量编辑部分失败")
            QMessageBox.warning(self, "完成", "批量编辑完成，但部分图片处理失败\n请查看日志了解详情")

    def _edit_single(self, path: str):
        """单图编辑"""
        log_info(f"[图库] 请求编辑单张图片: {Path(path).name}")

        # 打开编辑器对话框
        editor = ImageEditorDialog(path, self)
        editor.image_saved.connect(lambda p: self._on_image_edited(p))
        editor.exec()

    def _on_image_edited(self, path: str):
        """图片编辑后刷新缩略图"""
        log_info(f"[图库] 图片已编辑，刷新缩略图: {Path(path).name}")
        QMessageBox.information(self, "提示", "图片已保存，请关闭图库后重新打开查看更新")

    def _upload_to_oss(self):
        """上传图片到阿里云 OSS"""
        log_info("[图库] 请求上传到 OSS")

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认上传",
            f"确定要将所有图片上传到阿里云 OSS 吗？\n\n"
            f"共 {len(self._image_paths)} 张图片\n\n"
            f"上传完成后将生成 Excel 报告",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 获取输出目录
        if self._image_paths:
            output_dir = str(Path(self._image_paths[0]).parent)
        else:
            QMessageBox.warning(self, "错误", "没有可上传的图片")
            return

        # 显示进度条
        self._progress_bar.setVisible(True)
        self._progress_lbl.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("上传到 OSS 中...")

        # 禁用上传按钮
        self._upload_oss_btn.setEnabled(False)

        # 启动上传线程
        self._oss_worker = OSSUploadWorkerThread(self.config, self._image_paths, output_dir)
        self._oss_worker.progress_updated.connect(self._on_oss_progress)
        self._oss_worker.all_done.connect(self._on_oss_done)
        self._oss_worker.error_occurred.connect(self._on_oss_error)
        self._oss_worker.start()

    def _on_oss_progress(self, current: int, total: int, filename: str):
        """OSS 上传进度更新"""
        progress = int((current / total) * 100)
        self._progress_bar.setValue(progress)
        self._progress_lbl.setText(f"上传到 OSS: {current}/{total} - {filename}")

    def _on_oss_done(self, success: bool, excel_path: str):
        """OSS 上传完成"""
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        self._upload_oss_btn.setEnabled(True)

        if success:
            log_info(f"[图库] OSS 上传完成，Excel 报告: {excel_path}")
            if excel_path:
                msg = f"上传完成！\n\nExcel 报告已生成:\n{excel_path}\n\n是否打开报告？"
                reply = QMessageBox.question(
                    self, "完成",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    import subprocess
                    subprocess.Popen(['start', excel_path], shell=True)
            else:
                QMessageBox.information(self, "完成", "上传完成！")
        else:
            QMessageBox.warning(self, "完成", "上传完成，但部分图片上传失败\n请查看日志了解详情")

    def _on_oss_error(self, error_msg: str):
        """OSS 上传错误"""
        self._progress_bar.setVisible(False)
        self._progress_lbl.setVisible(False)
        self._upload_oss_btn.setEnabled(True)

        log_error(f"[图库] OSS 上传错误: {error_msg}")
        QMessageBox.critical(self, "错误", f"上传失败:\n{error_msg}")

    def closeEvent(self, event):
        """关闭对话框时停止加载线程"""
        if self._loader and self._loader.isRunning():
            self._loader.stop()
            self._loader.wait()
        log_info("[图库] 关闭图库对话框")
        super().closeEvent(event)


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

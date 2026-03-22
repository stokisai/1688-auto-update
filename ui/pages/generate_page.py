"""

图生图页 - 选择源图 -> 选择引擎/模式 -> 生成 -> 结果预览

支持拖放、图库选择、多种生成模式、提示词改写

"""



import os

import threading

from pathlib import Path



from PySide6.QtCore import Qt

from PySide6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,

    QTextEdit, QComboBox, QCheckBox, QFrame, QFileDialog,

    QSplitter, QApplication, QScrollArea,

)



from ..theme import Theme, Icons

from ..widgets.image_viewer import ImageViewer

from ..widgets.log_panel import LogPanel

from ..workers.generate_worker import GenerateWorker



_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}





class GeneratePage(QWidget):

    def __init__(self, config, parent=None):

        super().__init__(parent)

        self.config = config

        self._output_dir = "./output/generated"

        self._selected_image = None

        self._result_path = None

        self._last_result = None

        self._wash_image = None

        self._worker = None

        self._gen_id = 0

        Path(self._output_dir).mkdir(parents=True, exist_ok=True)

        self._build_ui()



    def _build_ui(self):

        root = QVBoxLayout(self)

        root.setContentsMargins(20, 15, 20, 15)

        root.setSpacing(16)



        # 鏍囬

        title = QLabel("图生图")

        title.setFont(Theme.font_header())

        root.addWidget(title)



        splitter = QSplitter(Qt.Orientation.Horizontal)

        root.addWidget(splitter, stretch=1)



        # ── 左侧：源图+ 閰种疆 ──

        left = QFrame()

        left.setFrameShape(QFrame.Shape.StyledPanel)

        ll = QVBoxLayout(left)

        ll.setSpacing(12)



        # 源功图预览 (支持拖放放)

        src_lbl = QLabel("源图图片（拖放或点击选择）")

        src_lbl.setFont(Theme.font_title())

        ll.addWidget(src_lbl)

        self._source_viewer = ImageViewer(

            placeholder="拖放图片到这里或点击下方按钮选择",

            accept_drop=True, max_size=400,

        )

        self._source_viewer.file_dropped.connect(self._on_image_selected)

        ll.addWidget(self._source_viewer, stretch=2)



        # 源图按钮行

        src_btns = QHBoxLayout()

        sel_btn = QPushButton("选择图片")

        sel_btn.setIcon(Icons.file_image())

        sel_btn.setFixedWidth(140)

        sel_btn.clicked.connect(self._select_image)

        src_btns.addWidget(sel_btn)



        gallery_btn = QPushButton("从图库选择")

        gallery_btn.setIcon(Icons.image())

        gallery_btn.setFixedWidth(150)

        gallery_btn.clicked.connect(self._load_gallery)

        src_btns.addWidget(gallery_btn)



        self._use_last_cb = QCheckBox("使用采集结果")

        self._use_last_cb.setEnabled(False)

        src_btns.addWidget(self._use_last_cb)

        src_btns.addStretch()

        ll.addLayout(src_btns)



        # 引擎选择

        eng_row = QHBoxLayout()

        eng_lbl = QLabel("生成引擎:")

        eng_lbl.setFont(Theme.font_body())

        eng_row.addWidget(eng_lbl)

        self._engine_map = {

            "ComfyUI": "comfyui",

            "Nano Banana": "nano_banana",

            "Nano Pro": "nano_banana_pro",

        }

        self._engine_combo = QComboBox()

        self._engine_combo.addItems(list(self._engine_map.keys()))

        self._engine_combo.setMinimumWidth(200)

        self._engine_combo.currentTextChanged.connect(self._on_engine_change)

        eng_row.addWidget(self._engine_combo)

        eng_row.addStretch()

        ll.addLayout(eng_row)



        # ComfyUI 工作流选择

        self._wf_row = QHBoxLayout()

        self._wf_label = QLabel("ComfyUI 工作流")

        self._wf_label.setFont(Theme.font_body())

        self._wf_row.addWidget(self._wf_label)

        self._wf_combo = QComboBox()

        wf_list = self.config.comfyui.list_workflows()

        if wf_list:

            self._wf_combo.addItems(wf_list)

            cur = self.config.comfyui.current_workflow

            if cur in wf_list:

                self._wf_combo.setCurrentText(cur)

        else:

            self._wf_combo.addItem("请先在配置页添加工作流")

        self._wf_combo.setMinimumWidth(250)

        self._wf_row.addWidget(self._wf_combo)

        self._refresh_wf_btn = QPushButton()
        self._refresh_wf_btn.setIcon(Icons.refresh())
        self._refresh_wf_btn.setToolTip("刷新工作流列表")
        self._refresh_wf_btn.setFixedWidth(36)
        self._refresh_wf_btn.clicked.connect(self._refresh_workflow_list)
        self._wf_row.addWidget(self._refresh_wf_btn)

        self._wf_row.addStretch()

        self._wf_widget = QWidget()

        self._wf_widget.setLayout(self._wf_row)

        ll.addWidget(self._wf_widget)

        self._wf_widget.setVisible(self._engine_map.get(self._engine_combo.currentText()) == "comfyui")



        # 提示词模式

        mode_row = QHBoxLayout()

        mode_lbl = QLabel("提示词模式")

        mode_lbl.setFont(Theme.font_body())

        mode_row.addWidget(mode_lbl)

        self._mode_map = {

            "文案提示词": "copywriting",

            "AI改写提示词": "rewrite",

            "洗图 (无提示词)": "wash",

            "自定义": "custom",

        }

        self._mode_combo = QComboBox()

        self._mode_combo.addItems(list(self._mode_map.keys()))

        self._mode_combo.setMinimumWidth(200)

        self._mode_combo.currentTextChanged.connect(self._on_mode_change)

        mode_row.addWidget(self._mode_combo)

        mode_row.addStretch()

        ll.addLayout(mode_row)



        # 提示词输入

        prompt_lbl = QLabel("提示词")

        prompt_lbl.setFont(Theme.font_body())

        ll.addWidget(prompt_lbl)

        self._prompt_text = QTextEdit()

        self._prompt_text.setFont(Theme.font_body())

        self._prompt_text.setMaximumHeight(100)

        ll.addWidget(self._prompt_text)



        # 提愮示识嶆搷浣?

        prompt_btns = QHBoxLayout()

        sync_btn = QPushButton("同步文案")

        sync_btn.setIcon(Icons.sync())

        sync_btn.setFixedWidth(130)

        sync_btn.clicked.connect(self._sync_copywriting)

        prompt_btns.addWidget(sync_btn)



        rewrite_btn = QPushButton("AI改写")

        rewrite_btn.setIcon(Icons.robot())

        rewrite_btn.setFixedWidth(120)

        rewrite_btn.clicked.connect(self._rewrite_prompt)

        prompt_btns.addWidget(rewrite_btn)



        translate_btn = QPushButton("翻译")

        translate_btn.setIcon(Icons.translate())

        translate_btn.setFixedWidth(100)

        translate_btn.clicked.connect(self._translate_prompt)

        prompt_btns.addWidget(translate_btn)

        prompt_btns.addStretch()

        ll.addLayout(prompt_btns)



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



        splitter.addWidget(left)



        # ── 右侧：结果+ 日志 ──

        right = QFrame()

        right.setFrameShape(QFrame.Shape.StyledPanel)

        rl = QVBoxLayout(right)

        rl.setSpacing(12)



        result_lbl = QLabel("生成结果")

        result_lbl.setFont(Theme.font_title())

        rl.addWidget(result_lbl)

        self._result_viewer = ImageViewer(placeholder="生成结果将显示在这里", max_size=500)

        rl.addWidget(self._result_viewer, stretch=2)



        # 结果操作作

        res_btns = QHBoxLayout()

        self._save_btn = QPushButton("另存为")

        self._save_btn.setIcon(Icons.save())

        self._save_btn.setFixedWidth(120)

        self._save_btn.setEnabled(False)

        self._save_btn.clicked.connect(self._save_result)

        res_btns.addWidget(self._save_btn)



        self._open_btn = QPushButton("打开")

        self._open_btn.setIcon(Icons.folder_open())

        self._open_btn.setFixedWidth(100)

        self._open_btn.setEnabled(False)

        self._open_btn.clicked.connect(lambda: os.startfile(self._result_path) if self._result_path else None)

        res_btns.addWidget(self._open_btn)



        open_folder_btn = QPushButton("输出文件夹")

        open_folder_btn.setIcon(Icons.folder_open())

        open_folder_btn.setFixedWidth(140)

        open_folder_btn.clicked.connect(lambda: os.startfile(self._output_dir))

        res_btns.addWidget(open_folder_btn)

        res_btns.addStretch()

        rl.addLayout(res_btns)



        # 图惧簱预览 (姘村钩婊氬姩)

        gallery_lbl = QLabel("采集图库")

        gallery_lbl.setFont(Theme.font_title())

        rl.addWidget(gallery_lbl)

        self._gallery_scroll = QScrollArea()

        self._gallery_scroll.setWidgetResizable(True)

        self._gallery_scroll.setFixedHeight(160)

        self._gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._gallery_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._gallery_container = QWidget()

        self._gallery_layout = QHBoxLayout(self._gallery_container)

        self._gallery_layout.setSpacing(6)

        self._gallery_scroll.setWidget(self._gallery_container)

        rl.addWidget(self._gallery_scroll)



        # 日志

        log_lbl = QLabel("日志")

        log_lbl.setFont(Theme.font_title())

        rl.addWidget(log_lbl)

        self._log = LogPanel(min_height=80)

        rl.addWidget(self._log)



        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)

        splitter.setStretchFactor(1, 1)



        self._load_gallery()



    # ── 源功图选择择 ──



    def _select_image(self):

        path, _ = QFileDialog.getOpenFileName(

            self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp)"

        )

        if path:

            self._on_image_selected(path)



    def _on_image_selected(self, path: str):

        self._selected_image = path

        self._source_viewer.set_image(path)

        self._log.append(f"已选择: {Path(path).name}", "info")



    def _load_gallery(self):

        """加载采集图库到水平滚动区域"""

        while self._gallery_layout.count():

            item = self._gallery_layout.takeAt(0)

            if item.widget():

                item.widget().deleteLater()



        img_dir = Path("./output/images")

        if not img_dir.is_dir():

            return



        files = sorted(

            [f for f in img_dir.iterdir() if f.suffix.lower() in _IMAGE_EXTS],

            key=lambda f: f.stat().st_mtime, reverse=True,

        )[:30]



        from PySide6.QtGui import QPixmap

        for f in files:

            lbl = QLabel()

            lbl.setFixedSize(140, 140)

            lbl.setCursor(Qt.CursorShape.PointingHandCursor)

            pm = QPixmap(str(f)).scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            lbl.setPixmap(pm)

            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl.setStyleSheet(f"background-color: {Theme.COLOR_INPUT_BG}; border-radius: 6px;")

            lbl.mousePressEvent = lambda e, p=str(f): self._on_image_selected(p)

            self._gallery_layout.addWidget(lbl)



        self._gallery_layout.addStretch()



    # ── 引擎擎分囨崲 ──



    def _refresh_workflow_list(self):
        """刷新工作流下拉列表"""
        from config.settings import reload_config
        self.config = reload_config()
        self._wf_combo.clear()
        wf_list = self.config.comfyui.list_workflows()
        if wf_list:
            self._wf_combo.addItems(wf_list)
            cur = self.config.comfyui.current_workflow
            if cur in wf_list:
                self._wf_combo.setCurrentText(cur)
        else:
            self._wf_combo.addItem("请先在配置页添加工作流")

    def _on_engine_change(self, text):

        is_comfyui = self._engine_map.get(text) == "comfyui"

        self._wf_widget.setVisible(is_comfyui)



    # ── 提示词──



    def _on_mode_change(self, text):

        mode = self._mode_map.get(text, "custom")

        if mode == "copywriting":

            self._sync_copywriting()

        elif mode == "rewrite":

            self._load_ai_prompt()

        elif mode == "wash":

            self._prompt_text.setPlainText("")

            self._prompt_text.setEnabled(False)

        else:

            self._prompt_text.setEnabled(True)



    def _sync_copywriting(self):

        self._prompt_text.setEnabled(True)

        try:

            p = Path("./output/product_info.txt")

            if p.exists():

                self._prompt_text.setPlainText(p.read_text(encoding="utf-8")[:3000])

                self._log.append("已同步文案", "success")

            else:

                self._log.append("未找到文案文件", "warning")

        except Exception as e:

            self._log.append(f"同步失败: {e}", "error")



    def _load_ai_prompt(self):

        self._prompt_text.setEnabled(True)

        try:

            p = Path("./output/ai_prompt.txt")

            if p.exists():

                self._prompt_text.setPlainText(p.read_text(encoding="utf-8"))

                self._log.append("已加载AI提示词", "success")

            else:

                self._log.append("未找到AI提示词，请先在文案页生成", "warning")

        except Exception as e:

            self._log.append(f"加载失败: {e}", "error")



    def _call_text_completion(self, api_key: str, messages):

        import requests



        resp = requests.post(

            "https://openrouter.ai/api/v1/chat/completions",

            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},

            json={"model": "openai/gpt-4o-mini", "messages": messages},

            timeout=60,

        )



        resp.raise_for_status()

        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if isinstance(content, str):

            return content

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict):

                    text = item.get("text") or item.get("content")

                    if text:

                        parts.append(str(text))

                elif isinstance(item, str):

                    parts.append(item)

            return "\n".join(parts).strip()

        return str(content)



    def _rewrite_prompt(self):

        raw = self._prompt_text.toPlainText().strip()

        if not raw:

            self._log.append("请先输入文案", "warning")

            return



        api_key = getattr(self.config.api_keys, "openrouter_api_key", "")

        if not api_key:

            self._log.append("请先配置 OpenRouter API Key", "error")

            return



        self._log.append("正在AI改写提示词...", "step")



        def do_rewrite():

            try:

                result = self._call_text_completion(

                    api_key,

                    [

                        {"role": "system", "content": "You are an expert AI art prompt generator."},

                        {

                            "role": "user",

                            "content": (

                                "Convert this product description to an AI image generation prompt "

                                "(English only, no explanation):\n\n" + raw[:3000]

                            ),

                        },

                    ],

                )

                self._prompt_text.setPlainText(result)

                self._log.append("AI改写完成", "success")

            except Exception as e:

                self._log.append(f"改写失败: {e}", "error")



        threading.Thread(target=do_rewrite, daemon=True).start()



    def _translate_prompt(self):

        raw = self._prompt_text.toPlainText().strip()

        if not raw:

            return



        api_key = getattr(self.config.api_keys, "openrouter_api_key", "")

        if not api_key:

            self._log.append("请先配置 OpenRouter API Key", "error")

            return



        self._log.append("正在翻译...", "step")



        def do_translate():

            try:

                result = self._call_text_completion(

                    api_key,

                    [

                        {

                            "role": "user",

                            "content": f"Translate to Chinese (direct translation only):\n\n{raw[:2000]}",

                        },

                    ],

                )

                self._prompt_text.setPlainText(result)

                self._log.append("翻译完成", "success")

            except Exception as e:

                self._log.append(f"翻译失败: {e}", "error")



        threading.Thread(target=do_translate, daemon=True).start()



    # ── 生成成 ──



    def _start_generate(self):

        source = self._selected_image

        if self._use_last_cb.isChecked() and self._last_result:

            source = self._last_result



        if not source or not Path(source).exists():

            self._log.append("请先选择源图片", "warning")

            return



        engine_key = self._engine_map.get(self._engine_combo.currentText(), "comfyui")

        mode = self._mode_map.get(self._mode_combo.currentText(), "custom")

        prompt = "" if mode == "wash" else self._prompt_text.toPlainText().strip()

        wf_name = self._wf_combo.currentText() if engine_key == "comfyui" else ""



        self._gen_id += 1

        gen_id = self._gen_id

        self._gen_btn.setEnabled(False)

        self._gen_btn.setText("生成中...")

        self._log.append(f"开始生成[{self._engine_combo.currentText()}]", "step")



        self._worker = GenerateWorker(

            config=self.config, engine=engine_key, prompt=prompt,

            source_image=source, output_dir=self._output_dir,

            workflow_name=wf_name,

        )

        self._worker.progress.connect(self._log.append)

        self._worker.finished.connect(lambda p, gid=gen_id: self._on_done(p, gid))

        self._worker.error.connect(self._on_error)

        self._worker.start()



    def _on_done(self, path: str, gen_id: int):

        if gen_id != self._gen_id:

            return

        self._result_path = path

        self._last_result = path

        self._use_last_cb.setEnabled(True)

        self._result_viewer.set_image(path, max_size=500)

        self._save_btn.setEnabled(True)

        self._open_btn.setEnabled(True)

        self._gen_btn.setEnabled(True)

        self._gen_btn.setText("开始生成")

        self._gen_btn.setIcon(Icons.palette())

        self._log.append(f"生成完成: {Path(path).name}", "success")



    def _on_error(self, err: str):

        self._log.append(f"错误: {err}", "error")

        self._gen_btn.setEnabled(True)

        self._gen_btn.setText("开始生成")

        self._gen_btn.setIcon(Icons.palette())



    def _save_result(self):

        if not self._result_path:

            return

        import shutil

        dest, _ = QFileDialog.getSaveFileName(self, "另存为", Path(self._result_path).name, "Images (*.png *.jpg *.webp)")

        if dest:

            shutil.copy2(self._result_path, dest)




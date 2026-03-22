"""

配置页 - API Keys, ComfyUI, 图床, Google Drive, 更新, 日志

"""



import sys

import json

import threading

from pathlib import Path

from datetime import datetime



from PySide6.QtCore import Qt

from PySide6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,

    QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox,

    QScrollArea, QFrame, QGroupBox, QFileDialog, QInputDialog,

    QMessageBox, QTextEdit, QDialog, QApplication,

)



from ..theme import Theme, Icons

from ..widgets.message_box import show_message_with_copy



# Logger

try:

    from utils.logger import (

        setup_logger, get_logger, log_info, log_error, log_debug,

        get_recent_logs, get_log_file_path, open_log_folder,

        is_debug_mode, set_debug_mode,

    )

    LOGGER_AVAILABLE = True

except ImportError:

    LOGGER_AVAILABLE = False



# Updater

try:

    from updater import AutoUpdater

except ImportError:

    AutoUpdater = None



REMOTE_VERSION_URL = "https://raw.githubusercontent.com/stokisai/1688-auto-update/main/version.json"





def _runtime_app_dir() -> Path:

    if getattr(sys, "frozen", False):

        return Path(sys.executable).parent

    return Path(__file__).parent.parent.parent





class ConfigPage(QWidget):

    def __init__(self, config, parent=None):

        super().__init__(parent)

        self.config = config

        self.api_entries: dict[str, QLineEdit] = {}

        self.image_url_entries: dict[str, QLineEdit] = {}

        self.google_drive_entries: dict[str, QLineEdit] = {}

        self._build_ui()



    def _build_ui(self):

        outer = QVBoxLayout(self)

        outer.setContentsMargins(0, 0, 0, 0)



        title = QLabel("API 配置")

        title.setFont(Theme.font_header())

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(title)



        hint = QLabel("提示: 每种类型只需配置至少一个API即可")

        hint.setProperty("class", "gray")

        hint.setFont(Theme.font_small())

        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(hint)



        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        outer.addWidget(scroll)



        container = QWidget()

        self._layout = QVBoxLayout(container)

        self._layout.setSpacing(24)

        scroll.setWidget(container)



        self._build_recognition_section()

        self._build_generation_section()

        self._build_comfyui_section()

        self._build_image_url_section()

        self._build_google_drive_section()

        self._build_update_section()

        if LOGGER_AVAILABLE:

            self._build_log_section()

        self._layout.addStretch()



        save_row = QHBoxLayout()

        save_btn = QPushButton("保存配置")

        save_btn.setIcon(Icons.save())

        save_btn.setFont(Theme.font_subheader())

        save_btn.setFixedHeight(45)

        save_btn.setFixedWidth(200)

        save_btn.setProperty("class", "success")

        save_btn.clicked.connect(self._save_config)

        save_row.addStretch()

        save_row.addWidget(save_btn)

        save_row.addStretch()

        outer.addLayout(save_row)



    # -- 各Section构建 --



    def _add_api_row(self, layout: QVBoxLayout, key: str, label: str, hint: str):

        row = QHBoxLayout()

        lbl = QLabel(f"{label}:")

        lbl.setFixedWidth(150)

        lbl.setFont(Theme.font_body())

        row.addWidget(lbl)



        entry = QLineEdit()

        entry.setPlaceholderText(hint or "API Key")

        entry.setEchoMode(QLineEdit.EchoMode.Password)

        entry.setFont(Theme.font_body())

        entry.setMinimumHeight(36)

        entry.setMaximumWidth(500)

        current = getattr(self.config.api_keys, key, "")

        if current:

            entry.setText(current)

        row.addWidget(entry, stretch=1)

        self.api_entries[key] = entry



        show_cb = QCheckBox("显示")

        show_cb.setFont(Theme.font_small())

        show_cb.toggled.connect(

            lambda checked, e=entry: e.setEchoMode(

                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password

            )

        )

        row.addWidget(show_cb)

        layout.addLayout(row)



    def _build_recognition_section(self):

        grp = QGroupBox("图像识别 API")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        self._add_api_row(gl, "doubao_api_key", "豆包 (推荐)", "免费额度大")

        self._add_api_row(gl, "qwen_api_key", "通义千问", "价格最低")

        self._add_api_row(gl, "openrouter_api_key", "OpenRouter", "一个Key多用")

        self._add_api_row(gl, "gemini_api_key", "Google Gemini", "")

        self._add_api_row(gl, "openai_api_key", "OpenAI GPT-4V", "")



        self._layout.addWidget(grp)



    def _build_generation_section(self):

        grp = QGroupBox("图生图 API")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        h = QLabel("推荐使用上方 Google Gemini API Key 进行图生图")

        h.setProperty("class", "gray")

        h.setFont(Theme.font_small())

        h.setWordWrap(True)

        gl.addWidget(h)



        self._add_api_row(gl, "openrouter_api_key", "OpenRouter", "一个Key多用")



        self._layout.addWidget(grp)



    def _build_comfyui_section(self):

        grp = QGroupBox("ComfyUI 配置")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        conn_hint = QLabel("两种连接方式任选其一: 直接填写完整链接，或填写账号密码 + 服务器地址")

        conn_hint.setStyleSheet(f"color: {Theme.COLOR_WARNING};")

        conn_hint.setFont(Theme.font_small())

        conn_hint.setWordWrap(True)

        gl.addWidget(conn_hint)



        conn_outer = QHBoxLayout()



        # 左侧: 所有输入字段

        fields_layout = QVBoxLayout()

        fields_layout.setSpacing(8)



        srv_row = QHBoxLayout()

        srv_lbl = QLabel("直连地址:")

        srv_lbl.setFont(Theme.font_body())

        srv_row.addWidget(srv_lbl)

        self._comfy_server = QLineEdit(self.config.comfyui.server_url or "")

        self._comfy_server.setPlaceholderText("https://xxx:port")

        self._comfy_server.setMinimumHeight(36)

        self._comfy_server.setMaximumWidth(500)

        srv_row.addWidget(self._comfy_server, stretch=1)

        fields_layout.addLayout(srv_row)



        auth_row1 = QHBoxLayout()

        auth_row1.addWidget(QLabel("账号:"))

        self._auth_user = QLineEdit(self.config.comfyui.auth_username or "")

        self._auth_user.setPlaceholderText("服务器账号")

        self._auth_user.setMinimumHeight(36)

        self._auth_user.setMaximumWidth(200)

        auth_row1.addWidget(self._auth_user)

        auth_row1.addWidget(QLabel("密码:"))

        self._auth_pass = QLineEdit(self.config.comfyui.auth_password or "")

        self._auth_pass.setPlaceholderText("服务器密码")

        self._auth_pass.setEchoMode(QLineEdit.EchoMode.Password)

        self._auth_pass.setMinimumHeight(36)

        self._auth_pass.setMaximumWidth(200)

        auth_row1.addWidget(self._auth_pass)

        auth_row1.addStretch()

        fields_layout.addLayout(auth_row1)



        auth_row2 = QHBoxLayout()

        auth_row2.addWidget(QLabel("服务器"))

        self._auth_server = QLineEdit(self.config.comfyui.auth_server_url or "")

        self._auth_server.setPlaceholderText("wp08.unicron.org.cn:端口")

        self._auth_server.setMinimumHeight(36)

        self._auth_server.setMaximumWidth(400)

        auth_row2.addWidget(self._auth_server)

        auth_row2.addStretch()

        fields_layout.addLayout(auth_row2)



        conn_outer.addLayout(fields_layout)



        # 右侧: 测试连接按钮 + 状态，垂直居中

        btn_layout = QVBoxLayout()

        btn_layout.addStretch()

        test_btn = QPushButton("测试连接")

        test_btn.setIcon(Icons.test())

        test_btn.setFixedWidth(130)

        test_btn.setFixedHeight(42)

        test_btn.clicked.connect(self._test_comfyui)

        btn_layout.addWidget(test_btn)

        self._comfy_status = QLabel("")

        self._comfy_status.setFont(Theme.font_small())

        self._comfy_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout.addWidget(self._comfy_status)

        btn_layout.addStretch()

        conn_outer.addLayout(btn_layout)

        conn_outer.addStretch()



        gl.addLayout(conn_outer)



        wf_title = QLabel("ComfyUI工作流配置")

        wf_title.setFont(Theme.font_body())

        gl.addWidget(wf_title)

        wf_row = QHBoxLayout()

        wf_row.addWidget(QLabel("选择工作流"))

        self._wf_combo = QComboBox()

        self._wf_combo.setMinimumWidth(250)

        self._wf_combo.setMaximumWidth(400)

        wf_list = self.config.comfyui.list_workflows()

        if wf_list:

            self._wf_combo.addItems(wf_list)

            cur = self.config.comfyui.current_workflow

            if cur in wf_list:

                self._wf_combo.setCurrentText(cur)

        else:

            self._wf_combo.addItem("暂无工作流")

        self._wf_combo.currentTextChanged.connect(self._on_workflow_change)

        wf_row.addWidget(self._wf_combo)

        refresh_wf_btn = QPushButton()
        refresh_wf_btn.setIcon(Icons.refresh())
        refresh_wf_btn.setToolTip("刷新工作流列表")
        refresh_wf_btn.setFixedWidth(36)
        refresh_wf_btn.clicked.connect(self._refresh_workflow_menu)
        wf_row.addWidget(refresh_wf_btn)

        wf_row.addStretch()

        gl.addLayout(wf_row)



        btn_row = QHBoxLayout()

        upload_btn = QPushButton("上传工作流JSON")

        upload_btn.setIcon(Icons.upload())

        upload_btn.setFixedWidth(180)

        upload_btn.setStyleSheet("background-color: #6f42c1;")

        upload_btn.clicked.connect(self._upload_workflow_json)

        btn_row.addWidget(upload_btn)



        self._del_wf_btn = QPushButton("删除工作流")

        self._del_wf_btn.setIcon(Icons.delete())

        self._del_wf_btn.setProperty("class", "danger")

        self._del_wf_btn.setFixedWidth(140)

        self._del_wf_btn.setEnabled(bool(wf_list))

        self._del_wf_btn.clicked.connect(self._delete_workflow)

        btn_row.addWidget(self._del_wf_btn)

        btn_row.addStretch()

        gl.addLayout(btn_row)



        wf_hint = QLabel("提示：上传ComfyUI导出的API格式JSON文件，可配置2-3个工作流供图生图使用")

        wf_hint.setProperty("class", "gray")

        wf_hint.setFont(Theme.font_small())

        wf_hint.setWordWrap(True)

        gl.addWidget(wf_hint)



        self._layout.addWidget(grp)



    def _build_image_url_section(self):

        grp = QGroupBox("图片链接配置 (图床)")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        h = QLabel("用于将本地图像转换为URL，当某些API需要图片URL时使用")

        h.setProperty("class", "gray")

        h.setFont(Theme.font_small())

        h.setWordWrap(True)

        gl.addWidget(h)



        def add_url_row(label, key, placeholder, attr_path, echo_pw=False):

            row = QHBoxLayout()

            lbl = QLabel(f"{label}:")

            lbl.setFont(Theme.font_body())

            row.addWidget(lbl)

            e = QLineEdit()

            e.setPlaceholderText(placeholder)

            e.setMinimumHeight(36)

            e.setFixedWidth(300)

            if echo_pw:

                e.setEchoMode(QLineEdit.EchoMode.Password)

            val = getattr(self.config.image_url, attr_path, "")

            if val:

                e.setText(val)

            row.addWidget(e)

            row.addStretch()

            gl.addLayout(row)

            self.image_url_entries[key] = e



        add_url_row("阿里云OSS Key ID", "aliyun_oss_access_key_id", "Access Key ID", "aliyun_oss_access_key_id")

        add_url_row("阿里云OSS 密钥", "aliyun_oss_access_key_secret", "Access Key Secret", "aliyun_oss_access_key_secret", echo_pw=True)

        add_url_row("阿里云OSS Bucket", "aliyun_oss_bucket", "bucket-name", "aliyun_oss_bucket")

        add_url_row("阿里云OSS Endpoint", "aliyun_oss_endpoint", "oss-cn-hangzhou.aliyuncs.com", "aliyun_oss_endpoint")



        test_btn = QPushButton("测试图片上传")

        test_btn.setIcon(Icons.test())

        test_btn.setFixedWidth(160)

        test_btn.clicked.connect(self._test_image_upload)

        gl.addWidget(test_btn, alignment=Qt.AlignmentFlag.AlignLeft)



        self._layout.addWidget(grp)



    def _build_google_drive_section(self):

        grp = QGroupBox("Google Drive 配置")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        h = QLabel("将文件保存到 Google Drive 云存储，需要OAuth 认证")

        h.setProperty("class", "gray")

        h.setFont(Theme.font_small())

        h.setWordWrap(True)

        gl.addWidget(h)



        def add_drive_row(label, key, placeholder, attr, echo_pw=False):

            row = QHBoxLayout()

            lbl = QLabel(f"{label}:")

            lbl.setFixedWidth(150)

            lbl.setFont(Theme.font_body())

            row.addWidget(lbl)

            e = QLineEdit()

            e.setPlaceholderText(placeholder)

            e.setMinimumHeight(36)

            e.setMaximumWidth(500)

            if echo_pw:

                e.setEchoMode(QLineEdit.EchoMode.Password)

            val = getattr(self.config.google_drive, attr, "")

            if val:

                e.setText(val)

            row.addWidget(e, stretch=1)

            gl.addLayout(row)

            self.google_drive_entries[key] = e



        add_drive_row("客户端ID", "client_id", "从Google Cloud Console 获取", "client_id")

        add_drive_row("客户端密钥", "client_secret", "客户端密钥", "client_secret", echo_pw=True)

        add_drive_row("文件夹名称", "folder_name", "自动贴建的文件夹名", "folder_name")

        add_drive_row("文件夹ID (可选)", "folder_id", "现有文件夹ID", "folder_id")



        btn_row = QHBoxLayout()

        is_auth = self.config.google_drive.is_authenticated()

        self._drive_status = QLabel("已认证" if is_auth else "未认证")

        self._drive_status.setStyleSheet(

            f"color: {Theme.COLOR_SUCCESS if is_auth else Theme.COLOR_WARNING};"

        )

        btn_row.addWidget(self._drive_status)



        auth_btn = QPushButton("OAuth 认证")

        auth_btn.setIcon(Icons.auth())

        auth_btn.setFixedWidth(140)

        auth_btn.clicked.connect(self._authenticate_google_drive)

        btn_row.addWidget(auth_btn)



        self._drive_test_btn = QPushButton("测试连接")

        self._drive_test_btn.setIcon(Icons.test())

        self._drive_test_btn.setFixedWidth(130)

        self._drive_test_btn.setEnabled(is_auth)

        self._drive_test_btn.clicked.connect(self._test_google_drive)

        btn_row.addWidget(self._drive_test_btn)

        btn_row.addStretch()

        gl.addLayout(btn_row)



        drive_hint = QLabel("获取 OAuth 凭凭证: console.cloud.google.com")

        drive_hint.setProperty("class", "gray")

        drive_hint.setFont(Theme.font_small())

        gl.addWidget(drive_hint)

        self._layout.addWidget(grp)



    def _build_update_section(self):

        grp = QGroupBox("软件更新")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        ver_row = QHBoxLayout()

        ver_row.addWidget(QLabel("当前版本:"))

        version = "未未知"

        try:

            if AutoUpdater:

                version = AutoUpdater(app_dir=str(_runtime_app_dir())).get_local_version()

            else:

                for p in [_runtime_app_dir() / "_internal" / "version.json", _runtime_app_dir() / "version.json"]:

                    if p.exists():

                        version = json.loads(p.read_text("utf-8")).get("version", "未未知")

                        break

        except Exception:

            pass

        v_lbl = QLabel(f"v{version}")

        v_lbl.setStyleSheet(f"color: {Theme.COLOR_PRIMARY};")

        ver_row.addWidget(v_lbl)



        self._update_status = QLabel("")

        self._update_status.setFont(Theme.font_small())

        ver_row.addWidget(self._update_status)

        ver_row.addStretch()

        gl.addLayout(ver_row)



        self._check_update_btn = QPushButton("检查更新")

        self._check_update_btn.setIcon(Icons.update())

        self._check_update_btn.setFixedWidth(140)

        self._check_update_btn.clicked.connect(self._check_for_update)

        gl.addWidget(self._check_update_btn, alignment=Qt.AlignmentFlag.AlignLeft)



        self._layout.addWidget(grp)



    def _build_log_section(self):

        grp = QGroupBox("调试日志")

        grp.setFont(Theme.font_title())

        gl = QVBoxLayout(grp)

        gl.setSpacing(16)



        dbg_row = QHBoxLayout()

        dbg_row.addWidget(QLabel("调试模式:"))

        self._debug_cb = QCheckBox("开启后记录详细日志")

        self._debug_cb.setChecked(is_debug_mode())

        self._debug_cb.toggled.connect(self._toggle_debug_mode)

        dbg_row.addWidget(self._debug_cb)

        dbg_row.addStretch()

        gl.addLayout(dbg_row)



        btn_row = QHBoxLayout()

        view_btn = QPushButton("查看日志")

        view_btn.setIcon(Icons.log())

        view_btn.setFixedWidth(130)

        view_btn.clicked.connect(self._view_logs)

        btn_row.addWidget(view_btn)



        folder_btn = QPushButton("打开日志文件夹")

        folder_btn.setIcon(Icons.folder_open())

        folder_btn.setProperty("class", "flat")

        folder_btn.setFixedWidth(160)

        folder_btn.clicked.connect(lambda: open_log_folder())

        btn_row.addWidget(folder_btn)

        btn_row.addStretch()

        gl.addLayout(btn_row)



        try:

            log_path_lbl = QLabel(f"日志文件: {get_log_file_path()}")

            log_path_lbl.setProperty("class", "gray")

            log_path_lbl.setFont(Theme.font_small())

            log_path_lbl.setWordWrap(True)

            gl.addWidget(log_path_lbl)

        except Exception:

            pass



        self._layout.addWidget(grp)



    # ── 操作方法 ──



    def _test_comfyui(self):

        # 先堜保存贴认试佷信息?

        self.config.comfyui.server_url = self._comfy_server.text().strip()

        self.config.comfyui.auth_username = self._auth_user.text().strip()

        self.config.comfyui.auth_password = self._auth_pass.text().strip()

        self.config.comfyui.auth_server_url = self._auth_server.text().strip()



        url = self.config.comfyui.get_effective_server_url()

        if not url:

            self._msg("请输入服务器地址（直连或认证方式二选一）", "warning")

            return

        try:

            from image_generation import ComfyUIFluxKontextClient

            client = ComfyUIFluxKontextClient(url)

            if client.test_connection():

                self._msg("连接成功!", "info")

                self._comfy_status.setText("已连接")

                self._comfy_status.setStyleSheet("color: #00C853;")

                self.config.save()

            else:

                self._msg("连接失败，请检查地址", "error")

                self._comfy_status.setText("连接失败")

                self._comfy_status.setStyleSheet("color: #FF5252;")

        except Exception as e:

            self._msg(f"连接失败: {e}", "error")

            self._comfy_status.setText("连接失败")

            self._comfy_status.setStyleSheet("color: #FF5252;")



    def _on_workflow_change(self, text):

        if text and text in (self.config.comfyui.workflows or {}):

            self.config.comfyui.current_workflow = text

            self._del_wf_btn.setEnabled(True)

        else:

            self._del_wf_btn.setEnabled(False)



    def _detect_prompt_node(self, wf):

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                ct = nd.get("class_type", "")

                if "Translator" in ct or "translator" in ct:

                    inp = nd.get("inputs", {})

                    if "text" in inp and isinstance(inp["text"], str):

                        return (nid, "inputs.text")

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                ct = nd.get("class_type", "")

                if ct in ("TextEncodeQwenImageEdit", "QwenImageEdit", "TextEncode") or "TextEncode" in ct:

                    inp = nd.get("inputs", {})

                    if "prompt" in inp and isinstance(inp["prompt"], str):

                        return (nid, "inputs.prompt")

        for nid, nd in wf.items():

            if isinstance(nd, dict) and nd.get("class_type") == "CLIPTextEncode":

                inp = nd.get("inputs", {})

                if "text" in inp and isinstance(inp["text"], str):

                    return (nid, "inputs.text")

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                inp = nd.get("inputs", {})

                ct = nd.get("class_type", "")

                if "prompt" in inp and isinstance(inp["prompt"], str) and "Save" not in ct and "Load" not in ct:

                    return (nid, "inputs.prompt")

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                inp = nd.get("inputs", {})

                ct = nd.get("class_type", "")

                if "text" in inp and isinstance(inp["text"], str) and "Save" not in ct and "Load" not in ct:

                    return (nid, "inputs.text")

        return ("6", "inputs.text")



    def _detect_image_node(self, wf):

        cand = ["image", "images", "image_path", "input_image", "source_image", "init_image", "reference_image"]

        def _img_key(inputs):

            for k in cand:

                if k in inputs:

                    return k

            for k in inputs:

                kl = str(k).lower()

                if kl in ("image_output", "filename_prefix"):

                    continue

                if any(t in kl for t in ("image", "img", "pixels", "source", "reference", "init")):

                    return k

            return None

        def _is_img_node(ct, inputs):

            cl = (ct or "").lower()

            if cl in ("loadimage", "loadimageoutput", "loadimagefromoutput", "loadimagefromoutputs"):

                return True

            if any(t in cl for t in ("loadimage", "imageinput", "imageloader", "inputimage")):

                return True

            if "image" in cl and any(t in cl for t in ("load", "input", "output", "reference", "reader")):

                return True

            return inputs.get("upload") == "image"

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                ct = nd.get("class_type", "")

                inp = nd.get("inputs", {})

                if _is_img_node(ct, inp):

                    k = _img_key(inp) or "image"

                    return (nid, f"inputs.{k}")

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                inp = nd.get("inputs", {})

                if inp.get("upload") == "image":

                    k = _img_key(inp) or "image"

                    return (nid, f"inputs.{k}")

        for nid, nd in wf.items():

            if isinstance(nd, dict):

                ct = nd.get("class_type", "")

                if "Save" in ct or "Preview" in ct:

                    continue

                inp = nd.get("inputs", {})

                k = _img_key(inp)

                if k:

                    return (nid, f"inputs.{k}")

        return (None, None)



    def _upload_workflow_json(self):

        path, _ = QFileDialog.getOpenFileName(self, "选择ComfyUI已ヤ作流丣SON文件", "", "JSON (*.json);;All Files (*.*)")

        if not path:

            return

        try:

            with open(path, "r", encoding="utf-8") as f:

                json_data = json.load(f)

            try:

                from image_generation.comfyui_client import ComfyUIFluxKontextClient

                normalized = ComfyUIFluxKontextClient._normalize_workflow_json(json_data)

            except Exception:

                normalized = json_data

            name, ok = QInputDialog.getText(self, "工作流名称", "请输入该工作流的显示名称（例如：背景替换工作流）")

            if not ok or not name:

                return

            pn_id, pn_path = self._detect_prompt_node(normalized)

            in_id, in_path = self._detect_image_node(normalized)

            self.config.comfyui.add_workflow(

                name=name, json_content=normalized,

                prompt_node_id=pn_id, prompt_param_path=pn_path,

                description=f"从{Path(path).name} 上传",

                image_node_id=in_id, image_param_path=in_path,

            )

            from config.settings import save_config

            save_config()

            self._refresh_workflow_menu()

            msg = f"工作流'{name}' 已叉添加燶n提示词节点 {pn_id} ({pn_path})"

            if in_id:

                msg += f"\n图片节点: {in_id} ({in_path})"

            self._msg(msg, "info")

        except Exception as e:

            self._msg(f"上传失败: {e}", "error")



    def _delete_workflow(self):

        sel = self._wf_combo.currentText()

        if not sel or sel == "暂无工作流":

            return

        reply = QMessageBox.question(self, "确认删除", f"确定要删除工作流 '{sel}' 吗")

        if reply == QMessageBox.StandardButton.Yes:

            if self.config.comfyui.remove_workflow(sel):

                from config.settings import save_config

                save_config()

                self._refresh_workflow_menu()

                self._msg(f"工作流 {sel} 已删除", "info")



    def _refresh_workflow_menu(self):

        self._wf_combo.clear()

        wf_list = self.config.comfyui.list_workflows()

        if wf_list:

            self._wf_combo.addItems(wf_list)

            cur = self.config.comfyui.current_workflow

            if cur in wf_list:

                self._wf_combo.setCurrentText(cur)

            self._del_wf_btn.setEnabled(True)

        else:

            self._wf_combo.addItem("暂无工作流")

            self._del_wf_btn.setEnabled(False)



    def _test_image_upload(self):

        key_id = self.image_url_entries.get("aliyun_oss_access_key_id", QLineEdit()).text().strip()

        key_secret = self.image_url_entries.get("aliyun_oss_access_key_secret", QLineEdit()).text().strip()

        bucket = self.image_url_entries.get("aliyun_oss_bucket", QLineEdit()).text().strip()

        endpoint = self.image_url_entries.get("aliyun_oss_endpoint", QLineEdit()).text().strip()

        if not all([key_id, key_secret, bucket, endpoint]):

            self._msg("请先完整配置阿里云OSS 的Key ID、密钥、Bucket 和Endpoint", "warning")

            return

        try:

            from image_generation.image_url_service import ImageUrlService

            svc = ImageUrlService(self.config.image_url)

            from PIL import Image

            import io, tempfile, os

            img = Image.new("RGB", (100, 100), color="red")

            tmp = os.path.join(tempfile.gettempdir(), "oss_test.png")

            img.save(tmp, format="PNG")

            url = svc.upload_to_url(tmp)

            if url:

                self._msg(f"阿里云OSS 上传成功!\nURL: {url}", "info")

            else:

                self._msg("上传失败，请启检查OSS 配置", "error")

            os.remove(tmp)

        except Exception as e:

            self._msg(f"测试失败: {e}", "error")



    def _authenticate_google_drive(self):

        self.config.google_drive.client_id = self.google_drive_entries["client_id"].text().strip()

        self.config.google_drive.client_secret = self.google_drive_entries["client_secret"].text().strip()

        if not self.config.google_drive.client_id or not self.config.google_drive.client_secret:

            self._msg("请先输入 Client ID 和Client Secret", "warning")

            return

        try:

            from image_generation import GoogleDriveUploader

            uploader = GoogleDriveUploader(self.config.google_drive, lambda: self.config.save())

            result = uploader.authenticate()

            if result.get("success"):

                self._msg("认证成功", "info")

                self._drive_status.setText("已认证")

                self._drive_status.setStyleSheet(f"color: {Theme.COLOR_SUCCESS};")

                self._drive_test_btn.setEnabled(True)

            else:

                self._msg(f"认证失败: {result.get('error', '未未知错误开')}", "error")

        except Exception as e:

            self._msg(f"认证失败: {e}", "error")



    def _test_google_drive(self):

        try:

            from image_generation import GoogleDriveUploader

            up = GoogleDriveUploader(self.config.google_drive)

            self._msg("Google Drive 连接成功" if up.test_connection() else "连接失败", "info" if up.test_connection() else "error")

        except Exception as e:

            self._msg(f"连接失败: {e}", "error")



    def _save_config(self):

        for key, entry in self.api_entries.items():

            setattr(self.config.api_keys, key, entry.text().strip())

        for key, entry in self.image_url_entries.items():

            setattr(self.config.image_url, key, entry.text().strip())

        for key, entry in self.google_drive_entries.items():

            setattr(self.config.google_drive, key, entry.text().strip())

        self.config.comfyui.server_url = self._comfy_server.text().strip()

        self.config.comfyui.auth_username = self._auth_user.text().strip()

        self.config.comfyui.auth_password = self._auth_pass.text().strip()

        self.config.comfyui.auth_server_url = self._auth_server.text().strip()

        self.config.comfyui.last_used = datetime.now().isoformat()

        try:
            self.config.save()
            self._msg("配置已保存", "info")
        except Exception as e:
            from config.settings import CONFIG_FILE
            self._msg(f"保存失败: {e}", "error")
            QMessageBox.critical(self, "保存失败",
                f"配置文件保存失败！\n\n保存路径: {CONFIG_FILE}\n错误: {e}\n\n"
                "可能原因：文件夹权限不足，请尝试以管理员身份运行程序。")



    def _check_for_update(self):

        self._check_update_btn.setEnabled(False)

        self._check_update_btn.setText("检查中...")

        self._update_status.setText("正在检查更新..")

        def _run():

            try:

                if not AutoUpdater:

                    msg = "更新功能未启用"

                else:

                    updater = AutoUpdater(app_dir=str(_runtime_app_dir()), remote_version_url=REMOTE_VERSION_URL)

                    has, info = updater.check_for_update()

                    if has and info:

                        msg = f"发现新版本 v{info.get('version', '?')}"

                    else:

                        msg = "已是最新版本"

            except Exception as e:

                msg = f"检查失败: {e}"

            self._update_status.setText(msg)

            self._check_update_btn.setEnabled(True)

            self._check_update_btn.setText("检查更新")

            self._check_update_btn.setIcon(Icons.update())

        threading.Thread(target=_run, daemon=True).start()



    def _toggle_debug_mode(self, checked):

        if LOGGER_AVAILABLE:

            set_debug_mode(checked)

            log_info(f"调试模式已{'开启' if checked else '关闭'}")



    def _view_logs(self):

        if not LOGGER_AVAILABLE:

            return

        dlg = QDialog(self)

        dlg.setWindowTitle("调试日志")

        dlg.resize(800, 600)

        lay = QVBoxLayout(dlg)

        te = QTextEdit()

        te.setReadOnly(True)

        te.setFont(Theme.font_log())

        te.setPlainText(get_recent_logs(500))

        lay.addWidget(te)

        br = QHBoxLayout()

        rb = QPushButton("刷新")

        rb.setIcon(Icons.refresh())

        rb.clicked.connect(lambda: te.setPlainText(get_recent_logs(500)))

        br.addWidget(rb)

        fb = QPushButton("打开文件夹")

        fb.setIcon(Icons.folder_open())

        fb.clicked.connect(lambda: open_log_folder())

        br.addWidget(fb)

        cb = QPushButton("复制全部")

        cb.setIcon(Icons.copy())

        cb.clicked.connect(lambda: QApplication.clipboard().setText(te.toPlainText()))

        br.addWidget(cb)

        br.addStretch()

        xb = QPushButton("关闭")

        xb.setIcon(Icons.close())

        xb.clicked.connect(dlg.close)

        br.addWidget(xb)

        lay.addLayout(br)

        dlg.exec()



    def _msg(self, msg: str, msg_type: str = "info"):

        title_map = {"info": "提示", "warning": "注意", "error": "错误开"}

        show_message_with_copy(self, title_map.get(msg_type, "提示"), msg, msg_type)






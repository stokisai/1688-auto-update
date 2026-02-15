"""
1688 图片抓取与图生图工具 - GUI应用

使用 CustomTkinter 构建的现代化图形界面。
"""

import os
import sys
import json
import time
import threading
import webbrowser
import windnd
from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime
import requests

import customtkinter as ctk
from PIL import Image, ImageTk
try:
    from CTkMessagebox import CTkMessagebox
except ImportError:
    CTkMessagebox = None

# 导入更新模块
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from updater import AutoUpdater
except ImportError:
    AutoUpdater = None

# 导入日志模块
try:
    from utils.logger import (
        setup_logger, get_logger, log_info, log_error, log_debug,
        get_recent_logs, get_log_file_path, open_log_folder,
        is_debug_mode, set_debug_mode
    )
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False

# 导入激活码验证模块
try:
    from license.license_manager import LicenseManager, get_license_manager
    from license.device_fingerprint import get_device_id
    LICENSE_AVAILABLE = True
except ImportError:
    LICENSE_AVAILABLE = False
    LicenseManager = None


# ==================== 远程版本配置 ====================
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/stokisai/1688-auto-update/main/version.json"
# =====================================================

# 设置外观
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class Theme:
    """UI 主题配置"""
    # 字体
    FONT_FAMILY = "Microsoft YaHei UI"
    HEADER_FONT = (FONT_FAMILY, 28, "bold")
    SUBHEADER_FONT = (FONT_FAMILY, 20, "bold") 
    TITLE_FONT = (FONT_FAMILY, 18, "bold")
    BODY_FONT = (FONT_FAMILY, 16)
    SMALL_FONT = (FONT_FAMILY, 14)
    LOG_FONT = ("Consolas", 16)
    
    # 颜色
    COLOR_PRIMARY = "#3B8ED0"  # Premium Tech Blue
    COLOR_BG_DARK = "#1A1A1A"  # Deep Charcoal/Black
    COLOR_INPUT_BG = "#333333" # Lighter background for inputs
    COLOR_SUCCESS = "#2ea043"  # 绿色
    COLOR_WARNING = "#bd8f22"  # 橙色
    COLOR_DANGER = "#d73a49"   # 红色
    COLOR_TEXT_MAIN = "#FFFFFF" # Pure White
    COLOR_TEXT_GRAY = "#CDCDCD" # Light Gray
    CARD_COLOR = "#222222"      # 卡片/区域背景色
    
    # 布局
    PAD_L = 30
    PAD_M = 15
    PAD_S = 8
    BTN_HEIGHT = 45
    ENTRY_HEIGHT = 45


def get_runtime_app_dir() -> Path:
    """获取运行目录：打包后为 exe 所在目录，开发模式为项目根目录。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def resolve_gemini_generation_key(api_keys, prefer_pro: bool = False) -> str:
    """
    解析 Nano 系列图生图可用的 API Key。

    优先使用专用 Nano Key；若未配置，则回退到 Gemini Key/环境变量，
    与配置页“使用 Gemini Key 进行图生图”的提示保持一致。
    """
    key_order = (
        ["nano_banana_pro_api_key", "nano_banana_api_key"]
        if prefer_pro
        else ["nano_banana_api_key", "nano_banana_pro_api_key"]
    )
    key_order.extend(["gemini_api_key"])

    for field_name in key_order:
        value = getattr(api_keys, field_name, "")
        if value:
            return value

    return os.environ.get("GEMINI_API_KEY", "")


def show_message_with_copy(parent, title: str, message: str, icon: str = "info"):
    """
    显示消息框；warning/error 提供"复制"按钮，便于直接反馈完整报错。
    弹窗固定居中到主窗口，避免多屏时找不到。
    """
    master = parent.winfo_toplevel() if parent else None
    if CTkMessagebox:
        if icon in ("warning", "error"):
            try:
                box = CTkMessagebox(
                    master=master,
                    title=title,
                    message=message,
                    icon=icon,
                    option_1="复制",
                    option_2="OK"
                )
                if box.get() == "复制":
                    try:
                        parent.clipboard_clear()
                        parent.clipboard_append(message)
                        CTkMessagebox(master=master, title="提示", message="报错信息已复制到剪贴板。", icon="check")
                    except Exception:
                        pass
                return
            except TypeError:
                # 兼容旧版 CTkMessagebox（不支持 option_1/option_2）
                pass
        CTkMessagebox(master=master, title=title, message=message, icon=icon)
    else:
        print(f"[{icon}] {title}: {message}")


class ConfigFrame(ctk.CTkFrame):
    """配置页面"""
    
    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self._setup_ui()
        
    def _setup_ui(self):
        # 标题
        title = ctk.CTkLabel(self, text="⚙️ API 配置", font=Theme.HEADER_FONT)
        title.pack(pady=Theme.PAD_L)
        
        # 提示
        hint = ctk.CTkLabel(self, text="💡 提示: 每种类型只需配置至少一个API即可",
                           text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        hint.pack(pady=(0, Theme.PAD_M))
        
        # 滚动区域
        scroll = ctk.CTkScrollableFrame(self, height=400)
        scroll.pack(fill="both", expand=True, padx=Theme.PAD_L, pady=Theme.PAD_M)
        
        # === 图像识别 API ===
        recog_frame = ctk.CTkFrame(scroll)
        recog_frame.pack(fill="x", pady=Theme.PAD_M)
        
        ctk.CTkLabel(recog_frame, text="📸 图像识别 API", 
                    font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        self.api_entries = {}
        
        # 豆包
        self._add_api_row(recog_frame, "doubao_api_key", "豆包 (推荐)", "免费额度大")
        # 通义千问
        self._add_api_row(recog_frame, "qwen_api_key", "通义千问", "价格最低")
        # OpenRouter
        self._add_api_row(recog_frame, "openrouter_api_key", "OpenRouter", "一个Key多用")
        # Gemini
        self._add_api_row(recog_frame, "gemini_api_key", "Google Gemini", "")
        # OpenAI
        self._add_api_row(recog_frame, "openai_api_key", "OpenAI GPT-4V", "")
        
        # === 图生图 API ===
        gen_frame = ctk.CTkFrame(scroll)
        gen_frame.pack(fill="x", pady=Theme.PAD_M)
        
        ctk.CTkLabel(gen_frame, text="🎨 图生图 API", 
                    font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        # 提示信息
        hint_label = ctk.CTkLabel(gen_frame, 
                                  text="💡 推荐使用上方的 Google Gemini API Key 进行图生图",
                                  text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        hint_label.pack(anchor="w", padx=Theme.PAD_M, pady=2)
        
        # OpenRouter (备选)
        self._add_api_row(gen_frame, "openrouter_api_key", "OpenRouter (备选)", "与图像识别共用")
        
        # === ComfyUI 配置 ===
        comfy_frame = ctk.CTkFrame(scroll)
        comfy_frame.pack(fill="x", pady=Theme.PAD_M)
        
        ctk.CTkLabel(comfy_frame, text="🖥️ ComfyUI 配置", 
                    font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        server_row = ctk.CTkFrame(comfy_frame)
        server_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        ctk.CTkLabel(server_row, text="端脑云 服务器地址:", width=130, font=Theme.BODY_FONT).pack(side="left")
        
        self.comfyui_server = ctk.CTkEntry(server_row, height=Theme.ENTRY_HEIGHT,
                                           placeholder_text="https://xxx:port", font=Theme.BODY_FONT,
                                           fg_color=Theme.COLOR_INPUT_BG)
        self.comfyui_server.pack(side="left", padx=5, fill="x", expand=True)
        self.comfyui_server.insert(0, self.config.comfyui.server_url or "")
        
        test_btn = ctk.CTkButton(server_row, text="测试连接", width=80, height=Theme.BTN_HEIGHT,
                                command=self._test_comfyui, font=Theme.BODY_FONT)
        test_btn.pack(side="left", padx=5)

        # 连接状态标签
        self.comfyui_status_label = ctk.CTkLabel(server_row, text="", font=Theme.SMALL_FONT)
        self.comfyui_status_label.pack(side="left", padx=5)
        
        hint2 = ctk.CTkLabel(comfy_frame,
                            text="⚠️ 注意: GPU端口可能变化，请在使用前确认地址正确",
                            text_color=Theme.COLOR_WARNING, font=Theme.SMALL_FONT)
        hint2.pack(anchor="w", padx=Theme.PAD_M, pady=5)

        # --- 认证服务器 (账号密码方式) ---
        auth_hint = ctk.CTkLabel(comfy_frame,
                                 text="🔐 端脑云 认证服务器 (如果服务商提供了账号密码，填写以下内容即可)",
                                 font=Theme.BODY_FONT)
        auth_hint.pack(anchor="w", padx=Theme.PAD_M, pady=(10, 2))

        auth_row1 = ctk.CTkFrame(comfy_frame)
        auth_row1.pack(fill="x", padx=Theme.PAD_M, pady=3)

        ctk.CTkLabel(auth_row1, text="账号:", width=60, font=Theme.BODY_FONT).pack(side="left")
        self.comfyui_auth_user = ctk.CTkEntry(auth_row1, width=180, height=Theme.ENTRY_HEIGHT,
                                               placeholder_text="服务器账号",
                                               font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.comfyui_auth_user.pack(side="left", padx=5)
        self.comfyui_auth_user.insert(0, self.config.comfyui.auth_username or "")

        ctk.CTkLabel(auth_row1, text="密码:", width=60, font=Theme.BODY_FONT).pack(side="left", padx=(10, 0))
        self.comfyui_auth_pass = ctk.CTkEntry(auth_row1, width=180, height=Theme.ENTRY_HEIGHT,
                                               placeholder_text="服务器密码", show="•",
                                               font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.comfyui_auth_pass.pack(side="left", padx=5)
        self.comfyui_auth_pass.insert(0, self.config.comfyui.auth_password or "")

        auth_row2 = ctk.CTkFrame(comfy_frame)
        auth_row2.pack(fill="x", padx=Theme.PAD_M, pady=3)

        ctk.CTkLabel(auth_row2, text="服务器:", width=60, font=Theme.BODY_FONT).pack(side="left")
        self.comfyui_auth_server = ctk.CTkEntry(auth_row2, width=350, height=Theme.ENTRY_HEIGHT,
                                                 placeholder_text="wp08.unicron.org.cn:端口",
                                                 font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.comfyui_auth_server.pack(side="left", padx=5)
        self.comfyui_auth_server.insert(0, self.config.comfyui.auth_server_url or "")

        auth_url_hint = ctk.CTkLabel(comfy_frame,
                                     text="💡 填写后自动拼接为 https://账号:密码@服务器地址，与上方直连地址二选一即可",
                                     text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        auth_url_hint.pack(anchor="w", padx=Theme.PAD_M, pady=(0, 5))

        # === ComfyUI 工作流配置 ===
        workflow_frame = ctk.CTkFrame(comfy_frame)
        workflow_frame.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        ctk.CTkLabel(workflow_frame, text="📋 ComfyUI工作流配置", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 工作流选择
        wf_row = ctk.CTkFrame(workflow_frame)
        wf_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        ctk.CTkLabel(wf_row, text="选择工作流:", width=100, font=Theme.BODY_FONT).pack(side="left", padx=Theme.PAD_S)

        # 获取已有的工作流列表
        workflow_list = self.config.comfyui.list_workflows()
        initial_values = workflow_list if workflow_list else ["暂无工作流"]

        self.config_workflow_var = ctk.StringVar()
        self.config_workflow_menu = ctk.CTkOptionMenu(wf_row, variable=self.config_workflow_var,
                                                   values=initial_values,
                                                   width=300, font=Theme.BODY_FONT,
                                                   text_color="#FFFFFF",
                                                   dropdown_text_color="#FFFFFF",
                                                   dynamic_resizing=False,
                                                   command=self._on_workflow_change)
        self.config_workflow_menu.pack(side="left", padx=5, expand=False, fill=None)

        # 设置初始选中值
        if workflow_list:
            current = self.config.comfyui.current_workflow
            if current and current in workflow_list:
                self.config_workflow_var.set(current)
            else:
                self.config_workflow_var.set(workflow_list[0])
        else:
            self.config_workflow_var.set("")

        # 工作流操作按钮
        wf_btn_row = ctk.CTkFrame(workflow_frame)
        wf_btn_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        self.upload_workflow_btn = ctk.CTkButton(wf_btn_row, text="📤 上传工作流 JSON", height=32,
                                                command=self._upload_workflow_json,
                                                font=Theme.SMALL_FONT, fg_color="#6f42c1", hover_color="#5c3bc1")
        self.upload_workflow_btn.pack(side="left", padx=5)

        self.delete_workflow_btn = ctk.CTkButton(wf_btn_row, text="🗑️ 删除工作流", height=32,
                                                command=self._delete_workflow,
                                                font=Theme.SMALL_FONT, fg_color="#dc3545", hover_color="#c82333",
                                                state="disabled")
        self.delete_workflow_btn.pack(side="left", padx=5)

        # 工作流信息显示
        self.workflow_info = ctk.CTkLabel(workflow_frame, text="💡 提示：上传ComfyUI导出的API格式JSON文件，可配置2-3个工作流供图生图使用",
                                             text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        self.workflow_info.pack(anchor="w", padx=Theme.PAD_M, pady=5)

        # === Google Drive 配置 ===
        drive_frame = ctk.CTkFrame(scroll)
        drive_frame.pack(fill="x", pady=Theme.PAD_M)

        ctk.CTkLabel(drive_frame, text="☁️ Google Drive 配置",
                    font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 提示信息
        drive_hint = ctk.CTkLabel(drive_frame,
                                  text="💡 将文件保存到 Google Drive 云存储，需要 OAuth 认证",
                                  text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        drive_hint.pack(anchor="w", padx=Theme.PAD_M, pady=2)

        self.google_drive_entries = {}

        # OAuth 凭证配置
        oauth_row = ctk.CTkFrame(drive_frame)
        oauth_row.pack(fill="x", padx=Theme.PAD_M, pady=3)

        ctk.CTkLabel(oauth_row, text="OAuth 凭证:", width=130, font=Theme.BODY_FONT).pack(side="left")

        oauth_sub_row = ctk.CTkFrame(oauth_row)
        oauth_sub_row.pack(side="left", fill="x", expand=True)

        # Client ID
        ctk.CTkLabel(oauth_sub_row, text="客户端 ID:", font=Theme.SMALL_FONT).pack(side="left", padx=2)
        self.drive_client_id_entry = ctk.CTkEntry(oauth_sub_row, width=200, height=Theme.ENTRY_HEIGHT,
                                                  placeholder_text="从 Google Cloud Console 获取",
                                                  font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.drive_client_id_entry.pack(side="left", padx=2)
        self.drive_client_id_entry.insert(0, self.config.google_drive.client_id or "")
        self.google_drive_entries["client_id"] = self.drive_client_id_entry

        # Client Secret
        ctk.CTkLabel(oauth_sub_row, text="密钥:", font=Theme.SMALL_FONT).pack(side="left", padx=2)
        self.drive_client_secret_entry = ctk.CTkEntry(oauth_sub_row, width=180, height=Theme.ENTRY_HEIGHT,
                                                      placeholder_text="客户端密钥",
                                                      font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG,
                                                      show="•")
        self.drive_client_secret_entry.pack(side="left", padx=2)
        self.drive_client_secret_entry.insert(0, self.config.google_drive.client_secret or "")
        self.google_drive_entries["client_secret"] = self.drive_client_secret_entry

        # 文件夹配置
        folder_row = ctk.CTkFrame(drive_frame)
        folder_row.pack(fill="x", padx=Theme.PAD_M, pady=3)

        ctk.CTkLabel(folder_row, text="文件夹:", width=130, font=Theme.BODY_FONT).pack(side="left")

        folder_sub_row = ctk.CTkFrame(folder_row)
        folder_sub_row.pack(side="left", fill="x", expand=True)

        # 文件夹名称
        ctk.CTkLabel(folder_sub_row, text="名称:", font=Theme.SMALL_FONT).pack(side="left", padx=2)
        self.drive_folder_name_entry = ctk.CTkEntry(folder_sub_row, width=180, height=Theme.ENTRY_HEIGHT,
                                                    placeholder_text="自动贴建的文件夹名",
                                                    font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.drive_folder_name_entry.pack(side="left", padx=2)
        self.drive_folder_name_entry.insert(0, self.config.google_drive.folder_name or "1688自动化工具")
        self.google_drive_entries["folder_name"] = self.drive_folder_name_entry

        # 文件夹 ID（可选）
        ctk.CTkLabel(folder_sub_row, text="ID (可选):", font=Theme.SMALL_FONT).pack(side="left", padx=2)
        self.drive_folder_id_entry = ctk.CTkEntry(folder_sub_row, width=150, height=Theme.ENTRY_HEIGHT,
                                                  placeholder_text="现有文件夹ID",
                                                  font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.drive_folder_id_entry.pack(side="left", padx=2)
        self.drive_folder_id_entry.insert(0, self.config.google_drive.folder_id or "")
        self.google_drive_entries["folder_id"] = self.drive_folder_id_entry

        # 认证状态和操作按钮
        drive_btn_row = ctk.CTkFrame(drive_frame)
        drive_btn_row.pack(fill="x", padx=Theme.PAD_M, pady=5)

        # 认证状态显示
        self.drive_auth_status = ctk.CTkLabel(
            drive_btn_row,
            text="未认证" if not self.config.google_drive.is_authenticated() else "已认证",
            text_color="orange" if not self.config.google_drive.is_authenticated() else "green",
            font=Theme.BODY_FONT
        )
        self.drive_auth_status.pack(side="left", padx=5)

        # 认证按钮
        self.drive_auth_btn = ctk.CTkButton(
            drive_btn_row,
            text="🔑 OAuth 认证",
            height=32,
            command=self._authenticate_google_drive,
            font=Theme.SMALL_FONT,
            fg_color=Theme.COLOR_PRIMARY
        )
        self.drive_auth_btn.pack(side="left", padx=5)

        # 测试连接按钮
        self.drive_test_btn = ctk.CTkButton(
            drive_btn_row,
            text="🧪 测试连接",
            height=32,
            command=self._test_google_drive,
            font=Theme.SMALL_FONT,
            fg_color="gray",
            state="disabled" if not self.config.google_drive.is_authenticated() else "normal"
        )
        self.drive_test_btn.pack(side="left", padx=5)

        # 帮助链接
        help_link = ctk.CTkLabel(
            drive_frame,
            text="💡 获取 OAuth 凭证: console.cloud.google.com",
            text_color=Theme.COLOR_TEXT_GRAY,
            font=Theme.SMALL_FONT
        )
        help_link.pack(anchor="w", padx=Theme.PAD_M, pady=2)

        # === 软件更新 ===
        update_frame = ctk.CTkFrame(scroll)
        update_frame.pack(fill="x", pady=Theme.PAD_M)

        ctk.CTkLabel(update_frame, text="🔄 软件更新",
                    font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 当前版本显示
        version_row = ctk.CTkFrame(update_frame)
        version_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        ctk.CTkLabel(version_row, text="当前版本:", width=100, font=Theme.BODY_FONT).pack(side="left")

        # 获取当前版本
        current_version = "未知"
        try:
            if AutoUpdater:
                updater = AutoUpdater(app_dir=str(get_runtime_app_dir()))
                current_version = updater.get_local_version()
            else:
                # 兜底：按运行目录查版本
                runtime_dir = get_runtime_app_dir()
                candidates = [
                    runtime_dir / "_internal" / "version.json",
                    runtime_dir / "version.json",
                ]
                for version_file in candidates:
                    if version_file.exists():
                        import json
                        with open(version_file, 'r', encoding='utf-8') as f:
                            version_info = json.load(f)
                            current_version = version_info.get("version", "未知")
                        break
        except:
            pass

        self.version_label = ctk.CTkLabel(version_row, text=f"v{current_version}",
                                          font=Theme.BODY_FONT, text_color=Theme.COLOR_PRIMARY)
        self.version_label.pack(side="left", padx=5)

        # 更新状态标签
        self.update_status_label = ctk.CTkLabel(version_row, text="",
                                                font=Theme.SMALL_FONT, text_color=Theme.COLOR_TEXT_GRAY)
        self.update_status_label.pack(side="left", padx=10)

        # 检查更新按钮
        update_btn_row = ctk.CTkFrame(update_frame)
        update_btn_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        self.check_update_btn = ctk.CTkButton(
            update_btn_row,
            text="🔍 检查更新",
            height=32,
            command=self._check_for_update,
            font=Theme.SMALL_FONT,
            fg_color=Theme.COLOR_PRIMARY
        )
        self.check_update_btn.pack(side="left", padx=5)

        update_hint = ctk.CTkLabel(
            update_frame,
            text="💡 点击检查更新按钮查看是否有新版本可用",
            text_color=Theme.COLOR_TEXT_GRAY,
            font=Theme.SMALL_FONT
        )
        update_hint.pack(anchor="w", padx=Theme.PAD_M, pady=2)

        # === 调试日志 ===
        if LOGGER_AVAILABLE:
            log_frame = ctk.CTkFrame(scroll)
            log_frame.pack(fill="x", pady=Theme.PAD_M)

            ctk.CTkLabel(log_frame, text="📋 调试日志",
                        font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

            # 调试模式开关
            debug_row = ctk.CTkFrame(log_frame)
            debug_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

            ctk.CTkLabel(debug_row, text="调试模式:", width=100, font=Theme.BODY_FONT).pack(side="left")

            self.debug_mode_var = ctk.BooleanVar(value=is_debug_mode())
            self.debug_switch = ctk.CTkSwitch(
                debug_row,
                text="开启后记录详细日志",
                variable=self.debug_mode_var,
                command=self._toggle_debug_mode,
                font=Theme.SMALL_FONT
            )
            self.debug_switch.pack(side="left", padx=5)

            # 日志操作按钮
            log_btn_row = ctk.CTkFrame(log_frame)
            log_btn_row.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

            self.view_log_btn = ctk.CTkButton(
                log_btn_row,
                text="📄 查看日志",
                height=32,
                command=self._view_logs,
                font=Theme.SMALL_FONT,
                fg_color=Theme.COLOR_PRIMARY
            )
            self.view_log_btn.pack(side="left", padx=5)

            self.open_log_folder_btn = ctk.CTkButton(
                log_btn_row,
                text="📁 打开日志文件夹",
                height=32,
                command=self._open_log_folder,
                font=Theme.SMALL_FONT,
                fg_color="gray"
            )
            self.open_log_folder_btn.pack(side="left", padx=5)

            # 日志文件路径显示
            try:
                log_path = get_log_file_path()
                log_path_label = ctk.CTkLabel(
                    log_frame,
                    text=f"💡 日志文件: {log_path}",
                    text_color=Theme.COLOR_TEXT_GRAY,
                    font=Theme.SMALL_FONT
                )
                log_path_label.pack(anchor="w", padx=Theme.PAD_M, pady=2)
            except:
                pass

        # === 保存配置按钮 ===
        save_btn = ctk.CTkButton(self, text="保存配置", height=40, font=Theme.SUBHEADER_FONT,
                                command=self._save_config)
        save_btn.pack(pady=Theme.PAD_L)
        
    def _add_api_row(self, parent, key: str, label: str, hint: str):
        """添加API配置行"""
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", padx=Theme.PAD_M, pady=3)
        
        lbl = ctk.CTkLabel(row, text=f"{label}:", width=120, font=Theme.BODY_FONT)
        lbl.pack(side="left")
        
        entry = ctk.CTkEntry(row, width=280, height=Theme.ENTRY_HEIGHT, placeholder_text=hint or "API Key",
                            show="•", font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        entry.pack(side="left", padx=5)
        
        # 填入现有值
        current = getattr(self.config.api_keys, key, "")
        if current:
            entry.insert(0, current)
            
        self.api_entries[key] = entry
        
        # 显示/隐藏按钮
        show_var = ctk.BooleanVar(value=False)
        def toggle_show():
            if show_var.get():
                entry.configure(show="")
            else:
                entry.configure(show="•")
                
        show_btn = ctk.CTkCheckBox(row, text="显示", variable=show_var, 
                                  command=toggle_show, width=60, font=Theme.SMALL_FONT)
        show_btn.pack(side="left", padx=5)
        
    def _test_comfyui(self):
        """测试ComfyUI连接"""
        # 先保存当前输入的认证信息
        self.config.comfyui.server_url = self.comfyui_server.get().strip()
        self.config.comfyui.auth_username = self.comfyui_auth_user.get().strip()
        self.config.comfyui.auth_password = self.comfyui_auth_pass.get().strip()
        self.config.comfyui.auth_server_url = self.comfyui_auth_server.get().strip()

        url = self.config.comfyui.get_effective_server_url()
        if not url:
            self._show_message("请输入服务器地址（直连或认证方式二选一）", "warning")
            self.comfyui_status_label.configure(text="")
            return

        try:
            from image_generation import ComfyUIFluxKontextClient
            client = ComfyUIFluxKontextClient(url)
            if client.test_connection():
                self._show_message("连接成功!", "info")
                self.comfyui_status_label.configure(text="✅ 已连接", text_color="#00C853")
                self.config.save()
            else:
                self._show_message("连接失败，请检查地址", "error")
                self.comfyui_status_label.configure(text="❌ 连接失败", text_color="#FF5252")
        except Exception as e:
            self._show_message(f"连接失败: {e}", "error")
            self.comfyui_status_label.configure(text="❌ 连接失败", text_color="#FF5252")

    def _save_config(self):
        """保存配置"""
        # 保存API Keys
        for key, entry in self.api_entries.items():
            value = entry.get().strip()
            setattr(self.config.api_keys, key, value)

        # 保存 Google Drive 配置
        for key, entry in self.google_drive_entries.items():
            value = entry.get().strip()
            setattr(self.config.google_drive, key, value)

        # 保存ComfyUI
        self.config.comfyui.server_url = self.comfyui_server.get().strip()
        self.config.comfyui.auth_username = self.comfyui_auth_user.get().strip()
        self.config.comfyui.auth_password = self.comfyui_auth_pass.get().strip()
        self.config.comfyui.auth_server_url = self.comfyui_auth_server.get().strip()
        self.config.comfyui.last_used = datetime.now().isoformat()

        # 保存到文件
        self.config.save()

        self._show_message("配置已保存", "info")

    def _authenticate_google_drive(self):
        """执行 Google Drive OAuth 认证"""
        # 先保存当前的 Client ID 和 Client Secret
        self.config.google_drive.client_id = self.drive_client_id_entry.get().strip()
        self.config.google_drive.client_secret = self.drive_client_secret_entry.get().strip()

        if not self.config.google_drive.client_id or not self.config.google_drive.client_secret:
            self._show_message("请先输入 Client ID 和 Client Secret", "warning")
            return

        self._show_message("正在打开浏览器进行认证...\n请在浏览器中完成授权", "info")

        try:
            from image_generation import GoogleDriveUploader

            # 贴建上传器并执行认证
            def save_config():
                # 认证成功后保存配置
                self.config.save()
                # 更新UI状态
                self.after(0, self._update_drive_auth_status)

            uploader = GoogleDriveUploader(self.config.google_drive, save_config)
            result = uploader.authenticate()

            if result.get("success"):
                self._show_message("认证成功！", "info")
                self._update_drive_auth_status()
            else:
                self._show_message(f"认证失败: {result.get('error', '未知错误')}", "error")

        except Exception as e:
            self._show_message(f"认证失败: {e}", "error")
            import traceback
            traceback.print_exc()

    def _update_drive_auth_status(self):
        """更新 Google Drive 认证状态显示"""
        is_auth = self.config.google_drive.is_authenticated()

        self.drive_auth_status.configure(
            text="已认证" if is_auth else "未认证",
            text_color="green" if is_auth else "orange"
        )

        self.drive_test_btn.configure(
            state="normal" if is_auth else "disabled"
        )

    def _test_google_drive(self):
        """测试 Google Drive 连接"""
        if not self.config.google_drive.is_authenticated():
            self._show_message("请先进行 OAuth 认证", "warning")
            return

        self._show_message("正在测试 Google Drive 连接...", "info")

        try:
            from image_generation import GoogleDriveUploader

            uploader = GoogleDriveUploader(self.config.google_drive)

            if uploader.test_connection():
                self._show_message("Google Drive 连接成功！", "info")
            else:
                self._show_message("连接失败，请检查配置", "error")

        except Exception as e:
            self._show_message(f"连接失败: {e}", "error")
            import traceback
            traceback.print_exc()

    def _detect_prompt_node(self, workflow_json: dict) -> tuple:
        """
        自动检测工作流中的提示词节点

        逻辑：
        1. 优先查找 DeepTranslatorTextNode 节点（翻译节点），其 inputs.text 是字符串
        2. 查找 TextEncodeQwenImageEdit 等节点，其 inputs.prompt 是字符串
        3. 查找 CLIPTextEncode 节点，其 inputs.text 是字符串（非引用）
        4. 最后查找任何包含 inputs.text 或 inputs.prompt 为字符串的节点

        Returns:
            (node_id, param_path) 元组
        """
        # 优先级1: 查找翻译节点 (DeepTranslatorTextNode)
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if "Translator" in class_type or "translator" in class_type:
                    inputs = node_data.get("inputs", {})
                    if "text" in inputs and isinstance(inputs["text"], str):
                        return (node_id, "inputs.text")

        # 优先级2: 查找 TextEncodeQwenImageEdit 等使用 prompt 参数的节点
        prompt_node_types = [
            "TextEncodeQwenImageEdit",
            "QwenImageEdit",
            "TextEncode",
        ]
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if class_type in prompt_node_types or "TextEncode" in class_type:
                    inputs = node_data.get("inputs", {})
                    if "prompt" in inputs and isinstance(inputs["prompt"], str):
                        return (node_id, "inputs.prompt")

        # 优先级3: 查找 CLIPTextEncode 节点，但 text 必须是字符串
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if class_type == "CLIPTextEncode":
                    inputs = node_data.get("inputs", {})
                    if "text" in inputs and isinstance(inputs["text"], str):
                        return (node_id, "inputs.text")

        # 优先级4: 查找任何包含 prompt 字符串的节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                inputs = node_data.get("inputs", {})
                if "prompt" in inputs and isinstance(inputs["prompt"], str):
                    class_type = node_data.get("class_type", "")
                    if "Save" not in class_type and "Load" not in class_type:
                        return (node_id, "inputs.prompt")

        # 优先级5: 查找任何包含 text 字符串的节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                inputs = node_data.get("inputs", {})
                if "text" in inputs and isinstance(inputs["text"], str):
                    # 排除一些不太可能是提示词的节点
                    class_type = node_data.get("class_type", "")
                    if "Save" not in class_type and "Load" not in class_type:
                        return (node_id, "inputs.text")

        # 默认返回节点6
        return ("6", "inputs.text")

    def _detect_image_node(self, workflow_json: dict) -> tuple:
        """
        自动检测工作流中的图片输入节点

        逻辑：
        1. 查找 LoadImage 节点
        2. 查找 LoadImageOutput 节点
        3. 查找其他包含 image 输入的节点

        Returns:
            (node_id, param_path) 元组，如果没找到返回 (None, None)
        """
        candidate_keys = [
            "image", "images", "image_path", "input_image",
            "source_image", "init_image", "reference_image"
        ]

        def _first_image_key(inputs: dict):
            for key in candidate_keys:
                if key in inputs:
                    return key
            return None

        def _first_image_like_key(inputs: dict):
            exact = _first_image_key(inputs)
            if exact:
                return exact
            for key in inputs.keys():
                key_l = str(key).lower()
                if key_l in ("image_output", "filename_prefix"):
                    continue
                if any(token in key_l for token in ("image", "img", "pixels", "source", "reference", "init")):
                    return key
            return None

        def _looks_like_image_input_node(class_type: str, inputs: dict) -> bool:
            cls = (class_type or "").lower()
            if cls in ("loadimage", "loadimageoutput", "loadimagefromoutput", "loadimagefromoutputs"):
                return True
            if any(token in cls for token in ("loadimage", "imageinput", "imageloader", "inputimage")):
                return True
            if "image" in cls and any(token in cls for token in ("load", "input", "output", "reference", "reader")):
                return True
            if inputs.get("upload") == "image":
                return True
            return False

        # 优先级1: 查找常见图片输入节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                inputs = node_data.get("inputs", {})
                if _looks_like_image_input_node(class_type, inputs):
                    key = _first_image_like_key(inputs) or "image"
                    if key:
                        return (node_id, f"inputs.{key}")

        # 优先级2: 更宽松地查找图片输入类节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if any(token in class_type for token in ["LoadImage", "ImageInput", "ImageLoader", "InputImage"]):
                    inputs = node_data.get("inputs", {})
                    key = _first_image_like_key(inputs)
                    if key:
                        return (node_id, f"inputs.{key}")

        # 优先级3: 带 upload=image 标识的节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                inputs = node_data.get("inputs", {})
                if inputs.get("upload") == "image":
                    key = _first_image_like_key(inputs) or "image"
                    return (node_id, f"inputs.{key}")

        # 优先级4: 查找其他包含常见图片输入字段的节点（排除输出节点）
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if "Save" in class_type or "Preview" in class_type:
                    continue
                inputs = node_data.get("inputs", {})
                key = _first_image_like_key(inputs)
                if key:
                    return (node_id, f"inputs.{key}")

        # 没找到图片节点
        return (None, None)

    def _upload_workflow_json(self):
        """上传工作流JSON文件"""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title="选择ComfyUI工作流JSON文件",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            # 兼容前端 workflow 格式，统一转成 API prompt 格式
            try:
                from image_generation.comfyui_client import ComfyUIFluxKontextClient
                normalized_json = ComfyUIFluxKontextClient._normalize_workflow_json(json_data)
            except Exception:
                normalized_json = json_data

            # 询问工作流名称
            from CTkMessagebox import CTkMessagebox
            from tkinter import simpledialog

            name = simpledialog.askstring("工作流名称",
                                           "请输入这个工作流的显示名称（如：背景替换工作流1）",
                                           parent=self.winfo_toplevel())

            if not name:
                return

            # 自动检测提示词节点
            detected_node_id, detected_param_path = self._detect_prompt_node(normalized_json)
            print(f"[工作流上传] 自动检测到提示词节点: {detected_node_id}, 路径: {detected_param_path}")

            # 自动检测图片输入节点
            image_node_id, image_param_path = self._detect_image_node(normalized_json)
            if image_node_id:
                print(f"[工作流上传] 自动检测到图片节点: {image_node_id}, 路径: {image_param_path}")

            # 添加工作流
            self.config.comfyui.add_workflow(
                name=name,
                json_content=normalized_json,
                prompt_node_id=detected_node_id,
                prompt_param_path=detected_param_path,
                description=f"从 {Path(file_path).name} 上传",
                image_node_id=image_node_id,
                image_param_path=image_param_path
            )

            from config.settings import save_config
            save_config()

            # 刷新下拉菜单
            self._refresh_workflow_menu()

            # 显示检测结果
            msg = f"工作流 '{name}' 已添加\n提示词节点: {detected_node_id} ({detected_param_path})"
            if image_node_id:
                msg += f"\n图片节点: {image_node_id} ({image_param_path})"
            self._show_message(msg, "info")

        except Exception as e:
            self._show_message(f"上传失败: {e}", "error")

    def _delete_workflow(self):
        """删除当前工作流"""
        selected = self.config_workflow_var.get()
        if not selected:
            return

        from CTkMessagebox import CTkMessagebox
        result = CTkMessagebox(
            title="确认删除",
            message=f"确定要删除工作流 '{selected}' 吗？",
            icon="warning",
            option_1="取消",
            option_2="删除"
        )

        if result.get() == "删除":
            if self.config.comfyui.remove_workflow(selected):
                # 保存配置到文件
                from config.settings import save_config
                save_config()
                self._refresh_workflow_menu()
                # 同时刷新图生图页面的工作流菜单
                if hasattr(self, 'gen_workflow_menu'):
                    self._refresh_comfy_workflow_menu()
                self._show_message(f"工作流 '{selected}' 已删除", "info")
            else:
                self._show_message(f"工作流 '{selected}' 不存在", "warning")

    def _refresh_workflow_menu(self):
        """刷新配置页面的工作流下拉菜单"""
        workflows = self.config.comfyui.list_workflows()

        if not workflows:
            # 先设置变量值，再更新下拉菜单选项
            self.config_workflow_var.set("")
            self.config_workflow_menu.configure(values=["暂无工作流"])
            self.config_workflow_menu.set("暂无工作流")
            self.delete_workflow_btn.configure(state="disabled")
        else:
            # 先确定要显示的值
            current = self.config.comfyui.current_workflow
            if current and current in workflows:
                new_value = current
            else:
                new_value = workflows[0]
                self.config.comfyui.current_workflow = new_value

            # 先设置变量值，再更新下拉菜单选项，最后强制设置显示值
            self.config_workflow_var.set(new_value)
            self.config_workflow_menu.configure(values=workflows)
            self.config_workflow_menu.set(new_value)
            self.delete_workflow_btn.configure(state="normal")

    def _on_workflow_change(self, event=None):
        """配置页面工作流切换事件"""
        selected = self.config_workflow_var.get()
        if selected and selected in self.config.comfyui.workflows:
            self.config.comfyui.current_workflow = selected
            self.delete_workflow_btn.configure(state="normal")
        else:
            self.delete_workflow_btn.configure(state="disabled")

    def _check_for_update(self):
        """检查软件更新"""
        self.check_update_btn.configure(state="disabled", text="检查中...")
        self.update_status_label.configure(text="正在检查更新...", text_color=Theme.COLOR_TEXT_GRAY)

        def check():
            try:
                if not AutoUpdater or not REMOTE_VERSION_URL:
                    self.after(0, lambda: self._update_check_result(False, None, "更新功能未启用"))
                    return

                updater = AutoUpdater(
                    app_dir=str(get_runtime_app_dir()),
                    remote_version_url=REMOTE_VERSION_URL
                )
                has_update, remote_info = updater.check_for_update()

                if has_update and remote_info:
                    self.after(0, lambda: self._update_check_result(True, remote_info, None, updater))
                elif remote_info:
                    self.after(0, lambda: self._update_check_result(False, remote_info, "已是最新版本"))
                else:
                    self.after(0, lambda: self._update_check_result(False, None, "检查失败，请检查网络"))
            except Exception as e:
                self.after(0, lambda: self._update_check_result(False, None, f"检查失败: {e}"))

        threading.Thread(target=check, daemon=True).start()

    def _update_check_result(self, has_update, remote_info, message, updater=None):
        """更新检查结果回调"""
        self.check_update_btn.configure(state="normal", text="🔍 检查更新")

        if has_update and remote_info:
            new_version = remote_info.get("version", "未知")
            self.update_status_label.configure(
                text=f"发现新版本 v{new_version}！",
                text_color=Theme.COLOR_SUCCESS
            )
            # 调用主窗口的更新对话框
            main_app = self.winfo_toplevel()
            if hasattr(main_app, '_show_update_dialog'):
                main_app._show_update_dialog(updater, remote_info)
        else:
            color = Theme.COLOR_SUCCESS if "最新" in (message or "") else Theme.COLOR_WARNING
            self.update_status_label.configure(text=message or "", text_color=color)

    def _show_message(self, msg: str, msg_type: str = "info"):
        """显示消息"""
        title_map = {"info": "提示", "warning": "注意", "error": "错误"}
        show_message_with_copy(self, title_map.get(msg_type, "提示"), msg, msg_type)

    def _toggle_debug_mode(self):
        """切换调试模式"""
        if LOGGER_AVAILABLE:
            enabled = self.debug_mode_var.get()
            set_debug_mode(enabled)
            log_info(f"调试模式已{'开启' if enabled else '关闭'}")
            self._show_message(f"调试模式已{'开启' if enabled else '关闭'}", "info")

    def _view_logs(self):
        """查看日志内容"""
        if not LOGGER_AVAILABLE:
            self._show_message("日志模块未加载", "warning")
            return

        # 贴建日志查看窗口
        log_window = ctk.CTkToplevel(self)
        log_window.title("调试日志")
        log_window.geometry("800x600")
        log_window.transient(self.winfo_toplevel())

        # 日志内容显示
        log_text = ctk.CTkTextbox(log_window, font=Theme.LOG_FONT)
        log_text.pack(fill="both", expand=True, padx=10, pady=10)

        # 加载日志内容
        logs = get_recent_logs(500)
        log_text.insert("1.0", logs)
        log_text.configure(state="disabled")

        # 刷新按钮
        btn_frame = ctk.CTkFrame(log_window)
        btn_frame.pack(fill="x", padx=10, pady=5)

        def refresh_logs():
            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            log_text.insert("1.0", get_recent_logs(500))
            log_text.configure(state="disabled")
            log_text.see("end")

        ctk.CTkButton(btn_frame, text="🔄 刷新", command=refresh_logs,
                     font=Theme.SMALL_FONT).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="📁 打开文件夹", command=self._open_log_folder,
                     font=Theme.SMALL_FONT).pack(side="left", padx=5)

        def copy_logs():
            content = log_text.get("1.0", "end-1c")
            log_window.clipboard_clear()
            log_window.clipboard_append(content)
            self._show_message("日志已复制到剪贴板", "info")

        ctk.CTkButton(btn_frame, text="📋 复制全部", command=copy_logs,
                     font=Theme.SMALL_FONT).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="关闭", command=log_window.destroy,
                     font=Theme.SMALL_FONT).pack(side="right", padx=5)

        # 滚动到底部
        log_text.see("end")

    def _open_log_folder(self):
        """打开日志文件夹"""
        if LOGGER_AVAILABLE:
            open_log_folder()
        else:
            self._show_message("日志模块未加载", "warning")


class ScrapeFrame(ctk.CTkFrame):
    """抓取页面"""
    
    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.images = []
        self.current_product = None
        self._setup_ui()
        
    def _setup_ui(self):
        # 标题
        title = ctk.CTkLabel(self, text="🔗 1688 商品抓取", font=Theme.HEADER_FONT)
        title.pack(pady=Theme.PAD_L)
        
        # 模式选择
        mode_frame = ctk.CTkFrame(self)
        mode_frame.pack(fill="x", padx=Theme.PAD_L, pady=Theme.PAD_S)
        
        ctk.CTkLabel(mode_frame, text="抓取模式:", font=Theme.TITLE_FONT).pack(side="left", padx=Theme.PAD_M)
        
        self.mode_var = ctk.StringVar(value="auto")
        ctk.CTkRadioButton(mode_frame, text="🤖 自动抓取", 
                          variable=self.mode_var, value="auto", font=Theme.BODY_FONT,
                          command=self._on_mode_change).pack(side="left", padx=Theme.PAD_M)
        ctk.CTkRadioButton(mode_frame, text="📝 手动模式 (粘贴HTML)", 
                          variable=self.mode_var, value="manual", font=Theme.BODY_FONT,
                          command=self._on_mode_change).pack(side="left", padx=Theme.PAD_M)
        
        # === 自动模式面板 ===
        self.auto_frame = ctk.CTkFrame(self)
        self.auto_frame.pack(fill="x", padx=Theme.PAD_L, pady=Theme.PAD_S)
        
        # 抓取方式选择行
        method_row = ctk.CTkFrame(self.auto_frame)
        method_row.pack(fill="x", pady=Theme.PAD_S)
        
        ctk.CTkLabel(method_row, text="抓取方式:", font=Theme.BODY_FONT).pack(side="left", padx=Theme.PAD_M)
        
        self.scrape_method_var = ctk.StringVar(value="Selenium 浏览器 (默认)")
        self.scrape_method_dropdown = ctk.CTkOptionMenu(
            method_row, 
            variable=self.scrape_method_var,
            values=["Selenium 浏览器 (默认)"],
            width=200,
            font=Theme.BODY_FONT,
            command=self._on_method_change
        )
        self.scrape_method_dropdown.pack(side="left", padx=Theme.PAD_S)
        
        self.method_hint = ctk.CTkLabel(method_row, text="本地浏览器抓取，可处理验证码", 
                                       text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        self.method_hint.pack(side="left", padx=Theme.PAD_L)
        
        # URL输入行
        url_row = ctk.CTkFrame(self.auto_frame)
        url_row.pack(fill="x", pady=Theme.PAD_S)
        
        ctk.CTkLabel(url_row, text="商品链接:", font=Theme.BODY_FONT).pack(side="left", padx=Theme.PAD_M)
        
        self.url_entry = ctk.CTkEntry(url_row, width=400, height=Theme.ENTRY_HEIGHT,
                                      placeholder_text="https://detail.1688.com/...", font=Theme.BODY_FONT,
                                      fg_color=Theme.COLOR_INPUT_BG)
        self.url_entry.pack(side="left", padx=Theme.PAD_S)
        
        self.scrape_btn = ctk.CTkButton(url_row, text="开始抓取", font=Theme.SUBHEADER_FONT,
                                       height=Theme.BTN_HEIGHT,
                                       command=self._start_scrape)
        self.scrape_btn.pack(side="left", padx=Theme.PAD_S)
        
        # 登录按钮
        self.login_btn = ctk.CTkButton(url_row, text="🔑 登录1688", font=Theme.BODY_FONT,
                                       height=Theme.BTN_HEIGHT, width=100,
                                       command=self._login_1688,
                                       fg_color=Theme.COLOR_WARNING)
        self.login_btn.pack(side="left", padx=Theme.PAD_S)
        
        # 登录状态提示
        self.login_status_label = ctk.CTkLabel(url_row, text="", 
                                               text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        self.login_status_label.pack(side="left", padx=Theme.PAD_S)
        
        # 检查是否有已保存的 Cookies
        self._check_saved_cookies()
        
        # === 手动模式面板 ===
        self.manual_frame = ctk.CTkFrame(self)
        # 默认隐藏
        
        manual_hint = ctk.CTkLabel(self.manual_frame, 
            text="💡 使用方法: 在浏览器打开1688商品页→右键→查看页面源代码→全选复制→粘贴到下方",
            text_color=Theme.COLOR_TEXT_GRAY, font=Theme.SMALL_FONT)
        manual_hint.pack(pady=Theme.PAD_S)
        
        html_btn_frame = ctk.CTkFrame(self.manual_frame)
        html_btn_frame.pack(fill="x", pady=Theme.PAD_S)
        
        ctk.CTkButton(html_btn_frame, text="📋 从剪贴板粘贴", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                     command=self._paste_html).pack(side="left", padx=Theme.PAD_S)
        ctk.CTkButton(html_btn_frame, text="📂 选择HTML文件", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                     command=self._load_html_file).pack(side="left", padx=Theme.PAD_S)
        ctk.CTkButton(html_btn_frame, text="🔍 解析HTML", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                     command=self._parse_html,
                     fg_color=Theme.COLOR_SUCCESS).pack(side="left", padx=Theme.PAD_S)
        ctk.CTkButton(html_btn_frame, text="🗑️ 清空", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                     command=self._clear_html,
                     fg_color="gray").pack(side="left", padx=Theme.PAD_S)
        
        self.html_input = ctk.CTkTextbox(self.manual_frame, height=120, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.html_input.pack(fill="x", expand=False, pady=Theme.PAD_S)
        self.html_input.insert("1.0", "在此粘贴1688商品页面的HTML源代码...")
        
        # 进度和控制区域
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=Theme.PAD_L, pady=Theme.PAD_S)
        
        self.progress = ctk.CTkLabel(progress_frame, text="就绪", text_color="gray", font=Theme.BODY_FONT)
        self.progress.pack(side="left", padx=Theme.PAD_M)
        
        # 停止按钮
        self.stop_btn = ctk.CTkButton(progress_frame, text="⏹️ 停止", width=80, height=Theme.BTN_HEIGHT,
                                      command=self._stop_scrape, fg_color=Theme.COLOR_DANGER, font=Theme.BODY_FONT,
                                      state="disabled")
        self.stop_btn.pack(side="right", padx=Theme.PAD_S)
        
        # 打开文件夹按钮
        self.open_folder_btn = ctk.CTkButton(progress_frame, text="📁 打开输出文件夹", width=120, height=Theme.BTN_HEIGHT,
                                             command=self._open_output_folder, fg_color="gray", font=Theme.BODY_FONT)
        self.open_folder_btn.pack(side="right", padx=Theme.PAD_S)
        
        # 日志区域 (放在底部，横条显示)
        self.log_frame = ctk.CTkFrame(self, height=40)
        self.log_frame.pack(side="bottom", fill="x", padx=Theme.PAD_L, pady=(0, Theme.PAD_M))
        
        self.log_area = ctk.CTkTextbox(self.log_frame, height=40, state="disabled", font=Theme.LOG_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.log_area.pack(fill="both", expand=True, padx=2, pady=2)

        # 内容区域 - 三列布局
        content = ctk.CTkFrame(self)
        content.pack(side="top", fill="both", expand=True, padx=Theme.PAD_L, pady=Theme.PAD_M)

        # 配置 Grid 权重 - 三列：缩略图列表(1) | 预览区(2) | 文案(1)
        content.grid_columnconfigure(0, weight=1, minsize=180)
        content.grid_columnconfigure(1, weight=2, minsize=350)
        content.grid_columnconfigure(2, weight=1, minsize=250)
        content.grid_rowconfigure(0, weight=1)

        # 左侧: 图片缩略图列表
        left = ctk.CTkFrame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=Theme.PAD_S)

        ctk.CTkLabel(left, text="📸 抓取的图片", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        self.image_list = ctk.CTkScrollableFrame(left, height=250)
        self.image_list.pack(fill="both", expand=True)

        # 中间: 图片预览区
        middle = ctk.CTkFrame(content)
        middle.grid(row=0, column=1, sticky="nsew", padx=Theme.PAD_S)

        ctk.CTkLabel(middle, text="🔍 图片预览", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        # 预览区域容器
        self.preview_container = ctk.CTkFrame(middle, fg_color=Theme.COLOR_INPUT_BG)
        self.preview_container.pack(fill="both", expand=True, padx=5, pady=5)

        # 预览图片标签
        self.preview_label = ctk.CTkLabel(
            self.preview_container,
            text="点击左侧图片预览\n\n支持:\n• 点击切换\n• 滚轮切换\n• 键盘↑↓切换",
            font=Theme.BODY_FONT,
            text_color=Theme.COLOR_TEXT_GRAY
        )
        self.preview_label.pack(expand=True)

        # 预览图片信息
        self.preview_info = ctk.CTkLabel(middle, text="", font=Theme.SMALL_FONT, text_color=Theme.COLOR_TEXT_GRAY)
        self.preview_info.pack(pady=2)

        # 绑定预览区域的滚轮和键盘事件
        self.preview_container.bind("<MouseWheel>", self._on_preview_scroll)
        self.preview_container.bind("<Button-4>", self._on_preview_scroll)  # Linux
        self.preview_container.bind("<Button-5>", self._on_preview_scroll)  # Linux
        self.preview_label.bind("<MouseWheel>", self._on_preview_scroll)

        # 右侧: 文案
        right = ctk.CTkFrame(content)
        right.grid(row=0, column=2, sticky="nsew", padx=Theme.PAD_S)

        text_header = ctk.CTkFrame(right, fg_color="transparent")
        text_header.pack(fill="x", pady=Theme.PAD_S)

        ctk.CTkLabel(text_header, text="📝 产品文案", font=Theme.TITLE_FONT).pack(side="left")

        ctk.CTkButton(text_header, text="📋 复制", width=60, height=24,
                     command=self._copy_text, font=Theme.SMALL_FONT).pack(side="right")

        self.text_area = ctk.CTkTextbox(right, height=250, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.text_area.pack(fill="both", expand=True)

        # 日志区域已移动到底部

        # 任务控制变量
        self.is_running = False
        self.should_stop = False
        self.current_thread = None
        self.downloaded_files = []  # 记录下载的文件

        # 预览相关变量
        self.preview_images = []  # 所有图片路径列表
        self.current_preview_index = -1  # 当前预览的图片索引
        self.preview_photo = None  # 保持引用防止被垃圾回收

        # 绑定键盘事件到预览容器（需要先设置焦点）
        self.preview_container.bind("<Up>", self._on_preview_key_up)
        self.preview_container.bind("<Down>", self._on_preview_key_down)
        self.preview_container.bind("<Button-1>", lambda e: self.preview_container.focus_set())
        
    def _copy_text(self):
        """复制抓取的文案"""
        text = self.text_area.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._log("文案已复制到剪贴板", "success")
        else:
            self._log("没有可复制的文案", "warning")
    
    def _log(self, message: str, level: str = "info"):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 根据级别设置前缀
        prefix_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "step": "▶️",
        }
        prefix = prefix_map.get(level, "•")

        log_text = f"[{timestamp}] {prefix} {message}\n"

        # 更新日志区域
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end") # 保持只显示最后几行
        self.log_area.insert("end", log_text)
        self.log_area.configure(state="disabled")

        # 同步写入文件日志
        try:
            from utils.logger import log_info, log_warning, log_error, log_debug
            file_msg = f"[抓取] {message}"
            if level == "error":
                log_error(file_msg)
            elif level == "warning":
                log_warning(file_msg)
            elif level == "step":
                log_debug(file_msg)
            else:
                log_info(file_msg)
        except Exception:
            pass
        
        # 同时更新进度标签
        self.progress.configure(text=message)
    
    def _clear_log(self):
        """清空日志"""
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

    def _toggle_log_view(self):
        """展开/收起底部日志区域"""
        if self.log_expanded:
            # 收起
            self.log_area.configure(height=40)
            self.log_expand_btn.configure(text="🔼")
            self.log_expanded = False
        else:
            # 展开
            self.log_area.configure(height=160)
            self.log_expand_btn.configure(text="🔽")
            self.log_expanded = True
    
    def _check_saved_cookies(self):
        """检查是否有已保存的登录 Cookies"""
        import os
        cookie_file = "./config/1688_cookies.json"
        if os.path.exists(cookie_file):
            try:
                import json
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                saved_at = data.get("saved_at", "")
                self.login_status_label.configure(
                    text=f"✅ 已登录 ({saved_at})",
                    text_color=Theme.COLOR_SUCCESS
                )
                self.login_btn.configure(text="🔄 重新登录", fg_color="gray")
            except:
                self.login_status_label.configure(
                    text="⚠️ 未登录",
                    text_color=Theme.COLOR_WARNING
                )
        else:
            self.login_status_label.configure(
                text="⚠️ 未登录",
                text_color=Theme.COLOR_WARNING
            )
    
    def _login_1688(self):
        """手动败发 1688 登录"""
        self._log("正在启动登录流程...", "step")
        self.login_btn.configure(state="disabled")
        
        def do_login():
            scraper = None
            try:
                from scraper import AlibabaScraper
                
                self.after(0, lambda: self._log("正在启动浏览器...", "step"))
                
                # 贴建 scraper 并初始化驱动
                scraper = AlibabaScraper(headless=False, timeout=120)
                scraper._init_driver()
                
                self.after(0, lambda: self._log("✓ 浏览器已启动", "success"))
                self.after(0, lambda: self._log("正在打开登录页面...", "step"))
                
                # 直接调用登录方法
                try:
                    success = scraper._do_login()
                except Exception as login_error:
                    self.after(0, lambda: self._log(f"登录过程出错: {login_error}", "error"))
                    success = False
                
                if success:
                    self.after(0, lambda: self._log("✅ 登录成功！Cookies 已保存", "success"))
                    self.after(0, self._check_saved_cookies)
                    # 登录成功后等待3秒再关闭
                    import time
                    time.sleep(3)
                    try:
                        scraper._close_driver()
                    except:
                        pass
                else:
                    self.after(0, lambda: self._log("⚠️ 登录未完成", "warning"))
                    self.after(0, lambda: self._log("浏览器保持打开，请手动完成登录", "info"))
                    self.after(0, lambda: self._log("完成后请手动关闭浏览器", "info"))
                    # 不关闭浏览器

            except Exception as e:
                import traceback
                error_msg = str(e)
                print(f"登录异常: {error_msg}")
                traceback.print_exc()

                # 检查是否是 Chrome 未安装的错误
                if "chrome" in error_msg.lower() or "无法启动" in error_msg:
                    self.after(0, lambda: self._log("❌ Chrome 浏览器未安装或无法启动", "error"))
                    self.after(0, lambda: self._log("请先安装 Google Chrome 浏览器:", "warning"))
                    self.after(0, lambda: self._log("  下载地址: https://www.google.com/chrome/", "info"))
                    self.after(0, lambda: self._log("  安装完成后重新点击登录按钮", "info"))
                else:
                    self.after(0, lambda: self._log(f"出错: {error_msg}", "error"))
                    self.after(0, lambda: self._log("浏览器保持打开，请手动操作", "info"))
                # 异常时也不关闭浏览器
            finally:
                self.after(0, lambda: self.login_btn.configure(state="normal"))
        
        # 使用非 daemon 线程，确保不会被意外终止
        login_thread = threading.Thread(target=do_login, daemon=False)
        login_thread.start()
    
    def _open_output_folder(self):
        """打开输出文件夹"""
        import os
        import sys
        output_dir = os.path.abspath("./output")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            os.system(f'open "{output_dir}"')
        else:
            os.system(f'xdg-open "{output_dir}"')
        
        self._log(f"已打开: {output_dir}", "info")
    
    def _stop_scrape(self):
        """停止抓取"""
        if not self.is_running:
            return
        
        self.should_stop = True
        self._log("正在停止任务...", "warning")
        self.stop_btn.configure(state="disabled")
        
        # 等待任务停止后询问是否删除文件
        def check_and_ask():
            import time
            for _ in range(30):  # 最多等待3秒
                if not self.is_running:
                    break
                time.sleep(0.1)
            
            self.after(0, self._ask_delete_files)
        
        threading.Thread(target=check_and_ask, daemon=True).start()
    
    def _ask_delete_files(self):
        """询问是否删除已下载的文件"""
        import os
        
        if not self.downloaded_files:
            self._log("任务已停止，没有需要清理的文件", "info")
            return
        
        # 使用消息框询问
        if CTkMessagebox:
            result = CTkMessagebox(
                title="停止任务",
                message=f"任务已停止。\n\n已下载 {len(self.downloaded_files)} 个文件。\n是否删除这些文件？",
                icon="question",
                option_1="保留文件",
                option_2="删除文件",
                option_3="打开文件夹"
            )
            choice = result.get()
            
            if choice == "删除文件":
                deleted = 0
                for f in self.downloaded_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                            deleted += 1
                    except:
                        pass
                self._log(f"已删除 {deleted} 个文件", "success")
                self.downloaded_files.clear()
            elif choice == "打开文件夹":
                self._open_output_folder()
                self._log(f"已保留 {len(self.downloaded_files)} 个文件", "info")
            else:
                self._log(f"已保留 {len(self.downloaded_files)} 个文件", "info")
        else:
            # 没有CTkMessagebox，直接保留
            self._log(f"任务已停止，保留了 {len(self.downloaded_files)} 个文件", "info")
            self._log(f"文件位置: ./output/", "info")
    
    def _set_running(self, running: bool):
        """设置运行状态"""
        self.is_running = running
        if running:
            self.should_stop = False
            self.scrape_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.downloaded_files.clear()
        else:
            self.scrape_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
    
    def _on_mode_change(self):
        """切换模式"""
        mode = self.mode_var.get()
        if mode == "auto":
            self.manual_frame.pack_forget()
            self.auto_frame.pack(fill="x", padx=20, pady=5, after=self.winfo_children()[1])
        else:
            self.auto_frame.pack_forget()
            self.manual_frame.pack(fill="x", padx=20, pady=5, after=self.winfo_children()[1])
    
    def _on_method_change(self, value):
        """切换抓取方式"""
        if "Selenium" in value:
            self.method_hint.configure(text="本地浏览器抓取，可处理验证码")
        elif "SerpApi" in value:
            self.method_hint.configure(text="API抓取，更稳定")
        elif "RapidAPI" in value:
            self.method_hint.configure(text="⚠️ 需要先配置API Key")
    
    def _paste_html(self):
        """从剪贴板粘贴HTML"""
        try:
            html = self.clipboard_get()
            if html:
                self.html_input.delete("1.0", "end")
                self.html_input.insert("1.0", html)
                self.progress.configure(text=f"已粘贴 {len(html)} 字符", text_color="gray")
        except:
            self.progress.configure(text="剪贴板为空或无法读取", text_color="red")
    
    def _load_html_file(self):
        """从文件加载HTML"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("HTML文件", "*.html;*.htm"), ("所有文件", "*.*")]
        )
        if path:
            try:
                for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                    try:
                        with open(path, 'r', encoding=encoding) as f:
                            content = f.read()
                        self.html_input.delete("1.0", "end")
                        self.html_input.insert("1.0", content)
                        self.progress.configure(text=f"已加载文件: {Path(path).name}", text_color="gray")
                        break
                    except UnicodeDecodeError:
                        continue
            except Exception as e:
                self.progress.configure(text=f"读取文件失败: {e}", text_color="red")
    
    def _clear_html(self):
        """清空HTML输入"""
        self.html_input.delete("1.0", "end")
        self.progress.configure(text="已清空", text_color="gray")
    
    def _parse_html(self):
        """解析HTML"""
        html_content = self.html_input.get("1.0", "end").strip()
        
        if not html_content or len(html_content) < 500:
            self.progress.configure(text="HTML内容太短，请确保复制了完整的页面源代码", text_color="red")
            return
        
        self.progress.configure(text="正在解析HTML...", text_color="gray")
        
        def do_parse():
            try:
                from scraper.html_parser import HTMLParser
                
                parser = HTMLParser()
                product = parser.parse_from_html(html_content)
                self.current_product = product
                
                # 合并主图和详情图
                all_images = product.main_images + product.detail_images
                
                if all_images:
                    self.after(0, lambda: self.progress.configure(
                        text=f"找到 {len(product.main_images)} 张主图, {len(product.detail_images)} 张详情图，正在下载..."))
                    
                    from scraper import ImageDownloader
                    downloader = ImageDownloader("./output/images")
                    downloader.clear_output_dir()  # 清空旧图片，避免缓存问题
                    
                    # 下载主图
                    main_results = downloader.download_main_images(product.main_images)
                    
                    # 下载详情图
                    detail_results = []
                    if product.detail_images:
                        detail_results = downloader.download_detail_images(product.detail_images)
                    
                    all_results = main_results + detail_results
                    
                    # 保存文案
                    from scraper import TextExtractor
                    extractor = TextExtractor("./output")
                    extractor.from_product_data(parser.get_product_text())
                    extractor.save_all()
                    
                    # 更新UI
                    self.after(0, lambda: self._update_results(
                        [r[1] for r in all_results],
                        extractor.copywriting.combined_copywriting
                    ))
                    self.after(0, lambda: self.progress.configure(
                        text=f"下载完成: 主图 {len(main_results)} 张, 详情图 {len(detail_results)} 张"))
                else:
                    # 没有图片，只显示文案
                    text_info = f"标题: {product.title}\n\n价格: {product.price_range}\n\n店铺: {product.shop_name}"
                    self.after(0, lambda: self._update_results([], text_info))
                    self.after(0, lambda: self.progress.configure(
                        text="⚠️ 未找到图片，可能HTML不完整或页面结构已更新", text_color="orange"))
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.progress.configure(text=f"解析失败: {e}", text_color="red"))
        
        threading.Thread(target=do_parse, daemon=True).start()
        
    def _start_scrape(self):
        """开始抓取"""
        url = self.url_entry.get().strip()
        if not url:
            self._log("请输入商品链接", "warning")
            return
        
        # 清空日志
        self._clear_log()
        
        # 获取选择的抓取方式
        method = self.scrape_method_dropdown.get()
        
        self._log(f"开始抓取: {url[:50]}...", "step")
        self._log(f"抓取方式: {method}", "info")
        
        self._set_running(True)
        
        # 使用忽略大小写的匹配
        method_lower = method.lower()
        if "selenium" in method_lower:
            self._scrape_with_selenium(url)
        elif "serpapi" in method_lower:
            self._scrape_with_serpapi(url)
        elif "rapidapi" in method_lower:
            self._scrape_with_rapidapi(url)
        else:
            # 默认使用 Selenium
            self._log("未识别的抓取方式，使用默认 Selenium", "warning")
            self._scrape_with_selenium(url)
    
    def _scrape_with_selenium(self, url: str):
        """使用Selenium抓取"""
        
        def do_scrape():
            try:
                from scraper import AlibabaScraper, ImageDownloader, TextExtractor
                
                # 检查是否被停止
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log("正在启动浏览器...", "step"))
                scraper = AlibabaScraper(headless=False, timeout=60)
                
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log("浏览器已启动，正在访问页面...", "step"))
                self.after(0, lambda: self._log("如有验证码请在浏览器中手动完成", "info"))
                
                product = scraper.scrape_product(url)
                self.current_product = product
                
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log(f"获取到标题: {product.title[:30] if product.title else '无'}...", "success"))
                self.after(0, lambda: self._log(f"发现 {len(product.main_images)} 张主图, {len(product.detail_images)} 张详情图", "info"))
                
                # 合并主图和详情图
                all_images = product.main_images + product.detail_images
                
                if all_images:
                    self.after(0, lambda: self._log(f"正在清空旧图片并下载 {len(all_images)} 张图片...", "step"))
                    
                    downloader = ImageDownloader("./output/images")
                    downloader.clear_output_dir()  # 清空旧图片，避免缓存问题
                    
                    # 下载主图
                    main_results = downloader.download_main_images(product.main_images)
                    
                    # 下载详情图
                    detail_results = []
                    if product.detail_images:
                        detail_results = downloader.download_detail_images(product.detail_images)
                    
                    all_results = main_results + detail_results
                    
                    # 记录下载的文件
                    for _, path in all_results:
                        self.downloaded_files.append(path)
                    
                    if self.should_stop:
                        self.after(0, lambda: self._log("任务已取消", "warning"))
                        return
                    
                    self.after(0, lambda: self._log(f"下载完成: 主图 {len(main_results)} 张, 详情图 {len(detail_results)} 张", "success"))
                    
                    extractor = TextExtractor("./output")
                    extractor.from_product_data(scraper.get_product_text())
                    extractor.save_all()
                    
                    self.after(0, lambda: self._log("文案已保存", "success"))
                    self.after(0, lambda: self._log("抓取完成！", "success"))
                    
                    self.after(0, lambda: self._update_results(
                        [r[1] for r in all_results],
                        extractor.copywriting.combined_copywriting
                    ))
                else:
                    self.after(0, lambda: self._log("未找到图片", "warning"))
                    text_info = f"标题: {product.title}\n\n价格: {product.price_range}"
                    self.after(0, lambda: self._update_results([], text_info))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self._log(f"抓取失败: {e}", "error"))
            finally:
                self.after(0, lambda: self._set_running(False))
                
        threading.Thread(target=do_scrape, daemon=True).start()
    
    def _scrape_with_serpapi(self, url: str):
        """使用SerpApi抓取"""
        
        def do_scrape():
            try:
                from scraper import SerpApiScraper, ImageDownloader, TextExtractor
                
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log("正在通过SerpApi抓取...", "step"))
                
                scraper = SerpApiScraper()
                product = scraper.scrape_product(url)
                self.current_product = product
                
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log(f"获取到标题: {product.title[:30] if product.title else '无'}...", "success" if product.title else "warning"))
                
                if product.main_images:
                    self.after(0, lambda: self._log(f"发现 {len(product.main_images)} 张图片，正在清空旧图并下载...", "step"))
                    
                    downloader = ImageDownloader("./output/images")
                    downloader.clear_output_dir()  # 清空旧图片，避免缓存问题
                    main_results = downloader.download_main_images(product.main_images)
                    
                    for _, path in main_results:
                        self.downloaded_files.append(path)
                    
                    extractor = TextExtractor("./output")
                    extractor.from_product_data(scraper.get_product_text())
                    extractor.save_all()
                    
                    self.after(0, lambda: self._log(f"下载完成: {len(main_results)} 张图片", "success"))
                    self.after(0, lambda: self._log("抓取完成！", "success"))
                    
                    self.after(0, lambda: self._update_results(
                        [r[1] for r in main_results],
                        extractor.copywriting.combined_copywriting
                    ))
                elif product.title:
                    # 有标题但无图片
                    self.after(0, lambda: self._log("获取到文案但无图片，建议使用Selenium模式获取完整内容", "warning"))
                    text_info = f"标题: {product.title}\n\n描述: {product.description}"
                    self.after(0, lambda: self._update_results([], text_info))
                else:
                    # 什么都没获取到
                    self.after(0, lambda: self._log("SerpApi无法获取页面内容", "error"))
                    self.after(0, lambda: self._log("目标网站有反爬保护，请使用Selenium浏览器模式", "info"))
                    self.after(0, lambda: self._update_results([], "抓取失败：目标网站有反爬保护，请使用Selenium浏览器模式"))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self._log(f"抓取失败: {e}", "error"))
            finally:
                self.after(0, lambda: self._set_running(False))
                
        threading.Thread(target=do_scrape, daemon=True).start()
    
    def _scrape_with_rapidapi(self, url: str):
        """使用RapidAPI抓取"""
        
        def do_scrape():
            try:
                from scraper import RapidApiScraper, ImageDownloader, TextExtractor
                
                self.after(0, lambda: self._log("检查RapidAPI配置...", "step"))
                
                scraper = RapidApiScraper()
                if not scraper.is_configured():
                    self.after(0, lambda: self._log("RapidAPI未配置", "error"))
                    self.after(0, lambda: self._log("请编辑 scraper/rapid_scraper.py 配置API", "info"))
                    return
                
                if self.should_stop:
                    self.after(0, lambda: self._log("任务已取消", "warning"))
                    return
                
                self.after(0, lambda: self._log("正在通过RapidAPI抓取...", "step"))
                
                product = scraper.scrape_product(url)
                self.current_product = product
                
                self.after(0, lambda: self._log(f"获取到标题: {product.title[:30] if product.title else '无'}...", "success"))
                
                if product.main_images:
                    self.after(0, lambda: self._log(f"发现 {len(product.main_images)} 张图片，正在清空旧图并下载...", "step"))
                    
                    downloader = ImageDownloader("./output/images")
                    downloader.clear_output_dir()  # 清空旧图片，避免缓存问题
                    main_results = downloader.download_main_images(product.main_images)
                    
                    for _, path in main_results:
                        self.downloaded_files.append(path)
                    
                    extractor = TextExtractor("./output")
                    extractor.from_product_data(scraper.get_product_text())
                    extractor.save_all()
                    
                    self.after(0, lambda: self._log(f"下载完成: {len(main_results)} 张图片", "success"))
                    self.after(0, lambda: self._log("抓取完成！", "success"))
                    
                    self.after(0, lambda: self._update_results(
                        [r[1] for r in main_results],
                        extractor.copywriting.combined_copywriting
                    ))
                else:
                    self.after(0, lambda: self._log("未找到图片", "warning"))
                    text_info = f"标题: {product.title}\n\n描述: {product.description}"
                    self.after(0, lambda: self._update_results([], text_info))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self._log(f"抓取失败: {e}", "error"))
            finally:
                self.after(0, lambda: self._set_running(False))
                
        threading.Thread(target=do_scrape, daemon=True).start()
        
    def _update_results(self, image_paths: List[str], text: str):
        """更新抓取结果"""
        self.progress.configure(text=f"✓ 抓取完成，共 {len(image_paths)} 张图片")

        # 保存图片路径列表用于预览
        self.preview_images = image_paths.copy()
        self.current_preview_index = -1

        # 清空并更新图片列表
        for widget in self.image_list.winfo_children():
            widget.destroy()

        for idx, path in enumerate(image_paths):
            self._add_image_item(path, idx)

        # 自动预览第一张图片
        if image_paths:
            self._show_preview(0)

        # 更新文案
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)

    def _add_image_item(self, path: str, index: int = 0):
        """添加图片项"""
        frame = ctk.CTkFrame(self.image_list, cursor="hand2")
        frame.pack(fill="x", pady=2)

        # 绑定点击事件
        frame.bind("<Button-1>", lambda e, idx=index: self._show_preview(idx))

        # 尝试显示缩略图
        try:
            img = Image.open(path)
            img.thumbnail((60, 60))
            photo = ctk.CTkImage(img, size=(60, 60))
            label = ctk.CTkLabel(frame, image=photo, text="", cursor="hand2")
            label.image = photo
            label.pack(side="left", padx=5)
            # 绑定点击事件到图片标签
            label.bind("<Button-1>", lambda e, idx=index: self._show_preview(idx))
        except:
            pass

        name_label = ctk.CTkLabel(frame, text=Path(path).name, cursor="hand2")
        name_label.pack(side="left", padx=5)
        # 绑定点击事件到文件名标签
        name_label.bind("<Button-1>", lambda e, idx=index: self._show_preview(idx))

    def _show_preview(self, index: int):
        """显示预览图片"""
        if not self.preview_images or index < 0 or index >= len(self.preview_images):
            return

        self.current_preview_index = index
        path = self.preview_images[index]

        try:
            img = Image.open(path)
            original_size = img.size

            # 获取预览区域大小
            self.preview_container.update_idletasks()
            container_width = self.preview_container.winfo_width() - 20
            container_height = self.preview_container.winfo_height() - 20

            # 确保最小尺寸
            container_width = max(container_width, 300)
            container_height = max(container_height, 300)

            # 计算缩放比例，保持宽高比
            ratio = min(container_width / img.width, container_height / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)

            # 缩放图片
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.preview_photo = ctk.CTkImage(img_resized, size=(new_width, new_height))

            # 更新预览标签
            self.preview_label.configure(image=self.preview_photo, text="")

            # 更新信息
            filename = Path(path).name
            self.preview_info.configure(
                text=f"{index + 1}/{len(self.preview_images)} | {filename} | {original_size[0]}x{original_size[1]}"
            )

            # 高亮当前选中的缩略图
            self._highlight_thumbnail(index)

            # 设置焦点到预览容器，使键盘事件生效
            self.preview_container.focus_set()

        except Exception as e:
            self.preview_label.configure(image=None, text=f"无法加载图片\n{str(e)}")
            self.preview_info.configure(text="")

    def _highlight_thumbnail(self, index: int):
        """高亮当前选中的缩略图"""
        for idx, widget in enumerate(self.image_list.winfo_children()):
            if idx == index:
                widget.configure(fg_color=Theme.COLOR_PRIMARY)
            else:
                widget.configure(fg_color="transparent")

    def _on_preview_scroll(self, event):
        """处理预览区域的滚轮事件"""
        if not self.preview_images:
            return

        # Windows: event.delta, Linux: event.num
        if hasattr(event, 'delta'):
            if event.delta > 0:
                self._preview_previous()
            else:
                self._preview_next()
        elif event.num == 4:
            self._preview_previous()
        elif event.num == 5:
            self._preview_next()

    def _on_preview_key_up(self, event):
        """处理键盘上键"""
        # 只在抓取页面激活时响应
        if hasattr(self, 'preview_images') and self.preview_images:
            self._preview_previous()

    def _on_preview_key_down(self, event):
        """处理键盘下键"""
        # 只在抓取页面激活时响应
        if hasattr(self, 'preview_images') and self.preview_images:
            self._preview_next()

    def _preview_previous(self):
        """预览上一张图片"""
        if self.current_preview_index > 0:
            self._show_preview(self.current_preview_index - 1)
        elif self.current_preview_index == 0 and self.preview_images:
            # 循环到最后一张
            self._show_preview(len(self.preview_images) - 1)

    def _preview_next(self):
        """预览下一张图片"""
        if self.current_preview_index < len(self.preview_images) - 1:
            self._show_preview(self.current_preview_index + 1)
        elif self.current_preview_index == len(self.preview_images) - 1:
            # 循环到第一张
            self._show_preview(0)


class GenerateFrame(ctk.CTkFrame):
    """图生图页面"""
    
    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.selected_image = None
        self.result_image_path = None
        self.last_result_image = None  # 上一轮生成的图片路径
        self.output_dir = "./output/generated"
        self.is_generating = False
        self.wash_image_path = None
        self._gen_id = 0  # 生成计数器，防止旧回调覆盖新状态
        self._setup_ui()
        
    def _setup_ui(self):
        title = ctk.CTkLabel(self, text="🎨 图生图", font=Theme.HEADER_FONT)
        title.pack(pady=Theme.PAD_L)
        
        # 日志区域 (放在底部，横条显示)
        # 日志区域 (放在底部，横条显示)
        self.log_frame = ctk.CTkFrame(self, height=40)
        self.log_frame.pack_propagate(False) # 禁止自动调整大小
        self.log_frame.pack(side="bottom", fill="x", padx=Theme.PAD_L, pady=(0, Theme.PAD_M))
        
        self.log_expand_btn = ctk.CTkButton(self.log_frame, text="🔼", width=30, height=30, 
                                           fg_color="transparent", text_color="gray", 
                                           command=self._toggle_log_view)
        self.log_expand_btn.pack(side="right", padx=5)
        
        self.log_area = ctk.CTkTextbox(self.log_frame, height=40, state="disabled", font=Theme.LOG_FONT)
        self.log_area.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        # 配置日志颜色标签 - 优化深色模式对比度
        self.log_area.tag_config("info", foreground="#89c4f4")    # 亮蓝色
        self.log_area.tag_config("success", foreground="#4caf50") # 亮绿色
        self.log_area.tag_config("warning", foreground="#ffb84d") # 亮橙色
        self.log_area.tag_config("error", foreground="#ff6b6b")   # 亮红色
        self.log_area.tag_config("step", foreground="#e0e0e0")    # 亮灰色
        self.log_expanded = False

        # === 顶部: 图片画廊 ===
        self.gallery_container = ctk.CTkFrame(self, fg_color="transparent")
        self.gallery_container.pack(fill="x", padx=Theme.PAD_L, pady=(0, Theme.PAD_M))
        
        ctk.CTkLabel(self.gallery_container, text="🖼️ 抓取图片库", font=Theme.TITLE_FONT).pack(anchor="w", pady=2)
        
        self.gallery_frame = ctk.CTkScrollableFrame(self.gallery_container, orientation="horizontal", height=220)
        self.gallery_frame.pack(fill="x", expand=True)
        
        # 绑定滚动和拖拽事件
        self.gallery_frame.bind("<MouseWheel>", self._on_gallery_scroll)
        self.gallery_frame._parent_canvas.bind("<MouseWheel>", self._on_gallery_scroll)
        
        # 拖拽相关变量
        self._drag_start_x = 0
        self.gallery_frame.bind("<ButtonPress-1>", self._on_drag_start)
        self.gallery_frame.bind("<B1-Motion>", self._on_drag_motion)
        self.gallery_frame._parent_canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.gallery_frame._parent_canvas.bind("<B1-Motion>", self._on_drag_motion)
        
        # 加载画廊
        self._load_gallery()

        # 主内容 - 两列布局
        content = ctk.CTkFrame(self)
        content.pack(side="top", fill="both", expand=True, padx=Theme.PAD_L, pady=Theme.PAD_M)

        # 配置 Grid 权重
        content.grid_columnconfigure(0, weight=1)  # 左侧（图片区）
        content.grid_columnconfigure(1, weight=1)  # 右侧（配置+日志区）
        content.grid_rowconfigure(0, weight=1)

        # === 左侧: 图片区（原图 + 结果图） ===
        left_panel = ctk.CTkFrame(content)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)

        # 左侧分为左右两部分 (Side-by-Side)
        left_panel.grid_columnconfigure(0, weight=1)  # 原图区域
        left_panel.grid_columnconfigure(1, weight=1)  # 结果图区域
        left_panel.grid_rowconfigure(0, weight=1)

        # === 原图区域 ===
        # === 原图区域 (左) ===
        source_frame = ctk.CTkFrame(left_panel)
        source_frame.grid(row=0, column=0, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)
        
        # 启用文件拖拽 (Only Windows)
        try:
            windnd.hook_dropfiles(source_frame, func=self._on_drop)
        except Exception as e:
            print(f"Drag and drop setup failed: {e}")

        ctk.CTkLabel(source_frame, text="📷 原图", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        select_btn = ctk.CTkButton(source_frame, text="选择图片文件", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                                  command=self._select_image)
        select_btn.pack(pady=Theme.PAD_S)

        self.image_preview = ctk.CTkLabel(source_frame, text="未选择图片", height=380, font=Theme.BODY_FONT)
        self.image_preview.pack(pady=Theme.PAD_S)

        self.image_path_label = ctk.CTkLabel(source_frame, text="", wraplength=280, text_color="gray", font=Theme.SMALL_FONT)
        self.image_path_label.pack()

        # 使用上一轮生成图
        self.use_last_var = ctk.BooleanVar(value=False)
        self.use_last_chk = ctk.CTkCheckBox(
            source_frame,
            text="使用上一轮生成图",
            variable=self.use_last_var,
            font=Theme.BODY_FONT,
            command=self._toggle_use_last,
        )
        self.use_last_chk.pack(pady=Theme.PAD_S)

        # === 结果图区域 (右) ===
        result_frame = ctk.CTkFrame(left_panel)
        result_frame.grid(row=0, column=1, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)

        ctk.CTkLabel(result_frame, text="✨ 生成结果", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        self.result_preview = ctk.CTkLabel(result_frame, text="等待生成...", width=480, height=480, font=Theme.BODY_FONT)
        self.result_preview.pack(pady=Theme.PAD_S, expand=True)

        self.result_path_label = ctk.CTkLabel(result_frame, text="", wraplength=280, text_color="gray", font=Theme.SMALL_FONT)
        self.result_path_label.pack()

        # 结果操作按钮行
        result_btn_row = ctk.CTkFrame(result_frame)
        result_btn_row.pack(pady=Theme.PAD_S)

        self.download_btn = ctk.CTkButton(
            result_btn_row, text="📥 打开生成图", command=self._open_result_file, state="disabled",
            height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT, width=140
        )
        self.download_btn.pack(side="left", padx=5)

        self.save_as_btn = ctk.CTkButton(
            result_btn_row, text="💾 另存为...", command=self._save_result_as, state="disabled",
            height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT, fg_color="gray", width=120
        )
        self.save_as_btn.pack(side="left", padx=5)

        self.status = ctk.CTkLabel(result_frame, text="就绪", text_color="gray", font=Theme.BODY_FONT)
        self.status.pack(pady=5)

        self.output_dir_label = ctk.CTkLabel(
            result_frame,
            text=f"输出: {Path(self.output_dir).name}",
            wraplength=280,
            text_color="gray",
            font=Theme.SMALL_FONT,
        )
        self.output_dir_label.pack(pady=4)

        # === 右侧: 配置区 + 提示词 + 日志 ===
        right_panel = ctk.CTkScrollableFrame(content, orientation="vertical")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)

        # --- 生成配置 ---
        config_frame = ctk.CTkFrame(right_panel)
        config_frame.pack(fill="x", pady=Theme.PAD_S, padx=Theme.PAD_S)

        ctk.CTkLabel(config_frame, text="⚙️ 生成配置", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        # 模式选择
        mode_frame = ctk.CTkFrame(config_frame)
        mode_frame.pack(fill="x", pady=Theme.PAD_S, padx=10)

        ctk.CTkLabel(mode_frame, text="生成模式:", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=2)

        self.mode_var = ctk.StringVar(value="comfyui")
        modes = [
            ("ComfyUI (云端)", "comfyui"),
            ("Nano Banana", "nano_banana"),
            ("Nano Banana Pro", "nano_banana_pro"),
        ]

        mode_row = ctk.CTkFrame(mode_frame)
        mode_row.pack(fill="x", pady=2)
        for text, value in modes:
            rb = ctk.CTkRadioButton(mode_row, text=text,
                                   variable=self.mode_var, value=value,
                                   command=self._on_mode_change,
                                   font=Theme.BODY_FONT)
            rb.pack(side="left", padx=8, pady=2)

        # ComfyUI 服务器 (条件显示)
        self.comfy_frame = ctk.CTkFrame(config_frame)
        self.comfy_frame.pack(fill="x", pady=Theme.PAD_S, padx=10)

        ctk.CTkLabel(self.comfy_frame, text="ComfyUI 服务器:", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=2)

        server_row = ctk.CTkFrame(self.comfy_frame)
        server_row.pack(fill="x", pady=2)
        ctk.CTkLabel(server_row, text="服务器:", font=Theme.BODY_FONT).pack(side="left", padx=(Theme.PAD_S))
        self.server_entry = ctk.CTkEntry(server_row, height=Theme.ENTRY_HEIGHT,
                                        placeholder_text="https://server:port", font=Theme.BODY_FONT,
                                        fg_color=Theme.COLOR_INPUT_BG)
        self.server_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.server_entry.insert(0, self.config.comfyui.get_effective_server_url() or "")

        # 工作流选择
        workflow_row = ctk.CTkFrame(self.comfy_frame)
        workflow_row.pack(fill="x", pady=6)

        ctk.CTkLabel(workflow_row, text="工作流:", font=Theme.BODY_FONT).pack(side="left", padx=(Theme.PAD_S))

        # 获取已有的工作流列表
        gen_workflow_list = self.config.comfyui.list_workflows()
        gen_initial_values = gen_workflow_list if gen_workflow_list else ["暂无工作流"]

        self.gen_workflow_var = ctk.StringVar()
        self.gen_workflow_menu = ctk.CTkOptionMenu(workflow_row, variable=self.gen_workflow_var,
                                                      values=gen_initial_values,
                                                      width=200, font=Theme.BODY_FONT,
                                                      text_color="#FFFFFF",
                                                      dropdown_text_color="#FFFFFF",
                                                      command=self._on_comfy_workflow_change)
        self.gen_workflow_menu.pack(side="left", padx=5)

        # 刷新工作流按钮
        self.refresh_workflow_btn = ctk.CTkButton(
            workflow_row, text="🔄", width=32, height=32,
            command=self._refresh_comfy_workflow_menu,
            font=Theme.BODY_FONT
        )
        self.refresh_workflow_btn.pack(side="left", padx=2)

        # 设置初始选中值
        if gen_workflow_list:
            gen_current = self.config.comfyui.current_workflow
            if gen_current and gen_current in gen_workflow_list:
                self.gen_workflow_var.set(gen_current)
            else:
                self.gen_workflow_var.set(gen_workflow_list[0])
        else:
            self.gen_workflow_var.set("")

        self.comfy_frame.pack_forget()  # 默认隐藏，切换到 ComfyUI 时显示

        # --- 提示词配置 ---
        prompt_frame = ctk.CTkFrame(right_panel)
        prompt_frame.pack(fill="x", pady=Theme.PAD_S, padx=Theme.PAD_S)

        ctk.CTkLabel(prompt_frame, text="📝 提示词配置", font=Theme.TITLE_FONT).pack(pady=Theme.PAD_S)

        ctk.CTkLabel(prompt_frame, text="提示词模式:", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=2)

        self.prompt_mode = ctk.StringVar(value="copywriting")

        prompt_row = ctk.CTkFrame(prompt_frame)
        prompt_row.pack(fill="x", pady=2)

        # 为1688文案识别单选按钮添加点击回调
        def on_rewrite_selected():
            self.prompt_mode.set("rewrite")
            self._on_prompt_mode_change()

        def on_copywriting_selected():
            self.prompt_mode.set("copywriting")
            self._on_prompt_mode_change()

        def on_wash_selected():
            self.prompt_mode.set("wash")
            self._on_prompt_mode_change()

        ctk.CTkRadioButton(prompt_row, text="使用文案",
                          variable=self.prompt_mode, value="copywriting", font=Theme.BODY_FONT, command=on_copywriting_selected).pack(side="left", padx=5)
        ctk.CTkRadioButton(prompt_row, text="1688文案识别",
                          variable=self.prompt_mode, value="rewrite", font=Theme.BODY_FONT, command=on_rewrite_selected).pack(side="left", padx=5)
        ctk.CTkRadioButton(prompt_row, text="洗稿",
                          variable=self.prompt_mode, value="wash", font=Theme.BODY_FONT, command=on_wash_selected).pack(side="left", padx=5)

        # 1688文案识别模式下添加同步按钮
        self.sync_ai_btn = ctk.CTkButton(prompt_frame, text="🤖 同步AI提示词", height=32, font=Theme.BODY_FONT,
                                        command=self._sync_ai_prompt_to_input, width=130, fg_color=Theme.COLOR_PRIMARY)
        self.sync_ai_btn.pack(anchor="e", padx=Theme.PAD_S, pady=(2, 0))
        self.sync_ai_btn.pack_forget()  # 默认隐藏

        self.prompt_text = ctk.CTkTextbox(prompt_frame, height=100, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.prompt_text.pack(fill="x", pady=5, padx=Theme.PAD_S)

        # 翻译按钮
        trans_btn = ctk.CTkButton(prompt_frame, text="🌐 翻译成中文", height=24, font=Theme.SMALL_FONT,
                                 command=self._translate_prompt, width=100, fg_color=Theme.COLOR_PRIMARY)
        trans_btn.pack(anchor="e", padx=Theme.PAD_S, pady=(0, 5))
        self.default_prompt = "Remove all text, keep the product"
        self.prompt_text.insert("1.0", self.default_prompt)

        # 洗稿配置（默认隐藏，洗稿模式时显示）
        self.wash_frame = ctk.CTkFrame(prompt_frame)
        # 上传竞品图
        wash_row = ctk.CTkFrame(self.wash_frame)
        wash_row.pack(fill="x", pady=4)
        ctk.CTkLabel(wash_row, text="竞品图:", font=Theme.BODY_FONT).pack(side="left")
        self.wash_image_label = ctk.CTkLabel(wash_row, text="未选择", text_color="gray", font=Theme.SMALL_FONT)
        self.wash_image_label.pack(side="left", padx=6)
        ctk.CTkButton(
            wash_row, text="选择图片", width=80, height=30, font=Theme.SMALL_FONT, command=self._select_wash_image
        ).pack(side="left", padx=4)

        # 洗稿引擎
        engine_row = ctk.CTkFrame(self.wash_frame)
        engine_row.pack(fill="x", pady=4)
        ctk.CTkLabel(engine_row, text="洗稿引擎:", font=Theme.BODY_FONT).pack(side="left")
        self.wash_engine_var = ctk.StringVar(value="nano_v1")
        ctk.CTkOptionMenu(
            engine_row,
            variable=self.wash_engine_var,
            values=["comfyui", "nano_v1", "nano_v2"],
            width=140,
            font=Theme.BODY_FONT
        ).pack(side="left", padx=6)

        # --- 操作按钮 ---
        btn_frame = ctk.CTkFrame(right_panel)
        btn_frame.pack(fill="x", pady=Theme.PAD_S, padx=Theme.PAD_S)

        self.gen_btn = ctk.CTkButton(btn_frame, text="🚀 开始生成", height=50, font=Theme.HEADER_FONT,
                               command=self._start_generate, fg_color=Theme.COLOR_SUCCESS)
        self.gen_btn.pack(fill="x", pady=2)

        self.open_folder_btn = ctk.CTkButton(btn_frame, text="📁 打开输出文件夹", height=Theme.BTN_HEIGHT, font=Theme.BODY_FONT,
                                             command=self._open_output_folder, fg_color="gray")
        self.open_folder_btn.pack(fill="x", pady=2)

        # --- 执行日志 ---
        log_frame = ctk.CTkFrame(right_panel)
        log_frame.pack(fill="both", expand=True, pady=Theme.PAD_S, padx=Theme.PAD_S)

        # 日志标题行
        log_header = ctk.CTkFrame(log_frame)
        log_header.pack(fill="x", padx=Theme.PAD_S, pady=(Theme.PAD_S, 0))

        ctk.CTkLabel(log_header, text="📋 执行日志", font=Theme.TITLE_FONT).pack(side="left")

        self.log_clear_btn = ctk.CTkButton(log_header, text="清空", width=60, height=24, font=Theme.SMALL_FONT,
                                          command=self._clear_log, fg_color="gray")
        self.log_clear_btn.pack(side="right", padx=5)

        # 日志文本区域
        self.log_area = ctk.CTkTextbox(
            log_frame,
            height=200,
            font=Theme.LOG_FONT,
            fg_color="#1a1a1a",
            text_color="#e0e0e0",
            wrap="word",
            state="disabled"
        )
        self.log_area.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=(0, Theme.PAD_S))

        # 配置日志颜色标签 - 优化深色模式对比度
        self.log_area.tag_config("info", foreground="#89c4f4")    # 亮蓝色
        self.log_area.tag_config("success", foreground="#4caf50") # 亮绿色
        self.log_area.tag_config("warning", foreground="#ffb84d") # 亮橙色
        self.log_area.tag_config("error", foreground="#ff6b6b")   # 亮红色
        self.log_area.tag_config("step", foreground="#e0e0e0")    # 亮灰色
        self.log_area.tag_config("prompt", foreground="#b39ddb")  # 紫色 - 提示词
        self.log_area.tag_config("api", foreground="#4db6ac")     # 青色 - API调用

    def _on_comfy_workflow_change(self, event=None):
        """图生图页面ComfyUI工作流切换事件"""
        # 刷新当前选择到配置
        selected = self.gen_workflow_var.get()
        if selected:
            self.config.comfyui.current_workflow = selected
            self._log(f"已切换到工作流: {selected}", "info")

    def _refresh_comfy_workflow_menu(self):
        """刷新图生图页面的ComfyUI工作流下拉菜单"""
        # 重新加载配置文件以获取最新的工作流列表
        from config import reload_config
        self.config = reload_config()

        workflows = self.config.comfyui.list_workflows()

        if not workflows:
            self.gen_workflow_var.set("")
            self.gen_workflow_menu.configure(values=["暂无工作流"])
            self.gen_workflow_menu.set("暂无工作流")
            self._log("工作流列表已刷新 (无工作流)", "info")
        else:
            # 先确定要显示的值
            current = self.config.comfyui.current_workflow
            if current and current in workflows:
                new_value = current
            else:
                new_value = workflows[0]
                self.config.comfyui.current_workflow = new_value

            # 先设置变量值，再更新下拉菜单选项，最后强制设置显示值
            self.gen_workflow_var.set(new_value)
            self.gen_workflow_menu.configure(values=workflows)
            self.gen_workflow_menu.set(new_value)

            self._log(f"工作流列表已刷新 (共 {len(workflows)} 个)", "success")

    def _log(self, message: str, level: str = "info"):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        prefix_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "step": "▶️",
        }
        prefix = prefix_map.get(level, "•")

        log_text = f"[{timestamp}] {prefix} {message}\n"

        self.log_area.configure(state="normal")
        # 始终追加到末尾
        self.log_area.insert("end", log_text, level)
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

        # 同步写入文件日志
        try:
            from utils.logger import log_info, log_warning, log_error, log_debug
            file_msg = f"[图生图] {message}"
            if level in ("error",):
                log_error(file_msg)
            elif level in ("warning",):
                log_warning(file_msg)
            elif level in ("step", "api", "prompt"):
                log_debug(file_msg)
            else:
                log_info(file_msg)
        except Exception:
            pass
    
    def _clear_log(self):
        """清空日志"""
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")
    
    def _toggle_log_view(self):
        """展开/收起底部日志区域（图生图）"""
        if self.log_expanded:
            self.log_area.configure(height=40)
            self.log_expand_btn.configure(text="▼")
            self.log_expanded = False
        else:
            self.log_area.configure(height=160)
            self.log_expand_btn.configure(text="▲")
            self.log_expanded = True
    
    def _on_mode_change(self):
        """切换生成模式"""
        mode = self.mode_var.get()
        if mode == "comfyui":
            try:
                self.comfy_frame.pack(fill="x", pady=5, padx=10, after=self.winfo_children()[1].winfo_children()[1])
            except:
                self.comfy_frame.pack(fill="x", pady=5, padx=10)
            # 刷新工作流菜单（会重新加载配置）
            self._refresh_comfy_workflow_menu()
            # 同步配置中的服务器地址到输入框
            effective_url = self.config.comfyui.get_effective_server_url()
            if hasattr(self, 'server_entry') and effective_url:
                self.server_entry.delete(0, "end")
                self.server_entry.insert(0, effective_url)
        else:
            self.comfy_frame.pack_forget()

    def _on_prompt_mode_change(self, *args):
        """切换提示词模式时更新UI"""
        mode = self.prompt_mode.get()
        # 显示/隐藏同步AI提示词按钮
        if mode == "rewrite":
            # 1688文案识别模式：显示同步按钮
            self.sync_ai_btn.pack(anchor="e", padx=Theme.PAD_S, pady=(2, 0))
        else:
            # 其他模式：隐藏同步按钮
            self.sync_ai_btn.pack_forget()

        # 显示/隐藏洗稿配置
        if mode == "wash":
            self.wash_frame.pack(fill="x", pady=Theme.PAD_S, padx=Theme.PAD_S)
        else:
            self.wash_frame.pack_forget()

    def _sync_ai_prompt_to_input(self):
        """同步文案识别页面生成的AI提示词到图生图的输入框"""
        try:
            output_dir = Path("./output")
            prompt_file = output_dir / "ai_prompt.txt"

            if not prompt_file.exists():
                self.prompt_text.delete("1.0", "end")
                self._log("未找到AI提示词记录，请先在文案识别页面生成", "warning")
                if CTkMessagebox:
                    CTkMessagebox(title="提示", message="未找到 AI 提示词记录，请先在“文案识别”页生成。", icon="warning")
                return

            with open(prompt_file, "r", encoding="utf-8") as f:
                text = f.read()

            # 检查是否是空内容或错误内容
            if not text or not text.strip():
                self.prompt_text.delete("1.0", "end")
                self._log("AI提示词文件为空", "warning")
                if CTkMessagebox:
                    CTkMessagebox(title="提示", message="AI 提示词文件为空，请先在“文案识别”页生成。", icon="warning")
                return

            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("1.0", text)
            self._log(f"已同步AI提示词 ({len(text)} 字符)", "success")

            # 同步后清理文件，避免下次误用旧提示
            try:
                prompt_file.unlink()
            except Exception:
                pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"同步AI提示词失败: {e}", "error")

    def _load_image_info(self):
        """加载图片信息（包括图二提示词）"""
        try:
            from scraper import TextExtractor
            extractor = TextExtractor("./output")
            if os.path.exists(os.path.join(extractor.output_dir, "product_info.json")):
                extractor.load_json()
                
                # 尝试获取所有的 label 和 description
                if extractor.copywriting and extractor.copywriting.image_analysis:
                    analysis = extractor.copywriting.image_analysis
                    # 如果有第2张图（index 1），显示它的提示词
                    if len(analysis) > 1:
                        # Optional: Could log this info instead since GUI element is removed
                        pass
        except Exception as e:
            print(f"Load image info error: {e}")

    def _on_drop(self, files):
        """处理文件拖拽"""
        if not files:
            return
            
        try:
            # windnd returns bytes on Python 3
            file_path = files[0]
            if isinstance(file_path, bytes):
                file_path = file_path.decode("gbk" if os.name == "nt" else "utf-8")
                
            if os.path.exists(file_path):
                # Check extension
                ext = os.path.splitext(file_path)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                    self._set_selected_image(file_path, log_msg="通过拖拽上传")
                else:
                    self._log("不支持的文件类型", "warning")
        except Exception as e:
            self._log(f"拖拽处理失败: {e}", "error")
            self._log(f"同步失败: {e}", "error")

    def _open_output_folder(self):
        """打开输出文件夹"""
        output_dir = os.path.abspath(self.output_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            os.system(f'open "{output_dir}"')
        else:
            os.system(f'xdg-open "{output_dir}"')
        
        self._log(f"已打开: {output_dir}", "info")
        
    def _select_image(self):
        """选择图片"""
        from tkinter import filedialog
        
        path = filedialog.askopenfilename(
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.webp")]
        )
        
        if path:
            self.use_last_var.set(False)
            self._set_selected_image(path, log_msg=f"已选择图片: {Path(path).name}")

    def _set_selected_image(self, path: str, log_msg: str = None):
        """更新左侧原图预览"""
        self.selected_image = path
        self.image_path_label.configure(text=Path(path).name)
        
        try:
            img = Image.open(path)
            img.thumbnail((450, 450))
            photo = ctk.CTkImage(img, size=(350, 350))
            self.image_preview.configure(image=photo, text="")
            self.image_preview.image = photo
            if log_msg:
                self._log(log_msg, "info")
        except Exception as e:
            self._log(f"图片加载失败: {e}", "error")
        
        # 尝试加载关联的图片信息（如提示词）
        self._load_image_info()

    def _toggle_use_last(self):
        """勾选使用上一轮生成图"""
        if self.use_last_var.get():
            if self.last_result_image and os.path.exists(self.last_result_image):
                self._set_selected_image(self.last_result_image, log_msg="已使用上一轮生成图作为原图")
            else:
                self._log("当前没有可用的上一轮生成图", "warning")
                self.use_last_var.set(False)
        # 取消勾选时不做处理，保持当前选择

    def _open_result_file(self):
        """打开/下载生成结果图"""
        if not self.result_image_path or not os.path.exists(self.result_image_path):
            self._log("暂无可下载的生成结果", "warning")
            return
        try:
            if sys.platform == "win32":
                os.startfile(self.result_image_path)
            elif sys.platform == "darwin":
                os.system(f'open "{self.result_image_path}"')
            else:
                os.system(f'xdg-open "{self.result_image_path}"')
            self._log(f"已打开生成图: {self.result_image_path}", "info")
        except Exception as e:
            self._log(f"打开生成图失败: {e}", "error")

    def _save_result_as(self):
        """另存为生成结果"""
        if not self.result_image_path or not os.path.exists(self.result_image_path):
            self._log("暂无可保存的生成结果", "warning")
            return
            
        try:
            from tkinter import filedialog
            import shutil
            import time
            
            # 获取原文件扩展名
            ext = os.path.splitext(self.result_image_path)[1]
            initial_file = f"result_{int(time.time())}{ext}"
            
            save_path = filedialog.asksaveasfilename(
                defaultextension=ext,
                initialfile=initial_file,
                filetypes=[("Image file", f"*{ext}"), ("All files", "*.*")]
            )
            
            if save_path:
                shutil.copy2(self.result_image_path, save_path)
                self._log(f"已另存为: {save_path}", "success")
                if CTkMessagebox:
                    CTkMessagebox(title="成功", message=f"图片已保存到:\n{save_path}", icon="check")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"另存为失败: {e}", "error")

    def _start_generate(self):
        """开始生成"""
        if self.is_generating:
            self._log("正在生成中，请稍候...", "warning")
            return

        if not self.selected_image:
            self.status.configure(text="请先选择图片", text_color="red")
            self._log("请先选择图片", "warning")
            return

        self._clear_log()
        self._set_generating(True)
        self._gen_id += 1
        current_gen_id = self._gen_id
        self.result_image_path = None

        # 用空白图替换旧预览，保持有效的 CTkImage 引用避免 Tk pyimage 错误
        try:
            old_pil = getattr(self, '_result_pil_img', None)
            blank = Image.new("RGB", (480, 480), (40, 40, 40))
            blank_photo = ctk.CTkImage(blank, size=(450, 450))
            self.result_preview.configure(image=blank_photo, text="正在生成中...")
            self.result_preview.image = blank_photo
            self._result_pil_img = None
            # 旧 CTkImage 已被替换，现在安全关闭旧 PIL Image
            if old_pil:
                try:
                    old_pil.close()
                except Exception:
                    pass
        except Exception:
            self.result_preview.configure(text="正在生成中...")
        self.result_path_label.configure(text="")
        self.download_btn.configure(state="disabled")
        self.save_as_btn.configure(state="disabled", fg_color="gray")

        mode = self.mode_var.get()
        prompt_mode = self.prompt_mode.get()

        # ========== 详细日志开始 ==========
        self._log("=" * 50, "step")
        self._log("开始生成流程", "step")
        self._log(f"选择原图: {Path(self.selected_image).name}", "info")

        user_prompt = self.prompt_text.get("1.0", "end").strip()
        prompt = ""

        self._log(f"提示词模式: {prompt_mode}", "info")

        # 确定提示词
        if prompt_mode == "wash":
            prompt = ""
            self._log("使用洗稿模式 (空提示词)", "info")
        elif prompt_mode == "copywriting":
            copy_prompt = ""
            try:
                from scraper import TextExtractor
                extractor = TextExtractor("./output")
                extractor.load_json()
                # 优先使用完整文案文本，若没有则退回关键词提示
                copy_prompt = extractor.copywriting.combined_copywriting.strip()
                if not copy_prompt:
                    copy_prompt = extractor.get_prompt_text()
                self._log("使用抓取的文案作为提示词", "info")
            except Exception:
                self._log("未找到文案，优先使用自定义提示词", "warning")

            if user_prompt:
                # 自定义指令优先，文案作为补侧关键词
                prompt = f"{user_prompt}\n\n{copy_prompt}".strip() if copy_prompt else user_prompt
                self._log(f"追加自定义提示词: {user_prompt[:50]}...", "info")
            else:
                prompt = copy_prompt
        elif prompt_mode == "rewrite":
            # 1688 文案识别：优先从保存的AI提示词读取，没有则提示用户先去生成
            try:
                output_dir = Path("./output")
                prompt_file = output_dir / "ai_prompt.txt"

                # 尝试读取已保存的AI提示词
                if prompt_file.exists():
                    with open(prompt_file, "r", encoding="utf-8") as f:
                        saved_prompt = f.read().strip()
                    if saved_prompt:
                        prompt = saved_prompt
                        self._log(f"使用已保存的AI提示词 ({len(saved_prompt)} 字符)", "info")
                    else:
                        # 文件存在但为空，不自动生成，让用户手动操作
                        self._log("AI提示词文件为空，请先在文案识别页面生成提示词，或点击下方同步按钮", "warning")
                        prompt = user_prompt
                else:
                    # 没有保存的AI提示词，不自动生成，让用户手动操作
                    self._log("未找到AI提示词记录，请先在文案识别页面生成提示词，或点击下方同步按钮", "warning")
                    prompt = user_prompt

            except Exception as e:
                self._log(f"读取AI提示词出错: {e}", "error")
                prompt = user_prompt
        else:
            prompt = user_prompt
            self._log(f"使用自定义提示词", "info")

        # 兜底：非洗稿模式下如果提示词为空，使用默认去字提示
        if not prompt and prompt_mode != "wash":
            prompt = getattr(self, "default_prompt", "Remove all text, keep the product")
            self._log("提示词为空，使用默认去字提示", "warning")

        # 显示完整提示词（紫色高亮）
        self._log("传入 API 的提示词:", "prompt")
        for line in prompt.split('\n'):
            self._log(f"  {line}", "prompt")

        wash_engine = self.wash_engine_var.get()
        if prompt_mode == "wash" and not self.wash_image_path:
            self._log("请先选择竞品图用于洗稿", "error")
            self._set_generating(False)
            return

        self.status.configure(text="正在生成...", text_color="orange")
        self._log(f"生成模式: {mode}", "api")
        self._log("-" * 50, "step")

        def do_generate():
            result = None
            try:
                if mode == "comfyui":
                    self.after(0, lambda: self._log("正在连接 ComfyUI 服务器...", "api"))
                    from image_generation import ComfyUIFluxKontextClient

                    server = self.server_entry.get().strip() or self.config.comfyui.get_effective_server_url()
                    if not server:
                        raise ValueError("请配置 ComfyUI 服务器地址")

                    self.after(0, lambda: self._log(f"服务器地址: {server}", "api"))

                    client = ComfyUIFluxKontextClient(server)

                    # 加载工作流配置
                    workflow_name = self.gen_workflow_var.get()
                    if workflow_name and self.config.comfyui.workflows.get(workflow_name):
                        wf = self.config.comfyui.get_workflow(workflow_name)
                        client.set_workflow(
                            wf["json"], wf["prompt_node_id"], wf["prompt_param_path"],
                            wf.get("image_node_id"), wf.get("image_param_path")
                        )
                        self.after(0, lambda: self._log(f"使用工作流: {workflow_name}", "api"))
                        self.after(0, lambda: self._log(f"  提示词节点: {wf['prompt_node_id']} ({wf['prompt_param_path']})", "api"))
                        if wf.get("image_node_id"):
                            self.after(0, lambda: self._log(f"  图片节点: {wf.get('image_node_id')} ({wf.get('image_param_path')})", "api"))
                    else:
                        self.after(0, lambda: self._log("使用默认工作流", "api"))

                    self.after(0, lambda: self._log("发送图生图请求到 ComfyUI...", "api"))
                    result = client.image_to_image(
                        self.selected_image, prompt,
                        output_dir=self.output_dir
                    )
                    
                elif mode == "nano_banana_pro":
                    # 洗稿模式：切换到洗稿引擎
                    if prompt_mode == "wash":
                        wash_engine = self.wash_engine_var.get()
                        self.after(0, lambda: self._log(f"洗稿引擎: {wash_engine}", "api"))
                        if wash_engine == "comfyui":
                            raise ValueError("ComfyUI 洗稿逻辑待对接，请稍后再试")
                        elif wash_engine == "nano_v1":
                            self.after(0, lambda: self._log("初始化 Nano Banana 洗稿客户端 (v1)...", "api"))
                            from image_generation import NanoBananaWashClient
                            api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                            if not api_key:
                                raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")
                            client = NanoBananaWashClient(api_key)
                            self.after(0, lambda: self._log("发送洗稿请求 (v1)...", "api"))
                            result = client.wash_v1(
                                self.wash_image_path,
                                prompt or "",
                                output_dir=self.output_dir
                            )
                        elif wash_engine == "nano_v2":
                            self.after(0, lambda: self._log("初始化 Nano Banana 洗稿客户端 (v2)...", "api"))
                            from image_generation import NanoBananaWashClient
                            api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                            if not api_key:
                                raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")
                            client = NanoBananaWashClient(api_key)
                            self.after(0, lambda: self._log("发送洗稿请求 (v2)...", "api"))
                            result = client.wash_v2(
                                self.wash_image_path,
                                prompt or "",
                                output_dir=self.output_dir
                            )
                        else:
                            raise ValueError(f"不支持的洗稿引擎: {wash_engine}")
                    else:
                        self.after(0, lambda: self._log("初始化 Nano Banana Pro 客户端...", "api"))
                        from image_generation import NanoBananaProClient

                        api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                        if not api_key:
                            raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")

                        client = NanoBananaProClient(api_key)

                        self.after(0, lambda: self._log("发送图生图请求到 Nano Banana Pro...", "api"))
                        result = client.image_to_image(
                            self.selected_image, prompt,
                            output_dir=self.output_dir
                        )
                elif mode == "nano_banana":
                    self.after(0, lambda: self._log("初始化 Nano Banana 基础客户端...", "api"))
                    from image_generation import NanoBananaBasicClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=False)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana API Key）")
                    client = NanoBananaBasicClient(api_key)
                    self.after(0, lambda: self._log("发送图生图请求到 Nano Banana...", "api"))
                    result = client.image_to_image(
                        self.selected_image,
                        prompt or "",
                        output_dir=self.output_dir
                    )
                else:
                    raise ValueError(f"不支持的生成模式: {mode}")

                if result:
                    self.after(0, lambda r=result, gid=current_gen_id: self._on_complete(r) if self._gen_id == gid else None)
                else:
                    self.after(0, lambda gid=current_gen_id: self._on_error("生成失败：未返回结果") if self._gen_id == gid else None)

            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = str(e)
                self.after(0, lambda msg=error_msg, gid=current_gen_id: self._on_error(msg) if self._gen_id == gid else None)
            finally:
                self.after(0, lambda gid=current_gen_id: self._set_generating(False) if self._gen_id == gid else None)
                
        threading.Thread(target=do_generate, daemon=True).start()

    # ==================== 自动化功能 ====================

    def _auto_bg_replace(self):
        """背景替换自动化：产品不变，替换背景"""
        print("[DEBUG] 背景替换按钮被点击")
        self._log("背景替换自动化启动...", "step")
        self._auto_generate(mode="bg_replace")

    def _auto_model_on_product(self):
        """产品上模特身自动化：将产品放入模特身上"""
        print("[DEBUG] 产品上模特身按钮被点击")
        self._log("产品上模特身自动化启动...", "step")
        self._auto_generate(mode="model_on_product")

    def _auto_generate(self, mode: str):
        """自动化生成主流程"""
        print(f"[DEBUG] _auto_generate 被调用, mode={mode}")
        url = self.auto_url_entry.get().strip()
        print(f"[DEBUG] URL={url}")
        if not url:
            self._log("请输入1688链接", "warning")
            self._auto_log("⚠️ 请先输入1688链接", "warning")
            return

        mode_name = "背景替换" if mode == "bg_replace" else "产品上模特身"
        self._log(f"开始自动化流程: {mode_name}", "step")
        self._auto_log(f"🚀 开始自动化: {mode_name}", "info")
        self._set_generating(True)

        def run_auto():
            import traceback
            import json

            try:
                # ========== 步骤1: 抓取1688产品信息和图片 ==========
                self._log("正在抓取1688产品...", "step")
                self._auto_log("📥 步骤1: 抓取1688产品信息", "info")

                from scraper import AlibabaScraper, ImageDownloader, TextExtractor

                scraper = AlibabaScraper(headless=True, timeout=120)
                product = scraper.scrape_product(url)

                self._auto_log(f"  ✓ 产品标题: {product.title[:50]}...", "success")

                # 保存抓取的信息
                extractor = TextExtractor("./output")
                extractor.from_product_data(scraper.get_product_text())
                extractor.save_all()

                self._auto_log(f"  ✓ 文案已保存", "success")

                # 下载图片
                downloader = ImageDownloader("./output/images")
                downloader.clear_output_dir()

                all_images = product.main_images + product.detail_images
                main_results = downloader.download_main_images(product.main_images)
                detail_results = downloader.download_detail_images(product.detail_images) if product.detail_images else []
                all_results = main_results + detail_results

                # 获取第一张图片路径作为主图
                main_image_path = None
                if all_results:
                    main_image_path = all_results[0][1]

                self._log(f"抓取完成: 标题={product.title[:20]}..., 图片={len(all_images)}张", "success")
                self._auto_log(f"  ✓ 下载完成: 主图{len(main_results)}张, 详情图{len(detail_results)}张", "success")

                # 刷新画廊
                self._auto_refresh_gallery()

                # ========== 步骤2: 识别主图 ==========
                self._log("正在分析图片识别主图...", "step")
                self._auto_log("🔍 步骤2: AI识别主图", "info")

                # 调用OpenRouter识别主图
                api_key = self.config.api_keys.openrouter_api_key
                if not api_key:
                    raise ValueError("请在配置页填写 OpenRouter API Key")

                import requests
                identify_url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                # 构建提示词：提供产品标题，要求AI识别哪张图是主图（产品图）
                identify_prompt = f"""请分析以下电商产品图片，识别哪张图片是主图（产品图）。

产品信息：
标题: {product.title}

要求：
1. 返回主图的文件名（不含路径）
2. 只返回JSON格式，不要其他解释
3. 返回格式: {{"main_image": "文件名"}} 或 {{"main_image": "none"}}

图片列表：
{chr(10).join([f"- {os.path.basename(p[1])}" for p in all_results[:5]])}
...

请直接返回JSON结果。"""

                payload = {
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是图片分析助手，只返回JSON格式结果。"},
                        {"role": "user", "content": identify_prompt},
                    ],
                    "max_tokens": 200,
                }

                self._auto_log(f"  → 调用 OpenRouter API...", "info")
                resp = requests.post(identify_url, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                # 解析响应
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 提取token使用情况
                input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                output_tokens = data.get("usage", {}).get("completion_tokens", 0)
                total_tokens = input_tokens + output_tokens

                self._auto_log(f"  ✓ API响应: {input_tokens}输入 + {output_tokens}输出 = {total_tokens}总计tokens", "success")

                # 解析主图文件名
                main_image_filename = "none"
                try:
                    if "{" in content:
                        result = json.loads(content)
                        main_image_filename = result.get("main_image", "none")
                except json.JSONDecodeError as e:
                    self._auto_log(f"  ⚠ JSON解析失败: {e}, 原始响应: {content[:100]}", "warning")

                self._log(f"识别结果: 主图={main_image_filename}", "info")
                self._auto_log(f"  ✓ 识别结果: {main_image_filename}", "success")

                # 确定主图路径
                final_main_image = None
                if main_image_filename != "none":
                    # 找到匹配的图片
                    for result in all_results:
                        if os.path.basename(result[1]) == main_image_filename:
                            final_main_image = result[1]
                            break

                if not final_main_image:
                    final_main_image = all_results[0][1] if all_results else main_image_path
                    self._auto_log(f"  ⚠ 未找到匹配主图，使用第一张图片", "warning")

                # ========== 步骤3: 生成提示词 ==========
                self._log("正在生成AI提示词...", "step")
                self._auto_log("✍️ 步骤3: 生成AI提示词", "info")

                # 获取文案
                raw_text = extractor.copywriting.combined_copywriting.strip()

                if mode == "bg_replace":
                    # 背景替换模式
                    final_prompt = f"产品不变，替换背景为: {raw_text[:800]}"
                    self._auto_log(f"  ✓ 模式: 背景替换", "success")
                else:
                    # 产品上模特身模式
                    final_prompt = f"产品放置在模特身上，保持产品特征，背景描述: {raw_text[:800]}"
                    self._auto_log(f"  ✓ 模式: 产品上模特身", "success")

                # 保存提示词到文件
                output_dir = Path("./output")
                output_dir.mkdir(parents=True, exist_ok=True)
                with open(output_dir / "auto_prompt.txt", "w", encoding="utf-8") as f:
                    f.write(final_prompt)

                self._auto_log(f"  ✓ 提示词长度: {len(final_prompt)}字符", "success")

                # ========== 步骤4: 执行图生图 ==========
                self._log("正在执行图生图...", "step")
                self._auto_log("🎨 步骤4: 执行图生图", "info")

                # 根据选择的模式和主图执行生成
                gen_mode = self.mode_var.get()
                self._auto_log(f"  → 生成引擎: {gen_mode}", "info")

                if gen_mode == "comfyui":
                    from image_generation import ComfyUIFluxKontextClient
                    server = self.server_entry.get().strip() or self.config.comfyui.get_effective_server_url()
                    client = ComfyUIFluxKontextClient(server)

                    # 加载工作流配置
                    workflow_name = self.gen_workflow_var.get()
                    if workflow_name and self.config.comfyui.workflows.get(workflow_name):
                        wf = self.config.comfyui.get_workflow(workflow_name)
                        client.set_workflow(
                            wf["json"], wf["prompt_node_id"], wf["prompt_param_path"],
                            wf.get("image_node_id"), wf.get("image_param_path")
                        )
                        self._auto_log(f"  → 使用工作流: {workflow_name}", "info")

                    if mode == "bg_replace":
                        self._log("使用主图作为参考进行背景替换", "info")
                        self._auto_log(f"  → ComfyUI背景替换: {Path(final_main_image).name}", "info")
                        result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)
                    else:
                        self._log("使用主图作为基础，产品上模特身", "info")
                        self._auto_log(f"  → ComfyUI产品上模特: {Path(final_main_image).name}", "info")
                        result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)

                elif gen_mode == "nano_banana":
                    from image_generation import NanoBananaBasicClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=False)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana API Key）")
                    client = NanoBananaBasicClient(api_key)
                    self._auto_log(f"  → Nano Banana生成", "info")
                    result = client.generate(final_prompt, output_dir=self.output_dir)

                elif gen_mode == "nano_banana_pro":
                    from image_generation import NanoBananaProClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")
                    client = NanoBananaProClient(api_key)
                    self._auto_log(f"  → Nano Banana Pro图生图: {Path(final_main_image).name}", "info")
                    result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)
                else:
                    raise ValueError(f"不支持的生成模式: {gen_mode}")

                # ========== 步骤5: 显示结果和token消耗 ==========
                self._log(f"✅ 自动化完成！", "success")
                self._auto_log(f"✅ 自动化流程完成！", "success")
                self._log(f"📊 Token消耗: 输入={input_tokens}, 输出={output_tokens}, 总计={total_tokens}", "info")
                self._auto_log(f"📊 Token统计: {input_tokens}输入 + {output_tokens}输出 = {total_tokens}总计", "info")

                # 显示结果
                self.after(0, lambda: self._on_complete(result))

            except Exception as e:
                error_traceback = traceback.format_exc()
                traceback.print_exc()
                self._log(f"自动化失败: {e}", "error")
                self._auto_log(f"❌ 自动化失败\n\n错误: {str(e)}\n\n详细回溯:\n{error_traceback}", "error")
                self.after(0, lambda: self._on_error(str(e)))
            finally:
                self.after(0, lambda: self._set_generating(False))

        threading.Thread(target=run_auto, daemon=True).start()

    def _rewrite_prompt_with_openrouter(self, raw_text: str) -> str:
        """调用 OpenRouter gpt-4o-mini 将文案整理为绘画提示词"""
        api_key = self.config.api_keys.openrouter_api_key
        if not api_key:
            self._log("请在配置页填写 OpenRouter API Key，用于文案识别", "warning")
            return raw_text
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "你是提示词整理助手，将商品文案提炼为用于 AI 绘画的英文提示词，突出主体、材质、场景、光线，避免品牌和水印。"},
                {"role": "user", "content": raw_text[:4000]},
            ],
            "max_tokens": 200,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() or raw_text
        except Exception as e:
            self._log(f"文案识别失败，使用原文案: {e}", "warning")
            return raw_text

    def _translate_prompt(self):
        """翻译提示词为中文"""
        text = self.prompt_text.get("1.0", "end").strip()
        if not text:
            self._log("提示词为空", "warning")
            return
            
        api_key = self.config.api_keys.openrouter_api_key or self.config.api_keys.gemini_api_key
        if not api_key:
            self._log("请配置 OpenRouter 或 Gemini API Key 以使用翻译功能", "warning")
            return

        self._log("正在翻译...", "step")
        
        def run():
            try:
                res = self._call_translator(text, api_key)
                self.after(0, lambda: self._show_trans_result(res))
            except Exception as e:
                self.after(0, lambda: self._log(f"翻译失败: {e}", "error"))
        
        threading.Thread(target=run, daemon=True).start()

    def _call_translator(self, text: str, api_key: str) -> str:
        """调用API进行翻译"""
        # 简单判断key类型
        is_gemini = "AIza" in api_key ## Simple check for Gemini key format if possible, otherwise assume OpenRouter or try standard
        
        prompt = f"Translate the following text to Chinese (Simplified). Only return the translation, no explanations:\n\n{text}"
        
        # 优先尝试 OpenRouter 格式 (兼容 OpenAI)
        url = "https://openrouter.ai/api/v1/chat/completions"
        if "AIza" in api_key: # Gemini via Google API? Or via OpenAI compat? 
            # 假设用户配置的是 OpenRouter 或类似兼容接口。
            # 如果是纯 Gemini API Key，需要用 google.generativeai 库，但这里为了不引入新库，
            # 我们可以假设用户主要用 OpenRouter，或者我们尝试用 requests 调 gemini rest api
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            try:
               return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except:
               return str(data)
        
        # OpenRouter / OpenAI format
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openai/gpt-4o-mini", # Default to cheap model
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        # 如果是 Gemini Key 但没走上面逻辑(比如没检测到)，可能会报错。
        # 这里为了稳妥，如果 format 看起来像 Gemini 但用户填在 OpenRouter 栏...
        # 暂时只支持 OpenRouter 里的模型，或者用户明确填写了 OpenRouter Key.
        # 我们复用 _rewrite_prompt_with_openrouter 的逻辑
        
        # Re-using logic from _rewrite... structure
        try:
             # Try OpenRouter standard
             resp = requests.post(url, headers=headers, json=payload, timeout=30)
             if resp.status_code != 200:
                 # FLlback or error
                 resp.raise_for_status()
             data = resp.json()
             return data["choices"][0]["message"]["content"].strip()
        except:
             # Fallback logic if needed
             raise

    def _show_trans_result(self, text):
        self._log("翻译完成", "success")
        if CTkMessagebox:
            CTkMessagebox(title="翻译结果", message=text, width=600)
        else:
            # 如果没有弹窗库，显示在日志里
            self._log(f"【翻译结果】: {text}", "info")

    def _select_wash_image(self):
        """选择洗稿用的竞品图"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.webp")]
        )
        if path:
            self.wash_image_path = path
            self.wash_image_label.configure(text=Path(path).name, text_color="white")
            self._log(f"已选择洗稿图: {Path(path).name}", "info")
    
    def _on_error(self, error_msg: str):
        """生成失败"""
        self._log(f"生成失败: {error_msg}", "error")
        self.status.configure(text="生成失败", text_color="red")
        self.result_preview.configure(text="生成失败")
        # 确保按钮状态恢复
        self._set_generating(False)
        
    def _on_complete(self, result_path: str):
        """生成完成"""
        self.result_image_path = result_path
        self.last_result_image = result_path

        # 检查文件是否真正存在
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            self._log("-" * 50, "step")
            self._log("图片生成成功！", "success")
            self._log(f"文件名: {Path(result_path).name}", "info")
            self._log(f"文件大小: {file_size / 1024:.1f} KB", "info")
            self._log(f"保存路径: {result_path}", "info")
            self._log("=" * 50, "step")

            self.status.configure(text="✓ 生成完成", text_color="green")
            self.result_path_label.configure(text=Path(result_path).name)
            self.download_btn.configure(state="normal")
            self.save_as_btn.configure(state="normal", fg_color=Theme.COLOR_SUCCESS)

            # 显示结果图片
            try:
                img = Image.open(result_path)
                img.load()  # 强制从磁盘读取，绕过惰性加载缓存
                img.thumbnail((550, 550))

                photo = ctk.CTkImage(img, size=(450, 450))
                self.result_preview.configure(image=photo, text="")
                self.result_preview.image = photo

                # 新 CTkImage 已设置，安全关闭旧 PIL Image
                old_pil = getattr(self, '_result_pil_img', None)
                self._result_pil_img = img
                if old_pil:
                    try:
                        old_pil.close()
                    except Exception:
                        pass

                self._log("预览图加载成功", "success")
            except Exception as e:
                self._log(f"预览加载失败: {e}", "warning")
        else:
            self._log("生成返回的文件不存在！", "error")
            self.status.configure(text="生成失败", text_color="red")
            return

        # 如果选择了"使用上一轮生成图"，自动切换原图
        if self.use_last_var.get():
            self._set_selected_image(result_path, log_msg="已切换为上一轮生成图作为原图")
        # 确保按钮状态恢复
        self._set_generating(False)



    def _set_generating(self, generating: bool):
        """Set generation state for GenerateFrame."""
        self.is_generating = generating
        try:
            if generating:
                if hasattr(self, 'gen_btn'):
                    self.gen_btn.configure(state="disabled")
            else:
                if hasattr(self, 'gen_btn'):
                    self.gen_btn.configure(state="normal")
        except Exception as e:
            print(f"Error setting GenerateFrame button state: {e}")

    def _load_gallery(self):
        """加载图片画廊"""
        # 清空现有
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
            
        output_dir = Path("./output/images")
        if not output_dir.exists():
            ctk.CTkLabel(self.gallery_frame, text="暂无抓取图片", text_color="gray").pack(padx=20, pady=20)
            return

        # 获取所有图片
        images = list(output_dir.glob("*.jpg")) + list(output_dir.glob("*.png")) + list(output_dir.glob("*.webp"))
        images.sort(key=os.path.getmtime, reverse=True) # 按时间倒序
        
        if not images:
            ctk.CTkLabel(self.gallery_frame, text="暂无抓取图片", text_color="gray").pack(padx=20, pady=20)
            return
            
        for img_path in images:
            self._add_gallery_item(str(img_path))
            
    def _add_gallery_item(self, path: str):
        """添加单个画廊项目"""
        try:
            # 贴建容器
            item_frame = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
            item_frame.pack(side="left", padx=5, pady=5)
            
            # 加载缩略图 - 加大尺寸
            img = Image.open(path)
            img.thumbnail((220, 220)) # preload slightly larger
            
            # 使用正方形裁剪
            w, h = img.size
            size = min(w, h)
            left = (w - size) / 2
            top = (h - size) / 2
            right = (w + size) / 2
            bottom = (h + size) / 2
            img = img.crop((left, top, right, bottom))
            img = img.resize((180, 180), Image.LANCZOS) # 最终显示尺寸加大
            
            ctk_img = ctk.CTkImage(img, size=(180, 180))
            
            # 按钮作为图片载体，点击可选
            btn = ctk.CTkButton(
                item_frame, 
                text="", 
                image=ctk_img, 
                width=180, 
                height=180,
                fg_color="transparent",
                hover_color=Theme.COLOR_PRIMARY,
                command=lambda p=path: self._set_selected_image(p, log_msg="从图库选择")
            )
            btn.pack()
            
            # 简短文件名
            ctk.CTkLabel(item_frame, text=Path(path).name[:15]+"..", font=("Arial", 11), text_color="gray").pack()
            
            # 绑定滚动事件给子控件，防止鼠标在图片上时滚动失效
            btn.bind("<MouseWheel>", self._on_gallery_scroll)
            # 绑定拖拽事件给子控件
            btn.bind("<ButtonPress-1>", self._on_drag_start, add="+") # add=+ 避免覆盖点击事件
            btn.bind("<B1-Motion>", self._on_drag_motion, add="+")
            
        except Exception as e:
            print(f"Load gallery item error: {e}")

    def _on_gallery_scroll(self, event):
        """鼠标滚轮横向滚动"""
        # Windows: event.delta = 120 (up/forward) or -120 (down/backward)
        # MacOS: event.delta might be different but direction is key
        # 向下滑动(负值) = 向右看 (xview scroll positive)
        # 向上滑动(正值) = 向左看 (xview scroll negative)
        if event.delta:
            # 提高滚动速度 (40 -> 8, 5倍速)
            self.gallery_frame._parent_canvas.xview_scroll(int(-1 * (event.delta / 8)), "units")

    def _on_drag_start(self, event):
        """拖拽开始"""
        self._drag_start_x = event.x_root

    def _on_drag_motion(self, event):
        """拖拽中"""
        delta_x = event.x_root - self._drag_start_x
        # 移动越远滚动越快，适当缩小系数
        # xview_scroll(number, "units")
        # 负delta(向左拖) -> 应该向右看(看右边的内容)? 不，向左拖是把内容往左拉，看到右边的内容
        # 这里的交互逻辑：
        # 鼠标往左移 (delta_x < 0) -> 内容应该随鼠标往左移 -> 视口向右移 -> xview_scroll(pos)
        
        sensitivity = 2 # 灵敏度
        if abs(delta_x) > 5: # 阈值
            self.gallery_frame._parent_canvas.xview_scroll(int(-1 * delta_x / sensitivity), "units")
            self._drag_start_x = event.x_root # 重置起点，避免加速滚动

    def _auto_refresh_gallery(self):
        """自动刷新画廊（用于自动化任务后）"""
        self.after(0, self._load_gallery)

    def _auto_log(self, message: str, level: str = "info"):
        """记录自动化日志"""
        def update_log():
            self.auto_log_area.configure(state="normal")
            self.auto_log_area.insert("end", message + "\n", level)
            self.auto_log_area.see("end")
            self.auto_log_area.configure(state="disabled")

        self.after(0, update_log)

        # 同步写入文件日志
        try:
            from utils.logger import log_info, log_warning, log_error
            file_msg = f"[自动化] {message}"
            if level == "error":
                log_error(file_msg)
            elif level == "warning":
                log_warning(file_msg)
            else:
                log_info(file_msg)
        except Exception:
            pass



class CopywritingFrame(ctk.CTkFrame):
    """文案识别页面"""
    
    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self._setup_ui()
        
    def _setup_ui(self):
        # 布局配置
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # 标题
        title = ctk.CTkLabel(self, text="📝 1688 文案识别", font=Theme.HEADER_FONT)
        title.grid(row=0, column=0, columnspan=2, pady=Theme.PAD_L)

        # === 左侧: 输入区 ===
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=1, column=0, sticky="nsew", padx=Theme.PAD_M, pady=Theme.PAD_M)

        ctk.CTkLabel(input_frame, text="原始文案", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 按钮行
        btn_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=Theme.PAD_M)

        ctk.CTkButton(btn_row, text="🔄 同步抓取文案", command=self._sync_scraped_text,
                     width=120).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="📋 粘贴", command=self._paste_text,
                     width=80).pack(side="left")

        # 文本输入
        self.input_text = ctk.CTkTextbox(input_frame, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.input_text.pack(fill="both", expand=True, padx=Theme.PAD_M, pady=Theme.PAD_S)

        # === 卖点分析区 ===
        selling_points_frame = ctk.CTkFrame(self)
        selling_points_frame.grid(row=2, column=0, sticky="nsew", padx=Theme.PAD_M, pady=Theme.PAD_M)

        ctk.CTkLabel(selling_points_frame, text="🌟 产品卖点分析", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 分析按钮
        analyze_points_btn = ctk.CTkButton(selling_points_frame, text="🔍 分析产品卖点",
                                          command=self._analyze_selling_points,
                                          height=35, font=Theme.BODY_FONT,
                                          fg_color="#ff6b6b", hover_color="#ff5252")
        analyze_points_btn.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 卖点展示区域
        self.selling_points_text = ctk.CTkTextbox(selling_points_frame, height=150,
                                                   font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.selling_points_text.pack(fill="both", expand=True, padx=Theme.PAD_M, pady=Theme.PAD_S)

        # 复制卖点按钮
        copy_points_btn = ctk.CTkButton(selling_points_frame, text="📋 复制卖点",
                                        command=self._copy_selling_points,
                                        fg_color=Theme.COLOR_WARNING, hover_color="#a87f1e")
        copy_points_btn.pack(pady=Theme.PAD_M)
        
        # 高级选项（图片上传） - 暂时作为占位符，用户提到后期支持
        # img_frame = ctk.CTkFrame(input_frame)
        # img_frame.pack(fill="x", padx=Theme.PAD_M, pady=Theme.PAD_S)
        # ctk.CTkLabel(img_frame, text="参考图片 (可选):").pack(side="left")
        # ctk.CTkButton(img_frame, text="上传白底图/产品图", width=150).pack(side="right")
        
        # === 中间: 操作区 ===
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, columnspan=2, pady=Theme.PAD_M)
        
        self.analyze_btn = ctk.CTkButton(action_frame, text="🚀 开始分析 & 生成提示词", 
                                       command=self._start_analysis,
                                       font=Theme.SUBHEADER_FONT, height=50, width=250,
                                       fg_color=Theme.COLOR_SUCCESS, hover_color="#268e3b")
        self.analyze_btn.pack()
        
        self.status_label = ctk.CTkLabel(action_frame, text="就绪", text_color="gray")
        self.status_label.pack(pady=5)
        
        # === 右侧: 输出区 ===
        output_frame = ctk.CTkFrame(self)
        output_frame.grid(row=1, column=1, sticky="nsew", padx=Theme.PAD_M, pady=Theme.PAD_M)
        
        ctk.CTkLabel(output_frame, text="生成结果 (AI绘画提示词)", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        # 结果文本
        self.output_text = ctk.CTkTextbox(output_frame, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.output_text.pack(fill="both", expand=True, padx=Theme.PAD_M, pady=Theme.PAD_S)
        
        # 复制按钮
        ctk.CTkButton(output_frame, text="📋 复制结果", command=self._copy_result,
                     fg_color=Theme.COLOR_WARNING, hover_color="#a87f1e").pack(pady=Theme.PAD_M)

    def _sync_scraped_text(self):
        """同步抓取到的文案"""
        # 尝试从全局或主窗口获取最新的抓取结果
        # 这里假设 Application 类有一个 current_scraped_text 属性，或者我们通过文件读取
        try:
            # 读取最新的 output/product_info.txt
            output_dir = Path("./output")
            copywriting_file = output_dir / "product_info.txt"
            if copywriting_file.exists():
                with open(copywriting_file, "r", encoding="utf-8") as f:
                    text = f.read()
                self.input_text.delete("1.0", "end")
                self.input_text.insert("1.0", text)
                self.status_label.configure(text="已同步最新抓取文案", text_color="green")
            else:
                self.status_label.configure(text="未找到抓取文案记录", text_color="orange")
        except Exception as e:
            self.status_label.configure(text=f"同步失败: {e}", text_color="red")

    def _save_ai_prompt(self, prompt: str):
        """保存AI生成的提示词到文件"""
        try:
            output_dir = Path("./output")
            output_dir.mkdir(parents=True, exist_ok=True)
            prompt_file = output_dir / "ai_prompt.txt"
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"[保存AI提示词] 已保存到 {prompt_file} ({len(prompt)} 字符)")
        except Exception as e:
            print(f"[保存AI提示词] 失败: {e}")

    def _analyze_selling_points(self):
        """分析产品卖点"""
        raw_text = self.input_text.get("1.0", "end").strip()
        if not raw_text:
            self.status_label.configure(text="请输入或同步文案", text_color="red")
            return

        api_key = self.config.api_keys.openrouter_api_key
        if not api_key:
            self.status_label.configure(text="请先在配置页设置 OpenRouter API Key", text_color="red")
            return

        self.status_label.configure(text="正在分析卖点...", text_color="blue")

        threading.Thread(target=self._do_analyze_selling_points, args=(api_key, raw_text), daemon=True).start()

    def _do_analyze_selling_points(self, api_key, text):
        """执行卖点分析"""
        try:
            import requests

            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            prompt = f"""请分析以下电商产品文案，提取产品的核心卖点（Selling Points）。

要求：
1. 提取3-5个最重要的产品卖点
2. 每个卖点用一句话概括，突出产品优势
3. 卖点包括但不限于：材质优势、功能特点、设计亮点、性价比、适用场景等
4. 使用中文输出，简洁明了
5. 直接列出卖点，不要有前言或解释

格式示例：
• 卖点1：xxx
• 卖点2：xxx
• 卖点3：xxx

产品文案：
{text[:3000]}

请直接输出卖点："""

            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "你是电商产品分析专家，擅长提炼产品核心卖点。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 800,
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            result = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            # 显示结果
            self.after(0, lambda: self._on_selling_points_success(result))

        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"分析失败: {e}", text_color="red"))

    def _on_selling_points_success(self, result):
        """卖点分析成功回调"""
        self.selling_points_text.delete("1.0", "end")
        self.selling_points_text.insert("1.0", result)
        self.status_label.configure(text="卖点分析完成", text_color="green")

        # 保存到文件
        try:
            output_dir = Path("./output")
            output_dir.mkdir(parents=True, exist_ok=True)
            points_file = output_dir / "selling_points.txt"
            with open(points_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"[卖点分析] 已保存到 {points_file}")
        except Exception as e:
            print(f"[卖点分析] 保存失败: {e}")

    def _copy_selling_points(self):
        """复制卖点"""
        text = self.selling_points_text.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_label.configure(text="卖点已复制", text_color="green")

    def _sync_ai_prompt(self):
        """同步右侧AI生成的提示词到左侧输入框"""
        try:
            # 从右侧输出框获取AI生成的提示词
            ai_prompt = self.output_text.get("1.0", "end").strip()
            if ai_prompt:
                self.input_text.delete("1.0", "end")
                self.input_text.insert("1.0", ai_prompt)
                self.status_label.configure(text="已同步AI提示词", text_color="green")
            else:
                self.status_label.configure(text="右侧暂无AI提示词", text_color="orange")
        except Exception as e:
            self.status_label.configure(text=f"同步失败: {e}", text_color="red")
            
    def _paste_text(self):
        try:
            text = self.clipboard_get()
            self.input_text.insert("insert", text)
        except:
            pass
            
    def _copy_result(self):
        text = self.output_text.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_label.configure(text="结果已复制", text_color="green")
            
    def _start_analysis(self):
        """调用OpenRouter进行分析"""
        raw_text = self.input_text.get("1.0", "end").strip()
        if not raw_text:
            self.status_label.configure(text="请输入或同步文案", text_color="red")
            return
            
        api_key = self.config.api_keys.openrouter_api_key
        if not api_key:
            self.status_label.configure(text="请先在配置页设置 OpenRouter API Key", text_color="red")
            return
            
        self.analyze_btn.configure(state="disabled", text="分析中...")
        self.status_label.configure(text="正在分析文案...", text_color="blue")
        
        threading.Thread(target=self._do_analyze, args=(api_key, raw_text), daemon=True).start()
        
    def _do_analyze(self, api_key, text):
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            prompt = """
            请分析以下电商商品文案，提取关键视觉信息（主体、材质、颜色、风格、场景），并生成一段适用于 AI 绘画（如 Midjourney, Stable Diffusion）的英文提示词（Prompt）。
            
            要求：
            1. 提示词应包含：Subject（主体）, Medium（媒介/风格）, Environment（场景）, Lighting（光线）, Color（配色）, Composition（构图）。
            2. 移除所有品牌名称、水印文字、促销信息。
            3. 强调商品的高级感和质感。
            4. 直接输出英文提示词，不要包含解释。
            
            商品文案：
            """
            
            payload = {
                "model": "openai/gpt-4o-mini", # 使用性价比高的模型
                "messages": [
                    {"role": "system", "content": "You are an expert AI art prompt generator for e-commerce products."},
                    {"role": "user", "content": prompt + text[:3000]}, # 截断防止超长
                ]
            }
            
            import requests
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            
            data = resp.json()
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            self.after(0, lambda: self._on_success(result))
            
        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))
            
    def _on_success(self, result):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", result)
        self.analyze_btn.configure(state="normal", text="🚀 开始分析 & 生成提示词")
        self.status_label.configure(text="生成成功！", text_color="green")

        # 保存AI生成的提示词到文件
        self._save_ai_prompt(result)
        
    def _on_error(self, error):
        self.status_label.configure(text=f"错误: {error}", text_color="red")
        self.analyze_btn.configure(state="normal", text="🚀 开始分析 & 生成提示词")


class AutomationFrame(ctk.CTkFrame):
    """智能自动化页面"""

    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.output_dir = "./output"
        self.is_generating = False
        self.should_stop = False  # 停止标志
        self.current_step = 0  # 当前步骤
        self.total_steps = 4  # 总步骤数
        self.selected_main_image = None  # 选中的主图路径
        self.history_images = []  # 历史图库路径列表
        self.history_thumbnails = []  # 保持缩略图引用防止GC
        self.history_grid_row = 0  # 历史图库当前行
        self.history_grid_col = 0  # 历史图库当前列
        self._setup_ui()

    def _setup_ui(self):
        # 布局配置
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 主容器
        main_container = ctk.CTkFrame(self)
        main_container.grid(row=0, column=0, sticky="nsew", padx=Theme.PAD_L, pady=Theme.PAD_M)
        
        # 左右分栏
        main_container.grid_columnconfigure(0, weight=1) # 左侧：图片 (40%)
        main_container.grid_columnconfigure(1, weight=1) # 右侧：操作 (60%)
        main_container.grid_rowconfigure(0, weight=1)
        
        # === 左侧: 图片展示区 + API提示词 (左右布局) ===
        left_panel = ctk.CTkFrame(main_container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(Theme.PAD_M, Theme.PAD_S), pady=Theme.PAD_M)
        left_panel.grid_rowconfigure(0, weight=2) # 主图+API提示词区域
        left_panel.grid_rowconfigure(1, weight=1) # 结果图区域
        left_panel.grid_columnconfigure(0, weight=1)

        # === 主图 + API提示词 容器 (左右分栏) ===
        top_section = ctk.CTkFrame(left_panel)
        top_section.grid(row=0, column=0, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)
        top_section.grid_columnconfigure(0, weight=1)  # 主图
        top_section.grid_columnconfigure(1, weight=1)  # API提示词
        top_section.grid_rowconfigure(0, weight=1)

        # 1. 主图区域 (左侧)
        main_img_frame = ctk.CTkFrame(top_section)
        main_img_frame.grid(row=0, column=0, sticky="nsew", padx=(Theme.PAD_S, Theme.PAD_S // 2), pady=Theme.PAD_S)

        ctk.CTkLabel(main_img_frame, text="🖼 AI选择的主图", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=(Theme.PAD_S, 5))

        self.main_image_preview = ctk.CTkLabel(main_img_frame, text="等待AI识别主图...",
                                                  font=Theme.BODY_FONT, text_color="gray")
        self.main_image_preview.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=Theme.PAD_S)

        self.main_image_info = ctk.CTkLabel(main_img_frame, text="", font=Theme.SMALL_FONT, text_color="gray")
        self.main_image_info.pack(anchor="w", padx=Theme.PAD_S, pady=(0, Theme.PAD_S))

        # 主图按钮
        main_btn_row = ctk.CTkFrame(main_img_frame, fg_color="transparent")
        main_btn_row.pack(fill="x", padx=Theme.PAD_S, pady=Theme.PAD_S)
        self.download_main_btn = ctk.CTkButton(main_btn_row, text="⬇ 下载", height=28, width=80, font=Theme.SMALL_FONT,
                                              command=lambda: self._download_image("main"), state="disabled")
        self.download_main_btn.pack(side="left", padx=(0, 5))
        self.open_main_folder_btn = ctk.CTkButton(main_btn_row, text="📁 打开文件夹", height=28, width=100, font=Theme.SMALL_FONT,
                                                  command=lambda: self._open_image_folder("main"), state="disabled", fg_color="gray")
        self.open_main_folder_btn.pack(side="left")

        # 2. API提示词显示区域 (右侧)
        api_prompt_frame = ctk.CTkFrame(top_section)
        api_prompt_frame.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_S // 2, Theme.PAD_S), pady=Theme.PAD_S)

        ctk.CTkLabel(api_prompt_frame, text="📝 API提示词 (只读)", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=(Theme.PAD_S, 5))
        self.used_prompt_display = ctk.CTkTextbox(api_prompt_frame, font=Theme.BODY_FONT, fg_color="#2b2b2b", state="disabled")
        self.used_prompt_display.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=(0, Theme.PAD_S))

        # 3. 结果图 + 历史图库区域 (下方，左右分栏)
        result_section = ctk.CTkFrame(left_panel)
        result_section.grid(row=1, column=0, sticky="nsew", padx=Theme.PAD_S, pady=Theme.PAD_S)
        result_section.grid_columnconfigure(0, weight=1)  # 结果图
        result_section.grid_columnconfigure(1, weight=1)  # 历史图库
        result_section.grid_rowconfigure(0, weight=1)

        # 3a. 结果图 (左侧)
        result_img_frame = ctk.CTkFrame(result_section)
        result_img_frame.grid(row=0, column=0, sticky="nsew", padx=(Theme.PAD_S, Theme.PAD_S // 2), pady=Theme.PAD_S)

        ctk.CTkLabel(result_img_frame, text="✨ 生成结果图", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=(Theme.PAD_S, 5))

        self.result_image_preview = ctk.CTkLabel(result_img_frame, text="等待生成...",
                                                   font=Theme.BODY_FONT, text_color="gray")
        self.result_image_preview.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=Theme.PAD_S)

        self.result_image_info = ctk.CTkLabel(result_img_frame, text="", font=Theme.SMALL_FONT, text_color="gray")
        self.result_image_info.pack(anchor="w", padx=Theme.PAD_S, pady=(0, Theme.PAD_S))

        # 结果图按钮
        result_btn_row = ctk.CTkFrame(result_img_frame, fg_color="transparent")
        result_btn_row.pack(fill="x", padx=Theme.PAD_S, pady=Theme.PAD_S)
        self.download_result_btn = ctk.CTkButton(result_btn_row, text="⬇ 下载", height=28, width=80, font=Theme.SMALL_FONT,
                                                command=lambda: self._download_image("result"), state="disabled")
        self.download_result_btn.pack(side="left", padx=(0, 5))
        self.open_result_folder_btn = ctk.CTkButton(result_btn_row, text="📁 打开文件夹", height=28, width=100, font=Theme.SMALL_FONT,
                                                    command=lambda: self._open_image_folder("result"), state="disabled", fg_color="gray")
        self.open_result_folder_btn.pack(side="left")

        # 3b. 历史图库 (右侧)
        history_frame = ctk.CTkFrame(result_section)
        history_frame.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_S // 2, Theme.PAD_S), pady=Theme.PAD_S)

        ctk.CTkLabel(history_frame, text="📚 历史图库", font=Theme.BODY_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=(Theme.PAD_S, 5))

        self.history_scroll = ctk.CTkScrollableFrame(history_frame, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=(0, Theme.PAD_S))
        # 配置2列网格
        self.history_scroll.grid_columnconfigure(0, weight=1)
        self.history_scroll.grid_columnconfigure(1, weight=1)


        # === 右侧: 配置与操作区 (可滚动) ===
        right_panel = ctk.CTkScrollableFrame(main_container, label_text="🚀 智能自动化配置")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_S, Theme.PAD_M), pady=Theme.PAD_M)
        
        # 1. URL & Engine
        config_group = ctk.CTkFrame(right_panel)
        config_group.pack(fill="x", padx=Theme.PAD_S, pady=Theme.PAD_S)
        
        ctk.CTkLabel(config_group, text="1. 产品链接", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=(Theme.PAD_S, 2))
        self.auto_url_entry = ctk.CTkEntry(config_group, height=Theme.ENTRY_HEIGHT, placeholder_text="1688商品链接...")
        self.auto_url_entry.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))
        
        ctk.CTkLabel(config_group, text="2. 生成引擎", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=(Theme.PAD_S, 2))
        engine_row = ctk.CTkFrame(config_group, fg_color="transparent")
        engine_row.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))
        self.auto_engine_var = ctk.StringVar(value="comfyui")
        self.engine_label_to_value = {
            "🧩 ComfyUI": "comfyui",
            "⚡ Nano": "nano_banana",
            "🚀 Nano Pro": "nano_banana_pro",
        }
        self.engine_value_to_label = {v: k for k, v in self.engine_label_to_value.items()}
        self.auto_engine_display_var = ctk.StringVar(
            value=self.engine_value_to_label[self.auto_engine_var.get()]
        )

        self.auto_engine_segment = ctk.CTkSegmentedButton(
            engine_row,
            values=list(self.engine_label_to_value.keys()),
            variable=self.auto_engine_display_var,
            command=self._on_engine_segment_change,
            height=38,
            corner_radius=10,
            font=Theme.BODY_FONT,
            selected_color="#1a73e8",
            selected_hover_color="#1666c1",
            unselected_color="#2f333a",
            unselected_hover_color="#3a4048",
            text_color="#f5f7fa",
            dynamic_resizing=False,
        )
        self.auto_engine_segment.pack(fill="x")

        # ComfyUI 工作流选择 (初始隐藏)
        self.comfyui_workflow_frame = ctk.CTkFrame(config_group, fg_color="transparent")
        # 不pack，初始隐藏

        ctk.CTkLabel(self.comfyui_workflow_frame, text="ComfyUI 工作流",
                     font=Theme.BODY_FONT).pack(side="left", padx=(0, 10))

        # 从配置中获取工作流列表
        workflow_options = self.config.comfyui.list_workflows()
        current_workflow = self.config.comfyui.current_workflow

        # 设置默认值（如果有配置的工作流，使用第一个；否则使用占位符）
        default_workflow = current_workflow if current_workflow in workflow_options else (workflow_options[0] if workflow_options else "请先配置工作流")

        self.comfyui_workflow_var = ctk.StringVar(value=default_workflow)
        self.comfyui_workflow_dropdown = ctk.CTkOptionMenu(
            self.comfyui_workflow_frame,
            variable=self.comfyui_workflow_var,
            values=workflow_options if workflow_options else ["请先配置工作流"],
            width=200,
            height=32,
            corner_radius=8,
            font=Theme.BODY_FONT,
            dropdown_font=Theme.BODY_FONT,
            fg_color="#2D2D2D",
            text_color="#FFFFFF",
            button_color="#3D3D3D",
            button_hover_color="#4D4D4D",
            dropdown_fg_color="#2D2D2D",
            dropdown_hover_color="#3D3D3D",
            dropdown_text_color="#FFFFFF",
            command=self._on_workflow_change
        )
        self.comfyui_workflow_dropdown.pack(side="left")
            
        # 3. 手动提示词 (可选)
        prompt_group = ctk.CTkFrame(right_panel)
        prompt_group.pack(fill="x", padx=Theme.PAD_S, pady=Theme.PAD_S)

        ctk.CTkLabel(prompt_group, text="3. 手动提示词 (可选 - 覆盖AI逻辑)", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=(Theme.PAD_S, 2))
        self.manual_prompt_text = ctk.CTkTextbox(prompt_group, height=80, font=Theme.BODY_FONT, fg_color=Theme.COLOR_INPUT_BG)
        self.manual_prompt_text.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))

        # 4. 操作按钮
        action_group = ctk.CTkFrame(right_panel)
        action_group.pack(fill="x", padx=Theme.PAD_S, pady=Theme.PAD_S)

        ctk.CTkLabel(action_group, text="4. 执行操作", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_M, pady=(Theme.PAD_S, 5))

        # ComfyUI 专属操作行 (初始隐藏)
        self.comfyui_action_row = ctk.CTkFrame(action_group, fg_color="transparent")
        # 不pack，初始隐藏

        self.comfyui_start_btn = ctk.CTkButton(
            self.comfyui_action_row,
            text="🚀 ComfyUI 开始生成",
            height=45,
            width=200,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=self._comfyui_start_generate,
            fg_color="#4CAF50",
            hover_color="#45A049"
        )
        self.comfyui_start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            self.comfyui_action_row,
            text="⏹ 停止",
            height=45,
            width=100,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=self._stop_generation,
            fg_color="#dc3545",
            state="disabled"
        )
        self.stop_btn.pack(side="left")

        # Nano/Nano Pro 操作行
        self.nano_action_row = ctk.CTkFrame(action_group, fg_color="transparent")
        self.nano_action_row.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))

        self.normal_generate_btn = ctk.CTkButton(
            self.nano_action_row,
            text="🚀 开始生成",
            height=40,
            width=140,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=lambda: self._auto_generate(mode="normal"),
            fg_color="#4CAF50",
            hover_color="#45A049"
        )
        self.normal_generate_btn.pack(side="left", padx=(0, 10))

        self.bg_replace_btn = ctk.CTkButton(
            self.nano_action_row,
            text="✨ 背景替换",
            height=40,
            width=160,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=lambda: self._auto_generate(mode="bg_replace"),
            fg_color="#1a73e8"
        )
        self.bg_replace_btn.pack(side="left", padx=(0, 10))

        self.model_on_product_btn = ctk.CTkButton(
            self.nano_action_row,
            text="👤 上模特身",
            height=40,
            width=160,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=lambda: self._auto_generate(mode="model_on_product"),
            fg_color="#9333ea"
        )
        self.model_on_product_btn.pack(side="left", padx=(0, 10))

        self.nano_stop_btn = ctk.CTkButton(
            self.nano_action_row,
            text="⏹ 停止",
            height=40,
            width=100,
            corner_radius=8,
            font=Theme.HEADER_FONT,
            command=self._stop_generation,
            fg_color="#dc3545",
            state="disabled"
        )
        self.nano_stop_btn.pack(side="right")
        
        # 进度条
        self.progress_bar = ctk.CTkProgressBar(action_group, height=15)
        self.progress_bar.pack(fill="x", padx=Theme.PAD_M, pady=(10, 5))
        self.progress_bar.set(0)
        self.progress_label = ctk.CTkLabel(action_group, text="就绪", font=Theme.SMALL_FONT, text_color="gray")
        self.progress_label.pack(anchor="e", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))

        # 4. 日志
        log_group = ctk.CTkFrame(right_panel)
        log_group.pack(fill="both", expand=True, padx=Theme.PAD_S, pady=Theme.PAD_S)
        
        ctk.CTkLabel(log_group, text="📜 执行日志", font=Theme.TITLE_FONT).pack(anchor="w", padx=Theme.PAD_S, pady=Theme.PAD_S)
        self.auto_log_area = ctk.CTkTextbox(log_group, height=200, font=Theme.LOG_FONT, state="disabled", fg_color=Theme.COLOR_INPUT_BG)
        self.auto_log_area.pack(fill="both", expand=True, padx=Theme.PAD_M, pady=(0, Theme.PAD_S))

        # Output info at bottom
        self.work_dir_label = ctk.CTkLabel(right_panel, text=f"工作目录: {Path(self.output_dir).name}", font=Theme.SMALL_FONT, text_color="gray")
        self.work_dir_label.pack(pady=5)
        
        # Init vars
        self.main_image_path = None
        self.result_image_path = None
        
        # Configure Log Tags
        self.auto_log_area.tag_config("info", foreground="#89c4f4")
        self.auto_log_area.tag_config("success", foreground="#4caf50")
        self.auto_log_area.tag_config("warning", foreground="#ffb84d")
        self.auto_log_area.tag_config("error", foreground="#ff6b6b")
        self.auto_log_area.tag_config("step", foreground="#e0e0e0")    # 亮灰色

        # 添加件迎信息
        self._auto_log("👋 件迎使用智能自动化功能！", "info")

        # 初始化引擎选择状态
        self._on_engine_change()
        self._auto_log("", "info")
        self._auto_log("自动化流程：", "step")
        self._auto_log("  1. 抓取1688产品信息和图片", "info")
        self._auto_log("  2. AI智能识别主图", "info")
        self._auto_log("  3. 生成AI提示词（背景替换会自动优化）", "info")
        self._auto_log("  4. 执行图生图", "info")
        self._auto_log("", "info")
        self._auto_log("⚡ 实时显示：执行进度、主图预览、文件路径", "info")

        # 加载历史图库
        self._load_history_images()

    def _auto_log(self, message: str, level: str = "info"):
        """记录自动化日志"""
        self.auto_log_area.configure(state="normal")
        self.auto_log_area.insert("end", message + "\n", level)
        self.auto_log_area.see("end")
        self.auto_log_area.configure(state="disabled")

        # 同步写入文件日志
        try:
            from utils.logger import log_info, log_warning, log_error, log_debug
            file_msg = f"[自动化] {message}"
            if level == "error":
                log_error(file_msg)
            elif level == "warning":
                log_warning(file_msg)
            else:
                log_info(file_msg)
        except Exception:
            pass

    def _update_progress(self, step: int, step_name: str):
        """更新进度条"""
        self.current_step = step
        progress = step / self.total_steps
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"步骤 {step}/{self.total_steps}: {step_name}")

        # 完成时变绿色
        if step == self.total_steps:
            self.progress_bar.configure(progress_color=("#4caf50"))  # 绿色
            self.progress_label.configure(text=f"✅ 完成！步骤 {step}/{self.total_steps}: {step_name}", text_color="#4caf50")
        else:
            self.progress_bar.configure(progress_color=("#1a73e8"))  # 蓝色（默认）
            self.progress_label.configure(text=f"步骤 {step}/{self.total_steps}: {step_name}", text_color="gray")

    def _update_process_info(self, info: str):
        """更新进程说明"""
        self.process_info.configure(text=f"⚡ {info}")

    def _update_process_info(self, info: str):
        """更新进程说明"""
        self.process_info.configure(text=f"⚡ {info}")

    def _on_engine_segment_change(self, selected_label: str):
        """分段按钮切换到内部引擎值"""
        selected_engine = self.engine_label_to_value.get(selected_label, "comfyui")
        self.auto_engine_var.set(selected_engine)
        self._on_engine_change()

    def _on_engine_change(self):
        """引擎切换回调"""
        selected_engine = self.auto_engine_var.get()

        # 当内部值变化时，同步分段按钮显示
        if hasattr(self, "auto_engine_display_var") and hasattr(self, "engine_value_to_label"):
            label = self.engine_value_to_label.get(selected_engine)
            if label and self.auto_engine_display_var.get() != label:
                self.auto_engine_display_var.set(label)

        if selected_engine == "comfyui":
            # 显示ComfyUI工作流下拉菜单和专属按钮
            self.comfyui_workflow_frame.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))
            self.comfyui_action_row.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))
            # 隐藏Nano操作行
            self.nano_action_row.pack_forget()
        else:
            # 隐藏ComfyUI工作流和专属按钮
            self.comfyui_workflow_frame.pack_forget()
            self.comfyui_action_row.pack_forget()
            # 显示Nano操作行
            self.nano_action_row.pack(fill="x", padx=Theme.PAD_M, pady=(0, Theme.PAD_S))

    def _on_workflow_change(self, choice):
        """工作流切换回调 - 更新配置"""
        self.config.comfyui.set_current_workflow(choice)

    def _comfyui_start_generate(self):
        """ComfyUI专属的开始生成方法"""
        workflow = self.comfyui_workflow_var.get()

        # 检查是否选择了有效工作流
        if not workflow or workflow == "请先配置工作流":
            self._auto_log("⚠️ 请先在配置页添加ComfyUI工作流", "warning")
            return

        # 使用工作流名称作为模式
        self._auto_generate(mode=workflow)

    def _stop_generation(self):
        """停止生成"""
        if self.is_generating:
            self.should_stop = True
            self._auto_log("\n⏹ 正在停止...", "warning")
            # 禁用所有停止按钮
            if hasattr(self, 'stop_btn'):
                self.stop_btn.configure(state="disabled")
            if hasattr(self, 'nano_stop_btn'):
                self.nano_stop_btn.configure(state="disabled")

    def _display_main_image(self, image_path: str):
        """显示主图"""
        try:
            from PIL import Image
            img = Image.open(image_path)
            img.thumbnail((300, 300))
            photo = ctk.CTkImage(img, size=(280, 280))
            self.main_image_preview.configure(image=photo, text="")
            self.main_image_preview.image = photo

            # 显示图片信息
            filename = Path(image_path).name
            self.main_image_info.configure(text=f"✓ {filename}")

            # 保存路径并启用按钮
            self.main_image_path = image_path
            self.download_main_btn.configure(state="normal")
            self.open_main_folder_btn.configure(state="normal")
        except Exception as e:
            self._auto_log(f"显示主图失败: {e}", "warning")
            self.main_image_preview.configure(text=f"加载失败: {str(e)}")
            self.main_image_info.configure(text="")

    def _display_result_image(self, result_path: str):
        """显示生成结果图"""
        try:
            from PIL import Image
            img = Image.open(result_path)
            orig_w, orig_h = img.size
            img.thumbnail((600, 600))
            photo = ctk.CTkImage(img, size=(500, 500))
            self.result_image_preview.configure(image=photo, text="")
            self.result_image_preview.image = photo

            # 显示图片详细信息（文件名 | 尺寸 | 文件大小）
            filename = Path(result_path).name
            file_size = Path(result_path).stat().st_size
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f}MB"
            else:
                size_str = f"{file_size / 1024:.1f}KB"
            self.result_image_info.configure(text=f"{filename} | {orig_w}x{orig_h} | {size_str}")
            self._auto_log(f"  📁 结果图: {result_path}", "info")

            # 保存路径并启用按钮
            self.result_image_path = result_path
            self.download_result_btn.configure(state="normal")
            self.open_result_folder_btn.configure(state="normal")

            # 添加到历史图库
            self._add_to_history(result_path)
        except Exception as e:
            self._auto_log(f"显示结果图失败: {e}", "warning")
            self.result_image_preview.configure(text=f"加载失败: {str(e)}")
            self.result_image_info.configure(text="")

    def _add_to_history(self, result_path: str):
        """将图片添加到历史图库"""
        try:
            result_path = str(Path(result_path).resolve())
            if result_path in self.history_images:
                return
            self.history_images.append(result_path)

            from PIL import Image
            img = Image.open(result_path)
            img.thumbnail((160, 160))
            thumb = ctk.CTkImage(img, size=(130, 130))
            self.history_thumbnails.append(thumb)

            item = ctk.CTkButton(
                self.history_scroll, image=thumb, text="",
                width=140, height=140, fg_color="#2b2b2b",
                hover_color="#3a3a3a", corner_radius=6,
                command=lambda p=result_path: self._on_history_click(p)
            )
            item.grid(row=self.history_grid_row, column=self.history_grid_col,
                      padx=3, pady=3, sticky="nsew")
            self.history_grid_col += 1
            if self.history_grid_col >= 2:
                self.history_grid_col = 0
                self.history_grid_row += 1
        except Exception as e:
            print(f"添加历史图库失败: {e}")

    def _on_history_click(self, path: str):
        """点击历史缩略图时显示该图"""
        if Path(path).exists():
            self._display_result_image(path)

    def _load_history_images(self):
        """启动时扫描output目录加载已有图片"""
        try:
            output_path = Path(self.output_dir)
            if not output_path.exists():
                return
            exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
            images = []
            for f in output_path.rglob("*"):
                if f.suffix.lower() in exts and f.is_file():
                    images.append(f)
            images.sort(key=lambda x: x.stat().st_mtime)
            for img_path in images[-30:]:
                self._add_to_history(str(img_path))
        except Exception as e:
            print(f"加载历史图库失败: {e}")

    def _download_image(self, image_type: str):
        """下载图片"""
        import shutil

        image_path = self.main_image_path if image_type == "main" else self.result_image_path
        if not image_path or not Path(image_path).exists():
            self._auto_log("⚠️ 图片路径不存在", "warning")
            return

        try:
            # 直接复制到用户选择的目录
            import tkinter as tk
            from tkinter import filedialog

            # 贴建临时的Tk窗口用于对话框
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            # 获取图片所在目录作为初始目录
            initial_dir = str(Path(image_path).parent)

            file_path = filedialog.asksaveasfilename(
                parent=root,
                initialdir=initial_dir,
                initialfile=Path(image_path).name,
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("JPG", "*.jpg"), ("All Files", "*.*")]
            )
            root.destroy()

            if file_path:
                shutil.copy2(image_path, file_path)
                self._auto_log(f"✓ 图片已下载到: {file_path}", "success")
        except Exception as e:
            import traceback
            self._auto_log(f"❌ 下载失败: {e}", "error")
            self._auto_log(f"详细错误: {traceback.format_exc()}", "error")

    def _open_image_folder(self, image_type: str):
        """打开图片所在文件夹"""
        image_path = self.main_image_path if image_type == "main" else self.result_image_path
        if not image_path or not Path(image_path).exists():
            self._auto_log("⚠️ 图片路径不存在", "warning")
            return

        try:
            folder_path = str(Path(image_path).parent.absolute())

            # 使用explorer命令打开文件夹并选中文件（Windows）
            import subprocess
            import platform

            if platform.system() == "Windows":
                # 使用explorer命令打开文件夹并选中文件
                subprocess.run(['explorer', '/select,', image_path], shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])

            self._auto_log(f"✓ 已打开文件夹: {folder_path}", "success")
        except Exception as e:
            import traceback
            self._auto_log(f"❌ 打开文件夹失败: {e}", "error")
            self._auto_log(f"详细错误: {traceback.format_exc()}", "error")

    def _auto_generate(self, mode: str):
        """自动化生成主流程"""
        url = self.auto_url_entry.get().strip()
        if not url:
            self._auto_log("⚠️ 请先输入1688产品链接", "warning")
            return

        # 重置状态
        self.should_stop = False
        self.selected_main_image = None

        if mode == "bg_replace":
            mode_name = "背景替换"
        elif mode == "model_on_product":
            mode_name = "产品上模特身"
        else:
            mode_name = "常规生成"
        engine = self.auto_engine_var.get()
        self._auto_log(f"\n{'='*60}", "step")
        self._auto_log(f"🚀 开始自动化流程: {mode_name}", "info")
        self._auto_log(f"📋 当前配置:", "info")
        self._auto_log(f"  • 自动化模式: {mode_name}", "info")
        self._auto_log(f"  • 生成引擎: {engine}", "info")
        self._auto_log(f"  • 工作目录: {Path(self.output_dir).absolute()}", "info")
        self._auto_log(f"{'='*60}\n", "step")

        self._set_generating(True)

        def run_auto():
            import traceback
            import json

            try:
                # ========== 步骤1: 抓取1688产品信息和图片 ==========
                self.after(0, lambda: self._update_progress(1, "抓取1688产品信息"))
                self.after(0, lambda: self._update_process_info("正在抓取1688产品信息..."))
                self._auto_log("📥 步骤1: 抓取1688产品信息...", "step")

                # 检查停止标志
                if self.should_stop:
                    self._auto_log("\n⏹ 用户停止执行", "warning")
                    return

                from scraper import AlibabaScraper, ImageDownloader, TextExtractor

                scraper = AlibabaScraper(headless=True, timeout=120)
                product = scraper.scrape_product(url)

                self.after(0, lambda: self._update_process_info(f"产品: {product.title[:30]}..."))
                self._auto_log(f"  ✓ 产品标题: {product.title[:50]}...", "success")

                # 保存抓取的信息
                extractor = TextExtractor("./output")
                extractor.from_product_data(scraper.get_product_text())
                extractor.save_all()

                self._auto_log(f"  ✓ 文案已保存到 output/product_info.txt", "success")

                # 下载图片
                downloader = ImageDownloader("./output/images")
                downloader.clear_output_dir()

                all_images = product.main_images + product.detail_images
                main_results = downloader.download_main_images(product.main_images)
                detail_results = downloader.download_detail_images(product.detail_images) if product.detail_images else []
                all_results = main_results + detail_results

                main_image_path = all_results[0][1] if all_results else None

                self.after(0, lambda: self._update_process_info(f"已下载 {len(all_results)} 张图片"))
                self._auto_log(f"  ✓ 下载完成: 主图{len(main_results)}张, 详情图{len(detail_results)}张", "success")
                self._auto_log(f"  📁 图片保存位置: {Path('./output/images').absolute()}", "info")

                # ========== 步骤2: 识别主图 ==========
                self.after(0, lambda: self._update_progress(2, "AI识别主图"))
                self.after(0, lambda: self._update_process_info("AI正在识别主图..."))
                self._auto_log("\n🔍 步骤2: AI识别主图...", "step")

                # 检查停止标志
                if self.should_stop:
                    self._auto_log("\n⏹ 用户停止执行", "warning")
                    return

                api_key = self.config.api_keys.openrouter_api_key
                if not api_key:
                    raise ValueError("请在配置页填写 OpenRouter API Key")

                import requests
                identify_url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                identify_prompt = f"""请分析以下电商产品图片，识别哪张图片是主图（产品图）。

产品信息：
标题: {product.title}

要求：
1. 返回主图的文件名（不含路径）
2. 只返回JSON格式，不要其他解释
3. 返回格式: {{"main_image": "文件名"}} 或 {{"main_image": "none"}}

图片列表：
{chr(10).join([f"- {os.path.basename(p[1])}" for p in all_results[:5]])}
...

请直接返回JSON结果。"""

                payload = {
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是图片分析助手，只返回JSON格式结果。"},
                        {"role": "user", "content": identify_prompt},
                    ],
                    "max_tokens": 200,
                }

                self._auto_log(f"  → 调用 OpenRouter API...", "info")
                resp = requests.post(identify_url, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                output_tokens = data.get("usage", {}).get("completion_tokens", 0)
                total_tokens = input_tokens + output_tokens

                self._auto_log(f"  ✓ API响应: {input_tokens}输入 + {output_tokens}输出 = {total_tokens}总计tokens", "success")

                main_image_filename = "none"
                try:
                    if "{" in content:
                        result = json.loads(content)
                        main_image_filename = result.get("main_image", "none")
                except json.JSONDecodeError as e:
                    self._auto_log(f"  ⚠ JSON解析失败: {e}", "warning")

                self._auto_log(f"  ✓ 识别结果: {main_image_filename}", "success")

                final_main_image = None
                if main_image_filename != "none":
                    for result in all_results:
                        if os.path.basename(result[1]) == main_image_filename:
                            final_main_image = result[1]
                            break

                if not final_main_image:
                    final_main_image = main_image_path
                    self._auto_log(f"  ⚠ 使用第一张图片作为主图", "warning")

                # 显示主图
                self.selected_main_image = final_main_image
                self.after(0, lambda: self._display_main_image(final_main_image))
                self._auto_log(f"  📁 主图路径: {final_main_image}", "info")

                # ========== 步骤3: AI处理文案（背景替换专用） ==========
                self.after(0, lambda: self._update_progress(3, "AI优化提示词"))
                self.after(0, lambda: self._update_process_info("AI正在优化提示词..."))
                self._auto_log("\n✍️ 步骤3: AI优化提示词...", "step")

                # 检查停止标志
                if self.should_stop:
                    self._auto_log("\n⏹ 用户停止执行", "warning")
                    return

                raw_text = extractor.copywriting.combined_copywriting.strip()
                manual_prompt = self.manual_prompt_text.get("1.0", "end").strip()

                # 初始化变量
                prompt_input_tokens = 0
                prompt_output_tokens = 0

                if manual_prompt:
                    final_prompt = manual_prompt
                    self._auto_log("  ✓ 使用手动提示词，跳过自动优化流程", "success")

                elif mode == "bg_replace":
                    # 背景替换模式：使用AI提取场景描述，去除产品描述
                    self._auto_log("  → 调用AI提取场景描述（去除产品描述）...", "info")

                    api_key = self.config.api_keys.openrouter_api_key
                    if not api_key:
                        raise ValueError("请在配置页填写 OpenRouter API Key")

                    import requests
                    prompt_url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }

                    # 构建提示词：要求AI只保留场景描述，去除产品本身描述
                    scene_prompt = f"""请分析以下商品文案，提取其中适合作为AI绘画背景的场景描述。

要求：
1. 只保留场景、环境、氛围、光线等背景相关的描述
2. 去除产品本身的描述（如颜色、尺寸、材质等）
3. 去除品牌、规格参数等信息
4. 输出为简洁的英文场景描述，适合用于AI绘画提示词
5. 直接输出场景描述，不要有任何解释或前言

商品文案：
{raw_text[:2000]}

请直接输出场景描述："""

                    payload = {
                        "model": "openai/gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "你是AI绘画提示词专家，擅长从商品文案中提取场景描述。"},
                            {"role": "user", "content": scene_prompt},
                        ],
                        "max_tokens": 500,
                    }

                    resp = requests.post(prompt_url, headers=headers, json=payload, timeout=60)
                    resp.raise_for_status()
                    prompt_data = resp.json()

                    scene_description = prompt_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                    # 记录Token消耗
                    prompt_input_tokens = prompt_data.get("usage", {}).get("prompt_tokens", 0)
                    prompt_output_tokens = prompt_data.get("usage", {}).get("completion_tokens", 0)
                    prompt_total_tokens = prompt_input_tokens + prompt_output_tokens

                    self._auto_log(f"  ✓ AI处理完成: {prompt_input_tokens}输入 + {prompt_output_tokens}输出 = {prompt_total_tokens}总计tokens", "success")
                    self._auto_log(f"  ✓ 提取的场景描述: {scene_description[:100]}...", "success")

                    # 使用AI提取的场景描述作为最终提示词
                    final_prompt = f"Background replacement: {scene_description}"
                    self._auto_log(f"  ✓ 模式: 背景替换（使用AI优化的场景描述）", "success")

                elif mode == "model_on_product":
                    # 产品上模特身模式：直接使用原始文案
                    final_prompt = f"Product placed on model, background: {raw_text[:800]}"
                    self._auto_log(f"  ✓ 模式: 产品上模特身（使用原始文案）", "success")
                else:
                    raise ValueError("常规生成模式请先填写手动提示词；不填写时请使用“背景替换”或“上模特身”。")

                # 显示最终使用的AI提示词
                self.after(0, lambda: self.used_prompt_display.configure(state="normal"))
                self.after(0, lambda: self.used_prompt_display.delete("1.0", "end"))
                self.after(0, lambda: self.used_prompt_display.insert("1.0", final_prompt))
                self.after(0, lambda: self.used_prompt_display.configure(state="disabled"))

                output_dir = Path("./output")
                output_dir.mkdir(parents=True, exist_ok=True)
                prompt_file = output_dir / "auto_prompt.txt"
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(final_prompt)

                self._auto_log(f"  ✓ 提示词已保存 (长度: {len(final_prompt)}字符)", "success")
                self._auto_log(f"  📁 提示词路径: {prompt_file.absolute()}", "info")

                # ========== 步骤4: 执行图生图 ==========
                self.after(0, lambda: self._update_progress(4, "执行图生图"))
                self.after(0, lambda: self._update_process_info(f"正在调用 {engine} API..."))
                self._auto_log("\n🎨 步骤4: 执行图生图...", "step")

                # 检查停止标志
                if self.should_stop:
                    self._auto_log("\n⏹ 用户停止执行", "warning")
                    return

                gen_mode = self.auto_engine_var.get()
                self._auto_log(f"  → 使用引擎: {gen_mode}", "info")

                if gen_mode == "comfyui":
                    from image_generation import ComfyUIFluxKontextClient
                    server = self.config.comfyui.get_effective_server_url()
                    if not server:
                        raise ValueError("请在配置页填写 ComfyUI 服务器地址")
                    client = ComfyUIFluxKontextClient(server)

                    # 加载工作流配置
                    workflow_name = self.comfyui_workflow_var.get() if hasattr(self, 'comfyui_workflow_var') else None
                    if not workflow_name and hasattr(self, 'gen_workflow_var'):
                        workflow_name = self.gen_workflow_var.get()
                    if workflow_name and self.config.comfyui.workflows.get(workflow_name):
                        wf = self.config.comfyui.get_workflow(workflow_name)
                        client.set_workflow(
                            wf["json"], wf["prompt_node_id"], wf["prompt_param_path"],
                            wf.get("image_node_id"), wf.get("image_param_path")
                        )
                        self._auto_log(f"  → 使用工作流: {workflow_name}", "info")

                    self._auto_log(f"  → 调用 ComfyUI (云端)...", "info")
                    result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)

                elif gen_mode == "nano_banana":
                    from image_generation import NanoBananaBasicClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=False)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana API Key）")
                    client = NanoBananaBasicClient(api_key)
                    self._auto_log(f"  → 调用 Nano Banana 图生图 API...", "info")
                    result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)

                elif gen_mode == "nano_banana_pro":
                    from image_generation import NanoBananaProClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")
                    client = NanoBananaProClient(api_key)
                    self._auto_log(f"  → 调用 Nano Banana Pro API...", "info")
                    result = client.image_to_image(final_main_image, final_prompt, output_dir=self.output_dir)

                else:
                    raise ValueError(f"不支持的生成引擎: {gen_mode}")

                self._auto_log(f"  ✓ 图生图执行完成", "success")

                # 显示结果图
                if result and Path(result).exists():
                    self.after(0, lambda r=result: self._display_result_image(r))

                # ========== 完成 ==========
                self.after(0, lambda: self._update_progress(4, "完成"))
                self.after(0, lambda: self._update_process_info("✅ 全部完成！"))
                self._auto_log(f"\n{'='*60}", "step")
                self._auto_log(f"✅ 自动化流程完成！", "success")

                # 统计Token消耗
                if mode == "bg_replace":
                    total_input = input_tokens + prompt_input_tokens
                    total_output = output_tokens + prompt_output_tokens
                    grand_total = total_input + total_output
                    self._auto_log(f"📊 Token统计:", "info")
                    self._auto_log(f"  • 识别主图: {input_tokens}输入 + {output_tokens}输出 = {input_tokens + output_tokens}", "info")
                    self._auto_log(f"  • 优化提示词: {prompt_input_tokens}输入 + {prompt_output_tokens}输出 = {prompt_total_tokens}", "info")
                    self._auto_log(f"  • 总计: {total_input}输入 + {total_output}输出 = {grand_total}tokens", "info")
                else:
                    self._auto_log(f"📊 Token统计: {input_tokens}输入 + {output_tokens}输出 = {total_tokens}总计", "info")

                self._auto_log(f"📁 工作目录: {Path(self.output_dir).absolute()}", "info")
                self._auto_log(f"📁 主图: {final_main_image}", "info")
                self._auto_log(f"📁 提示词: {prompt_file.absolute()}", "info")
                if result:
                    self._auto_log(f"📁 结果图: {result}", "info")
                self._auto_log(f"{'='*60}\n", "step")

            except Exception as e:
                error_traceback = traceback.format_exc()
                self._auto_log(f"\n❌ 自动化失败", "error")
                self._auto_log(f"错误: {str(e)}", "error")
                self._auto_log(f"\n详细回溯:\n{error_traceback}", "error")
            finally:
                self.after(0, lambda: self._set_generating(False))

        threading.Thread(target=run_auto, daemon=True).start()

    def _set_generating(self, generating: bool):
        """设置生成状态"""
        self.is_generating = generating

        # Trigger automation glow on main app
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "start_automation_glow"):
                if generating:
                    app.start_automation_glow()
                else:
                    app.stop_automation_glow()
        except Exception as e:
            print(f"Failed to trigger automation glow: {e}")

        # 确保按钮状态被正确设置
        try:
            if generating:
                # 主生成按钮
                if hasattr(self, 'gen_btn'):
                    self.gen_btn.configure(state="disabled")
                # Nano模式按钮
                self.normal_generate_btn.configure(state="disabled")
                self.bg_replace_btn.configure(state="disabled")
                self.model_on_product_btn.configure(state="disabled")
                if hasattr(self, 'nano_stop_btn'):
                    self.nano_stop_btn.configure(state="normal", fg_color="#dc3545", hover_color="#c82333")
                # ComfyUI模式按钮
                if hasattr(self, 'comfyui_start_btn'):
                    self.comfyui_start_btn.configure(state="disabled")
                if hasattr(self, 'stop_btn'):
                    self.stop_btn.configure(state="normal", fg_color="#dc3545", hover_color="#c82333")
            else:
                # 主生成按钮 - 确保总是被重置
                if hasattr(self, 'gen_btn'):
                    self.gen_btn.configure(state="normal")
                # Nano模式按钮
                try:
                    self.normal_generate_btn.configure(state="normal")
                    self.bg_replace_btn.configure(state="normal")
                    self.model_on_product_btn.configure(state="normal")
                except:
                    pass
                if hasattr(self, 'nano_stop_btn'):
                    self.nano_stop_btn.configure(state="disabled", fg_color="#6c757d", hover_color="#5a6268")
                # ComfyUI模式按钮
                if hasattr(self, 'comfyui_start_btn'):
                    self.comfyui_start_btn.configure(state="normal")
                if hasattr(self, 'stop_btn'):
                    self.stop_btn.configure(state="disabled", fg_color="#6c757d", hover_color="#5a6268")

                if hasattr(self, 'current_step') and hasattr(self, 'total_steps') and hasattr(self, 'progress_label'):
                    if self.current_step < self.total_steps:
                        self.progress_label.configure(text=f"已停止 (步骤 {self.current_step}/{self.total_steps})")
        except Exception as e:
            print(f"Error setting button state: {e}")
            # 确保主按钮总是被重置
            if not generating and hasattr(self, 'gen_btn'):
                try:
                    self.gen_btn.configure(state="normal")
                except:
                    pass


class Text2ImageFrame(ctk.CTkFrame):
    """文生图页面 - 纯文字生成图片"""

    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.result_image_path = None
        self.result_original_size = (0, 0)
        self.output_dir = Path("output/text2image")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 图库相关属性
        self.gallery_images = []
        self.selected_images = set()
        self.gallery_check_vars = {}
        self.gallery_total_count = 0
        self._preview_window = None
        self._setup_ui()

    def _setup_ui(self):
        # 顶部标题
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(12, 6))
        ctk.CTkLabel(header, text="✨ 文生图", font=Theme.HEADER_FONT).pack(side="left", padx=10)

        # 打开输出文件夹按钮
        ctk.CTkButton(header, text="📁 打开输出文件夹", width=120,
                      command=self._open_output_folder).pack(side="right", padx=5)

        # 主内容区
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=10)
        main_container.grid_columnconfigure(0, weight=6)
        main_container.grid_columnconfigure(1, weight=7)
        main_container.grid_rowconfigure(0, weight=1)

        # 左侧：输入区
        left_panel = ctk.CTkFrame(main_container, fg_color=Theme.CARD_COLOR)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # 提示词输入
        ctk.CTkLabel(left_panel, text="📝 输入提示词", font=Theme.TITLE_FONT).pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(left_panel, text="描述你想生成的图片内容（支持中英文）",
                     font=Theme.SMALL_FONT, text_color="gray").pack(anchor="w", padx=15)

        self.prompt_input = ctk.CTkTextbox(
            left_panel,
            height=130,
            font=Theme.BODY_FONT,
            fg_color=Theme.COLOR_INPUT_BG,
            border_width=1,
            border_color="#334866",
            corner_radius=10
        )
        self.prompt_input.pack(fill="x", padx=15, pady=10)
        self.prompt_input.insert("1.0", "A beautiful sunset over the ocean, with orange and purple clouds")

        # 生成引擎选择
        engine_frame = ctk.CTkFrame(left_panel, fg_color="#243043", corner_radius=10)
        engine_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(
            engine_frame,
            text="生成引擎",
            font=Theme.BODY_FONT,
            text_color="#dce9ff"
        ).pack(side="left", padx=(10, 0))
        self.engine_display_to_key = {
            "Nano Banana 标准": "nano_banana",
            "Nano Banana Pro": "nano_banana_pro",
            "ComfyUI 工作流": "comfyui",
        }
        self.engine_var = ctk.StringVar(value="Nano Banana 标准")
        self.engine_menu = ctk.CTkOptionMenu(
            engine_frame,
            variable=self.engine_var,
            values=list(self.engine_display_to_key.keys()),
            width=250,
            height=36,
            font=Theme.SMALL_FONT,
            fg_color="#355f8a",
            button_color="#4a7cb0",
            button_hover_color="#5b8fc6",
            dropdown_fg_color="#202a38",
            dropdown_hover_color="#2e3d52",
            text_color="#eaf2ff",
            dynamic_resizing=False,
            corner_radius=8
        )
        self.engine_menu.pack(side="left", padx=10, pady=8)

        # 生成按钮（增强主操作视觉层级）
        self.gen_btn_shell = ctk.CTkFrame(
            left_panel,
            fg_color="#16263b",
            corner_radius=14,
            border_width=1,
            border_color="#3f6a97"
        )
        self.gen_btn_shell.pack(fill="x", padx=15, pady=(12, 10))

        self.gen_btn = ctk.CTkButton(
            self.gen_btn_shell,
            text="✨ 开始生成",
            height=52,
            font=("Segoe UI", 16, "bold"),
            corner_radius=11,
            command=self._start_generate,
            fg_color="#2488ff",
            hover_color="#3a99ff",
            border_width=1,
            border_color="#8cc3ff",
            text_color="#f6fbff"
        )
        self.gen_btn.pack(fill="x", padx=4, pady=4)

        self.gen_btn_hint = ctk.CTkLabel(
            left_panel,
            text="支持 Nano Banana / Nano Banana Pro / ComfyUI",
            font=Theme.SMALL_FONT,
            text_color="#86a6c8"
        )
        self.gen_btn_hint.pack(anchor="w", padx=18, pady=(0, 10))

        # 当前生成结果预览（从右侧调整到左侧）
        ctk.CTkLabel(left_panel, text="🖼️ 生成结果预览", font=Theme.TITLE_FONT).pack(
            anchor="w", padx=15, pady=(6, 5)
        )

        self.result_preview_frame = ctk.CTkFrame(
            left_panel,
            fg_color="#1a1a1a",
            corner_radius=8,
            border_width=1,
            border_color="#2f425f",
            height=320
        )
        self.result_preview_frame.pack(fill="both", expand=True, padx=15, pady=(0, 6))
        self.result_preview_frame.pack_propagate(False)
        self.result_preview_frame.grid_rowconfigure(0, weight=1)
        self.result_preview_frame.grid_columnconfigure(0, weight=1)

        self.result_label = ctk.CTkLabel(
            self.result_preview_frame,
            text="生成的图片将显示在这里",
            font=Theme.BODY_FONT,
            text_color="gray",
            anchor="center"
        )
        self.result_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.result_preview_frame.bind("<Configure>", self._on_result_preview_resize)

        # 结果详细信息
        self.result_meta_frame = ctk.CTkFrame(left_panel, fg_color="#2a2a2a", corner_radius=8)
        self.result_meta_frame.pack(fill="x", padx=15, pady=(0, 6))

        self.result_meta_line1 = ctk.CTkLabel(
            self.result_meta_frame, text="文件名: -", font=Theme.SMALL_FONT,
            text_color="#d0d0d0", anchor="w"
        )
        self.result_meta_line1.pack(fill="x", padx=10, pady=(5, 2))

        self.result_meta_line2 = ctk.CTkLabel(
            self.result_meta_frame, text="尺寸: -    体积: -    格式: -", font=Theme.SMALL_FONT,
            text_color="#a8b0b8", anchor="w"
        )
        self.result_meta_line2.pack(fill="x", padx=10, pady=(0, 5))

        # 结果操作按钮
        btn_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 12))

        self.save_btn = ctk.CTkButton(btn_frame, text="💾 另存为", width=100,
                                      command=self._save_result, state="disabled")
        self.save_btn.pack(side="left", padx=5)

        self.open_btn = ctk.CTkButton(btn_frame, text="📂 打开", width=100,
                                      command=self._open_result, state="disabled")
        self.open_btn.pack(side="left", padx=5)

        # 右侧：历史图库 + 日志
        right_panel = ctk.CTkFrame(main_container, fg_color=Theme.CARD_COLOR)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_panel.grid_rowconfigure(0, weight=0)  # 图库标题
        right_panel.grid_rowconfigure(1, weight=1)  # 图库区域
        right_panel.grid_rowconfigure(2, weight=0)  # 日志标题
        right_panel.grid_rowconfigure(3, weight=0)  # 日志区
        right_panel.grid_columnconfigure(0, weight=1)

        # ========== 图库区域 ==========
        gallery_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        gallery_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))

        ctk.CTkLabel(gallery_header, text="📚 历史图库", font=Theme.TITLE_FONT).pack(side="left")
        self.gallery_info_label = ctk.CTkLabel(gallery_header, text="已选 0/0",
                                                text_color="#9fb3c8", font=Theme.SMALL_FONT)
        self.gallery_info_label.pack(side="left", padx=(10, 0))

        # 图库操作按钮
        gallery_actions = ctk.CTkFrame(gallery_header, fg_color="transparent")
        gallery_actions.pack(side="right")

        ctk.CTkButton(gallery_actions, text="☑ 全选", width=70, font=Theme.SMALL_FONT,
                      command=self._select_all_gallery, fg_color="#455a64",
                      hover_color="#37474f").pack(side="left", padx=2)

        ctk.CTkButton(gallery_actions, text="☐ 取消", width=70, font=Theme.SMALL_FONT,
                      command=self._deselect_all_gallery, fg_color="#455a64",
                      hover_color="#37474f").pack(side="left", padx=2)

        ctk.CTkButton(gallery_actions, text="⬇ 下载", width=70, font=Theme.SMALL_FONT,
                      command=self._download_selected_gallery, fg_color="#1a73e8",
                      hover_color="#1666c1").pack(side="left", padx=2)

        ctk.CTkButton(gallery_actions, text="🗑 删除", width=70, font=Theme.SMALL_FONT,
                      command=self._delete_selected_gallery, fg_color="#9b2c2c",
                      hover_color="#7f1d1d").pack(side="left", padx=2)

        ctk.CTkButton(gallery_actions, text="🧹 清空", width=70, font=Theme.SMALL_FONT,
                      command=self._clear_all_gallery, fg_color="#7f1d1d",
                      hover_color="#5f1111").pack(side="left", padx=2)

        ctk.CTkButton(gallery_actions, text="🔄", width=40, font=Theme.SMALL_FONT,
                      command=self._load_gallery, fg_color="#455a64",
                      hover_color="#37474f").pack(side="left", padx=2)

        # 图库滚动区域
        self.gallery_scroll = ctk.CTkScrollableFrame(right_panel, fg_color="#1b1f26")
        self.gallery_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

        # 配置网格列
        for col in range(4):
            self.gallery_scroll.grid_columnconfigure(col, weight=1)

        # 日志区（移动到历史图库下方）
        ctk.CTkLabel(right_panel, text="📋 执行日志", font=Theme.BODY_FONT).grid(
            row=2, column=0, sticky="w", padx=15, pady=(2, 2)
        )
        self.log_box = ctk.CTkTextbox(
            right_panel,
            height=130,
            font=Theme.LOG_FONT,
            fg_color=Theme.COLOR_INPUT_BG,
            state="disabled"
        )
        self.log_box.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))

        # 加载图库
        self._load_gallery()

    def _log(self, message: str, level: str = "info"):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}.get(level, "")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {prefix} {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

        # 同步写入文件日志
        try:
            from utils.logger import log_info, log_warning, log_error, log_debug
            file_msg = f"[我的图库] {message}"
            if level == "error":
                log_error(file_msg)
            elif level == "warning":
                log_warning(file_msg)
            else:
                log_info(file_msg)
        except Exception:
            pass

    def _open_output_folder(self):
        """打开输出文件夹"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.output_dir))

    def _set_generate_btn_idle_style(self):
        """恢复生成按钮默认样式。"""
        self.gen_btn.configure(
            state="normal",
            text="✨ 开始生成",
            fg_color="#2488ff",
            hover_color="#3a99ff",
            border_color="#8cc3ff",
            text_color="#f6fbff"
        )
        if hasattr(self, "gen_btn_hint"):
            self.gen_btn_hint.configure(text="支持 Nano Banana / Nano Banana Pro / ComfyUI", text_color="#86a6c8")

    def _set_generate_btn_busy_style(self):
        """切换到生成中样式。"""
        self.gen_btn.configure(
            state="disabled",
            text="⏳ 生成中...",
            fg_color="#4b6483",
            hover_color="#4b6483",
            border_color="#6f89aa",
            text_color="#dce6f2"
        )
        if hasattr(self, "gen_btn_hint"):
            self.gen_btn_hint.configure(text="正在请求引擎并生成图片，请稍候...", text_color="#9eb5cf")

    def _start_generate(self):
        """开始生成"""
        prompt = self.prompt_input.get("1.0", "end").strip()
        if not prompt:
            self._log("请输入提示词", "error")
            return

        engine_display = self.engine_var.get()
        engine = self.engine_display_to_key.get(engine_display, engine_display)
        self._log(f"开始生成，引擎: {engine_display}", "info")
        self._set_generate_btn_busy_style()

        def do_generate():
            try:
                result = None
                if engine == "nano_banana":
                    from image_generation import NanoBananaBasicClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=False)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana API Key）")
                    client = NanoBananaBasicClient(api_key)
                    self.after(0, lambda: self._log("调用 Nano Banana API...", "info"))
                    result = client.generate(prompt, output_dir=str(self.output_dir))

                elif engine == "nano_banana_pro":
                    from image_generation import NanoBananaProClient
                    api_key = resolve_gemini_generation_key(self.config.api_keys, prefer_pro=True)
                    if not api_key:
                        raise ValueError("请在配置页设置 Gemini API Key（或 Nano Banana Pro API Key）")
                    client = NanoBananaProClient(api_key)
                    self.after(0, lambda: self._log("调用 Nano Banana Pro API...", "info"))
                    result = client.generate(prompt, output_dir=str(self.output_dir))

                elif engine == "comfyui":
                    from image_generation import ComfyUIClient
                    comfyui_url = self.config.api_keys.comfyui_url
                    if not comfyui_url:
                        raise ValueError("请在配置页设置 ComfyUI URL")
                    client = ComfyUIClient(comfyui_url)
                    self.after(0, lambda: self._log("调用 ComfyUI API...", "info"))
                    result = client.generate(prompt=prompt, output_dir=str(self.output_dir))
                else:
                    raise ValueError(f"未知引擎: {engine_display} ({engine})")

                # 处理返回结果 - 可能是字符串(路径)或字典
                if isinstance(result, str) and os.path.exists(result):
                    # NanoBanana 返回的是文件路径字符串
                    self.after(0, lambda p=result: self._on_complete(p))
                elif isinstance(result, dict) and result.get("success"):
                    image_path = result.get("image_path")
                    self.after(0, lambda p=image_path: self._on_complete(p))
                else:
                    error = result.get("error", "生成失败") if isinstance(result, dict) else "生成失败"
                    self.after(0, lambda err=error: self._on_error(err))

            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._on_error(msg))

        threading.Thread(target=do_generate, daemon=True).start()

    def _on_complete(self, image_path: str):
        """生成完成"""
        self.result_image_path = image_path
        self._log(f"生成成功: {image_path}", "success")
        self._set_generate_btn_idle_style()
        self.save_btn.configure(state="normal")
        self.open_btn.configure(state="normal")
        self._render_result_preview()
        self._update_result_meta()
        # 刷新图库
        self._load_gallery()

    def _on_error(self, error_msg: str):
        """生成失败"""
        self._log(f"生成失败: {error_msg}", "error")
        self._set_generate_btn_idle_style()

    def _format_size(self, size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        value = float(size_bytes)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{size_bytes} B"

    def _on_result_preview_resize(self, event=None):
        """右侧预览区尺寸变化时，重绘图片以尽量铺满。"""
        if self.result_image_path and os.path.exists(self.result_image_path):
            self._render_result_preview()

    def _render_result_preview(self):
        """按右侧容器可用空间渲染大图预览（保持比例）。"""
        if not self.result_image_path or not os.path.exists(self.result_image_path):
            return
        try:
            with Image.open(self.result_image_path) as img:
                self.result_original_size = img.size

                frame_w = max(self.result_preview_frame.winfo_width() - 20, 100)
                frame_h = max(self.result_preview_frame.winfo_height() - 20, 100)

                # 首次布局未完成时使用一个较大的兜底尺寸
                if frame_w <= 120 or frame_h <= 120:
                    frame_w, frame_h = 780, 640

                img_copy = img.copy()
                img_copy.thumbnail((frame_w, frame_h), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                self.result_label.configure(image=ctk_img, text="")
                self.result_label._ctk_image = ctk_img
        except Exception as e:
            self._log(f"无法加载预览: {e}", "warning")

    def _update_result_meta(self):
        """更新生成结果详细信息。"""
        if not self.result_image_path or not os.path.exists(self.result_image_path):
            self.result_meta_line1.configure(text="文件名: -")
            self.result_meta_line2.configure(text="尺寸: -    体积: -    格式: -")
            return

        path = Path(self.result_image_path)
        try:
            with Image.open(str(path)) as img:
                width, height = img.size
                fmt = (img.format or path.suffix.replace(".", "").upper() or "未知")
        except Exception:
            width, height = self.result_original_size
            fmt = (path.suffix.replace(".", "").upper() or "未知")

        size_text = self._format_size(path.stat().st_size)

        self.result_meta_line1.configure(text=f"文件名: {path.name}")
        self.result_meta_line2.configure(text=f"尺寸: {width} x {height}    体积: {size_text}    格式: {fmt}")

    def _save_result(self):
        """另存为"""
        if not self.result_image_path or not os.path.exists(self.result_image_path):
            return
        from tkinter import filedialog
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile=os.path.basename(self.result_image_path)
        )
        if save_path:
            import shutil
            shutil.copy2(self.result_image_path, save_path)
            self._log(f"已保存到: {save_path}", "success")

    def _open_result(self):
        """打开结果"""
        if self.result_image_path and os.path.exists(self.result_image_path):
            os.startfile(self.result_image_path)

    # ========== 图库功能 ==========
    def _load_gallery(self):
        """加载图库"""
        # 清空现有内容
        for widget in self.gallery_scroll.winfo_children():
            widget.destroy()

        self.gallery_check_vars = {}
        self.selected_images.clear()

        # 获取图片列表
        images = []
        if self.output_dir.exists():
            images = list(self.output_dir.glob('*.jpg')) + \
                     list(self.output_dir.glob('*.png')) + \
                     list(self.output_dir.glob('*.webp'))
            images.sort(key=os.path.getmtime, reverse=True)

        self.gallery_images = images
        self.gallery_total_count = len(images)
        self._update_gallery_info()

        if not images:
            ctk.CTkLabel(
                self.gallery_scroll,
                text="📭 暂无图片\n生成图片后将自动显示在这里",
                text_color="gray",
                font=Theme.BODY_FONT
            ).grid(row=0, column=0, columnspan=4, padx=20, pady=40)
            return

        # 显示图片网格
        for idx, img_path in enumerate(images):
            row = idx // 4
            col = idx % 4
            self._add_gallery_item(img_path, row, col)

    def _add_gallery_item(self, img_path: Path, row: int, col: int):
        """添加图库项"""
        try:
            item_frame = ctk.CTkFrame(self.gallery_scroll, fg_color="#252b34",
                                      corner_radius=8, border_width=1, border_color="#334155")
            item_frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            # 加载缩略图
            img = Image.open(str(img_path))
            img.thumbnail((140, 140))
            # 裁剪为正方形
            w, h = img.size
            size = min(w, h)
            left = (w - size) / 2
            top = (h - size) / 2
            img = img.crop((left, top, left + size, top + size))
            img = img.resize((120, 120), Image.LANCZOS)

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))

            # 图片按钮
            btn = ctk.CTkButton(
                item_frame, text="", image=ctk_img, width=120, height=120,
                fg_color="transparent", hover_color="#3a4552",
                command=lambda p=str(img_path): self._on_gallery_image_click(p)
            )
            btn.image = ctk_img
            btn.pack(padx=8, pady=(8, 4))

            # 复选框
            select_var = ctk.BooleanVar(value=False)
            self.gallery_check_vars[str(img_path)] = select_var
            ctk.CTkCheckBox(
                item_frame, text="选择", variable=select_var, font=Theme.SMALL_FONT,
                command=lambda p=str(img_path), v=select_var: self._on_gallery_select_toggle(p, v)
            ).pack(anchor="w", padx=8, pady=(0, 2))

            # 文件名
            name = img_path.name
            if len(name) > 16:
                name = name[:14] + '...'
            ctk.CTkLabel(
                item_frame, text=name, text_color="#e2e8f0", font=Theme.SMALL_FONT
            ).pack(anchor="w", padx=8, pady=(0, 6))

        except Exception as e:
            print(f"[Text2Image Gallery] Failed to load image {img_path}: {e}")

    def _on_gallery_select_toggle(self, image_path: str, check_var):
        """切换选择状态"""
        if check_var.get():
            self.selected_images.add(image_path)
        else:
            self.selected_images.discard(image_path)
        self._update_gallery_info()

    def _update_gallery_info(self):
        """更新图库信息"""
        self.gallery_info_label.configure(text=f"已选 {len(self.selected_images)}/{self.gallery_total_count}")

    def _on_gallery_image_click(self, image_path: str):
        """点击图片预览"""
        path = Path(image_path)
        if not path.exists():
            return

        try:
            if self._preview_window and self._preview_window.winfo_exists():
                self._preview_window.destroy()
        except Exception:
            pass

        preview = ctk.CTkToplevel(self)
        preview.title(f"预览 - {path.name}")
        preview.attributes("-topmost", True)
        preview.geometry("900x700")
        preview.minsize(600, 500)
        preview.transient(self.winfo_toplevel())
        self._preview_window = preview

        container = ctk.CTkFrame(preview, fg_color="#13161c")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        with Image.open(str(path)) as img:
            width, height = img.size
            max_w = 800
            max_h = 600
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            preview_img = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=img.size)

        img_label = ctk.CTkLabel(container, text="", image=preview_img)
        img_label.image = preview_img
        img_label.pack(fill="both", expand=True, padx=10, pady=(10, 8))

        size_text = self._format_size(path.stat().st_size)
        info_text = f"文件名: {path.name}    尺寸: {width}x{height}    体积: {size_text}"
        ctk.CTkLabel(container, text=info_text, font=Theme.BODY_FONT, text_color="#cbd5e1").pack(pady=(0, 8))

        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(action_row, text="📁 打开所在文件夹",
                      command=lambda p=path: os.startfile(str(p.parent))).pack(side="left")
        ctk.CTkButton(action_row, text="关闭", width=90, command=preview.destroy,
                      fg_color="#455a64").pack(side="right")

    def _select_all_gallery(self):
        """全选"""
        for path, var in self.gallery_check_vars.items():
            var.set(True)
            self.selected_images.add(path)
        self._update_gallery_info()

    def _deselect_all_gallery(self):
        """取消全选"""
        for path, var in self.gallery_check_vars.items():
            var.set(False)
        self.selected_images.clear()
        self._update_gallery_info()

    def _download_selected_gallery(self):
        """下载选中的图片"""
        if not self.selected_images:
            if CTkMessagebox:
                CTkMessagebox(title="提示", message="请先选择要下载的图片", icon="info")
            return

        from tkinter import filedialog
        save_dir = filedialog.askdirectory(title="选择保存目录")
        if not save_dir:
            return

        import shutil
        count = 0
        for img_path in self.selected_images:
            if Path(img_path).exists():
                shutil.copy2(img_path, save_dir)
                count += 1

        self._log(f"已下载 {count} 张图片到: {save_dir}", "success")
        if CTkMessagebox:
            CTkMessagebox(title="完成", message=f"已下载 {count} 张图片", icon="check")

    def _delete_selected_gallery(self):
        """删除选中的图片"""
        if not self.selected_images:
            if CTkMessagebox:
                CTkMessagebox(title="提示", message="请先选择要删除的图片", icon="info")
            return

        if CTkMessagebox:
            confirm = CTkMessagebox(
                title="确认删除",
                message=f"确定要删除选中的 {len(self.selected_images)} 张图片吗？\n此操作不可恢复！",
                icon="warning",
                option_1="取消",
                option_2="删除"
            )
            if confirm.get() != "删除":
                return

        count = 0
        for img_path in list(self.selected_images):
            try:
                Path(img_path).unlink()
                count += 1
            except Exception as e:
                print(f"[Text2Image Gallery] Failed to delete {img_path}: {e}")

        self._log(f"已删除 {count} 张图片", "success")
        self._load_gallery()

    def _clear_all_gallery(self):
        """清空所有图片"""
        if not self.gallery_images:
            if CTkMessagebox:
                CTkMessagebox(title="提示", message="图库已经是空的", icon="info")
            return

        if CTkMessagebox:
            confirm = CTkMessagebox(
                title="确认清空",
                message=f"确定要清空所有 {len(self.gallery_images)} 张图片吗？\n此操作不可恢复！",
                icon="warning",
                option_1="取消",
                option_2="清空"
            )
            if confirm.get() != "清空":
                return

        count = 0
        for img_path in self.gallery_images:
            try:
                img_path.unlink()
                count += 1
            except Exception as e:
                print(f"[Text2Image Gallery] Failed to delete {img_path}: {e}")

        self._log(f"已清空 {count} 张图片", "success")
        self._load_gallery()


class GalleryFrame(ctk.CTkFrame):
    """我的图库（支持预览与 ComfyUI 批量出图）"""
    def __init__(self, master, config):
        super().__init__(master)
        self.config = config
        self.selected_gallery_images = set()
        self.gallery_check_vars = {}
        self.gallery_total_count = 0
        self.comfy_result_paths = []
        self.selected_result_images = set()
        self.result_check_vars = {}
        self.result_card_map = {}
        self._drag_start_x = 0
        self._is_comfy_generating = False
        self._preview_window = None
        self._setup_ui()

    def _setup_ui(self):
        # 顶部标题栏
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(12, 6))

        ctk.CTkLabel(header, text="🖼️ 我的图库", font=Theme.HEADER_FONT).pack(side="left", padx=10)
        self.selected_info_label = ctk.CTkLabel(header, text="已选 0/0", text_color="#9fb3c8", font=Theme.BODY_FONT)
        self.selected_info_label.pack(side="left", padx=(10, 0))
        ctk.CTkButton(header, text="🔄 刷新图库", width=110, command=self._load_gallery).pack(side="right", padx=5)

        # ComfyUI 操作区
        comfy_panel = ctk.CTkFrame(self, fg_color="#1f252d", corner_radius=10)
        comfy_panel.pack(fill="x", padx=20, pady=(0, 10))

        row1 = ctk.CTkFrame(comfy_panel, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(row1, text="🎛️ ComfyUI 做图入口", font=Theme.TITLE_FONT).pack(side="left")
        self.comfy_server_label = ctk.CTkLabel(
            row1,
            text=f"服务器: {self.config.comfyui.get_effective_server_url() or '未配置'}",
            font=Theme.SMALL_FONT,
            text_color="#9fb3c8"
        )
        self.comfy_server_label.pack(side="right")

        row2 = ctk.CTkFrame(comfy_panel, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(row2, text="工作流:", font=Theme.BODY_FONT).pack(side="left")
        self.gallery_workflow_var = ctk.StringVar(value="")
        workflow_values = self.config.comfyui.list_workflows() or ["暂无工作流"]
        self.gallery_workflow_menu = ctk.CTkOptionMenu(
            row2,
            variable=self.gallery_workflow_var,
            values=workflow_values,
            width=260,
            font=Theme.BODY_FONT,
            text_color="#FFFFFF",
            dropdown_text_color="#FFFFFF"
        )
        self.gallery_workflow_menu.pack(side="left", padx=8)
        ctk.CTkButton(
            row2,
            text="🔄 刷新工作流",
            width=120,
            command=self._refresh_workflow_options,
            font=Theme.SMALL_FONT
        ).pack(side="left", padx=4)

        current_workflow = self.config.comfyui.current_workflow
        if workflow_values and workflow_values[0] != "暂无工作流":
            self.gallery_workflow_var.set(current_workflow if current_workflow in workflow_values else workflow_values[0])
            self.gallery_workflow_menu.set(self.gallery_workflow_var.get())
        else:
            self.gallery_workflow_var.set("暂无工作流")
            self.gallery_workflow_menu.set("暂无工作流")

        row3 = ctk.CTkFrame(comfy_panel, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(row3, text="提示词:", font=Theme.BODY_FONT).pack(side="left")
        self.gallery_prompt_entry = ctk.CTkEntry(
            row3,
            placeholder_text="可选：留空则按工作流默认逻辑执行",
            height=36,
            font=Theme.BODY_FONT
        )
        self.gallery_prompt_entry.pack(side="left", fill="x", expand=True, padx=8)

        row4 = ctk.CTkFrame(comfy_panel, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=(6, 10))
        self.gallery_comfy_btn = ctk.CTkButton(
            row4,
            text="🚀 用已选图片做图",
            width=170,
            command=self._start_comfyui_generate_from_gallery,
            fg_color="#1a73e8",
            hover_color="#1666c1",
            font=Theme.BODY_FONT
        )
        self.gallery_comfy_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row4,
            text="🧹 清空选择",
            width=110,
            command=self._clear_selected_gallery,
            fg_color="#455a64",
            hover_color="#37474f",
            font=Theme.SMALL_FONT
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            row4,
            text="🔄 刷新结果",
            width=110,
            command=self._load_recent_comfy_results,
            fg_color="#455a64",
            hover_color="#37474f",
            font=Theme.SMALL_FONT
        ).pack(side="left", padx=4)
        self.comfy_status_label = ctk.CTkLabel(row4, text="就绪", text_color="#9fb3c8", font=Theme.SMALL_FONT)
        self.comfy_status_label.pack(side="right")

        # 图库区（原图）
        ctk.CTkLabel(self, text="📚 原图图库", font=Theme.TITLE_FONT).pack(anchor="w", padx=24, pady=(4, 2))
        self.gallery_frame = ctk.CTkScrollableFrame(
            self,
            orientation="horizontal",
            height=320,
            fg_color=Theme.CARD_COLOR
        )
        self.gallery_frame.pack(fill="x", padx=20, pady=(0, 12))

        # 绑定滚动和拖拽事件
        self.gallery_frame.bind("<MouseWheel>", self._on_gallery_scroll)
        self.gallery_frame._parent_canvas.bind("<MouseWheel>", self._on_gallery_scroll)
        self.gallery_frame.bind("<ButtonPress-1>", self._on_drag_start)
        self.gallery_frame.bind("<B1-Motion>", self._on_drag_motion)
        self.gallery_frame._parent_canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.gallery_frame._parent_canvas.bind("<B1-Motion>", self._on_drag_motion)

        # 结果区（ComfyUI 反馈）
        result_header = ctk.CTkFrame(self, fg_color="transparent")
        result_header.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(result_header, text="🎨 ComfyUI 结果陈列", font=Theme.TITLE_FONT).pack(side="left")
        result_action_row = ctk.CTkFrame(result_header, fg_color="transparent")
        result_action_row.pack(side="right")
        self.result_selected_label = ctk.CTkLabel(result_action_row, text="已勾选 0 张", text_color="#9fb3c8", font=Theme.SMALL_FONT)
        self.result_selected_label.pack(side="left", padx=(0, 8))
        self.result_count_label = ctk.CTkLabel(result_action_row, text="共 0 张", text_color="#9fb3c8", font=Theme.BODY_FONT)
        self.result_count_label.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            result_action_row,
            text="⬇ 下载勾选",
            width=110,
            command=self._download_selected_results,
            font=Theme.SMALL_FONT,
            fg_color="#1a73e8",
            hover_color="#1666c1"
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            result_action_row,
            text="⬇ 下载全部",
            width=110,
            command=self._download_all_results,
            font=Theme.SMALL_FONT,
            fg_color="#334155",
            hover_color="#283341"
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            result_action_row,
            text="🗑 清除勾选",
            width=110,
            command=self._clear_selected_results,
            font=Theme.SMALL_FONT,
            fg_color="#9b2c2c",
            hover_color="#7f1d1d"
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            result_action_row,
            text="🗑 一键清空",
            width=110,
            command=self._clear_all_results,
            font=Theme.SMALL_FONT,
            fg_color="#7f1d1d",
            hover_color="#5f1111"
        ).pack(side="left")

        self.result_frame = ctk.CTkScrollableFrame(
            self,
            orientation="vertical",
            fg_color="#1b1f26",
            height=360
        )
        self.result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for col in range(4):
            self.result_frame.grid_columnconfigure(col, weight=1)

        self._load_gallery()
        self._load_recent_comfy_results()

    def _notify(self, message: str, icon: str = "info"):
        title_map = {"info": "提示", "warning": "注意", "error": "错误"}
        show_message_with_copy(self, title_map.get(icon, "提示"), message, icon)

    def _set_comfy_status(self, text: str, color: str = "#9fb3c8"):
        self.comfy_status_label.configure(text=text, text_color=color)

    def _set_comfy_generating(self, generating: bool):
        self._is_comfy_generating = generating
        state = "disabled" if generating else "normal"
        self.gallery_comfy_btn.configure(state=state)

    def _refresh_workflow_options(self):
        from config import reload_config
        self.config = reload_config()

        workflows = self.config.comfyui.list_workflows()
        if not workflows:
            self.gallery_workflow_var.set("暂无工作流")
            self.gallery_workflow_menu.configure(values=["暂无工作流"])
            self.gallery_workflow_menu.set("暂无工作流")
            self._set_comfy_status("未发现可用工作流", "#ffb84d")
            return

        self.gallery_workflow_menu.configure(values=workflows)
        current = self.config.comfyui.current_workflow
        new_value = current if current in workflows else workflows[0]
        self.gallery_workflow_var.set(new_value)
        self.gallery_workflow_menu.set(new_value)
        self._set_comfy_status(f"工作流已刷新，共 {len(workflows)} 个", "#89c4f4")

    def _clear_selected_gallery(self):
        self.selected_gallery_images.clear()
        for var in self.gallery_check_vars.values():
            var.set(False)
        self._update_selected_info()

    def _update_selected_info(self):
        self.selected_info_label.configure(text=f"已选 {len(self.selected_gallery_images)}/{self.gallery_total_count}")

    def _update_result_selected_info(self):
        self.result_selected_label.configure(text=f"已勾选 {len(self.selected_result_images)} 张")

    def _norm_path(self, p) -> str:
        try:
            return str(Path(p).resolve())
        except Exception:
            return str(p)

    def _human_size(self, size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size_bytes} B"

    def _get_image_info(self, img_path: Path):
        try:
            with Image.open(str(img_path)) as img:
                width, height = img.size
            size_text = self._human_size(img_path.stat().st_size)
            return width, height, size_text
        except Exception:
            return 0, 0, "未知"

    def _load_gallery(self):
        """加载 output/images 下的图片"""
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()

        self.gallery_check_vars = {}
        self.selected_gallery_images.clear()

        output_dir = Path('./output/images')
        if not output_dir.exists():
            self.gallery_total_count = 0
            self._update_selected_info()
            ctk.CTkLabel(
                self.gallery_frame,
                text="🖼️ 暂无图片\\n请先在抓取页下载图片",
                text_color="gray",
                font=Theme.BODY_FONT
            ).pack(padx=20, pady=20)
            return

        images = list(output_dir.glob('*.jpg')) + list(output_dir.glob('*.png')) + list(output_dir.glob('*.webp'))
        images.sort(key=os.path.getmtime, reverse=True)
        self.gallery_total_count = len(images)
        self._update_selected_info()

        if not images:
            ctk.CTkLabel(
                self.gallery_frame,
                text="🖼️ 图片目录为空\\n请先在抓取页下载图片",
                text_color="gray",
                font=Theme.BODY_FONT
            ).pack(padx=20, pady=20)
            return

        for img_path in images:
            self._add_gallery_item(img_path)

    def _add_gallery_item(self, img_path: Path):
        try:
            item_frame = ctk.CTkFrame(self.gallery_frame, fg_color="#252b34", corner_radius=10, border_width=1, border_color="#334155")
            item_frame.pack(side="left", padx=8, pady=8)

            img = Image.open(str(img_path))
            img.thumbnail((300, 300))
            w, h = img.size
            size = min(w, h)
            left = (w - size) / 2
            top = (h - size) / 2
            right = (w + size) / 2
            bottom = (h + size) / 2
            img = img.crop((left, top, right, bottom))
            img = img.resize((170, 170), Image.LANCZOS)

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(170, 170))

            btn = ctk.CTkButton(
                item_frame,
                text="",
                image=ctk_img,
                width=170,
                height=170,
                fg_color="transparent",
                hover_color="#3a4552",
                command=lambda p=str(img_path): self._on_gallery_image_click(p)
            )
            btn.image = ctk_img
            btn.pack(padx=10, pady=(10, 6))

            btn.bind("<MouseWheel>", self._on_gallery_scroll)
            btn.bind("<ButtonPress-1>", self._on_drag_start, add="+")
            btn.bind("<B1-Motion>", self._on_drag_motion, add="+")

            select_var = ctk.BooleanVar(value=False)
            self.gallery_check_vars[str(img_path)] = select_var
            ctk.CTkCheckBox(
                item_frame,
                text="选择",
                variable=select_var,
                font=Theme.SMALL_FONT,
                command=lambda p=str(img_path), v=select_var: self._on_gallery_select_toggle(p, v)
            ).pack(anchor="w", padx=10, pady=(0, 4))

            width, height, size_text = self._get_image_info(img_path)
            ctk.CTkLabel(
                item_frame,
                text=img_path.name[:22] + '...' if len(img_path.name) > 22 else img_path.name,
                text_color="#e2e8f0",
                font=Theme.SMALL_FONT
            ).pack(anchor="w", padx=10)
            ctk.CTkLabel(
                item_frame,
                text=f"{width}x{height}  |  {size_text}",
                text_color="#94a3b8",
                font=Theme.SMALL_FONT
            ).pack(anchor="w", padx=10, pady=(0, 8))
        except Exception as e:
            print(f"[Gallery] Failed to load image {img_path}: {e}")

    def _on_gallery_select_toggle(self, image_path: str, check_var):
        if check_var.get():
            self.selected_gallery_images.add(image_path)
        else:
            self.selected_gallery_images.discard(image_path)
        self._update_selected_info()

    def _on_gallery_image_click(self, image_path: str):
        path = Path(image_path)
        if not path.exists():
            self._notify(f"文件不存在: {image_path}", "error")
            return

        try:
            if self._preview_window and self._preview_window.winfo_exists():
                self._preview_window.destroy()
        except Exception:
            pass

        preview = ctk.CTkToplevel(self)
        preview.title(f"预览 - {path.name}")
        preview.attributes("-topmost", True)
        preview.geometry("1320x900")
        preview.minsize(900, 640)
        preview.transient(self.winfo_toplevel())
        self._preview_window = preview

        container = ctk.CTkFrame(preview, fg_color="#13161c")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        with Image.open(str(path)) as img:
            width, height = img.size
            screen_w = preview.winfo_screenwidth()
            screen_h = preview.winfo_screenheight()
            max_w = int(screen_w * 0.9)
            max_h = int(screen_h * 0.9)
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            preview_img = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=img.size)

        img_label = ctk.CTkLabel(container, text="", image=preview_img)
        img_label.image = preview_img
        img_label.pack(fill="both", expand=True, padx=10, pady=(10, 8))

        size_text = self._human_size(path.stat().st_size)
        info_text = f"文件名: {path.name}    尺寸: {width}x{height}    体积: {size_text}"
        ctk.CTkLabel(container, text=info_text, font=Theme.BODY_FONT, text_color="#cbd5e1").pack(pady=(0, 8))

        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(action_row, text="📁 打开所在文件夹", command=lambda p=path: os.startfile(str(p.parent))).pack(side="left")
        ctk.CTkButton(action_row, text="关闭", width=90, command=preview.destroy, fg_color="#455a64").pack(side="right")

    def _start_comfyui_generate_from_gallery(self):
        if self._is_comfy_generating:
            return

        selected_paths = [p for p in self.selected_gallery_images if Path(p).exists()]
        if not selected_paths:
            self._notify("请先在图库中勾选至少一张图片。", "warning")
            return

        workflow_name = self.gallery_workflow_var.get().strip()
        if not workflow_name or workflow_name == "暂无工作流":
            self._notify("请先选择一个 ComfyUI 工作流。", "warning")
            return

        server = self.config.comfyui.get_effective_server_url()
        if not server:
            self._notify("请先在配置页填写 ComfyUI 服务器地址。", "warning")
            return

        workflow = self.config.comfyui.get_workflow(workflow_name)
        if not workflow:
            self._notify("当前工作流不存在，请点击“刷新工作流”后重试。", "warning")
            return

        prompt = self.gallery_prompt_entry.get().strip()
        self._set_comfy_generating(True)
        self._set_comfy_status(f"开始生成，共 {len(selected_paths)} 张输入图...", "#89c4f4")

        threading.Thread(
            target=self._run_comfyui_batch,
            args=(selected_paths, workflow_name, prompt),
            daemon=True
        ).start()

    def _run_comfyui_batch(self, selected_paths, workflow_name: str, prompt: str):
        generated_paths = []
        errors = []

        try:
            from image_generation import ComfyUIFluxKontextClient

            server = self.config.comfyui.get_effective_server_url()
            workflow = self.config.comfyui.get_workflow(workflow_name)
            client = ComfyUIFluxKontextClient(server)
            client.set_workflow(
                workflow["json"],
                workflow["prompt_node_id"],
                workflow["prompt_param_path"],
                workflow.get("image_node_id"),
                workflow.get("image_param_path")
            )

            total = len(selected_paths)
            for idx, image_path in enumerate(selected_paths, start=1):
                self.after(0, lambda i=idx, t=total, p=Path(image_path).name:
                           self._set_comfy_status(f"正在处理 {i}/{t}: {p}", "#89c4f4"))
                try:
                    if hasattr(client, "image_to_image_all"):
                        outputs = client.image_to_image_all(
                            image_path,
                            prompt or "",
                            output_dir="./output/generated"
                        )
                    else:
                        single = client.image_to_image(
                            image_path,
                            prompt or "",
                            output_dir="./output/generated"
                        )
                        outputs = [single] if single else []
                    for out in outputs:
                        if out and Path(out).exists():
                            generated_paths.append(out)
                except Exception as e:
                    errors.append(f"{Path(image_path).name}: {e}")

        except Exception as e:
            errors.append(str(e))
        finally:
            self.after(0, lambda: self._on_comfyui_batch_done(generated_paths, errors))

    def _on_comfyui_batch_done(self, generated_paths, errors):
        self._set_comfy_generating(False)

        if generated_paths:
            # 保留历史：本次完成后从结果目录重载，而不是只展示本次输出
            unique_paths = []
            seen = set()
            for p in generated_paths:
                rp = str(Path(p).resolve())
                if rp not in seen and Path(rp).exists():
                    seen.add(rp)
                    unique_paths.append(rp)

            self._load_recent_comfy_results()
            self._set_comfy_status(
                f"生成完成，新增 {len(unique_paths)} 张，历史共 {len(self.comfy_result_paths)} 张",
                "#4caf50"
            )
        else:
            # 失败时不清空历史结果
            if not self.comfy_result_paths:
                self._load_recent_comfy_results()
            self._set_comfy_status("本次未获得新输出，已保留历史结果", "#ffb84d")

        if errors:
            show_err = "\n".join(errors[:6])
            if len(errors) > 6:
                show_err += f"\n... 另外 {len(errors)-6} 条错误"
            self._notify(f"部分任务失败：\n{show_err}", "warning")

    def _load_recent_comfy_results(self):
        output_dir = Path("./output/generated")
        if not output_dir.exists():
            self.comfy_result_paths = []
            self.selected_result_images.clear()
            self._render_comfy_results([])
            return

        images = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            images.extend(output_dir.glob(ext))
        images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        # 保留完整历史，不截断结果列表
        self.comfy_result_paths = [self._norm_path(p) for p in images]
        self._render_comfy_results(self.comfy_result_paths)

    def _render_comfy_results(self, image_paths):
        for widget in self.result_frame.winfo_children():
            widget.destroy()
        self.result_check_vars = {}
        self.result_card_map = {}

        normalized_paths = [self._norm_path(p) for p in image_paths]
        self.selected_result_images = {
            p for p in self.selected_result_images if p in set(normalized_paths)
        }

        count = len(normalized_paths)
        self.result_count_label.configure(text=f"共 {count} 张")
        self._update_result_selected_info()

        if count == 0:
            ctk.CTkLabel(
                self.result_frame,
                text="暂无 ComfyUI 结果图\n点击“用已选图片做图”开始生成",
                text_color="#94a3b8",
                font=Theme.BODY_FONT
            ).grid(row=0, column=0, padx=16, pady=16, sticky="w")
            return

        columns = 4
        for idx, path in enumerate(normalized_paths):
            p = Path(path)
            if not p.exists():
                continue
            row = idx // columns
            col = idx % columns
            self._add_result_card(p, idx + 1, row, col)

    def _add_result_card(self, img_path: Path, index: int, row: int, col: int):
        norm_path = self._norm_path(img_path)
        card = ctk.CTkFrame(
            self.result_frame,
            fg_color="#222a35",
            corner_radius=10,
            border_width=1,
            border_color="#334155"
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        self.result_card_map[norm_path] = card

        try:
            img = Image.open(str(img_path))
            width, height = img.size
            img.thumbnail((190, 190), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            btn = ctk.CTkButton(
                card,
                text="",
                image=ctk_img,
                width=190,
                height=190,
                fg_color="transparent",
                hover_color="#334155",
                command=lambda p=str(img_path): self._on_gallery_image_click(p)
            )
            btn.image = ctk_img
            btn.pack(padx=6, pady=(6, 4))

            size_text = self._human_size(img_path.stat().st_size)
            select_var = ctk.BooleanVar(value=(norm_path in self.selected_result_images))
            self.result_check_vars[norm_path] = select_var
            ctk.CTkCheckBox(
                card,
                text="勾选下载",
                variable=select_var,
                font=Theme.SMALL_FONT,
                command=lambda p=norm_path, v=select_var: self._on_result_select_toggle(p, v)
            ).pack(anchor="w", padx=8, pady=(0, 2))
            ctk.CTkLabel(
                card,
                text=f"#{index} {img_path.name}",
                text_color="#e2e8f0",
                font=Theme.SMALL_FONT,
                wraplength=190,
                justify="left"
            ).pack(anchor="w", padx=8)
            ctk.CTkLabel(
                card,
                text=f"尺寸: {width} x {height}",
                text_color="#94a3b8",
                font=Theme.SMALL_FONT
            ).pack(anchor="w", padx=8)
            ctk.CTkLabel(
                card,
                text=f"体积: {size_text}",
                text_color="#94a3b8",
                font=Theme.SMALL_FONT
            ).pack(anchor="w", padx=8, pady=(0, 8))
            self._set_result_card_selected_style(norm_path, select_var.get())
        except Exception as e:
            ctk.CTkLabel(card, text=f"加载失败: {e}", text_color="#ff6b6b", font=Theme.SMALL_FONT).pack(padx=8, pady=8)

    def _set_result_card_selected_style(self, norm_path: str, selected: bool):
        card = self.result_card_map.get(norm_path)
        if not card:
            return
        if selected:
            card.configure(
                fg_color="#243b2f",
                border_color="#22c55e",
                border_width=2
            )
        else:
            card.configure(
                fg_color="#222a35",
                border_color="#334155",
                border_width=1
            )

    def _on_result_select_toggle(self, norm_path: str, check_var):
        if check_var.get():
            self.selected_result_images.add(norm_path)
        else:
            self.selected_result_images.discard(norm_path)
        self._set_result_card_selected_style(norm_path, check_var.get())
        self._update_result_selected_info()

    def _download_result_images(self, paths):
        if not paths:
            self._notify("没有可下载的结果图。", "warning")
            return

        from tkinter import filedialog
        import shutil

        target_dir = filedialog.askdirectory(title="选择结果图下载目录")
        if not target_dir:
            return

        target = Path(target_dir)
        success = 0
        failed = []

        for src_raw in paths:
            src = Path(src_raw)
            if not src.exists():
                failed.append(f"{src.name}: 文件不存在")
                continue
            dst = target / src.name
            if dst.exists():
                stem = src.stem
                suffix = src.suffix
                n = 1
                while True:
                    candidate = target / f"{stem}_{n}{suffix}"
                    if not candidate.exists():
                        dst = candidate
                        break
                    n += 1
            try:
                shutil.copy2(str(src), str(dst))
                success += 1
            except Exception as e:
                failed.append(f"{src.name}: {e}")

        msg = f"下载完成：成功 {success} 张"
        if failed:
            msg += f"\n失败 {len(failed)} 张"
            if len(failed) <= 6:
                msg += "\n" + "\n".join(failed)
        self._notify(msg, "info" if success > 0 else "warning")

    def _download_all_results(self):
        self._download_result_images(self.comfy_result_paths)

    def _download_selected_results(self):
        selected = [p for p in self.comfy_result_paths if self._norm_path(p) in self.selected_result_images]
        self._download_result_images(selected)

    def _confirm_result_clear(self, title: str, message: str) -> bool:
        """确认是否执行清理操作。"""
        if CTkMessagebox:
            try:
                result = CTkMessagebox(
                    title=title,
                    message=message,
                    icon="warning",
                    option_1="取消",
                    option_2="确定清除"
                )
                return result.get() == "确定清除"
            except TypeError:
                # 兼容旧版 CTkMessagebox
                result = CTkMessagebox(title=title, message=message, icon="warning")
                return str(result.get()).lower() in ("ok", "yes", "确定", "确认")
        return True

    def _delete_result_images(self, paths, action_name: str):
        """删除指定结果图文件，并刷新结果陈列。"""
        if not paths:
            self._notify("没有可清除的结果图。", "warning")
            return

        success = 0
        failed = []
        seen = set()

        for raw_path in paths:
            norm = self._norm_path(raw_path)
            if norm in seen:
                continue
            seen.add(norm)
            p = Path(norm)
            if not p.exists():
                failed.append(f"{p.name}: 文件不存在")
                continue
            try:
                p.unlink()
                success += 1
            except Exception as e:
                failed.append(f"{p.name}: {e}")

        self.selected_result_images.clear()
        self._load_recent_comfy_results()

        msg = f"{action_name}完成：成功 {success} 张"
        if failed:
            msg += f"\n失败 {len(failed)} 张"
            if len(failed) <= 6:
                msg += "\n" + "\n".join(failed)
        self._notify(msg, "info" if success > 0 else "warning")

    def _clear_selected_results(self):
        selected = [p for p in self.comfy_result_paths if self._norm_path(p) in self.selected_result_images]
        if not selected:
            self._notify("请先勾选要清除的结果图。", "warning")
            return

        if not self._confirm_result_clear(
            "确认清除",
            f"将删除勾选的 {len(selected)} 张结果图文件。\n此操作不可撤销，是否继续？"
        ):
            return

        self._delete_result_images(selected, "勾选清除")

    def _clear_all_results(self):
        output_dir = Path("./output/generated")
        if not output_dir.exists():
            self._notify("结果目录不存在，无需清除。", "warning")
            return

        all_images = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            all_images.extend(output_dir.glob(ext))

        if not all_images:
            self._notify("当前没有历史结果图。", "warning")
            return

        if not self._confirm_result_clear(
            "确认一键清空",
            f"将删除 output/generated 下的 {len(all_images)} 张结果图文件。\n此操作不可撤销，是否继续？"
        ):
            return

        self._delete_result_images([str(p) for p in all_images], "一键清空")

    def _on_gallery_scroll(self, event):
        """鼠标滚轮横向滚动 - 快速模式"""
        if event.delta:
            # 提高滚动速度 (event.delta通常为120的倍数)
            # 使用较小的除数来增加每次滚动的幅度
            self.gallery_frame._parent_canvas.xview_scroll(int(-1 * (event.delta / 2)), "units")

    def _on_drag_start(self, event):
        """拖拽开始"""
        self._drag_start_x = event.x_root

    def _on_drag_motion(self, event):
        """拖拽中 - 快速模式"""
        delta_x = event.x_root - self._drag_start_x
        # 提高拖拽灵敏度，delta_x直接作为滚动距离甚至放大
        sensitivity = 1 # 1:1跟随, <1则放大移动
        if abs(delta_x) > 2: # 降低防抖阈值
            self.gallery_frame._parent_canvas.xview_scroll(int(-1 * delta_x * 2), "units") # *2 放大拖拽效果
            self._drag_start_x = event.x_root

class App(ctk.CTk):
    """主应用"""

    def __init__(self):
        super().__init__()

        # 初始化日志系统
        if LOGGER_AVAILABLE:
            setup_logger(debug_mode=True)
            log_info("应用程序启动")

        # 加载配置
        from config.settings import get_config
        self.config = get_config()
        
        # 窗口设置
        self.title("1688 图片抓取与图生图工具")

        # 设置最小窗口尺寸，防止窗口变形
        self.minsize(1200, 800)

        # 尝试最大化窗口以适应屏幕
        try:
            self.state("zoomed")
        except:
             self.geometry("1900x1200")
        
        self.frames = {} # Cache for frames
        self._setup_ui()
        
        # 首次启动检查配置
        if not self.config.is_configured():
            self._show_config_hint()

        # 检查更新（后台运行）
        self._check_for_update()
            
    def _setup_ui(self):
        # 侧边栏
        sidebar = ctk.CTkFrame(self, width=200)
        sidebar.pack(side="left", fill="y", padx=5, pady=5)
        sidebar.pack_propagate(False)

        # Logo - 使用多路径尝试支持PyInstaller打包
        self._logo_img = None  # 保持引用
        self._pil_image = None  # 保持PIL图像引用
        logo_loaded = False

        try:
            # 尝试多个可能的路径
            possible_paths = []

            if getattr(sys, 'frozen', False):
                # PyInstaller打包后的exe运行
                # 1. _MEIPASS路径 (onefile模式)
                if hasattr(sys, '_MEIPASS'):
                    possible_paths.append(Path(sys._MEIPASS) / "assets" / "logo_circle.png")
                # 2. exe所在目录的_internal/assets (onedir模式)
                exe_dir = Path(sys.executable).parent
                possible_paths.append(exe_dir / "_internal" / "assets" / "logo_circle.png")
                possible_paths.append(exe_dir / "assets" / "logo_circle.png")
                if LOGGER_AVAILABLE:
                    log_debug(f"Frozen mode, exe_dir: {exe_dir}")
                    log_debug(f"Trying paths: {possible_paths}")
            else:
                # 作为脚本运行
                script_dir = Path(__file__).parent.parent
                possible_paths.append(script_dir / "assets" / "logo_circle.png")
                if LOGGER_AVAILABLE:
                    log_debug(f"Script mode, script_dir: {script_dir}")

            # 尝试每个路径
            for logo_path in possible_paths:
                if LOGGER_AVAILABLE:
                    log_debug(f"Trying logo path: {logo_path}, exists: {logo_path.exists()}")
                if logo_path.exists():
                    self._pil_image = Image.open(str(logo_path))
                    self._pil_image = self._pil_image.resize((150, 150), Image.Resampling.LANCZOS)
                    self._logo_img = ctk.CTkImage(
                        light_image=self._pil_image,
                        dark_image=self._pil_image,
                        size=(150, 150)
                    )
                    self._logo_label = ctk.CTkLabel(sidebar, image=self._logo_img, text="", fg_color="transparent")
                    self._logo_label.pack(pady=(40, 20))
                    logo_loaded = True
                    if LOGGER_AVAILABLE:
                        log_info(f"Logo loaded successfully from: {logo_path}")
                    break

            if not logo_loaded:
                if LOGGER_AVAILABLE:
                    log_warning("Logo not found in any path, using text fallback")
                ctk.CTkLabel(sidebar, text="LOGO", font=Theme.HEADER_FONT).pack(pady=40)

        except Exception as e:
            if LOGGER_AVAILABLE:
                log_error(f"Logo load error: {e}", exc_info=True)
            else:
                import traceback
                print(f"[ERROR] Logo load error: {e}")
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
            ctk.CTkLabel(sidebar, text="LOGO", font=Theme.HEADER_FONT).pack(pady=30)

        # App Name
        ctk.CTkLabel(sidebar, text="跨境AI小甜甜", font=Theme.SUBHEADER_FONT).pack(pady=(0, 20))
        
        nav_btns = [
            ("🔗 抓取", self._show_scrape),
            ("📝 文案识别", self._show_copywriting),
            ("🎨 图生图", self._show_generate),
            ("✨ 文生图", self._show_text2image),
            ("🚀 智能自动化", self._show_automation),
            ("🖼️ 我的图库", self._show_gallery),
            ("⚙️ 配置", self._show_config),
        ]
        
        self.nav_buttons = []
        for text, command in nav_btns:
            btn = ctk.CTkButton(sidebar, text=text, command=command, font=Theme.TITLE_FONT,
                               height=40,
                               fg_color="transparent", text_color=("gray10", "gray90"),
                               anchor="w")
            btn.pack(fill="x", padx=10, pady=5)
            self.nav_buttons.append(btn)
            
            # Save reference to automation button explicitly for effect
            if "智能自动化" in text:
                self.btn_automation = btn

        # Glow effect state
        self._glow_id = None
        self._glow_state = False
        
        # 主内容区
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        self.main_frame.pack_propagate(False)  # 防止内容影响框架大小
        
        # 默认显示抓取页
        self.current_frame = None
        self._show_scrape()
        
    def _show_scrape(self):
        self._highlight_nav(0)
        self._switch_frame(ScrapeFrame, self.config)
        
    def _show_copywriting(self):
        self._highlight_nav(1)
        self._switch_frame(CopywritingFrame, self.config)
        
    def _show_generate(self):
        self._highlight_nav(2)
        self._switch_frame(GenerateFrame, self.config)

    def _show_text2image(self):
        self._highlight_nav(3)
        self._switch_frame(Text2ImageFrame, self.config)

    def _show_automation(self):
        self._highlight_nav(4)
        self._switch_frame(AutomationFrame, self.config)

    def _show_gallery(self):
        self._highlight_nav(5)
        self._switch_frame(GalleryFrame, self.config)

    def _show_config(self):
        self._highlight_nav(6)
        self._switch_frame(ConfigFrame, self.config)
        
    def _highlight_nav(self, index):
        """高亮当前导航按钮"""
        for i, btn in enumerate(self.nav_buttons):
            # Skip if it's the automation button and it's currently glowing
            if btn == getattr(self, "btn_automation", None) and self._glow_id is not None:
                continue
                
            if i == index:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

    def start_automation_glow(self):
        """Start the glowing effect for automation button"""
        if self._glow_id is not None:
            return # Already glowing
            
        print("[App] Starting automation glow effect")
        self.btn_automation.configure(border_width=2)
        self._glow_loop()

    def _glow_loop(self):
        """Recursive loop for glowing effect"""
        try:
            if self._glow_state:
                # Dim state
                self.btn_automation.configure(
                    border_color="#3B8ED0", # Default theme blue
                    fg_color=("gray75", "gray25") if self.current_frame == self.frames.get(AutomationFrame) else "transparent"
                )
            else:
                # Bright/Glowing state
                self.btn_automation.configure(
                    border_color="#00E5FF", # Neon Cyan
                    fg_color="#1E3246" # Slight background tint
                )
            
            self._glow_state = not self._glow_state
            self._glow_id = self.after(800, self._glow_loop)
            
        except Exception as e:
            print(f"Glow error: {e}")
            self.stop_automation_glow()

    def stop_automation_glow(self):
        """Stop the glowing effect"""
        if self._glow_id:
            self.after_cancel(self._glow_id)
            self._glow_id = None
        
        if hasattr(self, 'btn_automation'):
            # Reset style
            self.btn_automation.configure(border_width=0, border_color="transparent")
            # Re-apply correct highlighting
            idx = 3 # Automation index
            if self.current_frame == self.frames.get(AutomationFrame):
                 self.btn_automation.configure(fg_color=("gray75", "gray25"))
            else:
                 self.btn_automation.configure(fg_color="transparent")
            if i == index:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
        
    def _switch_frame(self, frame_class, *args):
        """切换页面 (使用缓存)"""
        # Hide current frame
        if self.current_frame:
            self.current_frame.pack_forget()
            
        # Get or create new frame
        if frame_class not in self.frames:
            self.frames[frame_class] = frame_class(self.main_frame, *args)
            
        self.current_frame = self.frames[frame_class]
        self.current_frame.pack(fill="both", expand=True)
        
    def _show_config_hint(self):
        """显示配置提示"""
        if CTkMessagebox:
            result = CTkMessagebox(
                title="件迎",
                message="首次使用，请先配置API Key",
                icon="info",
                option_1="去配置"
            )
            if result.get() == "去配置":
                self._show_config()

    def _check_for_update(self):
        """检查更新（在后台线程中运行）"""
        if not AutoUpdater or not REMOTE_VERSION_URL:
            return

        def check():
            try:
                updater = AutoUpdater(
                    app_dir=str(get_runtime_app_dir()),
                    remote_version_url=REMOTE_VERSION_URL
                )
                has_update, remote_info = updater.check_for_update()

                if has_update and remote_info:
                    # 在主线程中显示更新对话框
                    self.after(0, lambda: self._show_update_dialog(updater, remote_info))
            except Exception as e:
                print(f"[更新检查] 错误: {e}")

        threading.Thread(target=check, daemon=True).start()

    def _show_update_dialog(self, updater, remote_info):
        """显示更新对话框"""
        new_version = remote_info.get("version", "未知")
        changelog = remote_info.get("changelog", "")
        download_url = remote_info.get("download_url", "")

        if not download_url:
            return

        if CTkMessagebox:
            msg = f"发现新版本 v{new_version}\n\n更新内容:\n{changelog[:200]}"
            result = CTkMessagebox(
                title="发现新版本",
                message=msg,
                icon="info",
                option_1="立即更新",
                option_2="稍后再说"
            )

            if result.get() == "立即更新":
                self._do_update(updater, download_url, new_version)

    def _do_update(self, updater, download_url, new_version):
        """执行更新"""
        # 贴建更新进度窗口
        progress_window = ctk.CTkToplevel(self)
        progress_window.title("正在更新...")
        progress_window.geometry("400x200")
        progress_window.transient(self)
        progress_window.grab_set()

        # 居中显示
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() - 400) // 2
        y = (progress_window.winfo_screenheight() - 200) // 2
        progress_window.geometry(f"+{x}+{y}")

        ctk.CTkLabel(progress_window, text=f"正在更新到 v{new_version}",
                    font=Theme.TITLE_FONT).pack(pady=20)

        progress_bar = ctk.CTkProgressBar(progress_window, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0)

        status_label = ctk.CTkLabel(progress_window, text="准备下载...",
                                   font=Theme.BODY_FONT)
        status_label.pack(pady=10)

        def update_thread():
            try:
                log_info("[GUI更新] 开始更新流程")
                # 下载更新
                def on_download_progress(downloaded, total):
                    if total > 0:
                        progress = downloaded / total
                        self.after(0, lambda p=progress: progress_bar.set(p))
                        self.after(0, lambda: status_label.configure(
                            text=f"下载中... {downloaded // 1024}KB / {total // 1024}KB"))

                status_label.configure(text="正在下载更新包...")
                zip_path = updater.download_update(download_url, on_download_progress)

                if not zip_path:
                    log_error("[GUI更新] 下载失败，zip_path为空")
                    self.after(0, lambda: status_label.configure(text="下载失败"))
                    return

                log_info(f"[GUI更新] 下载完成: {zip_path}")

                # 安装更新
                def on_install_progress(msg):
                    log_debug(f"[GUI更新] 安装进度: {msg}")
                    self.after(0, lambda m=msg: status_label.configure(text=m))

                success = updater.install_update(zip_path, on_install_progress)

                if success:
                    log_info("[GUI更新] 安装成功")
                    self.after(0, lambda: self._update_complete(progress_window, updater))
                else:
                    log_error("[GUI更新] 安装失败")
                    self.after(0, lambda: status_label.configure(text="安装失败，请查看日志"))

            except Exception as e:
                log_error(f"[GUI更新] 更新异常: {e}", exc_info=True)
                self.after(0, lambda: status_label.configure(text=f"更新失败: {e}"))

        threading.Thread(target=update_thread, daemon=True).start()

    def _update_complete(self, progress_window, updater=None):
        """更新完成"""
        progress_window.destroy()

        if CTkMessagebox:
            result = CTkMessagebox(
                title="更新完成",
                message="更新已完成，需要重启程序才能生效。\n\n是否立即重启？",
                icon="info",
                option_1="立即重启",
                option_2="稍后重启"
            )

            if result.get() == "立即重启":
                try:
                    # 必须通过 updater.restart_app() 才会执行 _do_update.bat 完成文件替换
                    if updater:
                        updater.restart_app()
                    else:
                        fallback_updater = AutoUpdater(app_dir=str(get_runtime_app_dir()))
                        fallback_updater.restart_app()
                except Exception as e:
                    if LOGGER_AVAILABLE:
                        log_error(f"[GUI更新] 重启失败: {e}", exc_info=True)
                    self.destroy()
                    sys.exit(0)


class ActivationWindow(ctk.CTk):
    """激活窗口 - 首次启动时显示"""

    def __init__(self):
        super().__init__()

        self.title("软件激活 - AI绘画工具")
        self.geometry("500x450")
        self.resizable(False, False)

        # 居中显示
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 500) // 2
        y = (self.winfo_screenheight() - 450) // 2
        self.geometry(f"500x450+{x}+{y}")

        self._activated = False
        self._setup_ui()

    def _setup_ui(self):
        # 标题
        title = ctk.CTkLabel(self, text="软件激活", font=Theme.HEADER_FONT)
        title.pack(pady=(30, 10))

        subtitle = ctk.CTkLabel(self, text="请输入激活码以继续使用",
                               font=Theme.BODY_FONT, text_color=Theme.COLOR_TEXT_GRAY)
        subtitle.pack(pady=(0, 20))

        # 设备ID显示
        device_frame = ctk.CTkFrame(self)
        device_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(device_frame, text="您的设备ID:", font=Theme.BODY_FONT).pack(anchor="w", padx=15, pady=(10, 5))

        device_id = get_device_id() if LICENSE_AVAILABLE else "无法获取"
        self.device_id_entry = ctk.CTkEntry(device_frame, width=380, height=40,
                                            font=("Consolas", 16), fg_color=Theme.COLOR_INPUT_BG)
        self.device_id_entry.pack(padx=15, pady=(0, 5))
        self.device_id_entry.insert(0, device_id)
        self.device_id_entry.configure(state="readonly")

        # 复制按钮
        copy_btn = ctk.CTkButton(device_frame, text="复制设备ID", width=100, height=30,
                                command=self._copy_device_id, font=Theme.SMALL_FONT)
        copy_btn.pack(pady=(0, 10))

        # 激活码输入
        license_frame = ctk.CTkFrame(self)
        license_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(license_frame, text="请输入激活码:", font=Theme.BODY_FONT).pack(anchor="w", padx=15, pady=(10, 5))

        self.license_entry = ctk.CTkEntry(license_frame, width=380, height=45,
                                          placeholder_text="请输入16位激活码",
                                          font=("Consolas", 18), fg_color=Theme.COLOR_INPUT_BG)
        self.license_entry.pack(padx=15, pady=(0, 15))
        self.license_entry.bind("<Return>", lambda e: self._activate())

        # 状态提示
        self.status_label = ctk.CTkLabel(self, text="", font=Theme.BODY_FONT)
        self.status_label.pack(pady=5)

        # 激活按钮
        activate_btn = ctk.CTkButton(self, text="激活", width=200, height=45,
                                    command=self._activate, font=Theme.TITLE_FONT,
                                    fg_color=Theme.COLOR_PRIMARY)
        activate_btn.pack(pady=20)

        # 提示
        hint = ctk.CTkLabel(self, text="请将设备ID发送给老师获取激活码",
                           font=Theme.SMALL_FONT, text_color=Theme.COLOR_TEXT_GRAY)
        hint.pack(pady=(0, 20))

    def _copy_device_id(self):
        """复制设备ID到剪贴板"""
        device_id = self.device_id_entry.get()
        self.clipboard_clear()
        self.clipboard_append(device_id)
        self.status_label.configure(text="设备ID已复制到剪贴板", text_color=Theme.COLOR_SUCCESS)

    def _activate(self):
        """激活软件"""
        if not LICENSE_AVAILABLE:
            self.status_label.configure(text="激活模块不可用", text_color=Theme.COLOR_DANGER)
            return

        license_key = self.license_entry.get().strip()
        if not license_key:
            self.status_label.configure(text="请输入激活码", text_color=Theme.COLOR_WARNING)
            return

        manager = get_license_manager()
        success, message = manager.activate(license_key)

        if success:
            self.status_label.configure(text=message, text_color=Theme.COLOR_SUCCESS)
            self._activated = True
            self.after(1000, self.destroy)
        else:
            self.status_label.configure(text=message, text_color=Theme.COLOR_DANGER)

    def is_activated(self) -> bool:
        """返回是否激活成功"""
        return self._activated


def check_and_activate() -> bool:
    """
    检查激活状态，如果未激活则显示激活窗口

    Returns:
        bool: 是否已激活（可以继续运行主程序）
    """
    if not LICENSE_AVAILABLE:
        print("[警告] 激活模块不可用，跳过激活检查")
        return True

    manager = get_license_manager()
    if manager.is_activated():
        print("[信息] 软件已激活")
        return True

    # 显示激活窗口
    print("[信息] 软件未激活，显示激活窗口")
    activation_window = ActivationWindow()
    activation_window.mainloop()

    # 检查是否激活成功
    return manager.is_activated()


if __name__ == "__main__":
    # 先检查激活状态
    if not check_and_activate():
        print("[信息] 用户取消激活，退出程序")
        sys.exit(0)

    # 激活成功，启动主程序
    app = App()
    app.mainloop()


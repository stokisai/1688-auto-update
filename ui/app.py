"""
主窗口 — QMainWindow + 侧边栏导航 + QStackedWidget 页面切换
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QSizePolicy,
    QMessageBox, QApplication, QGraphicsOpacityEffect,
)

from .theme import Theme, Icons, NAV_ICON_MAP, logo_path


# 远程版本配置
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/stokisai/ai-drawing-tool-releases/main/version.json"


def _runtime_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


class App(QMainWindow):
    """主应用窗口"""

    NAV_ITEMS = [
        ("抓取",       "scrape"),
        ("文案识别",   "copywriting"),
        ("图生图",     "generate"),
        ("本地图生文生图", "local_browse"),
        ("文生图",     "text2image"),
        ("智能自动化", "automation"),
        ("我的图库",   "gallery"),
        ("配置",       "config"),
    ]

    def __init__(self):
        super().__init__()

        # 初始化日志
        try:
            from utils.logger import setup_logger, log_info
            setup_logger(debug_mode=True)
            log_info("应用程序启动")
        except ImportError:
            pass

        # 加载配置
        from config.settings import get_config
        self.config = get_config()

        self.setWindowTitle("1688 图片抓取与图生图工具")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # 页面缓存
        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: list[QPushButton] = []
        self._current_key: str = ""

        # Glow 动画
        self._glow_timer: QTimer | None = None
        self._glow_state = False
        self._active_anim_timer: QTimer | None = None
        self._active_anim_state = False

        self._build_ui()

        # 首次配置提示
        if not self.config.is_configured():
            self._show_config_hint()

        # 后台检查更新
        self._check_for_update()

    # ── UI 构建 ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(5)

        # 侧边栏
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(Theme.SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo = logo_path()
        if logo:
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pm = QPixmap(str(logo)).scaled(
                120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl.setPixmap(pm)
            sidebar_layout.addSpacing(30)
            sidebar_layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            sidebar_layout.addSpacing(30)

        # App 名称
        name_lbl = QLabel("跨境AI小甜甜")
        name_lbl.setObjectName("appTitle")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFont(Theme.font_subheader())
        sidebar_layout.addSpacing(12)
        sidebar_layout.addWidget(name_lbl)
        sidebar_layout.addSpacing(20)

        # 导航按钮
        for text, key in self.NAV_ITEMS:
            btn = QPushButton(text)
            btn.setFont(Theme.font_title())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # 设置矢量图标
            icon_fn = NAV_ICON_MAP.get(key)
            if icon_fn:
                btn.setIcon(icon_fn())
                btn.setIconSize(QSize(24, 24))
            btn.clicked.connect(lambda checked=False, k=key: self._navigate(k))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()
        root_layout.addWidget(sidebar)

        # 主内容区
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, stretch=1)

        # 默认显示抓取页
        self._navigate("scrape")

    # ── 页面导航 ──

    def _navigate(self, key: str):
        if key == self._current_key:
            return

        # 停止旧页面的活跃动画
        self._stop_active_anim()

        self._current_key = key

        # 高亮
        for i, (_, k) in enumerate(self.NAV_ITEMS):
            btn = self._nav_buttons[i]
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # 启动新页面的活跃动画（呼吸效果）
        self._start_active_anim(key)

        # 懒加载页面
        if key not in self._pages:
            self._pages[key] = self._create_page(key)
            self._stack.addWidget(self._pages[key])

        self._stack.setCurrentWidget(self._pages[key])

    def _create_page(self, key: str) -> QWidget:
        """按 key 懒加载对应页面。"""
        if key == "scrape":
            from .pages.scrape_page import ScrapePage
            return ScrapePage(self.config)
        elif key == "copywriting":
            from .pages.copywriting_page import CopywritingPage
            return CopywritingPage(self.config)
        elif key == "generate":
            from .pages.generate_page import GeneratePage
            return GeneratePage(self.config)
        elif key == "local_browse":
            from .pages.local_browse_page import LocalBrowsePage
            return LocalBrowsePage(self.config)
        elif key == "text2image":
            from .pages.text2image_page import Text2ImagePage
            return Text2ImagePage(self.config)
        elif key == "automation":
            from .pages.automation_page import AutomationPage
            return AutomationPage(self.config)
        elif key == "gallery":
            from .pages.gallery_page import GalleryPage
            return GalleryPage(self.config)
        elif key == "config":
            from .pages.config_page import ConfigPage
            return ConfigPage(self.config)
        # fallback
        placeholder = QLabel(f"页面 [{key}] 尚未实现")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setFont(Theme.font_header())
        return placeholder

    # ── 活跃页面呼吸动画 (通用) ──

    def _start_active_anim(self, key: str):
        """启动当前活跃页面导航按钮的呼吸脉冲效果。"""
        idx = next((i for i, (_, k) in enumerate(self.NAV_ITEMS) if k == key), None)
        if idx is None:
            return
        self._active_anim_timer = QTimer(self)
        self._active_anim_state = False
        self._active_anim_timer.timeout.connect(lambda: self._active_anim_tick(idx))
        self._active_anim_timer.start(900)

    def _active_anim_tick(self, idx: int):
        btn = self._nav_buttons[idx]
        self._active_anim_state = not self._active_anim_state
        if self._active_anim_state:
            btn.setObjectName("glowing")
        else:
            btn.setObjectName("")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _stop_active_anim(self):
        """停止当前活跃动画并重置按钮样式。"""
        if self._active_anim_timer:
            self._active_anim_timer.stop()
            self._active_anim_timer = None
        # 重置所有按钮的 objectName
        for btn in self._nav_buttons:
            if btn.objectName() == "glowing":
                btn.setObjectName("")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    # ── Glow 动画 (自动化按钮 — 兼容旧接口) ──

    def start_automation_glow(self):
        if self._glow_timer is not None:
            return
        idx = next((i for i, (_, k) in enumerate(self.NAV_ITEMS) if k == "automation"), None)
        if idx is None:
            return
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(lambda: self._glow_tick(idx))
        self._glow_timer.start(800)

    def _glow_tick(self, idx: int):
        btn = self._nav_buttons[idx]
        self._glow_state = not self._glow_state
        if self._glow_state:
            btn.setObjectName("glowing")
        else:
            btn.setObjectName("")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def stop_automation_glow(self):
        if self._glow_timer:
            self._glow_timer.stop()
            self._glow_timer = None
        idx = next((i for i, (_, k) in enumerate(self.NAV_ITEMS) if k == "automation"), None)
        if idx is not None:
            btn = self._nav_buttons[idx]
            btn.setObjectName("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── 配置提示 ──

    def _show_config_hint(self):
        reply = QMessageBox.information(
            self, "件迎",
            "首次使用，请先配置API Key",
            QMessageBox.StandardButton.Ok,
        )
        if reply == QMessageBox.StandardButton.Ok:
            self._navigate("config")

    # ── 更新检查 ──

    def _check_for_update(self):
        try:
            from updater import AutoUpdater
        except ImportError:
            return
        if not REMOTE_VERSION_URL:
            return

        from .workers.update_worker import UpdateCheckWorker
        self._update_worker = UpdateCheckWorker(
            str(_runtime_app_dir()), REMOTE_VERSION_URL
        )
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, remote_info: dict):
        new_version = remote_info.get("version", "未知")
        changelog = remote_info.get("changelog", "")
        download_url = remote_info.get("download_url", "")
        if not download_url:
            return

        msg = f"发现新版本 v{new_version}\n\n更新内容:\n{changelog[:200]}"
        reply = QMessageBox.question(
            self, "发现新版本", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._do_update(download_url, new_version)

    def _do_update(self, download_url: str, new_version: str):
        from .workers.update_worker import UpdateDownloadWorker
        from updater import AutoUpdater

        updater = AutoUpdater(
            app_dir=str(_runtime_app_dir()),
            remote_version_url=REMOTE_VERSION_URL,
        )

        self._dl_worker = UpdateDownloadWorker(updater, download_url)
        self._dl_worker.progress.connect(self._on_update_progress)
        self._dl_worker.finished.connect(lambda ok: self._on_update_done(ok, updater))
        self._dl_worker.start()

    def _on_update_progress(self, msg: str):
        self.statusBar().showMessage(msg)

    def _on_update_done(self, success: bool, updater):
        if success:
            reply = QMessageBox.question(
                self, "更新完成",
                "更新已完成，需要重启程序才能生效。\n\n是否立即重启？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    updater.restart_app()
                except Exception:
                    self.close()
                    sys.exit(0)
        else:
            QMessageBox.warning(self, "更新失败", "更新安装失败，请查看日志。")

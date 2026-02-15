"""
UI 主题配置 — qt-material 暗色主题 + qtawesome 图标 + 字体放大
"""

import sys
from pathlib import Path
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtCore import QSize


def _asset_dir() -> Path:
    """返回 assets/ 目录路径，兼容 PyInstaller 打包。"""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "assets"
        return Path(sys.executable).parent / "_internal" / "assets"
    return Path(__file__).parent.parent / "assets"


class Theme:
    # ── 颜色 ──
    COLOR_PRIMARY = "#3B8ED0"
    COLOR_BG_DARK = "#1A1A1A"
    COLOR_BG_CARD = "#222222"
    COLOR_INPUT_BG = "#2D2D2D"
    COLOR_SUCCESS = "#4CAF50"
    COLOR_WARNING = "#FFA726"
    COLOR_DANGER = "#FF5252"
    COLOR_TEXT = "#FFFFFF"
    COLOR_TEXT_GRAY = "#B0B0B0"
    COLOR_SIDEBAR = "#1E1E1E"
    COLOR_NAV_HOVER = "#2A2D32"
    COLOR_NAV_ACTIVE = "#333333"
    COLOR_GLOW_CYAN = "#00E5FF"
    COLOR_GLOW_BG = "#1E3246"

    # 日志颜色
    LOG_ERROR = "#FF5252"
    LOG_SUCCESS = "#4CAF50"
    LOG_STEP = "#42A5F5"
    LOG_WARNING = "#FFA726"
    LOG_CRITICAL = "#FF1744"

    # ── 布局 ──
    PAD_L = 30
    PAD_M = 15
    PAD_S = 8
    BTN_HEIGHT = 45
    ENTRY_HEIGHT = 45
    SIDEBAR_WIDTH = 220

    # ── 字体 ──
    FONT_FAMILY = "Microsoft YaHei UI"
    LOG_FONT_FAMILY = "Consolas"

    @staticmethod
    def font_header() -> QFont:
        return QFont(Theme.FONT_FAMILY, 28, QFont.Weight.Bold)

    @staticmethod
    def font_subheader() -> QFont:
        return QFont(Theme.FONT_FAMILY, 22, QFont.Weight.Bold)

    @staticmethod
    def font_title() -> QFont:
        return QFont(Theme.FONT_FAMILY, 18, QFont.Weight.Bold)

    @staticmethod
    def font_body() -> QFont:
        return QFont(Theme.FONT_FAMILY, 16)

    @staticmethod
    def font_small() -> QFont:
        return QFont(Theme.FONT_FAMILY, 13)

    @staticmethod
    def font_log() -> QFont:
        return QFont(Theme.LOG_FONT_FAMILY, 13)


# ── Icons 类 (qtawesome 封装) ──

class Icons:
    """集中管理所有 qtawesome 图标，fallback 到空 QIcon。"""

    _QTA = None

    @classmethod
    def _qta(cls):
        if cls._QTA is None:
            try:
                import qtawesome as qta
                cls._QTA = qta
            except ImportError:
                cls._QTA = False
        return cls._QTA if cls._QTA else None

    @classmethod
    def _icon(cls, name: str, color: str = "#FFFFFF", size: int = 24) -> QIcon:
        qta = cls._qta()
        if qta:
            try:
                return qta.icon(name, color=color)
            except Exception:
                pass
        return QIcon()

    # ── 导航栏图标 ──
    @classmethod
    def nav_scrape(cls): return cls._icon("mdi6.link-variant")
    @classmethod
    def nav_copywriting(cls): return cls._icon("mdi6.file-document-edit-outline")
    @classmethod
    def nav_generate(cls): return cls._icon("mdi6.palette-outline")
    @classmethod
    def nav_local_browse(cls): return cls._icon("mdi6.folder-open-outline")
    @classmethod
    def nav_text2image(cls): return cls._icon("mdi6.creation-outline")
    @classmethod
    def nav_automation(cls): return cls._icon("mdi6.rocket-launch-outline")
    @classmethod
    def nav_gallery(cls): return cls._icon("mdi6.image-multiple-outline")
    @classmethod
    def nav_config(cls): return cls._icon("mdi6.cog-outline")

    # ── 通用按钮图标 ──
    @classmethod
    def search(cls): return cls._icon("mdi6.magnify")
    @classmethod
    def key(cls): return cls._icon("mdi6.key-variant")
    @classmethod
    def file_image(cls): return cls._icon("mdi6.file-image-outline")
    @classmethod
    def folder_open(cls): return cls._icon("mdi6.folder-open-outline")
    @classmethod
    def copy(cls): return cls._icon("mdi6.content-copy")
    @classmethod
    def sync(cls): return cls._icon("mdi6.sync")
    @classmethod
    def robot(cls): return cls._icon("mdi6.robot-outline")
    @classmethod
    def translate(cls): return cls._icon("mdi6.translate")
    @classmethod
    def palette(cls): return cls._icon("mdi6.palette-outline")
    @classmethod
    def save(cls): return cls._icon("mdi6.content-save-outline")
    @classmethod
    def download(cls): return cls._icon("mdi6.download")
    @classmethod
    def delete(cls): return cls._icon("mdi6.delete-outline")
    @classmethod
    def stop(cls): return cls._icon("mdi6.stop-circle-outline")
    @classmethod
    def refresh(cls): return cls._icon("mdi6.refresh")
    @classmethod
    def upload(cls): return cls._icon("mdi6.upload")
    @classmethod
    def test(cls): return cls._icon("mdi6.flask-outline")
    @classmethod
    def update(cls): return cls._icon("mdi6.update")
    @classmethod
    def log(cls): return cls._icon("mdi6.text-box-outline")
    @classmethod
    def paste(cls): return cls._icon("mdi6.content-paste")
    @classmethod
    def analyze(cls): return cls._icon("mdi6.chart-box-outline")
    @classmethod
    def play(cls): return cls._icon("mdi6.play-circle-outline")
    @classmethod
    def image(cls): return cls._icon("mdi6.image-outline")
    @classmethod
    def prev(cls): return cls._icon("mdi6.chevron-left")
    @classmethod
    def next(cls): return cls._icon("mdi6.chevron-right")
    @classmethod
    def select_all(cls): return cls._icon("mdi6.select-all")
    @classmethod
    def deselect(cls): return cls._icon("mdi6.select-off")
    @classmethod
    def auth(cls): return cls._icon("mdi6.shield-key-outline")
    @classmethod
    def debug(cls): return cls._icon("mdi6.bug-outline")
    @classmethod
    def close(cls): return cls._icon("mdi6.close")

    @classmethod
    def star(cls): return cls._icon("mdi6.star-outline")

    @classmethod
    def star_filled(cls): return cls._icon("mdi6.star", "#FFD700")


# ── 导航图标映射 ──

NAV_ICON_MAP = {
    "scrape": Icons.nav_scrape,
    "copywriting": Icons.nav_copywriting,
    "generate": Icons.nav_generate,
    "local_browse": Icons.nav_local_browse,
    "text2image": Icons.nav_text2image,
    "automation": Icons.nav_automation,
    "gallery": Icons.nav_gallery,
    "config": Icons.nav_config,
}


# ── Override QSS ──

def _get_override_qss() -> str:
    return """
    /* ── 全局字体 ── */
    * {
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    }

    /* ── 侧边栏 ── */
    #sidebar {
        background-color: #1E1E1E;
        border-right: 1px solid #333;
    }
    #sidebar QPushButton {
        text-align: left;
        padding: 12px 18px;
        border: none;
        border-radius: 6px;
        margin: 3px 8px;
        font-size: 16px;
        color: #B0B0B0;
        background-color: transparent;
    }
    #sidebar QPushButton:hover {
        background-color: #282B30;
        color: #FFFFFF;
    }
    #sidebar QPushButton[active="true"] {
        background-color: #333333;
        color: #00E5FF;
        font-weight: bold;
    }
    #sidebar QPushButton#glowing {
        background-color: #1E3246;
        color: #00E5FF;
    }
    #appTitle {
        color: #FFFFFF;
        font-size: 20px;
    }

    /* ── 输入框 VS Code 风格灰底 ── */
    QLineEdit, QTextEdit, QPlainTextEdit {
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 10px;
        color: #FFFFFF;
        font-size: 15px;
        selection-background-color: #264F78;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
        border: 1px solid #3B8ED0;
    }

    /* ── 下拉菜单 ── */
    QComboBox {
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 12px;
        color: #FFFFFF;
        font-size: 15px;
        min-height: 32px;
    }
    QComboBox:!editable, QComboBox::drop-down:editable {
        color: #FFFFFF;
    }
    QComboBox:!editable:on, QComboBox::drop-down:editable:on {
        color: #FFFFFF;
    }
    QComboBox:hover {
        border: 1px solid #555;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 4px;
        color: #FFFFFF;
        font-size: 15px;
        selection-background-color: #666666;
        selection-color: #FFFFFF;
        outline: none;
    }
    QComboBox QAbstractItemView::item {
        padding: 6px 10px;
        min-height: 28px;
        color: #FFFFFF;
    }
    QComboBox QAbstractItemView::item:hover {
        background-color: #666666;
        color: #FFFFFF;
    }
    QComboBox QAbstractItemView::item:selected {
        background-color: #666666;
        color: #FFFFFF;
    }

    /* ── 按钮通用 ── */
    QPushButton {
        background-color: #333;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 8px 16px;
        color: #FFFFFF;
        font-size: 15px;
        min-height: 32px;
    }
    QPushButton:hover {
        background-color: #3A3A3A;
        border: 1px solid #555;
    }
    QPushButton:pressed {
        background-color: #404040;
    }
    QPushButton:disabled {
        background-color: #2A2A2A;
        color: #666;
        border: 1px solid #333;
    }

    /* 按钮变体 */
    QPushButton[class="success"] {
        background-color: #2E7D32;
        border: 1px solid #4CAF50;
        color: #FFFFFF;
    }
    QPushButton[class="success"]:hover {
        background-color: #33862E;
    }
    QPushButton[class="danger"] {
        background-color: #C62828;
        border: 1px solid #FF5252;
        color: #FFFFFF;
    }
    QPushButton[class="danger"]:hover {
        background-color: #CF2E2E;
    }
    QPushButton[class="warning"] {
        background-color: #E65100;
        border: 1px solid #FFA726;
        color: #FFFFFF;
    }
    QPushButton[class="warning"]:hover {
        background-color: #E86800;
    }
    QPushButton[class="flat"] {
        background-color: transparent;
        border: 1px solid #444;
    }
    QPushButton[class="flat"]:hover {
        background-color: #333;
    }

    /* ── QGroupBox ── */
    QGroupBox {
        border: 1px solid #444;
        border-radius: 8px;
        margin-top: 16px;
        padding: 20px 16px 16px 16px;
        font-size: 17px;
        font-weight: bold;
        color: #FFFFFF;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        color: #FFFFFF;
    }

    /* ── QLabel ── */
    QLabel {
        color: #FFFFFF;
        font-size: 15px;
    }
    QLabel[class="gray"] {
        color: #B0B0B0;
    }

    /* ── 滚动条 ── */
    QScrollBar:vertical {
        background: #1A1A1A;
        width: 10px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background: #444;
        border-radius: 5px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #555;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar:horizontal {
        background: #1A1A1A;
        height: 10px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal {
        background: #444;
        border-radius: 5px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #555;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
    }

    /* ── QFrame ── */
    QFrame[frameShape="6"] {
        border: 1px solid #333;
        border-radius: 8px;
        background-color: #1E1E1E;
    }

    /* ── QProgressBar ── */
    QProgressBar {
        border: 1px solid #444;
        border-radius: 6px;
        background-color: #2D2D2D;
        text-align: center;
        color: #FFFFFF;
        font-size: 13px;
        min-height: 22px;
    }
    QProgressBar::chunk {
        background-color: #3B8ED0;
        border-radius: 5px;
    }

    /* ── QCheckBox ── */
    QCheckBox {
        color: #FFFFFF;
        font-size: 14px;
        spacing: 8px;
    }

    /* ── QSplitter ── */
    QSplitter::handle {
        background-color: #333;
    }
    QSplitter::handle:horizontal {
        width: 3px;
    }
    QSplitter::handle:vertical {
        height: 3px;
    }

    /* ── QScrollArea ── */
    QScrollArea {
        border: none;
        background-color: transparent;
    }

    /* ── QListWidget ── */
    QListWidget {
        background-color: #2D2D2D;
        border: 1px solid #444;
        border-radius: 6px;
        color: #FFFFFF;
        font-size: 14px;
    }
    QListWidget::item:selected {
        background-color: #3B8ED0;
    }
    QListWidget::item:hover {
        background-color: #353535;
    }
    """


# ── 主题初始化 ──

def setup_app_theme(app):
    """应用 qt-material 暗色主题 + 自定义覆盖样式 + 柔和高亮色。"""
    try:
        from qt_material import apply_stylesheet
        apply_stylesheet(app, theme='dark_teal.xml')
        # 替换 qt-material 生成的亮色高亮为柔和深灰
        qss = app.styleSheet()
        qss = qss.replace('#6effe8', '#666666')
        qss = qss.replace('#1de9b6', '#666666')
        qss = qss.replace('rgba(29, 233, 182, 0.2)', 'rgba(255, 255, 255, 0.10)')
        qss = qss.replace('rgba(29, 233, 182, 0.1)', 'rgba(255, 255, 255, 0.06)')
        app.setStyleSheet(qss + _get_override_qss())
    except ImportError:
        qss = _load_fallback_qss()
        app.setStyleSheet(qss + _get_override_qss())

    # 覆盖 QPalette 高亮色 & 下拉菜单文字色
    from PySide6.QtGui import QPalette
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#666666"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
    app.setPalette(palette)


def _load_fallback_qss() -> str:
    """加载 assets/style.qss 作为 fallback。"""
    qss_path = _asset_dir() / "style.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def load_qss() -> str:
    """兼容旧接口，返回空字符串（已由 setup_app_theme 替代）。"""
    return ""


def logo_path() -> Path | None:
    """返回 logo 图片路径，找不到返回 None。"""
    for name in ("logo_circle.png", "logo.jpg", "logo.ico"):
        p = _asset_dir() / name
        if p.exists():
            return p
    return None

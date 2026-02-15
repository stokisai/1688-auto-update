"""
日志系统模块 - 用于调试和错误追踪

提供统一的日志记录功能，支持：
- 文件日志记录
- 控制台输出
- 日志级别控制
- 日志文件查看
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# 全局日志实例
_logger: Optional[logging.Logger] = None
_log_file_path: Optional[Path] = None
_debug_mode: bool = False
_stdout_redirected: bool = False


class _LogRedirector:
    """将 print() 输出同时写入日志文件"""

    def __init__(self, original_stream, log_file_path: Path):
        self._original = original_stream
        self._log_file = log_file_path

    def write(self, text):
        # 写到原始控制台
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        # 写到日志文件（跳过空行）
        if text and text.strip():
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self._log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] [PRINT] {text.rstrip()}\n")
            except Exception:
                pass

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise OSError("no fileno")

    def isatty(self):
        if self._original:
            return self._original.isatty()
        return False


def get_log_dir() -> Path:
    """获取日志目录路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后，使用exe所在目录
        base_dir = Path(sys.executable).parent
    else:
        # 脚本模式，使用项目根目录
        base_dir = Path(__file__).parent.parent

    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


def get_log_file_path() -> Path:
    """获取当前日志文件路径"""
    global _log_file_path
    if _log_file_path is None:
        log_dir = get_log_dir()
        # 使用日期作为日志文件名
        date_str = datetime.now().strftime("%Y-%m-%d")
        _log_file_path = log_dir / f"app_{date_str}.log"
    return _log_file_path


def setup_logger(debug_mode: bool = False) -> logging.Logger:
    """初始化日志系统"""
    global _logger, _debug_mode
    _debug_mode = debug_mode

    if _logger is not None:
        # 更新日志级别
        level = logging.DEBUG if debug_mode else logging.INFO
        _logger.setLevel(level)
        for handler in _logger.handlers:
            handler.setLevel(level)
        return _logger

    _logger = logging.getLogger("AI绘画工具")
    level = logging.DEBUG if debug_mode else logging.INFO
    _logger.setLevel(level)

    # 日志格式
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件处理器
    log_file = get_log_file_path()
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    # 控制台处理器 (使用原始stdout，避免重定向后重复)
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    # 记录启动信息
    _logger.info("=" * 50)
    _logger.info("AI绘画工具 日志系统启动")
    _logger.info(f"日志文件: {log_file}")
    _logger.info(f"调试模式: {'开启' if debug_mode else '关闭'}")
    _logger.info("=" * 50)

    # 重定向 stdout/stderr，让 print() 也写入日志
    global _stdout_redirected
    if not _stdout_redirected:
        sys.stdout = _LogRedirector(sys.__stdout__, log_file)
        sys.stderr = _LogRedirector(sys.__stderr__, log_file)
        _stdout_redirected = True

    return _logger


def get_logger() -> logging.Logger:
    """获取日志实例"""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def log_debug(msg: str):
    """记录调试信息"""
    get_logger().debug(msg)


def log_info(msg: str):
    """记录普通信息"""
    get_logger().info(msg)


def log_warning(msg: str):
    """记录警告信息"""
    get_logger().warning(msg)


def log_error(msg: str, exc_info: bool = False):
    """记录错误信息"""
    get_logger().error(msg, exc_info=exc_info)


def log_exception(msg: str):
    """记录异常信息（包含堆栈）"""
    get_logger().exception(msg)


def is_debug_mode() -> bool:
    """检查是否为调试模式"""
    return _debug_mode


def set_debug_mode(enabled: bool):
    """设置调试模式"""
    setup_logger(debug_mode=enabled)


def get_recent_logs(lines: int = 100) -> str:
    """获取最近的日志内容"""
    log_file = get_log_file_path()
    if not log_file.exists():
        return "暂无日志记录"

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)
    except Exception as e:
        return f"读取日志失败: {e}"


def get_all_log_files() -> list:
    """获取所有日志文件列表"""
    log_dir = get_log_dir()
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob("app_*.log"), reverse=True)
    return [f.name for f in log_files]


def clear_old_logs(keep_days: int = 7):
    """清理旧日志文件"""
    log_dir = get_log_dir()
    if not log_dir.exists():
        return

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=keep_days)

    for log_file in log_dir.glob("app_*.log"):
        try:
            # 从文件名解析日期
            date_str = log_file.stem.replace("app_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                log_info(f"已删除旧日志: {log_file.name}")
        except (ValueError, OSError):
            pass


def open_log_folder():
    """打开日志文件夹"""
    import subprocess
    log_dir = get_log_dir()
    if sys.platform == 'win32':
        os.startfile(str(log_dir))
    elif sys.platform == 'darwin':
        subprocess.run(['open', str(log_dir)])
    else:
        subprocess.run(['xdg-open', str(log_dir)])

"""
QThread workers for update checking and downloading.
"""

from PySide6.QtCore import QThread, Signal


class UpdateCheckWorker(QThread):
    """后台检查是否有新版本。"""
    update_available = Signal(dict)  # remote_info

    def __init__(self, app_dir: str, remote_url: str, parent=None):
        super().__init__(parent)
        self._app_dir = app_dir
        self._remote_url = remote_url

    def run(self):
        try:
            from updater import AutoUpdater
            updater = AutoUpdater(
                app_dir=self._app_dir,
                remote_version_url=self._remote_url,
            )
            has_update, remote_info = updater.check_for_update()
            if has_update and remote_info:
                self.update_available.emit(remote_info)
        except Exception as e:
            print(f"[更新检查] 错误: {e}")


class UpdateDownloadWorker(QThread):
    """下载并安装更新。"""
    progress = Signal(str)
    finished = Signal(bool)

    def __init__(self, updater, download_url: str, parent=None):
        super().__init__(parent)
        self._updater = updater
        self._url = download_url

    def run(self):
        try:
            self.progress.emit("正在下载更新包...")

            def on_progress(downloaded, total):
                if total > 0:
                    self.progress.emit(
                        f"下载中... {downloaded // 1024}KB / {total // 1024}KB"
                    )

            zip_path = self._updater.download_update(self._url, on_progress)
            if not zip_path:
                self.finished.emit(False)
                return

            self.progress.emit("正在安装更新...")
            success = self._updater.install_update(
                zip_path, lambda msg: self.progress.emit(msg)
            )
            self.finished.emit(success)
        except Exception as e:
            self.progress.emit(f"更新失败: {e}")
            self.finished.emit(False)

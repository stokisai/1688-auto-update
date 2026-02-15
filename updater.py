# -*- coding: utf-8 -*-
"""
Auto updater module.

Provides:
- version check
- update package download
- staged install script creation
- restart and apply update
"""

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests

try:
    from utils.logger import log_info, log_debug, log_error
except ImportError:
    def log_info(msg):  # type: ignore
        print(f"[INFO] {msg}")
    def log_debug(msg):  # type: ignore
        print(f"[DEBUG] {msg}")
    def log_error(msg, exc_info=False):  # type: ignore
        print(f"[ERROR] {msg}")


class AutoUpdater:
    """Auto updater."""

    def __init__(self, app_dir: str = None, remote_version_url: str = None):
        if app_dir:
            provided_dir = Path(app_dir)
            # If caller passed .../_internal by mistake, normalize to parent app root.
            if provided_dir.name.lower() == "_internal":
                parent_dir = provided_dir.parent
                try:
                    has_exe = any(
                        p.is_file() and p.suffix.lower() == ".exe"
                        for p in parent_dir.iterdir()
                    )
                except Exception:
                    has_exe = False
                if has_exe:
                    log_debug(f"[更新器] app_dir 从 _internal 自动纠正到根目录: {provided_dir} -> {parent_dir}")
                    provided_dir = parent_dir
            self.app_dir = provided_dir
        elif getattr(sys, "frozen", False):
            self.app_dir = Path(sys.executable).parent
        else:
            self.app_dir = Path(__file__).parent

        self.remote_version_url = remote_version_url
        self.local_version_file = self._find_version_file()
        self.local_version_info = self._load_local_version()
        self._report_previous_update_result()

    def _report_previous_update_result(self):
        """
        Report previous update script result into app log for easier diagnosis.
        """
        try:
            flag = self.app_dir / "_update_success.flag"
            bat_log = self.app_dir / "_do_update.log"
            if flag.exists():
                log_info(f"[更新结果] 检测到成功标记: {flag}")
                try:
                    flag.unlink()
                except Exception:
                    pass
                return

            if bat_log.exists():
                try:
                    text = bat_log.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = bat_log.read_text(encoding="gbk", errors="ignore")
                tail = "\n".join(text.splitlines()[-30:])
                log_error(f"[更新结果] 上次更新脚本未标记成功，_do_update.log 尾部:\n{tail}")
        except Exception:
            pass

    def _find_version_file(self) -> Path:
        """
        Find version.json with stable priority.
        Prefer standard locations first to avoid stale nested paths.
        """
        # 开发模式下优先读根目录 version.json（源文件），
        # 打包模式下优先读 _internal/version.json（打包产物）。
        if getattr(sys, "frozen", False):
            preferred = [
                self.app_dir / "_internal" / "version.json",
                self.app_dir / "version.json",
            ]
        else:
            preferred = [
                self.app_dir / "version.json",
                self.app_dir / "_internal" / "version.json",
            ]
        if self.app_dir.name.lower() == "_internal":
            preferred.extend([
                self.app_dir.parent / "_internal" / "version.json",
                self.app_dir.parent / "version.json",
            ])

        fallback = [
            self.app_dir / "_internal" / "_internal" / "version.json",
            self.app_dir.parent / "_internal" / "_internal" / "version.json",
        ]

        seen = set()
        for p in preferred + fallback:
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            if not p.exists():
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    info = json.load(f)
                version = str(info.get("version", "0.0.0"))
                log_debug(f"[更新器] 找到版本文件: {p} (version={version})")
                return p
            except Exception:
                continue

        default_path = self.app_dir / "_internal" / "version.json"
        log_debug(f"[更新器] 未找到版本文件，使用默认路径: {default_path}")
        return default_path

    def _load_local_version(self) -> dict:
        if self.local_version_file.exists():
            try:
                with open(self.local_version_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": "0.0.0", "app_name": "AI绘画工具"}

    def get_local_version(self) -> str:
        return str(self.local_version_info.get("version", "0.0.0"))

    def _compare_versions(self, v1: str, v2: str) -> int:
        def parse(v: str):
            parts = []
            for x in str(v).split("."):
                try:
                    parts.append(int(x))
                except Exception:
                    parts.append(0)
            return parts

        p1 = parse(v1)
        p2 = parse(v2)
        for i in range(max(len(p1), len(p2))):
            a = p1[i] if i < len(p1) else 0
            b = p2[i] if i < len(p2) else 0
            if a > b:
                return 1
            if a < b:
                return -1
        return 0

    def check_for_update(self) -> Tuple[bool, Optional[dict]]:
        if not self.remote_version_url:
            log_debug("[更新检查] 未配置远程版本 URL")
            return False, None

        try:
            log_info(f"[更新检查] 正在检查更新: {self.remote_version_url}")
            response = requests.get(self.remote_version_url, timeout=10)
            response.raise_for_status()
            remote_info = response.json()

            remote_version = str(remote_info.get("version", "0.0.0"))
            local_version = self.get_local_version()
            log_info(f"[更新检查] 本地版本: {local_version}, 远程版本: {remote_version}")

            if self._compare_versions(remote_version, local_version) > 0:
                log_info("[更新检查] 发现新版本!")
                return True, remote_info

            log_info("[更新检查] 已是最新版本")
            return False, remote_info
        except Exception as e:
            log_error(f"[更新检查] 检查更新失败: {e}")
            return False, None

    def download_update(
        self,
        download_url: str,
        progress_callback: Callable[[int, int], None] = None,
    ) -> Optional[str]:
        try:
            log_info(f"[更新下载] 开始下载: {download_url}")
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            log_debug(f"[更新下载] 文件大小: {total_size} bytes")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            temp_path = temp_file.name
            temp_file.close()
            log_debug(f"[更新下载] 临时文件: {temp_path}")

            downloaded = 0
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

            log_info(f"[更新下载] 下载完成: {downloaded} bytes")
            return temp_path
        except Exception as e:
            log_error(f"[更新下载] 下载失败: {e}")
            return None

    def install_update(
        self,
        zip_path: str,
        progress_callback: Callable[[str], None] = None,
    ) -> bool:
        """
        Stage update files to app_dir/_update and create _do_update.bat.
        Actual replacement is done after app exits.
        """
        try:
            log_info("[更新安装] 开始安装更新")
            log_debug(f"[更新安装] zip路径: {zip_path}")
            log_debug(f"[更新安装] 应用目录: {self.app_dir}")
            log_debug(f"[更新安装] sys.executable: {sys.executable}")
            log_debug(f"[更新安装] sys.frozen: {getattr(sys, 'frozen', False)}")

            if progress_callback:
                progress_callback("正在解压更新包...")

            update_dir = self.app_dir / "_update"
            if update_dir.exists():
                shutil.rmtree(update_dir, ignore_errors=True)
            update_dir.mkdir(parents=True, exist_ok=True)
            log_debug(f"[更新安装] 更新目录: {update_dir}")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                names = zip_ref.namelist()
                log_debug(f"[更新安装] zip文件数量: {len(names)}")
                zip_ref.extractall(update_dir)

            log_info("[更新安装] 解压完成")

            extracted_items = list(update_dir.iterdir())
            log_debug(f"[更新安装] 解压后根目录内容: {[x.name for x in extracted_items]}")
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]
                log_debug(f"[更新安装] 检测到单一根目录，使用: {source_dir}")
            else:
                source_dir = update_dir
                log_debug(f"[更新安装] 使用更新目录作为源: {source_dir}")

            if progress_callback:
                progress_callback("正在准备更新脚本...")

            self._create_update_script(source_dir, zip_path)

            if progress_callback:
                progress_callback("更新准备完成，重启后生效！")

            log_info("[更新安装] 更新脚本已创建，等待重启")
            return True
        except Exception as e:
            log_error(f"[更新安装] 安装失败: {e}", exc_info=True)
            return False

    def _create_update_script(self, source_dir: Path, zip_path: str):
        """Create _do_update.bat, _do_update.vbs, and _update_progress.hta in app root."""
        script_path = self.app_dir / "_do_update.bat"
        vbs_path = self.app_dir / "_do_update.vbs"
        hta_path = self.app_dir / "_update_progress.hta"

        current_exe = Path(sys.executable).name if getattr(sys, "frozen", False) else "python.exe"
        new_exe_name = current_exe
        for item in source_dir.iterdir():
            if item.is_file() and item.suffix.lower() == ".exe" and item.name != "selenium-manager.exe":
                new_exe_name = item.name
                break

        # Flag file in %TEMP% signals the HTA to close itself.
        flag_name = "_ai_update_done.flag"

        # --- BAT: actual update logic (runs hidden via VBS) ---
        script_content = f"""@echo off
setlocal EnableExtensions
set "APP_DIR=%~dp0"
set "LOG=%APP_DIR%_do_update.log"
set "FLAG=%APP_DIR%_update_success.flag"
set "DONE_FLAG=%TEMP%\\{flag_name}"
set "CURRENT_EXE={current_exe}"
set "NEW_EXE={new_exe_name}"
set "SRC=%APP_DIR%_update"
set "SRC_EXE=%SRC%\\\\%NEW_EXE%"
set "SRC_INTERNAL=%SRC%\\\\_internal"
set "DST_EXE=%APP_DIR%%NEW_EXE%"
set "DST_INTERNAL=%APP_DIR%_internal"
set "BAK_DIR=%TEMP%\\\\ai_update_bak"
set "RC=0"

cd /d "%APP_DIR%"
if exist "%DONE_FLAG%" del /f /q "%DONE_FLAG%" >nul 2>&1
echo [%%date%% %%time%%] updater start>"%LOG%"
if exist "%FLAG%" del /f /q "%FLAG%" >nul 2>&1

echo [1/6] force close running app>>"%LOG%"
taskkill /F /IM %CURRENT_EXE% >nul 2>&1

echo [1/6] wait process exit>>"%LOG%"
:wait_loop
tasklist /FI "IMAGENAME eq %CURRENT_EXE%" 2>NUL | find /I "%CURRENT_EXE%" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo [2/6] backup user files>>"%LOG%"
if exist "%BAK_DIR%" rmdir /s /q "%BAK_DIR%" >nul 2>&1
mkdir "%BAK_DIR%" >nul 2>&1
if exist "%DST_INTERNAL%\\\\user_config.json" copy /y "%DST_INTERNAL%\\\\user_config.json" "%BAK_DIR%\\\\user_config.json" >nul 2>&1
if exist "%DST_INTERNAL%\\\\config\\\\1688_cookies.json" (
    if not exist "%BAK_DIR%\\\\config" mkdir "%BAK_DIR%\\\\config"
    copy /y "%DST_INTERNAL%\\\\config\\\\1688_cookies.json" "%BAK_DIR%\\\\config\\\\1688_cookies.json" >nul 2>&1
)

echo [3/6] remove old internal>>"%LOG%"
if exist "%DST_INTERNAL%" rmdir /s /q "%DST_INTERNAL%" >nul 2>&1

echo [4/6] copy new files>>"%LOG%"
if not exist "%SRC_EXE%" (
    echo [error] source exe missing: %SRC_EXE%>>"%LOG%"
    goto copy_fail
)
copy /y "%SRC_EXE%" "%DST_EXE%" >nul
if errorlevel 1 (
    echo [error] copy exe failed>>"%LOG%"
    goto copy_fail
)
if not exist "%SRC_INTERNAL%" (
    echo [error] source internal missing: %SRC_INTERNAL%>>"%LOG%"
    goto copy_fail
)
robocopy "%SRC_INTERNAL%" "%DST_INTERNAL%" /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NC /NS >nul
set "RC=%ERRORLEVEL%"
echo [info] robocopy internal rc=%RC%>>"%LOG%"
if %RC% GEQ 8 goto copy_fail

echo [5/6] restore user files>>"%LOG%"
if exist "%BAK_DIR%\\\\user_config.json" (
    if not exist "%DST_INTERNAL%" mkdir "%DST_INTERNAL%"
    copy /y "%BAK_DIR%\\\\user_config.json" "%DST_INTERNAL%\\\\user_config.json" >nul 2>&1
)
if exist "%BAK_DIR%\\\\config\\\\1688_cookies.json" (
    if not exist "%DST_INTERNAL%\\\\config" mkdir "%DST_INTERNAL%\\\\config"
    copy /y "%BAK_DIR%\\\\config\\\\1688_cookies.json" "%DST_INTERNAL%\\\\config\\\\1688_cookies.json" >nul 2>&1
)

echo [6/6] cleanup>>"%LOG%"
rmdir /s /q "%APP_DIR%_update" >nul 2>&1
if exist "%BAK_DIR%" rmdir /s /q "%BAK_DIR%" >nul 2>&1
if exist "{zip_path}" del /f /q "{zip_path}" >nul 2>&1

echo [ok] update applied>>"%LOG%"
echo ok>"%FLAG%"
echo done>"%DONE_FLAG%"

echo [done] start new exe>>"%LOG%"
if exist "%APP_DIR%%NEW_EXE%" (
    start "" "%APP_DIR%%NEW_EXE%"
) else (
    start "" "%APP_DIR%%CURRENT_EXE%"
)

if exist "%APP_DIR%_update_progress.hta" del /f /q "%APP_DIR%_update_progress.hta" >nul 2>&1
if exist "%APP_DIR%_do_update.vbs" del /f /q "%APP_DIR%_do_update.vbs" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
exit /b 0

:copy_fail
echo [error] update failed, rc=%RC%>>"%LOG%"
echo done>"%DONE_FLAG%"
start "" "%APP_DIR%%CURRENT_EXE%"
if exist "%APP_DIR%_update_progress.hta" del /f /q "%APP_DIR%_update_progress.hta" >nul 2>&1
if exist "%APP_DIR%_do_update.vbs" del /f /q "%APP_DIR%_do_update.vbs" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
exit /b 1
"""

        # --- HTA: small progress window (auto-closes when flag appears) ---
        hta_content = (
            '<html>\n<head>\n'
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            '<title>AI Drawing Tool</title>\n'
            '<HTA:APPLICATION BORDER="thin" INNERBORDER="no" SCROLL="no" '
            'MAXIMIZEBUTTON="no" MINIMIZEBUTTON="no" SYSMENU="no" />\n'
            '<script language="javascript">\n'
            'window.resizeTo(400,180);\n'
            'window.moveTo((screen.width-400)/2,(screen.height-180)/2);\n'
            'var wsh=new ActiveXObject("WScript.Shell");\n'
            'var fso=new ActiveXObject("Scripting.FileSystemObject");\n'
            'var flag=wsh.ExpandEnvironmentStrings("%TEMP%")+"\\\\' + flag_name + '";\n'
            'function chk(){if(fso.FileExists(flag)){'
            'try{fso.DeleteFile(flag);}catch(e){}'
            'window.close();}}\n'
            'setInterval(chk,1000);\n'
            '</script>\n'
            '<style>\n'
            'body{font-family:Microsoft YaHei,sans-serif;text-align:center;'
            'background:#2b2b2b;color:#fff;margin:0;padding:35px 20px;}\n'
            'h2{margin:0 0 12px;font-size:17px;font-weight:normal;}\n'
            'p{color:#999;font-size:12px;margin:0;}\n'
            '</style>\n</head>\n<body>\n'
            '<h2>\u23f3 \u7a0b\u5e8f\u6b63\u5728\u66f4\u65b0\u4e2d\uff0c\u8bf7\u7a0d\u5019...</h2>\n'
            '<p>\u66f4\u65b0\u5b8c\u6210\u540e\u7a0b\u5e8f\u5c06\u81ea\u52a8\u91cd\u542f\uff0c'
            '\u8bf7\u52ff\u5173\u95ed\u6b64\u7a97\u53e3</p>\n'
            '</body>\n</html>'
        )

        # --- VBS: launches HTA then runs BAT hidden ---
        vbs_content = (
            'Set WshShell = CreateObject("WScript.Shell")\n'
            'Set fso = CreateObject("Scripting.FileSystemObject")\n'
            'strDir = fso.GetParentFolderName(WScript.ScriptFullName)\n'
            'strBat = strDir & "\\_do_update.bat"\n'
            'strHta = strDir & "\\_update_progress.hta"\n'
            'If fso.FileExists(strHta) Then\n'
            '    WshShell.Run """" & strHta & """", 1, False\n'
            'End If\n'
            'WshShell.Run "cmd /c """ & strBat & """", 0, True\n'
        )

        try:
            with open(script_path, "w", encoding="ascii", errors="ignore") as f:
                f.write(script_content)
            with open(hta_path, "w", encoding="utf-8") as f:
                f.write(hta_content)
            with open(vbs_path, "w", encoding="ascii", errors="ignore") as f:
                f.write(vbs_content)
            log_debug(f"[更新安装] 创建更新脚本: {script_path}, {vbs_path}, {hta_path}")
        except Exception as e:
            log_error(f"[更新安装] 创建更新脚本失败: {e}")

    def restart_app(self):
        """Restart app; if update script exists, run it."""
        if getattr(sys, "frozen", False):
            current_exe = Path(sys.executable)
            update_vbs = self.app_dir / "_do_update.vbs"
            update_script = self.app_dir / "_do_update.bat"

            if update_vbs.exists():
                log_info("[重启] 检测到更新脚本(VBS)，静默执行更新...")
                subprocess.Popen(
                    ["wscript", str(update_vbs)],
                    cwd=str(self.app_dir),
                )
            elif update_script.exists():
                log_info("[重启] 检测到更新脚本(BAT)，执行更新...")
                kwargs = {"cwd": str(self.app_dir)}
                try:
                    kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
                except Exception:
                    pass
                subprocess.Popen(["cmd", "/c", str(update_script)], **kwargs)
            else:
                log_info(f"[重启] 未找到更新脚本，直接重启: {current_exe}")
                subprocess.Popen([str(current_exe)], cwd=str(self.app_dir))
        else:
            python = sys.executable
            script = str(self.app_dir / "main.py")
            subprocess.Popen([python, script], cwd=str(self.app_dir))

        sys.exit(0)


def check_update_on_startup(remote_url: str) -> Tuple[bool, Optional[dict]]:
    updater = AutoUpdater(remote_version_url=remote_url)
    return updater.check_for_update()

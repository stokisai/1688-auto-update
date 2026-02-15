"""
设备指纹模块 - 收集设备硬件信息生成唯一设备ID

使用多种硬件信息组合生成设备指纹，确保唯一性和稳定性。
所有信息都经过hash处理，不存储明文。
"""

import hashlib
import subprocess
import platform
import uuid
from typing import Optional


class DeviceFingerprint:
    """设备指纹生成器"""

    def __init__(self):
        self._fingerprint_cache: Optional[str] = None

    def get_device_id(self) -> str:
        """
        获取设备唯一ID（16位十六进制字符串）

        Returns:
            str: 设备唯一ID
        """
        if self._fingerprint_cache:
            return self._fingerprint_cache

        # 收集各种硬件信息
        components = []

        # 1. CPU ID
        cpu_id = self._get_cpu_id()
        if cpu_id:
            components.append(f"CPU:{cpu_id}")

        # 2. 主板序列号
        motherboard_sn = self._get_motherboard_serial()
        if motherboard_sn:
            components.append(f"MB:{motherboard_sn}")

        # 3. 硬盘序列号
        disk_sn = self._get_disk_serial()
        if disk_sn:
            components.append(f"DISK:{disk_sn}")

        # 4. MAC地址
        mac = self._get_mac_address()
        if mac:
            components.append(f"MAC:{mac}")

        # 5. 操作系统信息作为补充
        os_info = f"{platform.system()}-{platform.machine()}"
        components.append(f"OS:{os_info}")

        # 组合所有信息并生成hash
        combined = "|".join(components)
        full_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        # 取前16位作为设备ID（便于用户输入）
        self._fingerprint_cache = full_hash[:16].upper()
        return self._fingerprint_cache

    def _run_wmic_command(self, command: str) -> Optional[str]:
        """运行WMIC命令并返回结果"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # 跳过标题行，获取实际值
                for line in lines[1:]:
                    value = line.strip()
                    if value and value.lower() not in ['', 'none', 'to be filled by o.e.m.']:
                        return value
        except Exception:
            pass
        return None

    def _get_cpu_id(self) -> Optional[str]:
        """获取CPU ID"""
        if platform.system() != 'Windows':
            return None

        cpu_id = self._run_wmic_command('wmic cpu get ProcessorId')
        if cpu_id:
            return hashlib.md5(cpu_id.encode()).hexdigest()[:12]
        return None

    def _get_motherboard_serial(self) -> Optional[str]:
        """获取主板序列号"""
        if platform.system() != 'Windows':
            return None

        serial = self._run_wmic_command('wmic baseboard get SerialNumber')
        if serial:
            return hashlib.md5(serial.encode()).hexdigest()[:12]
        return None

    def _get_disk_serial(self) -> Optional[str]:
        """获取硬盘序列号"""
        if platform.system() != 'Windows':
            return None

        serial = self._run_wmic_command('wmic diskdrive get SerialNumber')
        if serial:
            return hashlib.md5(serial.encode()).hexdigest()[:12]
        return None

    def _get_mac_address(self) -> Optional[str]:
        """获取MAC地址"""
        try:
            mac = uuid.getnode()
            mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
            return hashlib.md5(mac_str.encode()).hexdigest()[:12]
        except Exception:
            return None

    def get_device_info_display(self) -> str:
        """
        获取设备信息的显示文本（用于调试/显示）

        Returns:
            str: 设备信息摘要
        """
        info_lines = [
            f"设备ID: {self.get_device_id()}",
            f"操作系统: {platform.system()} {platform.release()}",
            f"处理器: {platform.processor() or '未知'}",
        ]
        return "\n".join(info_lines)


# 单例实例
_fingerprint_instance: Optional[DeviceFingerprint] = None


def get_device_fingerprint() -> DeviceFingerprint:
    """获取设备指纹单例实例"""
    global _fingerprint_instance
    if _fingerprint_instance is None:
        _fingerprint_instance = DeviceFingerprint()
    return _fingerprint_instance


def get_device_id() -> str:
    """快捷方法：获取设备ID"""
    return get_device_fingerprint().get_device_id()


if __name__ == "__main__":
    # 测试
    fp = DeviceFingerprint()
    print("设备指纹信息:")
    print(fp.get_device_info_display())

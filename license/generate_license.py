"""
激活码生成工具 - 老师专用

使用方法：
1. 学员运行软件，获取设备ID
2. 学员将设备ID发给老师
3. 老师运行此脚本，输入设备ID，生成激活码
4. 老师将激活码发给学员
5. 学员输入激活码完成激活

注意：此脚本仅供老师使用，请勿分发给学员！
"""

import hmac
import hashlib

# ==================== 密钥配置 ====================
# 重要：这个密钥必须与 license_manager.py 中的一致
SECRET_KEY = "AI_BINDAO_2024_STOKIS_SECRET_KEY_V1"
# =================================================


def generate_license_key(device_id: str) -> str:
    """
    根据设备ID生成激活码

    Args:
        device_id: 设备ID（16位十六进制字符串）

    Returns:
        str: 16位激活码
    """
    message = device_id.upper().strip().encode('utf-8')
    key = SECRET_KEY.encode('utf-8')
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return signature[:16].upper()


def validate_device_id(device_id: str) -> tuple[bool, str]:
    """验证设备ID格式"""
    device_id = device_id.strip()
    if len(device_id) != 16:
        return False, f"错误：设备ID应为16位，当前输入为{len(device_id)}位"
    try:
        int(device_id, 16)
    except ValueError:
        return False, "错误：设备ID应为十六进制字符串（只包含0-9和A-F）"
    return True, ""


def interactive_mode():
    """交互模式 - 循环输入设备ID生成激活码"""
    print("=" * 50)
    print("    AI绘画工具 - 激活码生成器（老师专用）")
    print("=" * 50)
    print()

    while True:
        print("请输入学员的设备ID（输入 q 退出）：")
        device_id = input("> ").strip()

        if device_id.lower() == 'q':
            print("再见！")
            break

        valid, error_msg = validate_device_id(device_id)
        if not valid:
            print(error_msg)
            print("请重新输入\n")
            continue

        license_key = generate_license_key(device_id)

        print()
        print("-" * 50)
        print(f"设备ID:   {device_id.upper()}")
        print(f"激活码:   {license_key}")
        print("-" * 50)
        print("请将激活码发送给学员")
        print()


def main():
    import sys

    # 如果有命令行参数，直接生成激活码
    if len(sys.argv) > 1:
        device_id = sys.argv[1]
        valid, error_msg = validate_device_id(device_id)
        if not valid:
            print(error_msg)
            sys.exit(1)

        license_key = generate_license_key(device_id)
        print(f"设备ID: {device_id.upper()}")
        print(f"激活码: {license_key}")
    else:
        # 无参数时进入交互模式
        interactive_mode()


if __name__ == "__main__":
    main()

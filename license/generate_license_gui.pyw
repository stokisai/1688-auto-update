"""
AI绘画工具 - 激活码生成器 GUI版（老师专用）
"""

import tkinter as tk
from tkinter import ttk, messagebox
import hmac
import hashlib

# 密钥配置 - 必须与 license_manager.py 中的一致
SECRET_KEY = "AI_BINDAO_2024_STOKIS_SECRET_KEY_V1"


def generate_license_key(device_id: str) -> str:
    """根据设备ID生成激活码"""
    message = device_id.upper().strip().encode('utf-8')
    key = SECRET_KEY.encode('utf-8')
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return signature[:16].upper()


def validate_device_id(device_id: str) -> tuple:
    """验证设备ID格式"""
    device_id = device_id.strip()
    if len(device_id) != 16:
        return False, f"设备ID应为16位，当前输入为{len(device_id)}位"
    try:
        int(device_id, 16)
    except ValueError:
        return False, "设备ID应为十六进制字符串（只包含0-9和A-F）"
    return True, ""


class LicenseGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI绘画工具 - 激活码生成器（老师专用）")
        self.root.geometry("500x350")
        self.root.resizable(False, False)

        # 设置窗口居中
        self.center_window()

        self.create_widgets()

    def center_window(self):
        """窗口居中显示"""
        self.root.update_idletasks()
        width = 500
        height = 350
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(
            main_frame,
            text="AI绘画工具 - 激活码生成器",
            font=("Microsoft YaHei", 16, "bold")
        )
        title_label.pack(pady=(0, 5))

        subtitle_label = ttk.Label(
            main_frame,
            text="（老师专用）",
            font=("Microsoft YaHei", 10),
            foreground="gray"
        )
        subtitle_label.pack(pady=(0, 20))

        # 设备ID输入区域
        input_frame = ttk.LabelFrame(main_frame, text="输入设备ID", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 15))

        self.device_id_var = tk.StringVar()
        self.device_id_entry = ttk.Entry(
            input_frame,
            textvariable=self.device_id_var,
            font=("Consolas", 12),
            width=30
        )
        self.device_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.device_id_entry.bind('<Return>', lambda e: self.generate())

        generate_btn = ttk.Button(
            input_frame,
            text="生成激活码",
            command=self.generate
        )
        generate_btn.pack(side=tk.LEFT)

        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="生成结果", padding="10")
        result_frame.pack(fill=tk.X, pady=(0, 15))

        # 设备ID显示
        device_row = ttk.Frame(result_frame)
        device_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(device_row, text="设备ID:", width=10).pack(side=tk.LEFT)
        self.device_id_result = tk.StringVar(value="-")
        ttk.Label(
            device_row,
            textvariable=self.device_id_result,
            font=("Consolas", 11)
        ).pack(side=tk.LEFT)

        # 激活码显示
        license_row = ttk.Frame(result_frame)
        license_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(license_row, text="激活码:", width=10).pack(side=tk.LEFT)
        self.license_result = tk.StringVar(value="-")
        license_label = ttk.Label(
            license_row,
            textvariable=self.license_result,
            font=("Consolas", 14, "bold"),
            foreground="green"
        )
        license_label.pack(side=tk.LEFT)

        # 复制按钮
        self.copy_btn = ttk.Button(
            result_frame,
            text="复制激活码",
            command=self.copy_license,
            state=tk.DISABLED
        )
        self.copy_btn.pack(pady=(10, 0))

        # 提示信息
        tip_label = ttk.Label(
            main_frame,
            text="提示：输入学员的16位设备ID，点击生成激活码，然后发送给学员",
            font=("Microsoft YaHei", 9),
            foreground="gray"
        )
        tip_label.pack(pady=(10, 0))

    def generate(self):
        """生成激活码"""
        device_id = self.device_id_var.get().strip()

        if not device_id:
            messagebox.showwarning("提示", "请输入设备ID")
            return

        valid, error_msg = validate_device_id(device_id)
        if not valid:
            messagebox.showerror("错误", error_msg)
            return

        device_id = device_id.upper()
        license_key = generate_license_key(device_id)

        self.device_id_result.set(device_id)
        self.license_result.set(license_key)
        self.copy_btn.config(state=tk.NORMAL)

        # 自动选中输入框内容，方便下次输入
        self.device_id_entry.select_range(0, tk.END)

    def copy_license(self):
        """复制激活码到剪贴板"""
        license_key = self.license_result.get()
        if license_key and license_key != "-":
            self.root.clipboard_clear()
            self.root.clipboard_append(license_key)
            messagebox.showinfo("成功", "激活码已复制到剪贴板！")


def main():
    root = tk.Tk()
    app = LicenseGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

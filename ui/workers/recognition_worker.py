"""
QThread worker for AI recognition tasks.
"""

from PySide6.QtCore import QThread, Signal


class RecognitionWorker(QThread):
    """后台执行 AI 识别（文案分析、卖点提取等）。"""

    progress = Signal(str, str)   # message, level
    finished = Signal(str)        # result text
    error = Signal(str)

    def __init__(self, api_key: str, text: str, mode: str = "prompt", parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._text = text
        self._mode = mode  # "prompt" | "selling_points"

    def run(self):
        try:
            import requests

            if self._mode == "selling_points":
                self._run_selling_points(requests)
            else:
                self._run_prompt_generation(requests)
        except Exception as e:
            self.error.emit(str(e))

    def _run_prompt_generation(self, requests):
        self.progress.emit("正在分析文案...", "step")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        prompt = (
            "请分析以下电商商品文案，提取关键视觉信息（主体、材质、颜色、风格、场景），"
            "并生成一段适用于 AI 绘画（如 Midjourney, Stable Diffusion）的英文提示词（Prompt）。\n\n"
            "要求：\n"
            "1. 提示词应包含：Subject, Medium, Environment, Lighting, Color, Composition。\n"
            "2. 移除品牌名称、水印文字、促销信息。\n"
            "3. 强调商品的高级感和质感。\n"
            "4. 直接输出英文提示词，不要解释。\n\n"
            "商品文案：\n"
        )

        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an expert AI art prompt generator for e-commerce products."},
                {"role": "user", "content": prompt + self._text[:3000]},
            ],
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.finished.emit(result)

    def _run_selling_points(self, requests):
        self.progress.emit("正在分析卖点...", "step")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        prompt = (
            "请分析以下电商产品文案，提取产品的核心卖点（Selling Points）。\n\n"
            "要求：\n"
            "1. 提取3-5个最重要的产品卖点\n"
            "2. 每个卖点用一句话概括，突出产品优势\n"
            "3. 卖点包括但不限于：材质优势、功能特点、设计亮点、性价比、适用场景等\n"
            "4. 使用中文输出，简洁明了\n"
            "5. 直接列出卖点，不要有前言或解释\n\n"
            "格式示例：\n"
            "• 卖点1：xxx\n• 卖点2：xxx\n• 卖点3：xxx\n\n"
            f"产品文案：\n{self._text[:3000]}\n\n请直接输出卖点："
        )

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
        self.finished.emit(result)

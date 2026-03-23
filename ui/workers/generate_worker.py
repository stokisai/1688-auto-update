"""
QThread worker for image generation (text2image + image2image).
"""

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal


def _resolve_gemini_key(api_keys, prefer_pro: bool = False) -> str:
    order = (
        ["nano_banana_pro_api_key", "nano_banana_api_key"]
        if prefer_pro
        else ["nano_banana_api_key", "nano_banana_pro_api_key"]
    )
    order.append("gemini_api_key")
    for field in order:
        v = getattr(api_keys, field, "")
        if v:
            return v
    return os.environ.get("GEMINI_API_KEY", "")


class GenerateWorker(QThread):
    """通用图片生成 worker，支持 text2image 和 image2image。"""

    progress = Signal(str, str)   # message, level
    finished = Signal(str)        # result_path
    error = Signal(str)

    def __init__(
        self,
        config,
        engine: str,
        prompt: str = "",
        source_image: str | None = None,
        output_dir: str = "./output/generated",
        workflow_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._engine = engine
        self._prompt = prompt
        self._source = source_image
        self._output = output_dir
        self._workflow = workflow_name

    def run(self):
        try:
            Path(self._output).mkdir(parents=True, exist_ok=True)

            if self._engine == "comfyui":
                self._run_comfyui()
            elif self._engine == "nano_banana":
                self._run_nano(pro=False)
            elif self._engine == "nano_banana_pro":
                self._run_nano(pro=True)
            elif self._engine == "doubao":
                self._run_doubao()
            else:
                self.error.emit(f"未知引擎: {self._engine}")
        except Exception as e:
            self.error.emit(str(e))

    def _run_comfyui(self):
        from image_generation import ComfyUIFluxKontextClient

        url = self._config.comfyui.get_effective_server_url()
        if not url:
            self.error.emit("请先配置 ComfyUI 服务器地址")
            return

        self.progress.emit("连接 ComfyUI...", "step")
        client = ComfyUIFluxKontextClient(url)

        if self._workflow:
            wf = self._config.comfyui.get_workflow(self._workflow)
            if wf:
                client.set_workflow(
                    wf.get("json", {}),
                    wf.get("prompt_node_id", "6"),
                    wf.get("prompt_param_path", "inputs.text"),
                    image_node_id=wf.get("image_node_id"),
                    image_param_path=wf.get("image_param_path"),
                )

        if not client.test_connection():
            self.error.emit(f"无法连接 ComfyUI: {url}")
            return

        self.progress.emit("正在生成...", "step")
        if self._source:
            result = client.image_to_image(self._source, self._prompt, output_dir=self._output)
        else:
            result = client.image_to_image(None, self._prompt, output_dir=self._output)

        if result:
            self.progress.emit("生成完成", "success")
            self.finished.emit(result)
        else:
            self.error.emit("ComfyUI 生成失败")

    def _run_nano(self, pro: bool):
        key = _resolve_gemini_key(self._config.api_keys, prefer_pro=pro)
        if not key:
            self.error.emit("请先配置 Gemini / Nano API Key")
            return

        self.progress.emit("正在生成...", "step")

        if pro:
            from image_generation import NanoBananaProClient
            client = NanoBananaProClient(key)
        else:
            from image_generation import NanoBananaBasicClient
            client = NanoBananaBasicClient(key)

        if self._source:
            result = client.image_to_image(self._source, self._prompt, output_dir=self._output)
        else:
            result = client.generate(self._prompt, output_dir=self._output)

        if result:
            self.progress.emit("生成完成", "success")
            self.finished.emit(result)
        else:
            self.error.emit("生成失败")

    def _run_doubao(self):
        key = getattr(self._config.api_keys, "doubao_api_key", "")
        if not key:
            self.error.emit("请先配置豆包 API Key")
            return

        self.progress.emit("正在生成...", "step")

        from image_generation import DoubaoGenerationClient
        client = DoubaoGenerationClient(key)

        if self._source:
            result = client.image_to_image(self._source, self._prompt, output_dir=self._output)
        else:
            result = client.generate(self._prompt, output_dir=self._output)

        if result:
            self.progress.emit("生成完成", "success")
            self.finished.emit(result)
        else:
            self.error.emit("生成失败")

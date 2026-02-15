"""
QThread worker for the 4-step automation pipeline.
"""

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class AutomationWorker(QThread):
    """
    4步自动化流水线:
    1. 采集 1688 商品
    2. AI 识别主图
    3. AI 优化提示词
    4. 执行图片生成
    """

    progress = Signal(str, str)       # message, level
    step_changed = Signal(int, str)   # step_number, step_name
    main_image = Signal(str)          # main image path
    result_image = Signal(str)        # generated result path
    prompt_ready = Signal(str)        # used prompt
    finished = Signal(bool)           # success
    error = Signal(str)

    def __init__(self, url, engine, config, prompt_override="", workflow_name="", parent=None):
        super().__init__(parent)
        self._url = url
        self._engine = engine
        self._config = config
        self._prompt_override = prompt_override
        self._workflow = workflow_name
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            # Step 1: 采集
            self.step_changed.emit(1, "采集商品")
            self.progress.emit("步骤 1/4: 开始采集商品...", "step")
            image_paths, raw_text = self._step_scrape()
            if self._should_stop:
                return

            # Step 2: AI 识别主图
            self.step_changed.emit(2, "AI识别主图")
            self.progress.emit("步骤 2/4: AI识别主图...", "step")
            main_path = self._step_identify_main(image_paths)
            if self._should_stop:
                return
            self.main_image.emit(main_path)

            # Step 3: AI 优化提示词
            self.step_changed.emit(3, "优化提示词")
            self.progress.emit("步骤 3/4: AI优化提示词...", "step")
            prompt = self._step_optimize_prompt(raw_text)
            if self._should_stop:
                return
            self.prompt_ready.emit(prompt)

            # Step 4: 生成图片
            self.step_changed.emit(4, "生成图片")
            self.progress.emit("步骤 4/4: 生成图片...", "step")
            result = self._step_generate(main_path, prompt)
            if self._should_stop:
                return
            self.result_image.emit(result)

            self.progress.emit("自动化流程完成", "success")
            self.finished.emit(True)

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

    def _step_scrape(self):
        from scraper import AlibabaScraper, ImageDownloader, TextExtractor

        scraper = AlibabaScraper(headless=True, timeout=120)
        try:
            scraper.load_cookies("./config/1688_cookies.json")
        except Exception:
            pass

        product = scraper.scrape_product(self._url)
        scraper.close()

        self.progress.emit(f"标题: {product.title[:50]}...", "info")

        downloader = ImageDownloader("./output/images")
        main_results = downloader.download_main_images(product.main_images)
        detail_results = downloader.download_detail_images(product.detail_images)
        all_paths = [p for _, p in main_results + detail_results]

        extractor = TextExtractor("./output")
        extractor.from_product_data(product.to_dict() if hasattr(product, 'to_dict') else {})
        extractor.save_all()
        raw_text = extractor.get_prompt_text() if hasattr(extractor, 'get_prompt_text') else product.title

        self.progress.emit(f"采集完成: {len(all_paths)} 张图片", "success")
        return all_paths, raw_text

    def _step_identify_main(self, image_paths):
        if not image_paths:
            raise RuntimeError("没有采集到图片")

        api_key = self._config.api_keys.openrouter_api_key
        if not api_key:
            self.progress.emit("未配置 OpenRouter，使用第一张图作为主图", "warning")
            return image_paths[0]

        try:
            import json
            import requests

            filenames = [Path(p).name for p in image_paths[:10]]
            prompt = (
                f"以下是一组电商产品图片的文件名列表:\n{json.dumps(filenames)}\n\n"
                "请分析哪张最可能是产品主图（白底图或正面展示图），"
                "返回JSON格式: {\"main_image\": \"文件名\"}"
            )
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]},
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content) if "{" in content else {}
            main_name = data.get("main_image", "")
            for p in image_paths:
                if Path(p).name == main_name:
                    self.progress.emit(f"AI选择主图: {main_name}", "success")
                    return p
        except Exception as e:
            self.progress.emit(f"AI识别失败，使用第一张: {e}", "warning")

        return image_paths[0]

    def _step_optimize_prompt(self, raw_text):
        if self._prompt_override:
            return self._prompt_override

        api_key = self._config.api_keys.openrouter_api_key
        if not api_key:
            return raw_text[:500]

        try:
            import requests
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are an expert AI art prompt generator for e-commerce products."},
                        {"role": "user", "content": f"Convert to AI image generation prompt (English, concise):\n\n{raw_text[:2000]}"},
                    ],
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"]
            self.progress.emit("提示词优化完成", "success")
            return result
        except Exception as e:
            self.progress.emit(f"提示词优化失败: {e}", "warning")
            return raw_text[:500]

    def _step_generate(self, source_image, prompt):
        import os
        output_dir = "./output/generated"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if self._engine == "comfyui":
            from image_generation import ComfyUIFluxKontextClient
            url = self._config.comfyui.get_effective_server_url()
            if not url:
                raise RuntimeError("请先配置 ComfyUI 服务器地址")
            client = ComfyUIFluxKontextClient(url)
            if self._workflow:
                wf = self._config.comfyui.get_workflow(self._workflow)
                if wf:
                    client.set_workflow(wf.get("json", {}), wf.get("prompt_node_id", "6"), wf.get("prompt_param_path", "inputs.text"),
                                       image_node_id=wf.get("image_node_id"), image_param_path=wf.get("image_param_path"))
            result = client.image_to_image(source_image, prompt, output_dir=output_dir)
        elif self._engine == "nano_banana_pro":
            from image_generation import NanoBananaProClient
            key = self._resolve_key(prefer_pro=True)
            client = NanoBananaProClient(key)
            result = client.image_to_image(source_image, prompt, output_dir=output_dir)
        else:
            from image_generation import NanoBananaClient
            key = self._resolve_key(prefer_pro=False)
            client = NanoBananaClient(key)
            result = client.image_to_image(source_image, prompt, output_dir=output_dir)

        if not result:
            raise RuntimeError("图片生成失败")
        self.progress.emit(f"生成完成: {Path(result).name}", "success")
        return result

    def _resolve_key(self, prefer_pro=False):
        import os
        order = (["nano_banana_pro_api_key", "nano_banana_api_key"] if prefer_pro
                 else ["nano_banana_api_key", "nano_banana_pro_api_key"])
        order.append("gemini_api_key")
        for f in order:
            v = getattr(self._config.api_keys, f, "")
            if v:
                return v
        return os.environ.get("GEMINI_API_KEY", "")

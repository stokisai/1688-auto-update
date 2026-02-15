"""
QThread worker for scraping operations.
"""

from PySide6.QtCore import QThread, Signal


class ScrapeWorker(QThread):
    """后台执行 1688 商品采集。"""

    progress = Signal(str, str)   # message, level
    finished = Signal(object)     # ProductData or dict
    images_ready = Signal(list)   # list of image paths
    text_ready = Signal(str)      # product text
    error = Signal(str)

    def __init__(self, url: str, engine: str = "selenium", config=None, parent=None):
        super().__init__(parent)
        self._url = url
        self._engine = engine
        self._config = config

    def run(self):
        try:
            self.progress.emit("开始采集...", "step")

            if self._engine == "selenium":
                self._run_selenium()
            elif self._engine == "serpapi":
                self._run_serpapi()
            elif self._engine == "rapidapi":
                self._run_rapidapi()
            else:
                self._run_selenium()
        except Exception as e:
            self.error.emit(str(e))

    def _run_selenium(self):
        from scraper import AlibabaScraper, ImageDownloader, TextExtractor

        self.progress.emit("启动浏览器...", "step")
        scraper = AlibabaScraper(headless=True, timeout=120)

        # 尝试加载 cookies
        try:
            scraper.load_cookies("./config/1688_cookies.json")
            self.progress.emit("已加载登录 cookies", "info")
        except Exception:
            pass

        self.progress.emit("正在采集商品信息...", "step")
        product = scraper.scrape_product(self._url)
        scraper.close()

        self.progress.emit(f"标题: {product.title[:50]}...", "info")
        self.progress.emit(f"主图: {len(product.main_images)} 张, 详情图: {len(product.detail_images)} 张", "info")

        # 下载图片
        self.progress.emit("下载图片...", "step")
        downloader = ImageDownloader("./output/images")
        main_results = downloader.download_main_images(product.main_images)
        detail_results = downloader.download_detail_images(product.detail_images)

        all_paths = [path for _, path in main_results + detail_results]
        self.images_ready.emit(all_paths)

        # 保存文案
        self.progress.emit("保存文案...", "step")
        extractor = TextExtractor("./output")
        extractor.from_product_data(product.to_dict() if hasattr(product, 'to_dict') else {})
        saved = extractor.save_all()

        text = extractor.get_prompt_text() if hasattr(extractor, 'get_prompt_text') else product.title
        self.text_ready.emit(text)

        self.progress.emit(f"采集完成! 共 {len(all_paths)} 张图片", "success")
        self.finished.emit(product)

    def _run_serpapi(self):
        from scraper import SerpApiScraper
        self.progress.emit("使用 SerpAPI 采集...", "step")
        scraper = SerpApiScraper()
        product = scraper.scrape_product(self._url)
        self.finished.emit(product)

    def _run_rapidapi(self):
        from scraper import RapidApiScraper
        self.progress.emit("使用 RapidAPI 采集...", "step")
        scraper = RapidApiScraper()
        product = scraper.scrape_product(self._url)
        self.finished.emit(product)


class LoginWorker(QThread):
    """后台执行 1688 登录。"""
    progress = Signal(str, str)
    finished = Signal(bool)
    error = Signal(str)

    def run(self):
        try:
            from scraper import AlibabaScraper
            self.progress.emit("打开登录页面...", "step")
            scraper = AlibabaScraper(headless=False)
            success = scraper.ensure_logged_in()
            if success:
                scraper._save_cookies()
                self.progress.emit("登录成功，cookies 已保存", "success")
            scraper._close_driver()
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))

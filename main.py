"""
1688 图片抓取与图生图工具 - 主程序入口

支持CLI和GUI两种模式。
"""

import click
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """1688 图片抓取与图生图工具"""
    if ctx.invoked_subcommand is None:
        # 默认启动GUI
        ctx.invoke(gui)


@cli.command()
def gui():
    """启动图形界面 (默认)"""
    console.print("[bold green]启动图形界面...[/bold green]")
    try:
        import sys
        from PySide6.QtWidgets import QApplication
        from ui.theme import setup_app_theme
        from ui.activation_window import check_and_activate
        from ui.app import App

        qt_app = QApplication.instance() or QApplication(sys.argv)
        setup_app_theme(qt_app)

        # 先检查激活状态（暂时跳过，测试用）
        # if not check_and_activate():
        #     console.print("[yellow]用户取消激活，退出程序[/yellow]")
        #     return

        # 激活成功，启动主程序
        window = App()
        window.show()
        sys.exit(qt_app.exec())
    except ImportError as e:
        console.print(f"[red]GUI启动失败: {e}[/red]")
        console.print("请确保已安装: pip install PySide6")


@cli.command()
@click.option("--check", is_flag=True, help="检查配置是否完整")
def config(check):
    """配置管理"""
    from config.settings import get_config
    
    cfg = get_config()
    
    if check:
        errors = cfg.validate()
        if errors:
            console.print("[yellow]配置不完整:[/yellow]")
            for err in errors:
                console.print(f"  [red]• {err}[/red]")
        else:
            console.print("[green]✓ 配置完整[/green]")
            
        # 显示已配置的API
        table = Table(title="已配置的API")
        table.add_column("类型", style="cyan")
        table.add_column("API", style="green")
        table.add_column("状态")
        
        recognition = cfg.api_keys.get_available_recognition_engines()
        generation = cfg.api_keys.get_available_generation_engines()
        
        if recognition:
            table.add_row("图像识别", ", ".join(recognition), "✓")
        else:
            table.add_row("图像识别", "-", "[red]未配置[/red]")
            
        if generation or cfg.comfyui.get_effective_server_url():
            engines = generation + (["comfyui"] if cfg.comfyui.get_effective_server_url() else [])
            table.add_row("图生图", ", ".join(engines), "✓")
        else:
            table.add_row("图生图", "-", "[red]未配置[/red]")
            
        console.print(table)
    else:
        # 打开配置界面
        console.print("请使用GUI模式进行配置: python main.py gui")


@cli.command()
@click.argument("url")
@click.option("--analyze", is_flag=True, help="同时进行图像识别")
@click.option("--engine", default="doubao", help="图像识别引擎")
@click.option("--output", "-o", default="./output", help="输出目录")
def scrape(url, analyze, engine, output):
    """抓取1688商品"""
    from scraper import AlibabaScraper, ImageDownloader, TextExtractor
    
    console.print(f"[bold]抓取商品: {url}[/bold]")
    
    # 1. 抓取商品
    scraper = AlibabaScraper(headless=True)
    product = scraper.scrape_product(url)
    
    console.print(f"[green]✓ 标题: {product.title[:50]}...[/green]")
    console.print(f"  主图: {len(product.main_images)} 张")
    console.print(f"  副图: {len(product.detail_images)} 张")
    
    # 2. 下载图片
    downloader = ImageDownloader(f"{output}/images")
    
    console.print("[bold]下载图片...[/bold]")
    main_results = downloader.download_main_images(product.main_images)
    detail_results = downloader.download_detail_images(product.detail_images)
    
    console.print(f"[green]✓ 下载完成: {len(main_results)} + {len(detail_results)} 张[/green]")
    
    # 3. 保存文案
    extractor = TextExtractor(output)
    extractor.from_product_data(scraper.get_product_text())
    
    # 4. 可选: 图像识别
    if analyze:
        console.print(f"[bold]图像识别 ({engine})...[/bold]")
        recognizer = _get_recognizer(engine)
        
        if recognizer:
            for url, path in main_results:
                try:
                    result = recognizer.analyze_image(path)
                    extractor.add_image_analysis(path, result)
                    console.print(f"  ✓ {Path(path).name}")
                except Exception as e:
                    console.print(f"  [red]✗ {Path(path).name}: {e}[/red]")
    
    # 5. 保存
    saved = extractor.save_all()
    console.print(f"[green]✓ 保存文案: {saved['json']}[/green]")


@cli.command()
@click.argument("path")
@click.option("--engine", default="doubao", help="识别引擎")
def analyze(path, engine):
    """图像识别"""
    path = Path(path)
    
    recognizer = _get_recognizer(engine)
    if not recognizer:
        console.print(f"[red]无法使用引擎: {engine}[/red]")
        return
    
    console.print(f"[bold]使用 {engine} 进行图像识别...[/bold]")
    
    if path.is_file():
        images = [str(path)]
    else:
        images = [str(f) for f in path.glob("*.jpg")] + \
                 [str(f) for f in path.glob("*.png")] + \
                 [str(f) for f in path.glob("*.webp")]
    
    for img_path in images:
        try:
            result = recognizer.analyze_image(img_path)
            console.print(f"\n[cyan]{Path(img_path).name}[/cyan]")
            console.print(f"  描述: {result.get('description', '')[:100]}...")
            if result.get('labels'):
                console.print(f"  标签: {', '.join(result['labels'][:5])}")
            if result.get('ocr_text'):
                console.print(f"  文字: {result['ocr_text'][:50]}...")
        except Exception as e:
            console.print(f"[red]✗ {Path(img_path).name}: {e}[/red]")


@cli.command()
@click.argument("image")
@click.option("--mode", default="comfyui", 
              type=click.Choice(["comfyui", "nano-banana", "openrouter"]))
@click.option("--prompt", "-p", default="", help="提示词")
@click.option("--wash", is_flag=True, help="洗稿模式(无提示词)")
@click.option("--use-copywriting", is_flag=True, help="使用整合文案作为提示词")
@click.option("--server", default="", help="ComfyUI服务器地址")
@click.option("--workflow", default="", help="ComfyUI工作流名称")
@click.option("--output", "-o", default="./output/generated", help="输出目录")
def generate(image, mode, prompt, wash, use_copywriting, server, workflow, output):
    """图生图生成"""
    from config.settings import get_config
    
    cfg = get_config()
    
    # 确定提示词
    if wash:
        prompt = ""
        console.print("[yellow]洗稿模式: 无提示词[/yellow]")
    elif use_copywriting:
        # 尝试从文案文件读取
        try:
            from scraper import TextExtractor
            extractor = TextExtractor("./output")
            extractor.load_json()
            prompt = extractor.get_prompt_text()
            console.print(f"[cyan]使用整合文案作为提示词[/cyan]")
        except:
            console.print("[yellow]无法读取文案，使用空提示词[/yellow]")
            prompt = ""
    
    console.print(f"[bold]图生图 ({mode}): {image}[/bold]")
    if prompt:
        console.print(f"  提示词: {prompt[:50]}...")
    
    if mode == "comfyui":
        from image_generation import ComfyUIFluxKontextClient
        
        server_url = server or cfg.comfyui.get_effective_server_url()
        if not server_url:
            console.print("[red]请指定ComfyUI服务器地址: --server URL[/red]")
            return
        
        client = ComfyUIFluxKontextClient(server_url)
        
        # 加载工作流
        if workflow and cfg.comfyui.workflows.get(workflow):
            wf = cfg.comfyui.get_workflow(workflow)
            client.set_workflow(wf["json"], wf["prompt_node_id"], wf["prompt_param_path"])
        
        if not client.test_connection():
            console.print(f"[red]无法连接到ComfyUI服务器: {server_url}[/red]")
            return
        
        result = client.image_to_image(image, prompt, output_dir=output)
        
    elif mode == "nano-banana":
        from image_generation import NanoBananaClient
        
        api_key = cfg.api_keys.nano_banana_api_key
        if not api_key:
            console.print("[red]请配置Nano Banana API Key[/red]")
            return
        
        client = NanoBananaClient(api_key)
        result = client.image_to_image(image, prompt, output_dir=output)
        
    elif mode == "openrouter":
        from image_generation import OpenRouterGenerationClient
        
        api_key = cfg.api_keys.openrouter_api_key
        if not api_key:
            console.print("[red]请配置OpenRouter API Key[/red]")
            return
        
        client = OpenRouterGenerationClient(api_key)
        result = client.image_to_image(image, prompt, output_dir=output)
    
    console.print(f"[green]✓ 生成完成: {result}[/green]")


@cli.group()
def competitor():
    """竞品分析"""
    pass


@competitor.command()
@click.argument("image")
def search(image):
    """以图搜图搜索竞品"""
    from competitor import GoogleImageSearch
    
    console.print(f"[bold]搜索竞品: {image}[/bold]")
    
    searcher = GoogleImageSearch(headless=True)
    results = searcher.search_by_image(image, filter_domain="amazon")
    
    if results:
        table = Table(title=f"找到 {len(results)} 个亚马逊竞品")
        table.add_column("#")
        table.add_column("标题")
        table.add_column("域名")
        table.add_column("链接")
        
        for i, r in enumerate(results[:10]):
            table.add_row(
                str(i+1),
                r.get("title", "")[:40],
                r.get("domain", ""),
                r.get("url", "")[:50]
            )
        
        console.print(table)
    else:
        console.print("[yellow]未找到亚马逊竞品[/yellow]")


@competitor.command()
@click.argument("url")
@click.option("--engine", default="doubao")
@click.option("--output", "-o", default="./output/competitor")
def analyze_url(url, engine, output):
    """分析指定的亚马逊链接"""
    from competitor import CompetitorAnalyzer
    
    recognizer = _get_recognizer(engine)
    analyzer = CompetitorAnalyzer(recognizer)
    
    result = analyzer.analyze_amazon_url(url, output)
    
    console.print(f"[green]✓ 分析完成[/green]")
    console.print(f"  标题: {result.amazon_title[:50]}...")
    console.print(f"  图片数量: {len(result.competitor_images)}")
    console.print(f"  提示词数量: {len(result.suggested_prompts)}")


@competitor.command()
@click.argument("image")
@click.option("--engine", default="doubao")
@click.option("--output", "-o", default="./output/competitor")
def full(image, engine, output):
    """完整竞品分析流程"""
    from competitor import CompetitorAnalyzer
    
    console.print(f"[bold]完整竞品分析: {image}[/bold]")
    
    recognizer = _get_recognizer(engine)
    analyzer = CompetitorAnalyzer(recognizer)
    
    result = analyzer.analyze_competitor(image, output)
    
    console.print(f"\n[green]✓ 竞品分析完成[/green]")
    if result.amazon_url:
        console.print(f"  竞品链接: {result.amazon_url}")
        console.print(f"  竞品标题: {result.amazon_title[:50]}...")
        console.print(f"  分析图片: {len(result.competitor_images)} 张")
        console.print(f"  生成提示词: {len(result.suggested_prompts)} 条")
    else:
        console.print("[yellow]  未找到匹配的亚马逊竞品[/yellow]")


@cli.group()
def workflow():
    """ComfyUI工作流管理"""
    pass


@workflow.command(name="list")
def workflow_list():
    """列出所有工作流"""
    from config.settings import get_config
    
    cfg = get_config()
    workflows = cfg.comfyui.list_workflows()
    
    if workflows:
        table = Table(title="ComfyUI 工作流")
        table.add_column("名称")
        table.add_column("Prompt节点")
        table.add_column("当前")
        
        for name in workflows:
            wf = cfg.comfyui.get_workflow(name)
            is_current = "✓" if name == cfg.comfyui.current_workflow else ""
            table.add_row(
                name,
                f"Node {wf.get('prompt_node_id', '?')}",
                is_current
            )
        
        console.print(table)
    else:
        console.print("[yellow]暂无工作流[/yellow]")


@workflow.command()
@click.argument("name")
@click.argument("json_file")
@click.option("--prompt-node", default="6", help="提示词节点ID")
@click.option("--prompt-path", default="inputs.text", help="提示词参数路径")
def add(name, json_file, prompt_node, prompt_path):
    """添加工作流"""
    from config.settings import get_config, save_config
    
    with open(json_file, 'r', encoding='utf-8') as f:
        workflow_json = json.load(f)
    
    cfg = get_config()
    cfg.comfyui.add_workflow(name, workflow_json, prompt_node, prompt_path)
    save_config()
    
    console.print(f"[green]✓ 添加工作流: {name}[/green]")


@workflow.command()
@click.argument("name")
def remove(name):
    """删除工作流"""
    from config.settings import get_config, save_config
    
    cfg = get_config()
    if cfg.comfyui.remove_workflow(name):
        save_config()
        console.print(f"[green]✓ 删除工作流: {name}[/green]")
    else:
        console.print(f"[red]工作流不存在: {name}[/red]")


def _get_recognizer(engine: str):
    """获取图像识别器"""
    from config.settings import get_config
    
    cfg = get_config()
    
    if engine == "doubao":
        from recognition import DoubaoVisionRecognizer
        return DoubaoVisionRecognizer(cfg.api_keys.doubao_api_key)
    elif engine == "qwen":
        from recognition import QwenVLRecognizer
        return QwenVLRecognizer(cfg.api_keys.qwen_api_key)
    elif engine == "openrouter":
        from recognition import OpenRouterClient
        return OpenRouterClient(cfg.api_keys.openrouter_api_key)
    elif engine == "gemini":
        from recognition import GeminiVisionRecognizer
        return GeminiVisionRecognizer(cfg.api_keys.gemini_api_key)
    elif engine == "openai":
        from recognition import OpenAIVisionRecognizer
        return OpenAIVisionRecognizer(cfg.api_keys.openai_api_key)
    elif engine == "google_vision":
        from recognition import GoogleVisionRecognizer
        return GoogleVisionRecognizer(cfg.api_keys.google_cloud_credentials)
    
    return None


if __name__ == "__main__":
    cli()

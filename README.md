# 1688 图片抓取与图生图工具

从 1688 商品链接抓取主图、副图和产品文案，通过图像识别模型分析图片，并提供多种图生图方案。

## 功能特性

- 🔗 **1688 商品抓取**: 自动抓取商品主图、副图、产品文案
- 🔍 **图像识别 (可选)**: 支持豆包、通义千问、Gemini、OpenRouter等多种API
- 🔎 **竞品分析 (可选)**: Google以图搜图，分析亚马逊竞品
- 🎨 **图生图**: 支持 Nano Banana API / OpenRouter / ComfyUI
- 🖥️ **GUI界面**: 现代化图形界面，配置向导

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动程序

```bash
python main.py
```

首次启动会打开配置向导，引导您完成 API Key 配置。

## 配置说明

### 图像识别 API (至少配置一个)

| API | 免费额度 | 推荐 |
|-----|---------|------|
| 豆包 | 50万token + 可领5亿 | 🌟 |
| 通义千问 | 新加坡区有 | 🌟 |
| OpenRouter | 部分模型免费 | |
| Gemini | $300新用户额度 | |
| GPT-4V | 有限免费 | |

### 图生图 API (至少配置一个)

| API | 价格 | 说明 |
|-----|------|------|
| ComfyUI | 免费 | 需要GPU服务器 |
| Nano Banana | $0.02-0.04/张 | 基于Google Gemini |
| OpenRouter | $0.03-0.15/张 | 支持多种模型 |

## 使用方式

### GUI模式 (推荐)

```bash
python main.py
```

### CLI模式

```bash
# 抓取商品
python main.py scrape "https://detail.1688.com/xxx"

# 图生图
python main.py generate --mode comfyui ./image.jpg --prompt "Remove all text"
```

## 项目结构

```
├── scraper/          # 1688 抓取模块
├── recognition/      # 图像识别模块
├── competitor/       # 竞品分析模块
├── image_generation/ # 图生图模块
├── ui/               # GUI界面
├── config/           # 配置模块
└── output/           # 输出目录
```

## License

MIT

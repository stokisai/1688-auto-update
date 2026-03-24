# 1688 登录与采集流程 Skill

## 概述
1688商品信息采集的完整技术方案，包括反机器人检测绕过、登录状态管理、商品数据提取。

## 技术栈
- `undetected-chromedriver` — 绕过1688/淘宝反机器人检测（替代标准selenium）
- `selenium` — 回退方案
- `BeautifulSoup` + `lxml` — HTML解析提取商品数据
- `PySide6 QThread` — UI线程与采集线程分离

## 核心流程

### 1. 浏览器初始化
- 优先使用 `undetected-chromedriver`，自动修补chromedriver移除自动化痕迹
- 回退到标准selenium + CDP命令隐藏`navigator.webdriver`
- `headless=False`（必须可见，用户需要手动处理验证码）

### 2. 登录流程
- 1688登录走淘宝统一认证（`login.1688.com` → `login.taobao.com`）
- **不要自动填入账号密码**（会触发反机器人验证）
- 打开登录页面，等待用户手动输入并登录
- 登录成功后保存cookies到本地 `./config/1688_cookies.json`
- cookies仅保存当前页面域的，不跳转到其他域收集

### 3. 登录状态复用
- **同一会话内**：登录后浏览器保持打开，采集时复用同一浏览器实例（不开新浏览器）
- **跨会话**：从cookies文件恢复登录状态（成功率取决于cookie是否过期）
- 采集时通过monkey-patch跳过 `_init_driver` 和 `_close_driver`，防止重新初始化浏览器

### 4. 商品数据提取
- 滚动页面加载懒加载内容（A+详情图）
- 提取Shadow DOM中的图片
- 使用BeautifulSoup解析：标题、价格、主图、详情图、规格参数、描述、店铺名

## 关键经验教训

### 反机器人检测
- 1688/淘宝检测`navigator.webdriver`属性、Chrome自动化横幅等
- 仅靠CDP命令隐藏webdriver不够，需要`undetected-chromedriver`
- **绝对不要用selenium自动填入登录表单**（send_keys/JS赋值都会触发验证）
- `--disable-blink-features=AutomationControlled` 和 `excludeSwitches: enable-automation` 是基本配置

### Cookie管理
- 1688登录session的关键cookies在`taobao.com`域
- 浏览器跨域限制：不能在`1688.com`页面设置`taobao.com`域的cookies
- 如需跨域加载cookies，必须分别访问各域名设置（会产生页面跳转）
- 最佳方案：复用同一浏览器，避免跨域cookie问题

### 架构设计
- LoginWorker和ScrapeWorker共享scraper实例（通过scrape_page持有）
- LoginWorker登录后通过signal传出scraper实例，不关闭浏览器
- ScrapeWorker检测到已有scraper时复用，否则走完整流程（新建浏览器+加载cookies）

## 文件结构
```
scraper/
  alibaba_scraper.py    # 核心爬虫：初始化、登录、采集、解析
ui/
  workers/
    scrape_worker.py    # ScrapeWorker + LoginWorker（QThread）
  pages/
    scrape_page.py      # UI页面：持有共享scraper实例
config/
  1688_cookies.json     # 登录cookies（本地存储，不上传）
```

## 复用指南
将此方案应用到其他需要登录的电商平台采集时：
1. 替换登录URL和登录检测逻辑
2. 替换商品数据解析的CSS选择器
3. 保持undetected-chromedriver + 手动登录 + 浏览器复用的架构

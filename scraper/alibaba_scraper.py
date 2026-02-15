"""
1688 商品页面抓取器

使用 Selenium 抓取 1688 商品页面的主图、副图和产品文案。
"""

import re
import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup


@dataclass
class ProductData:
    """商品数据结构"""
    url: str = ""
    title: str = ""
    description: str = ""
    price_range: str = ""
    specifications: Dict[str, str] = field(default_factory=dict)
    main_images: List[str] = field(default_factory=list)
    detail_images: List[str] = field(default_factory=list)
    shop_name: str = ""
    raw_html: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "price_range": self.price_range,
            "specifications": self.specifications,
            "main_images": self.main_images,
            "detail_images": self.detail_images,
            "shop_name": self.shop_name,
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class AlibabaScraper:
    """1688 商品抓取器"""
    
    # Cookie 保存路径
    COOKIE_FILE = "./config/1688_cookies.json"
    
    # 1688 账号配置（用户需要自行输入）
    DEFAULT_USERNAME = ""
    DEFAULT_PASSWORD = ""
    
    def __init__(self, headless: bool = False, timeout: int = 60, 
                 username: str = None, password: str = None):
        """
        初始化抓取器
        
        Args:
            headless: 是否使用无头模式 (建议False以便手动处理验证码)
            timeout: 页面加载超时时间(秒)
            username: 1688账号（可选，默认使用预设账号）
            password: 1688密码（可选，默认使用预设密码）
        """
        self.headless = headless
        self.timeout = timeout
        self.driver: Optional[webdriver.Chrome] = None
        self.product_data: Optional[ProductData] = None
        self.username = username or self.DEFAULT_USERNAME
        self.password = password or self.DEFAULT_PASSWORD
        
    def _init_driver(self):
        """初始化 Chrome WebDriver"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # 增强反检测设置
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 禁用自动化标志
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # 设置偏好
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("detach", True)
        
        try:
            print("正在启动 Chrome Driver...")
            self.driver = webdriver.Chrome(options=options)
            print("Chrome Driver 启动成功")
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Chrome Driver 启动失败: {e}")

            # 提供更友好的错误提示
            if "chrome" in error_msg or "chromedriver" in error_msg or "cannot find" in error_msg:
                raise Exception(
                    "无法启动 Chrome 浏览器！\n\n"
                    "请确保已安装 Google Chrome 浏览器：\n"
                    "1. 访问 https://www.google.com/chrome/ 下载安装\n"
                    "2. 安装完成后重新点击登录按钮\n\n"
                    f"原始错误: {e}"
                )
            raise
        
        # 执行 CDP 命令隐藏 webdriver 属性
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
                window.chrome = {runtime: {}};
            """
        })
        
    def _close_driver(self):
        """关闭 WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _save_cookies(self):
        """保存 Cookies 到本地文件"""
        if not self.driver:
            return False
        
        try:
            # 获取当前页面的 cookies
            all_cookies = self.driver.get_cookies()
            
            # 尝试访问 1688.com 获取其 cookies
            try:
                current_url = self.driver.current_url
                if "1688.com" not in current_url:
                    print("访问 1688.com 获取其 Cookies...")
                    self.driver.get("https://www.1688.com")
                    time.sleep(3)
                    # 合并 1688 的 cookies
                    for c in self.driver.get_cookies():
                        if c not in all_cookies:
                            all_cookies.append(c)
            except:
                pass
            
            cookie_data = {
                "cookies": all_cookies,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "domain": "1688.com"
            }
            
            # 确保目录存在
            cookie_path = Path(self.COOKIE_FILE)
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)
            
            print(f"✓ Cookies 已保存 ({len(all_cookies)} 个)")
            return True
        except Exception as e:
            print(f"保存 Cookies 失败: {e}")
            return False
    
    def _load_cookies(self) -> bool:
        """从本地文件加载 Cookies"""
        if not self.driver:
            return False
        
        cookie_path = Path(self.COOKIE_FILE)
        if not cookie_path.exists():
            print("未找到保存的 Cookies，需要登录")
            return False
        
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)
            
            cookies = cookie_data.get("cookies", [])
            if not cookies:
                return False
            
            print(f"加载 Cookies (保存于: {cookie_data.get('saved_at', '未知')})...")
            
            # 按域名分组 cookies
            taobao_cookies = [c for c in cookies if 'taobao' in c.get('domain', '')]
            alibaba_cookies = [c for c in cookies if '1688' in c.get('domain', '') or 'alibaba' in c.get('domain', '')]
            
            # 先访问 taobao.com 设置其 cookies (因为 1688 使用淘宝账号系统)
            if taobao_cookies:
                print(f"   设置 taobao.com 域 cookies ({len(taobao_cookies)} 个)...")
                try:
                    self.driver.get("https://www.taobao.com")
                    time.sleep(2)
                    for cookie in taobao_cookies:
                        try:
                            clean_cookie = self._clean_cookie(cookie)
                            self.driver.add_cookie(clean_cookie)
                        except:
                            pass
                except Exception as e:
                    print(f"   taobao.com 设置失败: {e}")
            
            # 再访问 1688.com 设置其 cookies
            print(f"   设置 1688.com 域...")
            try:
                self.driver.get("https://www.1688.com")
                time.sleep(2)
                
                # 尝试为 1688.com 设置通用 cookies
                for cookie in alibaba_cookies:
                    try:
                        clean_cookie = self._clean_cookie(cookie)
                        self.driver.add_cookie(clean_cookie)
                    except:
                        pass
            except Exception as e:
                print(f"   1688.com 设置失败: {e}")
            
            print("✓ Cookies 加载完成")
            return True
            
        except Exception as e:
            print(f"加载 Cookies 失败: {e}")
            return False
    
    def _clean_cookie(self, cookie: dict) -> dict:
        """清理 cookie 字典，移除可能导致问题的字段"""
        clean = cookie.copy()
        if 'expiry' in clean:
            clean['expiry'] = int(clean['expiry'])
        if 'sameSite' in clean and clean['sameSite'] not in ['Strict', 'Lax', 'None']:
            del clean['sameSite']
        return clean
    
    def _check_login_status(self) -> bool:
        """检查是否已登录 1688"""
        if not self.driver:
            return False
        
        try:
            page_source = self.driver.page_source
            
            # 检查是否有登录标志
            login_indicators = [
                "login.1688.com",  # 在登录页面
                "请登录",
                "会员登录",
                "用户登录",
            ]
            
            # 检查是否有已登录标志
            logged_in_indicators = [
                "我的阿里",
                "退出登录",
                "账户中心",
                "memberInfo",
                "已登录",
            ]
            
            # 如果有已登录标志，说明已登录
            for indicator in logged_in_indicators:
                if indicator in page_source:
                    print("✓ 检测到已登录状态")
                    return True
            
            # 检查 URL 是否在商品详情页（而非登录页）
            current_url = self.driver.current_url
            if "detail.1688.com" in current_url and not any(ind in page_source for ind in login_indicators[:2]):
                # 在商品页面且没有明显的登录提示，可能已登录
                return True
            
            return False
        except Exception as e:
            print(f"检查登录状态出错: {e}")
            return False
    
    def _do_login(self) -> bool:
        """执行登录操作"""
        if not self.driver:
            return False
        
        try:
            print("=" * 50)
            print("开始登录流程")
            print("=" * 50)
            
            print("正在访问登录页面...")
            self.driver.get("https://login.1688.com/member/signin.htm")
            
            # 等待较长时间让页面完全加载
            print("等待页面加载...")
            time.sleep(8)
            
            # 等待页面加载
            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                print("页面加载可能不完整，继续尝试...")
            
            # 检查是否有 iframe
            print("检查登录表单...")
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            print(f"   发现 {len(iframes)} 个 iframe")
            
            # 尝试切换到可能的登录 iframe
            login_iframe_found = False
            for i, iframe in enumerate(iframes):
                try:
                    src = iframe.get_attribute("src") or ""
                    if "login" in src.lower() or "passport" in src.lower():
                        print(f"   切换到登录 iframe #{i}")
                        self.driver.switch_to.frame(iframe)
                        login_iframe_found = True
                        time.sleep(2)
                        break
                except:
                    continue
            
            # 切换到密码登录模式
            print("尝试切换到密码登录...")
            password_tab_clicked = False
            
            # 使用 JavaScript 查找并点击密码登录
            try:
                self.driver.execute_script("""
                    var tabs = document.querySelectorAll('*');
                    for (var i = 0; i < tabs.length; i++) {
                        var text = tabs[i].textContent || tabs[i].innerText;
                        if (text.trim() === '密码登录') {
                            tabs[i].click();
                            break;
                        }
                    }
                """)
                time.sleep(2)
                password_tab_clicked = True
                print("✓ 已切换到密码登录模式")
            except Exception as e:
                print(f"   JavaScript 点击失败: {e}")
            
            # 如果 JavaScript 失败，尝试 Selenium 点击
            if not password_tab_clicked:
                password_tab_selectors = [
                    "//span[contains(text(), '密码登录')]",
                    "//div[contains(text(), '密码登录')]",
                    "//a[contains(text(), '密码登录')]",
                    "//*[text()='密码登录']",
                ]
                for selector in password_tab_selectors:
                    try:
                        elems = self.driver.find_elements(By.XPATH, selector)
                        for elem in elems:
                            if elem.is_displayed():
                                elem.click()
                                time.sleep(2)
                                print("✓ 已切换到密码登录模式 (Selenium)")
                                password_tab_clicked = True
                                break
                        if password_tab_clicked:
                            break
                    except:
                        continue
            
            if not password_tab_clicked:
                print("⚠️ 未能自动切换到密码登录，请手动点击")
            
            # 等待表单加载
            time.sleep(3)
            
            # 使用 JavaScript 填入用户名
            print(f"填入用户名: {self.username[:3]}***...")
            try:
                self.driver.execute_script(f"""
                    var inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input:not([type])');
                    for (var i = 0; i < inputs.length; i++) {{
                        var input = inputs[i];
                        if (input.offsetParent !== null) {{  // 可见
                            input.value = '{self.username}';
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            console.log('填入用户名到:', input);
                            break;
                        }}
                    }}
                """)
                print("✓ 用户名已填入")
            except Exception as e:
                print(f"⚠️ 自动填入用户名失败: {e}")
                print("   请手动输入用户名")
            
            time.sleep(1)
            
            # 使用 JavaScript 填入密码
            print("填入密码...")
            try:
                self.driver.execute_script(f"""
                    var inputs = document.querySelectorAll('input[type="password"]');
                    for (var i = 0; i < inputs.length; i++) {{
                        var input = inputs[i];
                        if (input.offsetParent !== null) {{  // 可见
                            input.value = '{self.password}';
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            console.log('填入密码到:', input);
                            break;
                        }}
                    }}
                """)
                print("✓ 密码已填入")
            except Exception as e:
                print(f"⚠️ 自动填入密码失败: {e}")
                print("   请手动输入密码")
            
            # 切换回主框架
            if login_iframe_found:
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
            
            print("")
            print("=" * 50)
            print("📝 请在浏览器中完成以下步骤：")
            print("   1. 确认账号密码已正确填入")
            print("   2. 如未填入，请手动输入")
            print("   3. 点击【登录】按钮")
            print("   4. 如有验证码，请完成验证")
            print("=" * 50)
            print("")
            
            # 等待用户完成登录（最多等待5分钟）
            print("⏳ 等待您完成登录（最多5分钟）...")
            print("   登录成功后会自动保存状态")
            
            for i in range(150):  # 150 * 2 = 300秒 = 5分钟
                time.sleep(2)
                
                try:
                    current_url = self.driver.current_url
                    
                    # 检查是否离开了登录页面
                    if "login.1688.com" not in current_url and "signin" not in current_url:
                        if "error" not in current_url.lower():
                            print("")
                            print("✓ 检测到页面跳转，登录成功！")
                            time.sleep(2)
                            self._save_cookies()
                            return True
                    
                    # 每60秒打印一次状态
                    if i > 0 and i % 30 == 0:
                        remaining = (150 - i) * 2
                        mins = remaining // 60
                        secs = remaining % 60
                        print(f"   还在等待... (剩余 {mins}分{secs}秒)")
                        
                except Exception as e:
                    print(f"检测状态出错: {e}")
                    # 可能浏览器被关闭
                    break
            
            print("")
            print("⚠️ 等待超时")
            print("   浏览器保持打开，请手动完成登录")
            print("   登录成功后请手动关闭浏览器")
            return False
            
        except Exception as e:
            print(f"登录过程出错: {e}")
            import traceback
            traceback.print_exc()
            print("请在浏览器中手动完成登录")
            return False
    
    def ensure_logged_in(self) -> bool:
        """确保已登录状态，如果未登录则进行登录"""
        if not self.driver:
            self._init_driver()
        
        # 检查是否有已保存的 cookies
        cookie_path = Path(self.COOKIE_FILE)
        if cookie_path.exists():
            print("发现已保存的登录信息，正在尝试恢复...")
            if self._load_cookies():
                # 刷新页面以应用 cookies
                self.driver.refresh()
                time.sleep(3)
                
                # 检查是否登录成功
                if self._check_login_status():
                    print("✓ 登录状态恢复成功")
                    return True
                else:
                    print("保存的登录信息已过期，需要重新登录")
        else:
            print("未找到已保存的登录信息")
        
        # 需要登录
        return self._do_login()
    
    def _wait_for_captcha(self) -> bool:
        """
        检测并等待用户完成验证码
        
        Returns:
            是否检测到验证码
        """
        page_source = self.driver.page_source
        
        # 检测验证码页面
        captcha_indicators = [
            "punish", "captcha", "验证", "x5secdata", 
            "请完成安全验证", "滑动验证"
        ]
        
        has_captcha = any(ind in page_source for ind in captcha_indicators)
        
        if has_captcha:
            print("⚠️ 检测到验证码页面，请在浏览器中完成验证...")
            print("   完成验证后，页面会自动继续...")
            
            # 等待用户完成验证 (最多等待120秒)
            for i in range(60):
                time.sleep(2)
                new_source = self.driver.page_source
                if not any(ind in new_source for ind in captcha_indicators):
                    print("✓ 验证完成!")
                    time.sleep(2)
                    return True
                    
            print("⚠️ 验证超时")
            return True
            
        return False
            
    def scrape_product(self, url: str) -> ProductData:
        """
        抓取商品所有信息
        
        Args:
            url: 1688商品链接
            
        Returns:
            ProductData 对象
        """
        self.product_data = ProductData(url=url)
        
        try:
            self._init_driver()
            
            # 先尝试加载已保存的 Cookies
            cookies_loaded = self._load_cookies()
            
            print(f"正在访问: {url}")
            
            # 访问页面
            self.driver.get(url)
            
            # 等待页面加载
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 检测验证码
            self._wait_for_captcha()
            
            # 检查是否需要登录
            page_source = self.driver.page_source
            needs_login = False
            
            # 检查页面是否有登录提示或跳转到登录页
            login_hints = ["请登录", "login.1688.com", "会员登录", "用户登录"]
            if any(hint in page_source or hint in self.driver.current_url for hint in login_hints):
                needs_login = True
                print("⚠️ 检测到需要登录")
            
            if needs_login:
                # 执行登录
                if self._do_login():
                    # 登录成功后重新访问商品页面
                    print(f"登录成功，正在重新访问商品页面...")
                    self.driver.get(url)
                    time.sleep(3)
                    WebDriverWait(self.driver, self.timeout).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    self._wait_for_captcha()
            
            # 等待主要内容加载
            print("等待页面内容加载...")
            time.sleep(5)
            
            # 尝试等待商品标题出现
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 
                        "[class*='title'], [class*='Title'], h1, .subject"))
                )
            except:
                print("等待标题超时，继续尝试...")
            
            # 滚动页面以加载更多内容
            self._scroll_page()
            
            # 提取 Shadow DOM 中的 A+ 图片
            shadow_images = self._extract_shadow_dom_images()
            
            # 获取页面HTML
            self.product_data.raw_html = self.driver.page_source
            
            # 解析内容
            soup = BeautifulSoup(self.product_data.raw_html, 'lxml')
            
            print("正在提取商品信息...")
            
            # 提取各项信息
            self._extract_title(soup)
            self._extract_price(soup)
            self._extract_main_images(soup)
            self._extract_detail_images(soup, shadow_images)
            self._extract_specifications(soup)
            self._extract_description(soup)
            self._extract_shop_name(soup)
            
            print(f"✓ 标题: {self.product_data.title[:50] if self.product_data.title else '未获取'}...")
            print(f"✓ 主图: {len(self.product_data.main_images)} 张")
            print(f"✓ 副图: {len(self.product_data.detail_images)} 张")
            
            # 抓取成功后保存 Cookies（用于下次使用）
            self._save_cookies()
            
        except Exception as e:
            print(f"抓取出错: {e}")
            # 出错时不关闭浏览器，让用户可以看到错误状态或手动操作
            print("⚠️ 浏览器保持打开状态，请手动关闭或完成验证后重试")
            raise
        
        # 只在成功抓取后关闭浏览器
        self._close_driver()
            
        return self.product_data
    
    def _scroll_page(self):
        """滚动页面以加载懒加载内容（包括A+详情）"""
        if not self.driver:
            return
        
        print("滚动页面加载A+详情内容...")
            
        # 获取页面高度
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        # 第一次滚动 - 快速预览整个页面
        scroll_step = 800
        current_position = 0
        
        while current_position < last_height:
            current_position += scroll_step
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.3)
            
            # 更新页面高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > last_height:
                last_height = new_height
        
        # 等待动态内容加载
        time.sleep(2)
        
        # 第二次滚动 - 慢速滚动确保懒加载内容加载
        current_position = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while current_position < last_height:
            current_position += 400
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.5)  # 更长等待时间
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > last_height:
                last_height = new_height
        
        # 滚动到详情区域并等待（A+内容通常在页面下半部分）
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
        time.sleep(2)
        
        # 尝试点击"查看更多"按钮展开详情
        try:
            more_btns = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), '查看更多') or contains(text(), '展开') or contains(@class, 'expand')]")
            for btn in more_btns:
                try:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                except:
                    pass
        except:
            pass
        
        # 最终滚动到底部
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
                
        # 滚回顶部
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
    def _extract_title(self, soup: BeautifulSoup):
        """提取商品标题"""
        # 尝试多种选择器
        selectors = [
            'h1.title-text',
            '.title-text',
            'h1[class*="title"]',
            '.mod-detail-title h1',
            '[class*="offerTitle"]',
            '.offer-title',
            '.detail-title',
            '.subject',
            # 新版1688标题选择器
            '[class*="Title"] h1',
            '[class*="title-content"]',
            '.d-title',
            '.product-title',
            '.goods-title',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                self.product_data.title = element.get_text(strip=True)
                return

        # 尝试从 h1 标签直接获取
        h1_elements = soup.find_all('h1')
        for h1 in h1_elements:
            text = h1.get_text(strip=True)
            if text and len(text) > 10 and len(text) < 200:
                self.product_data.title = text
                return

        # 备用方案：从meta标签获取
        meta_title = soup.find('meta', {'property': 'og:title'})
        if meta_title and meta_title.get('content'):
            self.product_data.title = meta_title['content']
            return

        # 从 title 标签获取
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除常见的后缀
            for suffix in ['-阿里巴巴', '- 阿里巴巴', '_阿里巴巴', '|阿里巴巴', '-1688.com', '- 1688.com']:
                if suffix in title_text:
                    title_text = title_text.split(suffix)[0].strip()
                    break
            if title_text and len(title_text) > 5:
                self.product_data.title = title_text
            
    def _extract_price(self, soup: BeautifulSoup):
        """提取价格区间"""
        selectors = [
            '.price-text',
            '[class*="price"]',
            '.mod-detail-price',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                # 匹配价格格式
                if re.search(r'[\d.]+', text):
                    self.product_data.price_range = text
                    return
                    
    def _extract_main_images(self, soup: BeautifulSoup):
        """提取主图列表（商品展示图 + SKU图）"""
        images = []
        
        # 方法1: 查找主图容器 (1688常用选择器)
        main_selectors = [
            # 新版1688 主图轮播
            '.detail-gallery-img img',
            '.vertical-img img',
            '.detail-gallery-turn-wrapper img',
            '[class*="mainImg"] img',
            '.mod-detail-gallery img',
            '.gallery-list img',
            '.id-content .gallery img',
            # SKU 规格图
            '.sku-item-image img',
            '.sku-wrapper img',
            '[class*="skuItem"] img',
            '[class*="sku-image"] img',
            '.detail-prop-img img',
            '.obj-sku img',
            # 旧版1688
            '#dt-tab img',
            '.tab-content img',
            '.main-image img',
            '#J_MImage img',
            '.main-img-container img',
            # 通用选择器
            '[class*="thumb"] img',
            '[class*="gallery"] img',
            '[class*="preview"] img',
            '.id-content img',
            '.app-offerdetail_container img',
            # 颜色/规格缩略图
            '[class*="color"] img',
            '[class*="prop"] img',
        ]
        
        for selector in main_selectors:
            elements = soup.select(selector)
            for img in elements:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-lazyload-src')
                if src:
                    # 处理图片URL，获取大图
                    src = self._process_image_url(src)
                    if src and src not in images and self._is_valid_product_image(src):
                        images.append(src)
        
        # 方法2: 从script标签中提取JSON数据中的主图
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找JSON数据中的图片（只取非详情图）
                matches = re.findall(r'"(https?://[^"]+\\.(?:jpg|jpeg|png|webp)(?:\\?[^"]*)?)"', script.string, re.I)
                for url in matches:
                    url = self._process_image_url(url)
                    # 过滤详情图（包含detail关键字）
                    if url and url not in images and 'detail' not in url.lower() and self._is_valid_product_image(url):
                        images.append(url)
        
        # 使用标准化 URL 去重
        seen_normalized = set()
        unique_images = []
        for img in images:
            normalized = self._normalize_url_for_dedup(img)
            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                unique_images.append(img)
        
        self.product_data.main_images = unique_images
        print(f"   找到主图/SKU图: {len(unique_images)} 张 (去重前: {len(images)})")
        
    def _extract_shadow_dom_images(self) -> List[str]:
        """从 Shadow DOM 中提取图片"""
        if not self.driver:
            return []
            
        print("正在从 Shadow DOM 提取图片...")
        try:
            # 使用 JavaScript 遍历所有 Shadow Roots 并提取图片
            script = """
            function getAllShadowImages() {
                let images = [];
                
                function traverse(node) {
                    if (!node) return;
                    
                    // 检查是否有 Shadow Root
                    if (node.shadowRoot) {
                        // 提取 Shadow Root 中的图片
                        let imgs = node.shadowRoot.querySelectorAll('img');
                        imgs.forEach(img => {
                            let src = img.getAttribute('src') || 
                                      img.getAttribute('data-src') || 
                                      img.getAttribute('data-lazy-src') ||
                                      img.getAttribute('data-original');
                            if (src) images.push(src);
                        });
                        
                        // 递归遍历 Shadow Root 的子节点
                        node.shadowRoot.querySelectorAll('*').forEach(child => traverse(child));
                    }
                    
                    // 递归遍历子节点 (普通节点)
                    if (node.children) {
                        Array.from(node.children).forEach(child => traverse(child));
                    }
                }
                
                traverse(document.body);
                return images;
            }
            return getAllShadowImages();
            """
            
            urls = self.driver.execute_script(script)
            processed_urls = []
            if urls:
                for url in urls:
                    processed = self._process_image_url(url)
                    if processed and self._is_valid_product_image(processed):
                        processed_urls.append(processed)
                        
            print(f"   从 Shadow DOM 提取到 {len(processed_urls)} 张图片")
            return processed_urls
            
        except Exception as e:
            print(f"Shadow DOM 提取失败: {e}")
            return []

    def _extract_detail_images(self, soup: BeautifulSoup, extra_images: List[str] = None):
        """提取详情页A+图（商品详情描述中的所有图片）"""
        images = []
        
        # 添加外部传入的图片 (如从 Shadow DOM 提取的)
        if extra_images:
            for img in extra_images:
                if img not in images and img not in self.product_data.main_images:
                    images.append(img)
        
        # A+ 详情区域选择器（覆盖1688各种详情模板）
        detail_selectors = [
            # 新版1688 详情区域
            '.detail-content img',
            '.detail-desc img',
            '.detail-desc-decorate-richtext img',
            '.mod-detail-description img',
            '.offer-detail-content img',
            '.detail-decorate img',
            '#J_DivItemDesc img',
            # A+ 富文本区域
            '[class*="richtext"] img',
            '[class*="RichText"] img',
            '[class*="desc"] img',
            '[class*="Desc"] img',
            '[class*="description"] img',
            '[class*="Description"] img',
            # 懒加载容器
            '#desc-lazyload-container img',
            '.lazyload-wrapper img',
            '[data-spm*="desc"] img',
            # 详情图片容器
            '.offer-attr-item img',
            '.de-description img',
            '.de-box img',
            '.detail-module img',
            '.module-desc img',
            # iframe 内容区域（某些详情在 iframe 中）
            '.desc-content img',
            '.offer-desc img',
            # 通用详情图
            '[class*="detail"] img',
            '[class*="Detail"] img',
        ]
        
        for selector in detail_selectors:
            try:
                elements = soup.select(selector)
                for img in elements:
                    # 支持多种图片 URL 属性
                    src = (img.get('src') or img.get('data-src') or 
                           img.get('data-lazy-src') or img.get('data-lazyload-src') or
                           img.get('data-original') or img.get('data-ks-lazyload'))
                    if src:
                        src = self._process_image_url(src)
                        if src and src not in images and src not in self.product_data.main_images:
                            if self._is_valid_product_image(src):
                                images.append(src)
            except:
                continue
        
        # 从 script 标签提取详情图 URL
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                text = script.string
                # 查找详情相关的 JSON 数据中的图片
                if 'detail' in text.lower() or 'desc' in text.lower():
                    matches = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', text, re.I)
                    for url in matches:
                        url = self._process_image_url(url)
                        if url and url not in images and url not in self.product_data.main_images:
                            if self._is_valid_product_image(url):
                                images.append(url)
        
        # 查找所有包含"详情"相关的区域
        for div in soup.find_all(['div', 'section', 'article']):
            class_name = ' '.join(div.get('class', []))
            if any(keyword in class_name.lower() for keyword in ['detail', 'desc', 'content', 'rich']):
                for img in div.find_all('img'):
                    src = (img.get('src') or img.get('data-src') or 
                           img.get('data-lazy-src') or img.get('data-lazyload-src'))
                    if src:
                        src = self._process_image_url(src)
                        if src and src not in images and src not in self.product_data.main_images:
                            if self._is_valid_product_image(src):
                                images.append(src)
        
        # 从原始 HTML 中直接提取 1688 A+ 图片 (cbu01.alicdn.com/img/ibank 格式)
        raw_html = str(soup)
        
        # 匹配 cbu01.alicdn.com 的图片（1688主要 CDN）
        cbu_patterns = [
            r'(https?://cbu01\.alicdn\.com/img/ibank/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
            r'(//cbu01\.alicdn\.com/img/ibank/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
            r'(https?://cbu01\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
            r'(//cbu01\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
        ]
        
        for pattern in cbu_patterns:
            matches = re.findall(pattern, raw_html, re.I)
            for url in matches:
                url = self._process_image_url(url)
                if url and url not in images and url not in self.product_data.main_images:
                    if self._is_valid_product_image(url):
                        images.append(url)
        
        # 匹配其他 alicdn.com 域的图片
        other_alicdn_patterns = [
            r'(https?://img\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
            r'(https?://gw\.alicdn\.com/[^"\'>\s]+\.(?:jpg|jpeg|png|webp))',
        ]
        
        for pattern in other_alicdn_patterns:
            matches = re.findall(pattern, raw_html, re.I)
            for url in matches:
                url = self._process_image_url(url)
                if url and url not in images and url not in self.product_data.main_images:
                    if self._is_valid_product_image(url):
                        images.append(url)
        
        print(f"   从 HTML 提取到 {len(images)} 张候选详情图")
        # 使用标准化 URL 去重（同时排除与主图重复的）
        seen_normalized = set()
        # 先加入主图的标准化形式
        for img in self.product_data.main_images:
            seen_normalized.add(self._normalize_url_for_dedup(img))
        
        unique_images = []
        for img in images:
            normalized = self._normalize_url_for_dedup(img)
            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                unique_images.append(img)
        
        self.product_data.detail_images = unique_images
        print(f"   找到A+详情图: {len(unique_images)} 张 (去重前: {len(images)})")
        
    def _extract_specifications(self, soup: BeautifulSoup):
        """提取规格参数（包括商品属性和包装信息）"""
        specs = {}

        # 方法1: 查找规格列表项
        selectors = [
            '.detail-attributes-item',
            '.mod-detail-attributes tr',
            '[class*="attribute"] li',
            '.obj-attr li',
            '.offer-attr-item',
            # 包装信息表格
            '[class*="package"] tr',
            '[class*="Package"] tr',
            '.product-info tr',
            '.detail-info tr',
            '.mod-detail-info tr',
            # 商品属性表格
            '.de-attibutes tr',
            '.detail-attrs tr',
        ]

        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # 尝试从 td/th 元素提取键值对
                    cells = element.select('td, th')
                    if len(cells) >= 2:
                        for i in range(0, len(cells) - 1, 2):
                            key = cells[i].get_text(strip=True).rstrip(':：')
                            value = cells[i+1].get_text(strip=True)
                            if key and value and len(key) < 30 and len(value) < 200:
                                if key not in specs:  # 避免覆盖
                                    specs[key] = value
                    else:
                        # 尝试拆分文本键值对
                        text = element.get_text(strip=True)
                        if ':' in text or '：' in text:
                            parts = re.split(r'[:：]', text, 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                if key and value and len(key) < 30:
                                    if key not in specs:
                                        specs[key] = value
            except:
                continue

        # 方法2: 专门查找包装信息表格（包含重量等信息）
        package_selectors = [
            '[class*="package"]',
            '[class*="Package"]',
            '.de-packaging',
            '.mod-package',
            '.packaging-info',
            '.pack-info',
            # 包装信息区域
            '[data-spm*="package"]',
            '.offer-attr-list',
        ]

        for pkg_selector in package_selectors:
            package_tables = soup.select(pkg_selector)
            for table in package_tables:
                # 处理表格行
                rows = table.select('tr')
                if rows:
                    # 获取表头
                    header_row = rows[0] if rows else None
                    headers = []
                    if header_row:
                        headers = [th.get_text(strip=True) for th in header_row.select('th, td')]

                    # 处理数据行
                    for row in rows[1:]:
                        cells = row.select('td')
                        if headers and len(cells) == len(headers):
                            for i, cell in enumerate(cells):
                                key = headers[i].rstrip(':：')
                                value = cell.get_text(strip=True)
                                if key and value and key not in specs:
                                    specs[key] = value
                        elif len(cells) >= 2:
                            # 两列格式
                            for i in range(0, len(cells) - 1, 2):
                                key = cells[i].get_text(strip=True).rstrip(':：')
                                value = cells[i+1].get_text(strip=True) if i+1 < len(cells) else ''
                                if key and value and key not in specs:
                                    specs[key] = value

        # 方法3: 从offer-attr-item提取
        offer_attrs = soup.select('.offer-attr-item')
        for attr in offer_attrs:
            label = attr.select_one('.offer-attr-item-label, .attr-name, .label')
            value = attr.select_one('.offer-attr-item-value, .attr-value, .value')
            if label and value:
                k = label.get_text(strip=True).rstrip(':：')
                v = value.get_text(strip=True)
                if k and v and k not in specs:
                    specs[k] = v

        # 方法4: 查找所有表格，提取包含关键字的行
        all_tables = soup.select('table')
        weight_keywords = ['重量', '克重', '净重', '毛重', 'weight', '包装']
        for table in all_tables:
            rows = table.select('tr')
            for row in rows:
                row_text = row.get_text(strip=True)
                # 检查是否包含重量相关关键字
                if any(kw in row_text.lower() for kw in weight_keywords):
                    cells = row.select('td, th')
                    if len(cells) >= 2:
                        for i in range(0, len(cells) - 1, 2):
                            key = cells[i].get_text(strip=True).rstrip(':：')
                            value = cells[i+1].get_text(strip=True)
                            if key and value and key not in specs:
                                specs[key] = value

        # 方法5: 解析attribute容器中的连续文本
        if len(specs) < 3:  # 如果提取的属性太少，尝试其他方法
            attr_container = soup.select_one('[class*="attribute"]')
            if attr_container:
                text = attr_container.get_text(strip=True)
                # 尝试按常见的属性名分割
                attr_names = ['材质', '处理工艺', '链子样式', '坠子材质', '品牌',
                              '流行元素', '风格', '生产编号', '销售序列号', '产地',
                              '货号', '适用场景', '适用人群', '适用性别', '克重',
                              '尺寸', '颜色', '包装', '重量', '净重', '毛重']
                for name in attr_names:
                    if name in text and name not in specs:
                        idx = text.find(name)
                        if idx >= 0:
                            rest = text[idx + len(name):]
                            next_idx = len(rest)
                            for next_name in attr_names:
                                pos = rest.find(next_name)
                                if pos > 0 and pos < next_idx:
                                    next_idx = pos
                            value = rest[:next_idx].strip()
                            if value:
                                specs[name] = value

        self.product_data.specifications = specs
        print(f"   找到规格参数: {len(specs)} 项")
        
    def _extract_description(self, soup: BeautifulSoup):
        """提取商品描述"""
        selectors = [
            '.detail-description',
            '.mod-detail-description',
            '[class*="description"] p',
            '.offer-attr-item',  # 新增：属性项也作为描述的一部分
        ]
        
        descriptions = []
        seen = set()
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 5 and text not in seen:
                    descriptions.append(text)
                    seen.add(text)
        
        # 提取SKU信息作为描述的一部分
        sku_items = soup.select('[class*="sku"] .sku-item-name, [class*="sku"] .name')
        sku_info = []
        for item in sku_items:
            text = item.get_text(strip=True)
            if text and text not in seen:
                sku_info.append(text)
                seen.add(text)
        if sku_info:
            descriptions.append('可选规格: ' + ', '.join(sku_info[:10]))
                    
        self.product_data.description = '\n'.join(descriptions[:20])  # 限制数量
        
    def _extract_shop_name(self, soup: BeautifulSoup):
        """提取店铺名称"""
        selectors = [
            '.store-name',      # 新版1688
            '.shop-name',
            '.company-name',
            '[class*="shopName"]',
            '[class*="companyName"]',
            '.title-company',
            '.seller-name',
            'a[href*="winport"]',  # 店铺链接
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 50:
                    self.product_data.shop_name = text
                    return
                
    def _process_image_url(self, url: str) -> Optional[str]:
        """处理图片URL，获取大图并标准化用于去重"""
        if not url:
            return None
            
        # 确保是HTTPS
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            return None
        
        # 移除缩略图尺寸参数 (如 _50x50.jpg, _100x100.jpg, .60x60.jpg)
        url = re.sub(r'[._]\d+x\d+\.', '.', url)
        
        # 移除 alicdn.com 常见的尺寸参数 (如 .jpg_Q75.jpg, .png_250x250.jpg_)
        url = re.sub(r'\.(jpg|jpeg|png|webp|gif)_.*$', r'.\1', url, flags=re.I)
        
        # 移除 URL 查询参数
        url = re.sub(r'\?.*$', '', url)
        
        # 移除结尾的数字后缀 (如 _1, _2, _3 在同一张图的变体)
        # 但保留图片本身的编号
        
        return url
    
    def _normalize_url_for_dedup(self, url: str) -> str:
        """标准化 URL 用于去重比较"""
        if not url:
            return ""
        # 提取图片的核心标识（去掉所有尺寸、参数）
        # 例如: https://cbu01.alicdn.com/img/abc123.jpg -> abc123.jpg
        match = re.search(r'/([^/]+\.(jpg|jpeg|png|webp|gif))$', url, re.I)
        if match:
            return match.group(1).lower()
        return url.lower()
    
    def _is_valid_product_image(self, url: str) -> bool:
        """检查是否为有效的产品图片URL"""
        if not url:
            return False
            
        url_lower = url.lower()
        
        # 排除常见的无效图片（logo、图标、占位符等）
        exclude_patterns = [
            # 通用无效图片
            'logo', 'icon', 'loading', 'placeholder', 
            'avatar', 'banner', 'advertisement',
            'blank', 'empty', '1x1', 'pixel', 'spacer',
            # 1688/阿里特有的无效图片
            'tb1', 'tb2',  # 淘宝小图标
            'iconfont', 'sprite', 'service', 
            'guarantee', 'badge', 'tag', 'label',
            'time', 'clock', 'shield', 'star', 'heart',
            'arrow', 'button', 'btn', 'close', 'check',
            'play', 'pause', 'video', 'audio',
            'qr', 'qrcode', 'barcode', 'wechat', 'alipay',
            'watermark', 'stamp', 'seal',
            # 常见UI元素
            'nav', 'menu', 'header', 'footer',
            'sidebar', 'bg', 'background',
            # 社交媒体图标
            'facebook', 'twitter', 'instagram', 'weibo', 'wechat',
            'share', 'like', 'comment',
            # 小尺寸标识
            '16x16', '24x24', '32x32', '48x48', '64x64',
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 排除过短的文件名（通常是图标）
        match = re.search(r'/([^/]+)\.(jpg|jpeg|png|webp|gif)$', url_lower)
        if match:
            filename = match.group(1)
            # 文件名太短通常是图标
            if len(filename) < 6:
                return False
            # 纯数字且很短的文件名可能是图标
            if filename.isdigit() and len(filename) < 8:
                return False
                
        # 检查是否有有效的图片扩展名
        if not re.search(r'\.(jpg|jpeg|png|webp|gif)($|\?)', url_lower):
            return False
        
        # 检查图片尺寸（从URL参数中判断，如果能判断的话）
        # 排除明确标注为小图的URL
        small_size_pattern = re.search(r'[._](\d+)x(\d+)[._]', url_lower)
        if small_size_pattern:
            width = int(small_size_pattern.group(1))
            height = int(small_size_pattern.group(2))
            # 排除尺寸小于100像素的图片
            if width < 100 or height < 100:
                return False
            
        return True
    
    def get_main_images(self) -> List[str]:
        """获取主图URL列表"""
        return self.product_data.main_images if self.product_data else []
    
    def get_detail_images(self) -> List[str]:
        """获取详情页图片URL列表"""
        return self.product_data.detail_images if self.product_data else []
    
    def get_product_text(self) -> Dict[str, Any]:
        """获取所有文案信息"""
        if not self.product_data:
            return {}
        return {
            "title": self.product_data.title,
            "description": self.product_data.description,
            "price_range": self.product_data.price_range,
            "specifications": self.product_data.specifications,
            "shop_name": self.product_data.shop_name,
        }

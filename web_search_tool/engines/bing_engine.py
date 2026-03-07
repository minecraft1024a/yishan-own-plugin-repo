"""
Bing search engine implementation
"""

import asyncio
import base64
import random
import traceback
import urllib.parse
from typing import Any, TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup, Tag

from src.kernel.logger import get_logger

from .base import BaseSearchEngine

if TYPE_CHECKING:
    from ..config import WebSearchConfig

logger = get_logger("bing_engine")

# 默认配置值（如果配置未加载时使用）
DEFAULT_ABSTRACT_MAX_LENGTH = 300
DEFAULT_CONTENT_MAX_LENGTH = 3000
DEFAULT_FETCH_CONTENT = True
DEFAULT_MAX_CONCURRENT_FETCHES = 3
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_CONTENT_FETCH_TIMEOUT = 8

user_agents = [
    # Edge浏览器
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    # Chrome浏览器
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Firefox浏览器
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# 请求头信息
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",  # 移除 br，避免 Brotli 压缩问题
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Host": "www.bing.com",
    "Referer": "https://www.bing.com/",
    "Sec-Ch-Ua": '"Chromium";v="122", "Microsoft Edge";v="122", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
}

bing_search_url = "https://www.bing.com/search?q="


class BingSearchEngine(BaseSearchEngine):
    """
    Bing搜索引擎实现
    """

    def __init__(self, config: "WebSearchConfig | None" = None):
        super().__init__(config)
        self.client = None
        
        # 从配置加载设置，如果配置不存在则使用默认值
        if config and hasattr(config, 'bing'):
            self.fetch_content = config.bing.fetch_page_content
            self.content_max_length = config.bing.content_max_length
            self.max_concurrent_fetches = config.bing.max_concurrent_fetches
            self.abstract_max_length = config.bing.abstract_max_length
            self.request_timeout = config.bing.request_timeout
            self.content_fetch_timeout = config.bing.content_fetch_timeout
        else:
            # 使用默认配置
            self.fetch_content = DEFAULT_FETCH_CONTENT
            self.content_max_length = DEFAULT_CONTENT_MAX_LENGTH
            self.max_concurrent_fetches = DEFAULT_MAX_CONCURRENT_FETCHES
            self.abstract_max_length = DEFAULT_ABSTRACT_MAX_LENGTH
            self.request_timeout = DEFAULT_REQUEST_TIMEOUT
            self.content_fetch_timeout = DEFAULT_CONTENT_FETCH_TIMEOUT
        
        logger.debug(f"Bing引擎配置: fetch_content={self.fetch_content}, "
                    f"content_max={self.content_max_length}, "
                    f"concurrent={self.max_concurrent_fetches}")

    def is_available(self) -> bool:
        """检查Bing搜索引擎是否可用"""
        return True  # Bing是免费搜索引擎，总是可用

    async def search(
        self,
        query: str,
        num_results: int = 3,
        time_range: str = "any"
    ) -> list[dict[str, Any]]:
        """执行Bing搜索"""
        logger.debug(f"Bing 搜索: query='{query}', num_results={num_results}, time_range={time_range}")

        try:
            search_response = await self._search_async(query, num_results, time_range)
            if search_response:
                logger.info(f"Bing 搜索成功，返回 {len(search_response)} 条结果")
            else:
                logger.warning(f"Bing 搜索未找到结果")
            return search_response
        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            return []

    async def _search_async(self, keyword: str, num_results: int, time_range: str) -> list[dict[str, Any]]:
        """异步执行Bing搜索"""
        if not keyword:
            return []

        list_result = []

        # 构建搜索URL
        search_url = bing_search_url + keyword

        # 如果指定了时间范围,添加时间过滤参数
        if time_range == "week":
            search_url += "&qft=+filterui:date-range-7"
        elif time_range == "month":
            search_url += "&qft=+filterui:date-range-30"

        try:
            data = await self._parse_html(search_url)
            if data:
                list_result.extend(data)
                logger.debug(f"Bing搜索 [{keyword}] 找到 {len(data)} 个结果")

        except Exception as e:
            logger.error(f"Bing搜索解析失败: {e}")
            return []

        logger.debug(f"Bing搜索 [{keyword}] 完成,总共 {len(list_result)} 个结果")
        return list_result[:num_results] if len(list_result) > num_results else list_result

    async def _parse_html(self, url: str) -> list[dict[str, Any]]:
        """解析处理结果"""
        try:
            logger.debug(f"访问Bing搜索URL: {url}")

            # 设置必要的Cookie
            cookies = {
                "SRCHHPGUSR": "SRCHLANG=zh-Hans",  # 设置默认搜索语言为中文
                "SRCHD": "AF=NOFORM",
                "SRCHUID": "V=2&GUID=1A4D4F1C8844493F9A2E3DB0D1BC806C",
                "_SS": "SID=0D89D9A3C95C60B62E7AC80CC85461B3",
                "_EDGE_S": "ui=zh-cn",  # 设置界面语言为中文
                "_EDGE_V": "1",
            }

            # 为每次请求随机选择不同的用户代理，降低被屏蔽风险
            headers = HEADERS.copy()
            headers["User-Agent"] = random.choice(user_agents)

            # 创建异步客户端
            async with httpx.AsyncClient(headers=headers, cookies=cookies, follow_redirects=True) as client:
                # 发送请求
                try:
                    res = await client.get(url=url, timeout=httpx.Timeout(self.request_timeout, connect=5.0))
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.warning(f"第一次请求超时，正在重试: {e!s}")
                    try:
                        res = await client.get(url=url, timeout=httpx.Timeout(self.request_timeout + 5, connect=10.0))
                    except Exception as e2:
                        logger.error(f"第二次请求也失败: {e2!s}")
                        return []

                # 检查响应状态
                logger.debug(f"收到响应: status={res.status_code}, encoding={res.headers.get('content-encoding', 'none')}")
                
                if res.status_code == 403:
                    logger.error("被禁止访问 (403)，可能是IP被限制")
                    return []

                if res.status_code != 200:
                    logger.error(f"请求失败，状态码: {res.status_code}")
                    return []

                # 检查是否被重定向到登录页面或验证页面
                if "login.live.com" in str(res.url) or "login.microsoftonline.com" in str(res.url):
                    logger.error("被重定向到登录页面")
                    return []

                if "https://www.bing.com/ck/a" in str(res.url):
                    logger.error("被重定向到验证页面")
                    return []

                # 获取文本内容
                try:
                    html_text = res.text
                    logger.debug(f"HTML 长度: {len(html_text)} 字符")
                except Exception as decode_error:
                    logger.error(f"解码响应失败: {decode_error}")
                    try:
                        html_text = res.content.decode('utf-8', errors='ignore')
                        logger.debug("使用 UTF-8 手动解码成功")
                    except Exception as e2:
                        logger.error(f"手动解码失败: {e2}")
                        return []

                # 解析HTML
                try:
                    root = BeautifulSoup(html_text, "lxml")
                except Exception:
                    try:
                        root = BeautifulSoup(html_text, "html.parser")
                    except Exception as e:
                        logger.error(f"HTML解析失败: {e!s}")
                        return []

                list_data = []

                # 尝试提取搜索结果
                # 方法1: 查找标准的搜索结果容器
                results = root.select("ol#b_results li.b_algo")
                logger.debug(f"找到 {len(results)} 个标准搜索结果")

                if results:
                    for _rank, result in enumerate(results, 1):
                        # 提取标题和链接
                        title_link = result.select_one("h2 a")
                        if not title_link:
                            continue

                        title = title_link.get_text().strip()
                        url_attr = title_link.get("href")
                        url = str(url_attr) if url_attr else ""
                        
                        # 解析 Bing 重定向链接，提取真实 URL
                        url = self._extract_real_url(url)

                        # 提取摘要 (支持 b_caption 下的 p 标签)
                        abstract = ""
                        abstract_elem = result.select_one("div.b_caption p")
                        if abstract_elem:
                            abstract = abstract_elem.get_text().strip()

                        # 限制摘要长度
                        if self.abstract_max_length and len(abstract) > self.abstract_max_length:
                            abstract = abstract[:self.abstract_max_length] + "..."

                        # 跳过无效的结果
                        if not url or not title:
                            continue

                        list_data.append({"title": title, "url": url, "snippet": abstract, "provider": "Bing"})

                        if len(list_data) >= 10:  # 限制结果数量
                            break

                # 方法2: 如果标准方法没找到结果，使用备用方法
                if not list_data:
                    logger.debug("使用备用方法搜索链接...")
                    all_links = root.find_all("a")
                    filtered_count = 0

                    for link in all_links:
                        if not isinstance(link, Tag):
                            continue
                        href_attr = link.get("href")
                        href = str(href_attr) if href_attr else ""
                        text = link.get_text().strip()

                        # 过滤有效的搜索结果链接
                        if (
                            href
                            and isinstance(href, str)
                            and text
                            and len(text) > 10
                            and not href.startswith("javascript:")
                            and not href.startswith("#")
                            and "http" in href
                            and not any(
                                x in href
                                for x in [
                                    "bing.com/search",
                                    "bing.com/images",
                                    "bing.com/videos",
                                    "bing.com/maps",
                                    "bing.com/news",
                                    "login",
                                    "account",
                                    "microsoft",
                                    "javascript",
                                ]
                            )
                        ):
                            filtered_count += 1
                            
                            # 解析 Bing 重定向链接
                            href = self._extract_real_url(href)
                            
                            # 尝试获取摘要
                            abstract = ""
                            parent = link.parent
                            if parent and parent.get_text():
                                full_text = parent.get_text().strip()
                                if len(full_text) > len(text):
                                    abstract = full_text.replace(text, "", 1).strip()

                            # 限制摘要长度
                            if self.abstract_max_length and len(abstract) > self.abstract_max_length:
                                abstract = abstract[:self.abstract_max_length] + "..."

                            list_data.append({"title": text, "url": href, "snippet": abstract, "provider": "Bing"})

                            if len(list_data) >= 10:
                                break

                    logger.debug(f"备用方法过滤后有效链接: {filtered_count}")

                if list_data:
                    logger.debug(f"解析到 {len(list_data)} 个搜索结果")
                    
                    # 获取网页完整内容
                    if self.fetch_content:
                        logger.debug(f"开始获取 {len(list_data)} 个网页的完整内容...")
                        list_data = await self._fetch_contents(list_data)
                else:
                    logger.warning("未解析到任何搜索结果")
                    logger.debug(f"HTML 长度: {len(html_text)}, 前200字符: {html_text[:200]}")
                        
                return list_data

        except Exception as e:
            logger.error(f"解析Bing页面失败: {e!s}")
            logger.debug(traceback.format_exc())
            return []

    def _extract_real_url(self, bing_url: str) -> str:
        """从 Bing 重定向链接中提取真实 URL"""
        if not bing_url:
            return bing_url
        
        # 如果不是 Bing 重定向链接，直接返回
        if "bing.com/ck/a" not in bing_url:
            return bing_url
        
        try:
            # 提取 u= 参数（真实 URL）
            parsed = urllib.parse.urlparse(bing_url)
            params = urllib.parse.parse_qs(parsed.query)
            
            if 'u' in params and params['u']:
                # 解码 Base64 编码的 URL
                encoded_url = params['u'][0]
                # Bing 使用的是一种特殊的编码，先去掉前缀
                if encoded_url.startswith('a1'):
                    encoded_url = encoded_url[2:]
                
                # Base64 解码
                try:
                    real_url = base64.b64decode(encoded_url + '==').decode('utf-8', errors='ignore')
                    logger.debug(f"提取真实 URL: {bing_url[:50]}... -> {real_url[:80]}...")
                    return real_url
                except Exception as decode_error:
                    logger.debug(f"Base64 解码失败: {decode_error}")
                    return bing_url
            
            return bing_url
            
        except Exception as e:
            logger.debug(f"提取真实 URL 失败: {e}")
            return bing_url

    async def _fetch_contents(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """并发获取所有搜索结果的网页内容"""
        # 使用信号量限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent_fetches)
        
        async def fetch_with_semaphore(result: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                content = await self._fetch_page_content(result["url"])
                if content:
                    result["content"] = content
                return result
        
        # 并发获取所有页面内容
        tasks = [fetch_with_semaphore(result) for result in results]
        updated_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤掉异常结果
        valid_results = []
        for result in updated_results:
            if isinstance(result, dict):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"获取页面内容时出错: {result}")
        
        return valid_results

    async def _fetch_page_content(self, url: str) -> str:
        """获取单个网页的文本内容"""
        try:
            # 跳过无效或重定向 URL
            if not url or "bing.com/ck/a" in url or url.startswith("javascript:") or url.startswith("#"):
                logger.debug(f"跳过无效 URL: {url[:80]}...")
                return ""
            
            logger.debug(f"正在获取页面内容: {url[:80]}...")
            
            # 使用随机User-Agent
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
            }
            
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                try:
                    response = await client.get(url, timeout=httpx.Timeout(self.content_fetch_timeout, connect=5.0))
                    
                    if response.status_code != 200:
                        logger.debug(f"页面请求失败: {url[:50]}..., 状态码: {response.status_code}")
                        return ""
                    
                    # 检查是否是重定向页面
                    html_text = response.text
                    if "Please click here if the page does not redirect" in html_text:
                        logger.debug(f"检测到重定向页面，跳过: {url[:50]}...")
                        return ""
                    
                    # 解析HTML并提取文本
                    try:
                        soup = BeautifulSoup(html_text, "lxml")
                    except Exception:
                        soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 移除脚本、样式等无用标签
                    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
                        tag.decompose()
                    
                    # 尝试提取主要内容
                    main_content = None
                    
                    # 方法1: 查找常见的主内容容器
                    for selector in ["article", "main", "[role='main']", ".content", "#content", ".post-content", ".article-content"]:
                        main_content = soup.select_one(selector)
                        if main_content:
                            break
                    
                    # 方法2: 如果没找到，使用body
                    if not main_content:
                        main_content = soup.find("body")
                    
                    if main_content:
                        # 提取文本并清理
                        text = main_content.get_text(separator="\n", strip=True)
                        # 去除多余空行
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        text = "\n".join(lines)
                        
                        # 限制长度
                        if len(text) > self.content_max_length:
                            text = text[:self.content_max_length] + "..."
                        
                        logger.debug(f"成功获取页面内容: {len(text)} 字符")
                        return text
                    else:
                        logger.debug("未找到页面主要内容")
                        return ""
                    
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.debug(f"获取页面超时: {url[:50]}... - {e!s}")
                    return ""
                except Exception as e:
                    logger.debug(f"获取页面内容失败: {url[:50]}... - {e!s}")
                    return ""
                    
        except Exception as e:
            logger.debug(f"处理页面时出错: {e!s}")
            return ""

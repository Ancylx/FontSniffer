import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Generator, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class FontSniffer:
    """智能字体爬虫 - 支持并发、重试、动态配置"""

    def __init__(self, user_agent: str, max_workers: int = 8) -> None:
        """
        初始化爬虫

        Args:
            user_agent: User-Agent 字符串
            max_workers: 并发线程数（建议 5-10）
        """
        # 请求配置
        self.base_url = "http://www.downcc.com/font/list_200_{page}.html"
        self.timeout = 15
        self.max_retries = 3
        self.base_delay = 0.3

        # 创建 Session 复用连接
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })

        # 并发配置
        self.max_workers = max(1, min(max_workers, 20))

        # 状态控制（可由 GUI 重写）
        self.should_stop: Callable[[], bool] = lambda: False

        # 预编译正则
        self._page_regex = re.compile(r"list_200_(\d+)\.html")
        self._font_regex = re.compile(r"/font/")

        # 统计信息
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retried_requests": 0,
        }

    def _detect_total_pages(self) -> int:
        """
        智能检测总页数
        
        Returns:
            总页数，失败时返回383
        """
        try:
            html = self._fetch_page(1)
            if not html:
                return 383

            soup = BeautifulSoup(html, "html.parser")
            pager = soup.find("div", class_="pages")

            if pager:
                page_links = pager.find_all("a", href=self._page_regex)
                if page_links:
                    page_numbers = [
                        int(match.group(1))
                        for link in page_links
                        if (match := self._page_regex.search(link.get("href", "")))
                    ]
                    return max(page_numbers) if page_numbers else 383

            return 383
        except Exception as e:
            print(f"页数检测失败: {e}")
            return 383

    def _fetch_page(self, page: int, retry_count: int = 0) -> Optional[str]:
        """
        获取单页内容（智能重试）

        Args:
            page: 页码
            retry_count: 当前重试次数

        Returns:
            HTML 文本或 None
        """
        if self.should_stop():
            return None

        try:
            self.stats["total_requests"] += 1

            url = self.base_url.format(page=page)
            response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
            response.raise_for_status()
            response.encoding = "utf-8"

            self.stats["successful_requests"] += 1
            return response.text
        except requests.exceptions.RequestException as e:
            self.stats["failed_requests"] += 1

            if retry_count < self.max_retries and not self.should_stop():
                self.stats["retried_requests"] += 1

                # 指数退避 + 随机抖动
                delay = self.base_delay * (2  ** retry_count) + random.uniform(0.1, 0.3)
                print(f"第{page}页请求失败: {str(e)[:50]}... | "
                      f"{delay:.2f}秒后重试({retry_count+1}/{self.max_retries})")

                time.sleep(delay)
                return self._fetch_page(page, retry_count + 1)

            print(f"第{page}页请求失败，已跳过: {str(e)[:50]}...")
            return None

    def _parse_and_filter_page(self, page: int) -> Tuple[int, List[Tuple[str, str]]]:
        """
        解析并过滤单页

        Args:
            page: 页码

        Returns:
            (页码, 匹配结果列表)
        """
        html = self._fetch_page(page)
        if not html:
            return page, []

        soup = BeautifulSoup(html, "html.parser")
        target_section = soup.find("section", class_="mg-t10 border soft-list")
        if not target_section:
            return page, []

        font_ul = target_section.find("ul", id="li-change-color",
                                     class_="soft-list-bd hover-one")
        if not font_ul:
            return page, []

        results = []
        keyword_lower = self._keyword.lower() if hasattr(self, '_keyword') else ""

        for li in font_ul.find_all("li"):
            font_a_tag = li.find("a", class_="mg-r10",
                               href=lambda x: x and self._font_regex.match(x))
            if not font_a_tag:
                continue

            font_name = font_a_tag.get_text(strip=True)
            if keyword_lower and keyword_lower not in font_name.lower():
                continue

            relative_url = font_a_tag.get("href", "")
            full_url = urljoin("http://www.downcc.com", relative_url)
            results.append((font_name, full_url))

        return page, results

    def search(self, keyword: str) -> Generator[Dict[str, str], None, None]:
        """
        并发搜索字体

        Args:
            keyword: 搜索关键词

        Yields:
            状态或结果字典
        """
        self._keyword = keyword

        # 动态检测页数
        yield {"type": "status", "content": "正在检测总页数..."}
        total_pages = self._detect_total_pages()
        yield {"type": "status", "content": f"✅ 检测到总页数: {total_pages}"}

        # 初始化并发
        yield {"type": "status",
               "content": f"启动 {self.max_workers} 个并发线程 | 关键词: '{keyword}'"}

        completed_pages = 0
        total_found = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_page = {
                executor.submit(self._parse_and_filter_page, page): page
                for page in range(1, total_pages + 1)
            }

            # 按完成顺序处理
            for future in as_completed(future_to_page):
                if self.should_stop():
                    executor.shutdown(wait=False)
                    yield {"type": "status", "content": "⏹ 搜索已中止"}
                    break

                page = future_to_page[future]
                try:
                    _, matched_fonts = future.result()
                    completed_pages += 1

                    # 进度状态
                    progress_msg = (
                        f"第{page}页完成 | "
                        f"已处理 {completed_pages}/{total_pages} 页 | "
                        f"找到 {total_found} 个字体"
                    )
                    yield {"type": "status", "content": progress_msg}

                    # 发送匹配结果
                    if matched_fonts:
                        total_found += len(matched_fonts)
                        for font_name, font_url in matched_fonts:
                            yield {
                                "type": "result",
                                "content": f'"{font_name}" 符合条件\n下载页面：{font_url}'
                            }
                except Exception as e:
                    yield {"type": "status",
                           "content": f"第{page}页处理异常: {str(e)[:50]}..."}

        # 完成报告
        if not self.should_stop():
            yield {
                "type": "status",
                "content": (
                    f"\n{'='*60}\n"
                    f"✅ 搜索完成！共找到 {total_found} 个字体\n"
                    f"📊 请求统计: 总={self.stats['total_requests']} "
                    f"| 成功={self.stats['successful_requests']} "
                    f"| 失败={self.stats['failed_requests']} "
                    f"| 重试={self.stats['retried_requests']}"
                )
            }

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self.stats.copy()


# 直接运行测试
if __name__ == "__main__":
    import time

    print("=" * 60)
    print("字体嗅探器 - 性能测试模式")
    print("=" * 60)

    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    sniffer = FontSniffer(user_agent=default_ua, max_workers=10)

    keyword = input("请输入测试关键词 (默认: 宋体): ").strip() or "宋体"

    print(f"\n开始搜索 '{keyword}'...")
    print(f"并发线程: {sniffer.max_workers}")
    print("-" * 60)

    start_time = time.time()
    found = 0

    try:
        for item in sniffer.search(keyword):
            if item["type"] == "result":
                found += 1
            elif item["type"] == "status" and ("完成" in item["content"]
                                             or "中止" in item["content"]):
                print(f"【状态】{item['content']}")
    except KeyboardInterrupt:
        print("\n⏹ 用户中止搜索")

    elapsed = time.time() - start_time

    print("-" * 60)
    print(f"🎯 测试完成！")
    print(f"⏱️  耗时: {elapsed:.2f} 秒")
    print(f"📁 找到字体: {found} 个")
    print(f"🔧 并发数: {sniffer.max_workers}")
    print(f"📊 请求统计: {sniffer.get_stats()}")
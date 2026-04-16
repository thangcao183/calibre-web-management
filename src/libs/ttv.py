from typing import Callable, Optional
from playwright.async_api import async_playwright
import asyncio
from .basescraper import BaseClient
from .lib_types import BookInfor, Chapter
from .text_proc import smart_punctuation
from unicodedata import normalize
import logging
import tqdm
from difflib import SequenceMatcher
import re
from bs4 import BeautifulSoup
from aiohttp import ClientSession

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { configurable: true, get: () => undefined });
window.navigator.chrome = { runtime: {} };
window.navigator.permissions.query = (parameters) => (
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : Promise.resolve({ state: 'prompt' })
);
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""


class TtvClient(BaseClient):
    def __init__(self,url):
        self.url = url
        self.book_infor = BookInfor()
        self.client = None
        self.main_page = None
        # self.page = None

    async def __aenter__(self):
        self.client = ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.close() # type: ignore

    @staticmethod
    def has_chapter_number(url):
        """Kiểm tra xem URL có chứa 'chuong-<số chương>' không."""
        pattern = r"/chuong-\d+$"
        return bool(re.search(pattern, url))


    async def fetch_page(self, url) -> Optional[str]:
        """
        Gửi HTTP GET request và trả về nội dung HTML nếu thành công.
        """
        # print(f"Fetching URL: {url}")
        try:
            async with self.client.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            return None

    def parse_book_description(self, text) -> str:
        """
        Lấy mô tả sách.
        """
        result = [
            "<p>" + smart_punctuation(line.strip()) + "</p>"
            for line in text.split("\n")
            if line.strip()
        ]
        return "\n".join(result).strip()

    @staticmethod
    def parse_infor(soup: BeautifulSoup, selector: str):
        try:
            result = soup.select(selector)
            # print(result[0].text)
            return result
        except:
            return []

    async def parse_book_info(self) -> BookInfor: # type: ignore
        """Lấy thông tin sách từ HTML trang chính"""
        html = await self.fetch_page(self.url)
        soup = BeautifulSoup(normalize("NFC", html), "lxml")
        self.book_infor.title = self.parse_infor(soup, "h1")[0].text.split("-")[0].strip()
        self.book_infor.author = self.parse_infor(soup, "div#authorId")[0].text.strip()
        self.book_infor.book_id = self.parse_infor(soup, "#story_id_hidden")[0]["value"] # type: ignore
        self.book_infor.tags = [
            i.text.strip()
            for i in self.parse_infor(soup, ".tags > .detail > .tag-wrap > .tags")
        ]
        self.book_infor.description = self.parse_book_description(
            self.parse_infor(soup, "div.book-intro > p")[0].text
        )
        self.book_infor.cover = (
            self.parse_infor(soup, "div.book-img > a > img")[0]["src"]
            if self.parse_infor(soup, "div.book-img > a > img")
            else "https://tangthuvien.top/images/default-book.png"
        ) # type: ignore
        self.book_infor.chapter_list = await self.get_chapters_list()
        return self.book_infor

    async def get_chapters_list(self) -> [Chapter]:  # type: ignore
        url = f"https://tangthuvien.top/story/chapters?story_id={self.book_infor.book_id}"
        html = await self.fetch_page(url)
        soup = BeautifulSoup(normalize("NFC", html), "lxml") # type: ignore
        chapters_selector = self.parse_infor(soup, "a")
        chapters_list = [
            Chapter(
                name=normalize("NFC", c_data["title"]).replace("\xa0:\xa0", ": "), # type: ignore
                chap_url=c_data["href"], # type: ignore
                index=index,
                is_locked=False,
            )
            for index, c_data in enumerate(chapters_selector)
        ]
        return chapters_list

    @staticmethod
    def parse_chapter_content(text, chapter_name):
        """
        Trích xuất nội dung chương từ HTML và định dạng lại.
        """
        result = [
            smart_punctuation(line.strip())
            for line in re.split(r"\n", text)
            if line.strip() and "<div" not in line.strip()
        ]

        if SequenceMatcher(None, result[0], chapter_name).ratio() > 0.8:
            result.pop(0)

        formatted_result = [
            f'<p class="line-{i}">{line}</p>' for i, line in enumerate(result)
        ]
        return "\n".join(formatted_result).strip()

    async def fetch_content(self, chapter: Chapter):
        """
        Fetch nội dung chương (async).
        """
        for _ in range(3):
            try:
                html = await self.fetch_page(chapter.chap_url)
                soup = BeautifulSoup(html, "lxml")
                content = (
                    self.parse_infor(soup, "div.box-chap")[0].text
                    if self.parse_infor(soup, "div.box-chap")
                    else "Không tìm thấy nội dung"
                )
                # print(content)
                return {
                    "title": chapter.name,
                    "content": self.parse_chapter_content(
                        normalize("NFC", content), chapter.name
                    ),
                }
            except Exception:
                await asyncio.sleep(2)
        return {"title": chapter.name, "content": ""}

    async def get_book_content(
        self,
        max_concurrent_tasks=5,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list:
        try:
            chapter_list = self.book_infor.chapter_list

            # Sử dụng Semaphore để giới hạn tác vụ đồng thời
            semaphore = asyncio.Semaphore(max_concurrent_tasks)

            async def safe_fetch(chapter, index):
                async with semaphore:
                    try:
                        content = await self.fetch_content(chapter)
                        return index, content
                    except Exception as e:
                        logging.error(f"Error downloading chapter {chapter}: {e}")
                        return index, None

            # Tạo tasks với chỉ số để giữ nguyên thứ tự
            tasks = [safe_fetch(chap, idx) for idx, chap in enumerate(chapter_list)]

            # Lưu trữ kết quả theo thứ tự ban đầu
            results = [None] * len(chapter_list)

            completed = 0
            total = len(chapter_list)

            for future in tqdm.tqdm(
                asyncio.as_completed(tasks),
                total=total,
                desc="Downloading Chapters",
            ):
                index, result = await future
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                if result is not None:
                    results[index] = result # type: ignore

            # Loại bỏ các chapter không tải được (nếu có)
            return [chapter for chapter in results if chapter is not None]

        except Exception as e:
            logging.error(f"Critical error in book content download: {e}")
            return []
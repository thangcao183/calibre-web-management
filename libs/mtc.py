import os
import re
import json
import asyncio
from typing import List, Optional
from bs4 import BeautifulSoup
from unicodedata import normalize
from .text_proc import smart_punctuation, clean_json_string
from .lib_types import Chapter, BookInfor
from .basescraper import BaseClient
import tqdm
from aiohttp import ClientSession
import logging


def parse_html_text(html: str, selector: str, attr: Optional[str] = None, default: str = "") -> str:
    """
    Trích xuất nội dung từ HTML theo selector CSS.
    Nếu attr không None, lấy giá trị thuộc tính, ngược lại lấy nội dung văn bản.
    """
    soup = BeautifulSoup(html, "lxml")
    element = soup.select_one(selector)
    if not element:
        return default
    return element[attr] if attr and attr in element.attrs else element.text.strip()


def parse_chapter_content(html: str) -> dict:
    """
    Trích xuất nội dung chương từ HTML và định dạng lại.
    """
    soup = BeautifulSoup(html, "lxml")
    chapter_name = parse_html_text(html, "div > h2.text-gray-600.text-balance")
    content_tag = soup.select_one("div#chapter-detail > div.break-words")

    if not content_tag:
        return chapter_name, ""

    raw_text = content_tag.decode_contents()
    result = [smart_punctuation(line.strip()) for line in re.split(r"<br\s*/?>", raw_text) if line.strip() and "<div" not in line.strip()]
    
    if result and result[0] == chapter_name:
        result.pop(0)

    formatted_result = [f'<p class="line-{i}">{line}</p>' for i, line in enumerate(result)]
    return {"title":chapter_name,"content": "\n".join(formatted_result).strip()}


class MtcClient(BaseClient):
    BASE_URL = "https://backend.metruyencv.com/api/"

    def __init__(self,url):
        self.url = url
        self.book_infor = BookInfor()
        self.client = None
        self.main_page = None

    async def __aenter__(self):
        self.client = ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.close()

    async def fetch_url(self, url) -> Optional[str]:
        """
        Gửi HTTP GET request và trả về nội dung HTML nếu thành công.
        """
        print(f"Fetching URL: {url}")
        try:
            async with self.client.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            return None

    async def parse_book_info(self) -> BookInfor:
        """
        Lấy thông tin sách từ trang chính.
        """
        self.main_page = await self.fetch_url(self.url)
        if not self.main_page:
            return self.book_infor

        soup = BeautifulSoup(self.main_page, "lxml")

        self.book_infor.title = parse_html_text(self.main_page, "h1")
        self.book_infor.author = parse_html_text(self.main_page, "div.mb-6 > a.text-gray-500")
        self.book_infor.book_id = self.parse_book_id()
        self.book_infor.description = self.parse_book_description(soup)
        self.book_infor.tags = self.parse_book_tags(soup)
        self.book_infor.cover = self.parse_cover(soup)
        self.book_infor.chapter_list = await self.get_chapters_urls()
        # await ClientSession().__aexit__(None, None, None)
        return self.book_infor

    def parse_cover(self, soup: BeautifulSoup) -> str:
        """
        Lấy URL ảnh bìa sách.
        """
        cover_tag = soup.select_one("div.mb-3 > a > img.w-44")
        return cover_tag["src"].replace('300.jpg', 'default.jpg') if cover_tag else ""
    
    def parse_book_description(self, soup: BeautifulSoup) -> str:
        """
        Lấy mô tả sách.
        """
        desc_tag = soup.select_one("div.text-gray-600.break-words")
        raw_text = desc_tag.decode_contents()
        result = [smart_punctuation(line.strip()) for line in re.split(r"<br\s*/?>", raw_text) if line.strip()]
        return "\n".join(result).strip()

    def parse_book_tags(self, soup: BeautifulSoup) -> List[str]:
        """
        Lấy danh sách thẻ từ HTML.
        """
        tags = soup.select("div.leading-10.md\\:leading-normal.space-x-4 > a > .text-xs")
        return [tag.text.strip() for tag in tags]

    def parse_book_id(self) -> int:
        """
        Lấy book_id từ script JSON trong HTML.
        """
        soup = BeautifulSoup(self.main_page, "html.parser")
        for script in soup.find_all("script"):
            if script.string and "window.bookData" in script.string:
                json_str = clean_json_string(script.string)
                try:
                    json_data = json.loads(json_str)
                    print(json_data)
                    return json_data.get("book", {}).get("id", 0)
                except json.JSONDecodeError:
                    return 0
        return 0

    async def get_chapters_urls(self) -> List[Chapter]:
        """
        Lấy danh sách chương truyện bằng API.
        """
        url = f"{self.BASE_URL}chapters?filter%5Bbook_id%5D={self.book_infor.book_id}"
        print(f"Fetching chapters from {url}")

        try:
            async with self.client.get(url) as response:
                response.raise_for_status()
                json_data = await response.json()
                return [
                    Chapter(
                        name=chap.get("name", "").strip(),
                        index=chap.get("index", 0),
                        is_locked=chap.get("is_locked", False),
                        chap_url=f"{self.url}/chuong-{chap.get('index', 0)}"
                    )
                    for chap in json_data.get("data", [])
                ]
        except Exception as e:
            print(f"❌ Error fetching chapters: {e}")
            return []

    async def fetch_content(self, chapter):
        """
        Fetch nội dung chương (async).
        """
        for _ in range(3):
            try:
                async with self.client.get(chapter.chap_url) as resp:
                    return parse_chapter_content(await resp.text())
            except Exception:
                await asyncio.sleep(2)
        return chapter.name, ""

    async def get_book_content(self, max_concurrent_tasks=10):
        """
        Tải nội dung tất cả các chương (async) với giới hạn nhiệm vụ đồng thời 
        và đảm bảo thứ tự các chương.
        
        Args:
            max_concurrent_tasks (int): Số lượng tác vụ tải xuống tối đa đồng thời.
        
        Returns:
            list: Nội dung các chương đã tải theo đúng thứ tự ban đầu.
        """
        try:
            chapter_list = await self.get_chapters_urls()
            
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
            
            for future in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading Chapters"):
                index, result = await future
                if result is not None:
                    results[index] = result
            
            # Loại bỏ các chapter không tải được (nếu có)
            return [chapter for chapter in results if chapter is not None]
        
        except Exception as e:
            logging.error(f"Critical error in book content download: {e}")
            return []
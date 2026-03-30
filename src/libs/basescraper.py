from abc import ABC, abstractmethod
from typing import Callable, Optional

class BaseClient(ABC):
    """Lớp cơ sở cho tất cả các Scraper."""
    
    def __init__(self, url: str):
        self.url = url
    
    @abstractmethod
    async def parse_book_info(self):
        """Lấy thông tin sách (title, author, tags, description, cover, chapters)"""
        pass

    @abstractmethod
    async def get_book_content(self, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Lấy nội dung toàn bộ chương"""
        pass
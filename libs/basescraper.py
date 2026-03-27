from abc import ABC, abstractmethod

class BaseClient(ABC):
    """Lớp cơ sở cho tất cả các Scraper."""
    
    def __init__(self, url: str):
        self.url = url
    
    @abstractmethod
    async def parse_book_info(self):
        """Lấy thông tin sách (title, author, tags, description, cover, chapters)"""
        pass

    @abstractmethod
    async def get_book_content(self):
        """Lấy nội dung toàn bộ chương"""
        pass
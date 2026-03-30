from dataclasses import dataclass
from typing import Optional

@dataclass
class Chapter:
    name: str = ""
    index: int = ""
    is_locked: Optional[bool] = False
    chap_url: str = ""
    
@dataclass
class BookInfor:
    title: str = ""
    author: str = ""
    book_id: int = 0
    description: str = ""
    cover: str = ""
    tags: list = None
    publisher: str = "Black Wolf"
    chapter_list: list = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.chapter_list is None:
            self.chapter_list = []
            
    def __str__(self):
        return (
            f"📖 Title: {self.title}\n"
            f"✍️ Author: {self.author}\n"
            f"🆔 Book ID: {self.book_id}\n"
            f"📝 Description: {self.description}\n"
            f"🖼️ Cover: {self.cover}\n"
            f"🏷️ Tags: {', '.join(self.tags) if self.tags else 'None'}\n"
            f"🏢 Publisher: {self.publisher}\n"
        )
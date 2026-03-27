

from .ttv import TtvClient
from .mtc import MtcClient
from .lib_types import BaseClient

async def process_scraper(url):
    """Xử lý scraper dựa trên URL"""
    scraper = BaseClient(url)

    # Dùng `async with` nếu scraper cần
    if hasattr(scraper, "__aenter__"):
        async with scraper:
            book_infor = await scraper.parse_book_infor()
            book_content = await scraper.get_book_content()
    else:
        book_infor = await scraper.parse_book_infor()
        book_content = await scraper.get_book_content()
    
    return(book_infor,book_content)
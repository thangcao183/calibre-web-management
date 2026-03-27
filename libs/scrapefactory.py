import re
from .ttv import TtvClient
from .mtc import MtcClient
from .ttc import TtcClient

class ScraperFactory:
    """Factory để chọn Scraper phù hợp dựa trên URL"""
    SCRAPER_MAPPING = {
        r"tangthuvien": TtvClient,
        r"metruyen": MtcClient,
        r"tiemtruyen": TtcClient
    }

    @staticmethod
    def get_scraper(url):
        for pattern, scraper in ScraperFactory.SCRAPER_MAPPING.items():
            if re.search(pattern, url):
                return scraper(url)
        raise ValueError(f"Không tìm thấy Scraper phù hợp cho {url}")

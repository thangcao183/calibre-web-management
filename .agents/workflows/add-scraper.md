---
description: How to add a new scraper for a novel website
---

# Add New Scraper

## Steps

1. Create a new file in `src/libs/` (e.g., `new_site.py`)

2. Inherit from `BaseScraper` in `src/libs/basescraper.py`
```python
from .basescraper import BaseScraper

class NewSiteScraper(BaseScraper):
    async def parse_book_info(self):
        # Return a BookInfor object
        pass
    
    async def get_book_content(self):
        # Return list of {"title": str, "content": str}
        pass
```

3. Register in `src/libs/scrapefactory.py`
```python
from .new_site import NewSiteScraper

class ScraperFactory:
    @staticmethod
    def get_scraper(url):
        if "newsite.com" in url:
            return NewSiteScraper(url)
        # ... existing scrapers
```

4. Test by downloading a book from the new site via the dashboard UI

## Data Types

- `BookInfor` defined in `src/libs/lib_types.py`
- Required fields: `book_id`, `title`, `author`, `cover` (URL), `description`, `publisher`, `tags`
- Chapter format: `{"title": "Chapter 1", "content": "<p>HTML content</p>"}`

## Notes
- All scrapers use async/await with aiohttp
- Cover images are auto-upscaled by Real-ESRGAN
- Downloaded books are saved as EPUB only, then auto-added to Calibre

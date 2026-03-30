import os
import asyncio
import traceback
from pathlib import Path
from typing import Optional
from libs.scrapefactory import ScraperFactory
from libs.book_gen import EPUBGenerator
from libs.text_proc import remove_accents_and_special_chars
from libs.kobo_device import kobo_server

class ScraperTask:
    def __init__(self, url):
        self.url = url
        self.ebook_dir = Path(kobo_server.ebook_dir)
        self.current_title: Optional[str] = None

    def _update_status(self, status, message, progress=None, error=""):
        payload = {
            "task_status": status,
            "task_message": message,
            "task_error": error,
        }
        if progress is not None:
            payload["download_progress"] = progress
        kobo_server.update_state(**payload)
        if status in {"queued", "success", "error"}:
            history_status = "info" if status == "queued" else status
            kobo_server.add_history("download", history_status, error or message)

    def _on_chapter_progress(self, completed: int, total: int):
        if total <= 0:
            return
        chapter_ratio = completed / total
        progress = 35 + int(chapter_ratio * 45)
        title = self.current_title or "book"
        self._update_status(
            "running",
            f"Downloading chapters for {title}... {completed}/{total}",
            min(progress, 80),
        )

    async def _async_run(self):
        """Logic xử lý chính (Asynchronous)."""
        try:
            self._update_status("running", "Fetching book details...", 10)

            # 1. Khởi tạo scraper phù hợp
            scraper = ScraperFactory.get_scraper(self.url)
            async with scraper as client:
                book_info = await client.parse_book_info()
                self.current_title = book_info.title
                self._update_status("running", f"Downloading chapters for {book_info.title}...", 35)
                book_content = await client.get_book_content(progress_callback=self._on_chapter_progress)
                
            # 2. Tạo file EPUB
            self._update_status("running", "Building EPUB file...", 55)
            epub_gen = EPUBGenerator(book_info, book_content)
            epub_name = remove_accents_and_special_chars(book_info.title).replace(" ", "_") + ".epub"
            epub_path = self.ebook_dir / epub_name
            
            # Lưu file EPUB
            epub_gen.generate()
            epub_gen.save(str(epub_path))
            
            # Fix EPUB (nếu cần)
            from libs.epub_fixer import fix_epub
            fix_epub(str(epub_path))
            
            # 3. Thêm vào Calibre Database
            if epub_path.exists():
                import subprocess
                calibre_library = os.path.expanduser("~/Calibre Library")
                self._update_status("running", "Adding book to Calibre...", 85)
                try:
                    subprocess.run(
                        ['calibredb', '--with-library', calibre_library, 'add', str(epub_path)],
                        check=True, capture_output=True, text=True, timeout=120
                    )
                    print(f"[Calibre] Added {epub_path.name} successfully.")
                except Exception as ce:
                    print(f"[Calibre] Failed to add: {ce}")
                    self._update_status("error", "Failed to add book to Calibre.", 0, str(ce))
                    return False, str(ce)

            self._update_status("success", f"Completed: {epub_path.name}", 100)
            kobo_server.update_state(last_downloaded_file=epub_path.name)
            
            return True, epub_path.name
            
        except Exception as e:
            print(f"[Scraper] Task error: {e}")
            traceback.print_exc()
            self._update_status("error", "Download task failed.", 0, str(e))
            return False, str(e)

    def run(self):
        """Hàm wrapper để chạy trong một Thread riêng (Synchronous)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success, result = loop.run_until_complete(self._async_run())
            return success, result
        finally:
            loop.close()

import os
import asyncio
import traceback
from pathlib import Path
from libs.scrapefactory import ScraperFactory
from libs.book_gen import EPUBGenerator
from libs.text_proc import remove_accents_and_special_chars
from libs.kobo_device import kobo_server

class ScraperTask:
    def __init__(self, url, add_to_calibre=False):
        self.url = url
        self.add_to_calibre = add_to_calibre
        self.ebook_dir = Path(kobo_server.ebook_dir)

    def _update_status(self, status, message, progress=None, error=""):
        kobo_server.state["task_status"] = status
        kobo_server.state["task_message"] = message
        kobo_server.state["task_error"] = error
        if progress is not None:
            kobo_server.state["download_progress"] = progress
        if status in {"queued", "success", "error"}:
            history_status = "info" if status == "queued" else status
            kobo_server.add_history("download", history_status, error or message)

    async def _async_run(self):
        """Logic xử lý chính (Asynchronous)."""
        try:
            self._update_status("running", "Fetching book details...", 10)

            # 1. Khởi tạo scraper phù hợp
            scraper = ScraperFactory.get_scraper(self.url)
            async with scraper as client:
                book_info = await client.parse_book_info()
                self._update_status("running", f"Downloading chapters for {book_info.title}...", 35)
                book_content = await client.get_book_content()
                
            # 2. Tạo file EPUB
            self._update_status("running", "Building EPUB file...", 55)
            epub_gen = EPUBGenerator(book_info, book_content)
            raw_epub_name = remove_accents_and_special_chars(book_info.title).replace(" ", "_") + ".epub"
            raw_epub_path = self.ebook_dir / raw_epub_name
            
            # Lưu file EPUB tạm
            epub_gen.generate()
            epub_gen.save(str(raw_epub_path))
            
            # Fix EPUB (nếu cần)
            from libs.epub_fixer import fix_epub
            fix_epub(str(raw_epub_path))
            
            # 3. Chuyển đổi sang KePub (nếu có thể)
            self._update_status("running", "Converting to KEPUB...", 75)
            kepub_name = raw_epub_name.replace(".epub", ".kepub.epub")
            kepub_path = self.ebook_dir / kepub_name
            
            success_kepub = False
            import kepubify
            try:
                kepubify.convert_to_kepub(str(raw_epub_path), str(kepub_path))
                if os.path.exists(kepub_path):
                    success_kepub = True
                    # Xóa file epub tạm nếu convert thành công
                    if raw_epub_path.exists(): raw_epub_path.unlink()
            except Exception as e:
                print(f"[Scraper] KePub convert failed: {e}")
                # Fallback: dùng chính file epub nhưng đổi tên thành .kepub.epub (lazy kepub)
                os.rename(raw_epub_path, kepub_path)
                success_kepub = True

            final_path = kepub_path if success_kepub else raw_epub_path
            
            # 4. Thêm vào Calibre Database
            if self.add_to_calibre and final_path.exists():
                import subprocess
                self._update_status("running", "Adding book to Calibre...", 90)
                try:
                    subprocess.run(['calibredb', 'add', str(final_path)], check=True)
                    print(f"[Calibre] Added {final_path.name} successfully.")
                except Exception as ce:
                    print(f"[Calibre] Failed to add: {ce}")
                    self._update_status("error", "Failed to add book to Calibre.", 0, str(ce))
                    return False, str(ce)

            self._update_status("success", f"Completed: {final_path.name}", 100)
            kobo_server.state["last_downloaded_file"] = final_path.name
            
            return True, final_path.name
            
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

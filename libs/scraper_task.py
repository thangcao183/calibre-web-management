import os
import asyncio
import traceback
import threading
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

    async def _async_run(self):
        """Logic xử lý chính (Asynchronous)."""
        try:
            # 1. Khởi tạo scraper phù hợp
            scraper = ScraperFactory.get_scraper(self.url)
            async with scraper as client:
                book_info = await client.parse_book_info()
                book_content = await client.get_book_content()
                
            # 2. Tạo file EPUB
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
                try:
                    subprocess.run(['calibredb', 'add', str(final_path)], check=True)
                    print(f"[Calibre] Added {final_path.name} successfully.")
                except Exception as ce:
                    print(f"[Calibre] Failed to add: {ce}")
            
            return True, final_path.name
            
        except Exception as e:
            print(f"[Scraper] Task error: {e}")
            traceback.print_exc()
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

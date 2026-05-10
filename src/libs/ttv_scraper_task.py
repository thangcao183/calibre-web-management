import os
import json
import traceback
import sys
from pathlib import Path
from typing import Optional

from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_api.ttv.story import build_story_cover_url

from libs.book_gen import EPUBGenerator
from libs.text_proc import remove_accents_and_special_chars
from libs.kobo_device import kobo_server
from libs.lib_types import BookInfor

class TTVScraperTask:
    def __init__(self, id_story: str, imei: str = "21bab69a53e003ff", token_adr: str = "fcm_ttv::test"):
        self.id_story = str(id_story)
        self.imei = imei
        self.token_adr = token_adr
        self.ebook_dir = Path(kobo_server.ebook_dir)
        self.current_title: Optional[str] = None
        self.last_progress = -1

    def _resolve_calibre_library_dir(self) -> str:
        default_library = os.path.expanduser(os.getenv("CALIBRE_LIBRARY_DIR", "~/Calibre Library"))
        config_path = Path(__file__).resolve().parents[2] / "app_settings.json"

        if not config_path.exists():
            return default_library

        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = json.load(config_file) or {}
        except Exception as config_err:
            print(f"[TTVScraper] Failed to load app settings: {config_err}")
            return default_library

        configured_library = config.get("calibre_library_dir")
        if isinstance(configured_library, str) and configured_library.strip():
            return os.path.expanduser(configured_library.strip())

        return default_library

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
        
        if abs(progress - self.last_progress) < 5:
            return
        
        self.last_progress = progress
        title = self.current_title or "book"
        self._update_status(
            "running",
            f"Downloading chapters for {title}... {completed}/{total}",
            min(progress, 80),
        )

    def _run_sync(self):
        try:
            self._update_status("running", "Authenticating with TangThuVien...", 5)
            client = TTVClient(imei=self.imei, token_adr=self.token_adr)
            token_res = client.get_token()
            if token_res.get("status") != 1 or not client.token:
                raise Exception("Failed to obtain TTV token.")
            
            self._update_status("running", "Fetching book details...", 10)
            # Find story detail from get_list_story or just fallback to chapter list title
            # get_json_story is typically better but we will just use chapter list for basic info
            chapters_res = client.get_list_chapter(self.id_story)
            if chapters_res.get("status") != 1:
                raise Exception(f"Failed to fetch chapter list: {chapters_res.get('message')}")
            
            chapters_data = chapters_res.get("chapter", [])
            if not chapters_data:
                raise Exception("Story has no chapters.")

            # Attempt to extract book info
            # TTV doesn't give much in get_list_chapter except story_name maybe.
            first_chap = chapters_data[0]
            # Since get_list_chapter doesn't provide story metadata directly,
            # we can try to guess from name_id_chapter or default to something
            # If we wanted full details, we would call get_json_story, but client.py doesn't have it.
            # We will use "TangThuVien Book ID {id_story}" for title if we don't have it.
            self.current_title = f"TTV Story {self.id_story}"
            book_info = BookInfor(
                title=self.current_title,
                author="Unknown",
                book_id=int(self.id_story),
                description="",
                cover=build_story_cover_url(""),
                publisher="TangThuVien",
                tags=["TTV", "Download"]
            )

            self._update_status("running", f"Downloading chapters for {self.current_title}...", 35)
            
            book_content = []
            total_chaps = len(chapters_data)
            
            for idx, chap in enumerate(chapters_data, 1):
                chap_id = str(chap.get("id"))
                chap_title = chap.get("name_id_chapter") or f"Chapter {idx}"
                
                content_res = client.get_content_chapter(chap_id, self.id_story)
                if content_res.get("status") == 1:
                    content_list = content_res.get("content_chapter") or []
                    if content_list and isinstance(content_list[0], dict):
                        html_content = content_list[0].get("content", "")
                        # Simple format
                        html_content = html_content.replace("\n", "<br/>")
                        book_content.append({"title": chap_title, "content": f"<p>{html_content}</p>"})
                
                self._on_chapter_progress(idx, total_chaps)
                
            if not book_content:
                raise Exception("Failed to download any valid chapters.")

            # Build EPUB
            self._update_status("running", "Building EPUB file...", 55)
            try:
                epub_gen = EPUBGenerator(book_info, book_content)
                epub_name = f"TTV_{self.id_story}.epub"
                epub_path = self.ebook_dir / epub_name
                
                epub_gen.generate()
                epub_gen.save(str(epub_path))
                
                from libs.epub_fixer import fix_epub
                fix_epub(str(epub_path))
            except Exception as epub_err:
                print(f"[TTVScraper] EPUB generation failed: {epub_err}")
                traceback.print_exc()
                self._update_status("error", "Failed to generate EPUB file.", 0, str(epub_err))
                return False, str(epub_err)
            
            # Add to Calibre
            if epub_path.exists():
                import subprocess
                calibre_library = self._resolve_calibre_library_dir()
                self._update_status("running", "Adding book to Calibre...", 85)
                try:
                    subprocess.run(
                        ['calibredb', '--with-library', calibre_library, 'add', str(epub_path)],
                        check=True, capture_output=True, text=True, timeout=60
                    )
                    print(f"[Calibre] Added {epub_path.name} successfully.")
                except subprocess.TimeoutExpired:
                    self._update_status("warning", f"Added to Calibre but timeout: {epub_path.name}", 95)
                except Exception as ce:
                    self._update_status("error", "Failed to add book to Calibre.", 0, str(ce))
                    return False, str(ce)

            self._update_status("success", f"Completed TTV Download: {epub_path.name}", 100)
            kobo_server.update_state(last_downloaded_file=epub_path.name)
            
            return True, epub_path.name

        except Exception as e:
            print(f"[TTVScraper] Task error: {e}")
            traceback.print_exc()
            self._update_status("error", "TTV Download task failed.", 0, str(e))
            return False, str(e)

    def run(self):
        return self._run_sync()

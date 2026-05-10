import os
import json
import traceback
import sys
from pathlib import Path
from typing import Optional

from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_api.ttv.story import build_story_cover_url

from libs.book_gen import EPUBGenerator
from libs.text_proc import remove_accents_and_special_chars, smart_punctuation
from libs.kobo_device import kobo_server
from libs.lib_types import BookInfor

class TTVScraperTask:
    def __init__(self, id_story: str, title: Optional[str] = None, author: Optional[str] = None, cover_url: Optional[str] = None, description: str = "", tags: list = None, imei: str = "21bab69a53e003ff", token_adr: str = "fcm_ttv::test"):
        self.id_story = str(id_story)
        self.title = title
        self.author = author
        self.cover_url = cover_url
        self.description = description
        self.tags = (tags or []) + ["TTV"]
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
            self.current_title = self.title or f"TTV Story {self.id_story}"
            # Format description like ttv.pypy
            formatted_desc = "\n".join([
                f"<p>{smart_punctuation(line.strip())}</p>"
                for line in self.description.split("\n")
                if line.strip()
            ])

            book_info = BookInfor(
                title=self.current_title,
                author=self.author or "Unknown",
                book_id=int(self.id_story),
                description=formatted_desc,
                cover=self.cover_url or build_story_cover_url(""),
                publisher="TangThuVien",
                tags=self.tags
            )

            self._update_status("running", f"Downloading chapters for {self.current_title}...", 35)
            
            book_content = []
            total_chaps = len(chapters_data)
            
            for idx, chap in enumerate(chapters_data, 1):
                chap_id = str(chap.get("id"))
                
                name_id = chap.get("name_id_chapter") or ""
                content_title = chap.get("content_title_of_chapter") or ""
                chap_title = f"{name_id}: {content_title}".strip(": ") if name_id or content_title else f"Chapter {idx}"
                
                content_res = client.get_content_chapter(chap_id, self.id_story)
                if content_res.get("status") == 1:
                    content_list = content_res.get("content_chapter") or []
                    if content_list and isinstance(content_list[0], dict):
                        html_content = content_list[0].get("content", "")
                        
                        # Format paragraphs like ttv.pypy
                        lines = [line.strip() for line in html_content.split("\n") if line.strip()]
                        formatted_content = ""
                        for i, line in enumerate(lines):
                            p_text = smart_punctuation(line)
                            if i == 0:
                                formatted_content += f'<p class="line-0">{p_text}</p>\n'
                            else:
                                formatted_content += f'<p>{p_text}</p>\n'
                                
                        book_content.append({"title": chap_title, "content": formatted_content})
                
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

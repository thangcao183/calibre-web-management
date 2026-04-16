import os
import dataclasses
from pathlib import Path
import requests
from ebooklib import epub
from typing import List, Dict, Optional, Union
from .cover_upscale import upscale_with_realesrgan, load_image
from .lib_types import BookInfor
import re

def split_chapter_names(chapter_name:str):
    """
    Purpose: To split the chapter name into title and subtitle
    """
    title = chapter_name
    splitted = re.split(r'[:\-]', title)  # Tách bằng dấu `:` hoặc `-`
    return (splitted[0].strip() ,splitted[-1].strip())
    
# end def


class EPUBGenerator:
    def __init__(
        self,
        book_info: BookInfor,
        chapters: List[Dict[str, str]],
        fonts_folder: str = "fonts",
        style_folder: str = "styles",
    ):
        """
        Initialize EPUB Generator with book information and chapters.

        :param book_info: BookInfo dataclass containing book metadata
        :param chapters: List of chapter dictionaries with 'title' and 'content' keys
        :param fonts_folder: Path to folder containing font files
        :param css_content: Custom CSS content (optional)
        """
        current_dir = Path(__file__).resolve().parent
        self.book_info = book_info
        self.chapters = chapters
        self.fonts_folder = current_dir / fonts_folder
        self.style_folder = current_dir / style_folder
        self.book = None

    # def _load_cover(self) -> Optional[tuple]:
    #     """
    #     Load cover image from URL or local file.

    #     :return: Tuple of (cover_data, cover_extension) or None
    #     """
    #     if not self.book_info.cover:
    #         return None

    #     try:
    #         # Try to download or load cover
    #         if self.book_info.cover.startswith(("http://", "https://")):
    #             response = requests.get(self.book_info.cover)
    #             cover_data = upscale_with_realesrgan(response.content)
    #             cover_ext = "jpg"
    #         else:
    #             # Assume it's a local file path
    #             with open(self.book_info.cover, "rb") as f:
    #                 cover_data = f.read()
    #             cover_ext = os.path.splitext(self.book_info.cover)[1][1:] or "jpg"

    #         return cover_data, cover_ext
    #     except Exception as e:
    #         print(f"Error processing cover: {e}")
    #         return None

    def _add_fonts(self):
        """
        Add fonts from the specified folder to the EPUB.
        """
        if not os.path.exists(self.fonts_folder):
            return []

        font_items = []
        for font_file in os.listdir(self.fonts_folder):
            font_path = os.path.join(self.fonts_folder, font_file)
            if os.path.isfile(font_path):
                font = epub.EpubItem(
                    uid=f"font_{font_file}",
                    file_name=f"fonts/{font_file}",
                    media_type=f"font/{os.path.splitext(font_file)[1][1:]}",
                    content=open(font_path, "rb").read(),
                )
                self.book.add_item(font)
                font_items.append(font)

        return font_items

    def _create_css(self):
        """
        Load CSS files for the EPUB.

        :return: List of CSS EpubItems
        """
        css_items = []
        css_files = [
            "fonts.css",
            "style.css",
        ]  # List of CSS files to include

        for css_file in css_files:
            css_path = self.style_folder / css_file
            if Path.exists(css_path):
                with open(css_path, "r", encoding="utf-8") as f:
                    css_content = f.read()
                    css_item = epub.EpubItem(
                        uid=f"style_{os.path.basename(css_file)}",
                        file_name=css_file,
                        media_type="text/css",
                        content=css_content.encode("utf-8"),
                    )
                    self.book.add_item(css_item)
                    css_items.append(css_item)
            else:
                print(f"Warning: CSS file {css_file} not found.")

        return css_items

    def _create_cover_page(self, css_items):
        """
        Create cover page with book metadata.

        :param css: CSS EpubItem
        :return: Cover page as EpubHtml
        """
        cover_page = epub.EpubHtml(
            title="Cover Page", file_name="cover_page.xhtml", lang="vi"
        )
        cover_page.content = f"""
        <body>
            <div class="book-metadata">
                <h1 class="chapter">{self.book_info.title}</h1>
                <p>Author: {self.book_info.author}</p>
                <p>Publisher: {self.book_info.publisher}</p>
                {f'<p>Tags: {", ".join(self.book_info.tags)}</p>' if self.book_info.tags else ''}
            </div>
            {"<div class='book-description'>" + self.book_info.description + "</div>" if self.book_info.description else ''}
        </body>
        """
        self.book.add_item(cover_page)
        for css in css_items:
            cover_page.add_item(css)
        return cover_page

    def _create_chapters(self, css_items, cover_page):
        """
        Create chapters for the EPUB.

        :param css: CSS EpubItem
        :param cover_page: Cover page EpubHtml
        :return: List of chapter EpubHtml items
        """
        chapters_list = [cover_page]  # Start with cover page
        for idx, chapter_data in enumerate(self.chapters, 1):
            chapter = epub.EpubHtml(
                title=chapter_data["title"], file_name=f"chapter_{idx}.xhtml", lang="vi"
            )
            c_name, c_title = split_chapter_names(chapter_data["title"])
            chapter.content = f"""
            <body>
                <div class="chapter-header">
                <div class="chap-label">{c_name}</div>
                <h2 class="chap-name">{c_title}</h2>
                </div>
                {chapter_data['content']}
            </body>
            """
            for css in css_items:
                chapter.add_item(css)
            self.book.add_item(chapter)
            chapters_list.append(chapter)

        return chapters_list

    def generate(self) -> bytes:
        """
        Generate EPUB file.

        :return: EPUB file as bytes
        """
        # Create EPUB book
        self.book = epub.EpubBook()

        # Set book metadata
        self.book.set_identifier(str(self.book_info.book_id))
        self.book.set_title(self.book_info.title)
        self.book.set_language("vi")
        self.book.add_author(self.book_info.author)
        self.book.add_metadata("DC", "description", self.book_info.description)
        self.book.add_metadata("DC", "publisher", self.book_info.publisher)
        for tag in self.book_info.tags:
            self.book.add_metadata("DC", "subject", tag)

        # Handle cover image
        # cover_data = load_image(self.book_info.cover)
        if not hasattr(self, "_cached_cover"):
            self._cached_cover = upscale_with_realesrgan(self.book_info.cover)
        cover = self._cached_cover
        if cover:
            self.book.set_cover(f"cover.jpg", cover)

        # Add fonts
        self._add_fonts()

        # Create CSS
        css_items = self._create_css()

        # Create cover page
        cover_page = self._create_cover_page(css_items)

        # Create chapters
        chapters_list = self._create_chapters(css_items, cover_page)

        # Create Table of Contents
        self.book.toc = tuple(chapters_list)

        # Add default NCX and Nav file
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        # Basic spine
        self.book.spine = ["nav"] + chapters_list

        # Write EPUB to bytes
        from io import BytesIO

        buffer = BytesIO()
        for item in self.book.items:
            # Ensure content is raw bytes
            if isinstance(item.get_content(), BytesIO):
                item.content = item.get_content().getvalue()

        epub.write_epub(buffer, self.book, {})
        return buffer.getvalue()

    def save(self, output_path: str = "output.epub"):
        """
        Save generated EPUB to a file.

        :param output_path: Path to save the EPUB file
        """
        epub_bytes = self.generate()
        with open(output_path, "wb") as f:
            f.write(epub_bytes)

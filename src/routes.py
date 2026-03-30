import os
import sqlite3
import json
import time
import tempfile
import subprocess
import threading
from collections import deque
from flask import Blueprint, jsonify, request, send_file, Response, session, render_template
from werkzeug.utils import secure_filename
from PIL import Image
from libs.kobo_device import kobo_server
from libs.scraper_task import ScraperTask
from libs.text_proc import remove_accents_and_special_chars

# --- Configuration ---
CALIBRE_LIBRARY_DIR = os.path.expanduser("~/Calibre Library")

api_bp = Blueprint('api', __name__, url_prefix='/api')
reader_bp = Blueprint('reader', __name__, url_prefix='/reader')

ALLOWED_UPLOAD_EXTENSIONS = {'.epub', '.kepub', '.kepub.epub'}
CALIBRE_ADD_TIMEOUT = int(os.getenv("CALIBRE_ADD_TIMEOUT_SECONDS", "120"))
DOWNLOAD_QUEUE = deque()
DOWNLOAD_QUEUE_LOCK = threading.Lock()
DOWNLOAD_WORKER_RUNNING = False

kobo_server.update_state(download_queue_count=0, current_download_url="")

@api_bp.before_request
def check_login():
    """Bảo vệ toàn bộ API bằng session, ngoại trừ whitelist cho Kobo và Dashboard UI."""
    whitelist = ['api_calibre_cover', 'api_calibre_epub', 'api_status_stream']
    if request.endpoint and any(request.endpoint.endswith(e) for e in whitelist):
        return
        
    if not session.get('logged_in'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

def get_db_connection():
    """Helper kết nối database Calibre ở chế độ Read-Only."""
    db_path = os.path.join(CALIBRE_LIBRARY_DIR, 'metadata.db')
    if not os.path.exists(db_path):
        return None
    return sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)

def is_allowed_upload(filename):
    """Cho phép upload EPUB và các biến thể KEPUB phổ biến."""
    if not filename:
        return False

    normalized = filename.lower()
    return any(normalized.endswith(ext) for ext in ALLOWED_UPLOAD_EXTENSIONS)

def run_calibredb_command(args):
    """Chạy calibredb với timeout và gom lỗi stdout/stderr."""
    return subprocess.run(
        ['calibredb', '--with-library', CALIBRE_LIBRARY_DIR, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=CALIBRE_ADD_TIMEOUT,
    )

def update_calibre_metadata(book_id, title=None, author=None, description=None, publisher=None, series=None, tags=None):
    args = ['set_metadata', str(book_id)]
    if title is not None:
        args.extend(['--field', f'title:{title}'])
    if author is not None:
        args.extend(['--field', f'authors:{author}'])
    if description is not None:
        args.extend(['--field', f'comments:{description}'])
    if publisher is not None:
        args.extend(['--field', f'publisher:{publisher}'])
    if series is not None:
        args.extend(['--field', f'series:{series}'])
    if tags is not None:
        args.extend(['--field', f'tags:{tags}'])
    return run_calibredb_command(args)

def normalize_book_text(text):
    return remove_accents_and_special_chars((text or "").lower())

def extract_epub_metadata(file_path):
    """Đọc metadata cơ bản từ EPUB/KEPUB để phục vụ duplicate detection."""
    try:
        from ebooklib import epub

        book = epub.read_epub(file_path)
        title_items = book.get_metadata('DC', 'title')
        creator_items = book.get_metadata('DC', 'creator')

        title = title_items[0][0].strip() if title_items and title_items[0][0] else ""
        author = creator_items[0][0].strip() if creator_items and creator_items[0][0] else ""
        return {"title": title, "author": author}
    except Exception:
        return {"title": "", "author": ""}

def find_duplicate_book(title, author):
    """Tìm duplicate tiềm năng theo title/author đã chuẩn hóa."""
    normalized_title = normalize_book_text(title)
    normalized_author = normalize_book_text(author)
    if not normalized_title:
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, author_sort FROM books')
        for book_id, existing_title, existing_author in cursor.fetchall():
            if normalize_book_text(existing_title) != normalized_title:
                continue

            existing_author_norm = normalize_book_text(existing_author)
            if not normalized_author or not existing_author_norm:
                return {"id": book_id, "title": existing_title, "author": existing_author}

            if normalized_author in existing_author_norm or existing_author_norm in normalized_author:
                return {"id": book_id, "title": existing_title, "author": existing_author}
    finally:
        conn.close()

    return None

def get_book_folder_path(book_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT path FROM books WHERE id = ?', (book_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return os.path.join(CALIBRE_LIBRARY_DIR, row[0])
    finally:
        conn.close()

# --- Library Endpoints ---

@api_bp.route('/calibre_books')
def api_calibre_books():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 24, type=int)
    search = request.args.get('search', '').strip().lower()
    fmt_filter = request.args.get('format', '').strip().lower()
    
    offset = (page - 1) * limit

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Calibre library not found"})
    
    try:
        cursor = conn.cursor()
        
        # Base query parts
        where_clauses = []
        params = []
        
        if search:
            where_clauses.append("(LOWER(b.title) LIKE ? OR LOWER(b.author_sort) LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])
        
        if fmt_filter:
            where_clauses.append("EXISTS (SELECT 1 FROM data d2 WHERE d2.book = b.id AND LOWER(d2.format) = ?)")
            params.append(fmt_filter.upper())

        where_stmt = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total filtered books
        count_query = f"SELECT COUNT(*) FROM books b {where_stmt}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Fetch page of books
        query = f'''
            SELECT
                b.id,
                b.title,
                b.author_sort,
                b.path,
                b.has_cover,
                COALESCE(df.formats, '')
            FROM books b
            LEFT JOIN (
                SELECT book, GROUP_CONCAT(LOWER(format)) AS formats
                FROM data
                GROUP BY book
            ) df ON b.id = df.book
            {where_stmt}
            ORDER BY b.timestamp DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, params + [limit, offset])
        
        books = []
        for row in cursor.fetchall():
            book_id, title, author, path, has_cover, formats_raw = row
            formats = [fmt for fmt in formats_raw.split(',') if fmt]
            
            # Chỉ check cover cho các sách trong trang hiện tại (tối ưu I/O)
            cover_exists = False
            if not has_cover:
                cover_exists = os.path.exists(os.path.join(CALIBRE_LIBRARY_DIR, path, 'cover.jpg'))

            books.append({
                "id": book_id,
                "title": title,
                "author": author,
                "has_cover": bool(has_cover) or cover_exists,
                "formats": formats
            })
            
        return jsonify({
            "success": True, 
            "books": books, 
            "total_count": total_count,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        conn.close()

@api_bp.route('/calibre/book/<int:book_id>')
def api_calibre_book_detail(book_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Calibre library not found"}), 404

    try:
        cursor = conn.cursor()
        query = '''
            SELECT
                b.id,
                b.title,
                b.author_sort,
                b.path,
                b.has_cover,
                c.text,
                COALESCE(df.formats, ''),
                COALESCE(p.name, ''),
                COALESCE(s.name, ''),
                COALESCE(tf.tags, '')
            FROM books b
            LEFT JOIN comments c ON b.id = c.book
            LEFT JOIN books_publishers_link bpl ON b.id = bpl.book
            LEFT JOIN publishers p ON bpl.publisher = p.id
            LEFT JOIN books_series_link bsl ON b.id = bsl.book
            LEFT JOIN series s ON bsl.series = s.id
            LEFT JOIN (
                SELECT book, GROUP_CONCAT(LOWER(format)) AS formats
                FROM data
                GROUP BY book
            ) df ON b.id = df.book
            LEFT JOIN (
                SELECT btl.book, GROUP_CONCAT(t.name, ', ') AS tags
                FROM books_tags_link btl
                JOIN tags t ON btl.tag = t.id
                GROUP BY btl.book
            ) tf ON b.id = tf.book
            WHERE b.id = ?
            LIMIT 1
        '''
        cursor.execute(query, (book_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Book not found"}), 404

        book_id, title, author, path, has_cover, desc, formats_raw, publisher, series, tags_raw = row
        formats = [fmt for fmt in formats_raw.split(',') if fmt]
        tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]
        cover_exists = os.path.exists(os.path.join(CALIBRE_LIBRARY_DIR, path, 'cover.jpg'))

        return jsonify({
            "success": True,
            "book": {
                "id": book_id,
                "title": title,
                "author": author,
                "path": path,
                "has_cover": bool(has_cover) or cover_exists,
                "formats": formats,
                "description": desc or "",
                "publisher": publisher or "",
                "series": series or "",
                "tags": tags
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@api_bp.route('/calibre/cover/<int:book_id>')
def api_calibre_cover(book_id):
    book_folder = get_book_folder_path(book_id)
    if not book_folder:
        return "Not found", 404
    try:
        cover_path = os.path.join(book_folder, 'cover.jpg')
        if os.path.exists(cover_path):
            return send_file(cover_path, mimetype='image/jpeg')
    except: pass
    return "Not found", 404

@api_bp.route('/calibre/epub/<int:book_id>')
def api_calibre_epub(book_id):
    conn = get_db_connection()
    if not conn: return "Not found", 404
    try:
        cursor = conn.cursor()
        query = 'SELECT b.path, d.name FROM books b JOIN data d ON b.id = d.book WHERE b.id = ? AND d.format = "EPUB"'
        cursor.execute(query, (book_id,))
        row = cursor.fetchone()
        if row:
            epub_path = os.path.join(CALIBRE_LIBRARY_DIR, row[0], f"{row[1]}.epub")
            if os.path.exists(epub_path):
                return send_file(epub_path, mimetype='application/epub+zip')
    except: pass
    finally: conn.close()
    return "Not found", 404

# --- Sync & Action Endpoints ---

@api_bp.route('/sync_calibre', methods=['POST'])
def api_sync_calibre():
    data = request.json or {}
    book_id = data.get("book_id")
    convert = data.get("convert_kepub", False)
    
    if not book_id: return jsonify({"success": False, "error": "Missing book_id"})
    if not kobo_server.client_socket: return jsonify({"success": False, "error": "Kobo not connected"})

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT path FROM books WHERE id = ?', (book_id,))
        b_row = cursor.fetchone()
        if not b_row: return jsonify({"success": False, "error": "Book not found"})
        
        book_rel_path = b_row[0]
        cursor.execute('SELECT format, name FROM data WHERE book = ?', (book_id,))
        formats = {fmt: name for fmt, name in cursor.fetchall()}
        
        source_path = None
        target_name = None

        if convert:
            if 'KEPUB' in formats:
                target_name = f"{formats['KEPUB']}.kepub"
                source_path = os.path.join(CALIBRE_LIBRARY_DIR, book_rel_path, target_name)
            elif 'EPUB' in formats:
                epub_path = os.path.join(CALIBRE_LIBRARY_DIR, book_rel_path, f"{formats['EPUB']}.epub")
                target_name = f"tmp_{book_id}.kepub.epub"
                source_path = os.path.join(kobo_server.ebook_dir, target_name)
                import kepubify
                kepubify.convert_to_kepub(epub_path, source_path)
        else:
            fmt = 'EPUB' if 'EPUB' in formats else 'KEPUB' if 'KEPUB' in formats else None
            if fmt:
                target_name = f"{formats[fmt]}.{fmt.lower()}"
                source_path = os.path.join(CALIBRE_LIBRARY_DIR, book_rel_path, target_name)

        if not source_path or not os.path.exists(source_path):
            return jsonify({"success": False, "error": "File not found on disk"})

        # Copy ra thư mục sync
        final_filename = f"calibre_{book_id}_{target_name}"
        final_path = os.path.join(kobo_server.ebook_dir, final_filename)
        
        import shutil
        if source_path != final_path:
            shutil.copy2(source_path, final_path)
            
        kobo_server.books_to_sync.append(final_filename)
        kobo_server.add_history("sync", "success", f"Queued {final_filename} for Kobo sync")
        return jsonify({"success": True})
    except Exception as e:
        kobo_server.add_history("sync", "error", str(e))
        return jsonify({"success": False, "error": str(e)})
    finally:
        if conn: conn.close()

@api_bp.route('/calibre_delete', methods=['POST'])
def api_calibre_delete():
    book_id = (request.json or {}).get("book_id")
    if not book_id: return jsonify({"success": False, "error": "Missing ID"})
    try:
        run_calibredb_command(['remove', str(book_id)])
        kobo_server.add_history("delete", "success", f"Deleted book ID {book_id}")
        return jsonify({"success": True})
    except subprocess.TimeoutExpired:
        kobo_server.add_history("delete", "error", "Calibre remove timed out")
        return jsonify({"success": False, "error": "Calibre remove timed out"}), 504
    except subprocess.CalledProcessError as e:
        error = (e.stderr or e.stdout or str(e)).strip()
        kobo_server.add_history("delete", "error", error)
        return jsonify({"success": False, "error": error}), 500
    except Exception as e:
        kobo_server.add_history("delete", "error", str(e))
        return jsonify({"success": False, "error": str(e)})

@api_bp.route('/calibre_bulk_delete', methods=['POST'])
def api_calibre_bulk_delete():
    ids = (request.json or {}).get("book_ids", [])
    if not ids: return jsonify({"success": False, "error": "No IDs"})
    try:
        run_calibredb_command(['remove', ",".join(map(str, ids))])
        kobo_server.add_history("delete", "success", f"Bulk deleted {len(ids)} books")
        return jsonify({"success": True, "count": len(ids)})
    except subprocess.TimeoutExpired:
        kobo_server.add_history("delete", "error", "Calibre bulk remove timed out")
        return jsonify({"success": False, "error": "Calibre bulk remove timed out"}), 504
    except subprocess.CalledProcessError as e:
        error = (e.stderr or e.stdout or str(e)).strip()
        kobo_server.add_history("delete", "error", error)
        return jsonify({"success": False, "error": error}), 500
    except Exception as e:
        kobo_server.add_history("delete", "error", str(e))
        return jsonify({"success": False, "error": str(e)})

@api_bp.route('/calibre_update_metadata', methods=['POST'])
def api_calibre_update_metadata():
    data = request.json or {}
    book_id = data.get("book_id")
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    publisher = (data.get("publisher") or "").strip()
    series = (data.get("series") or "").strip()
    tags = data.get("tags") or []
    clear_publisher = bool(data.get("clear_publisher"))
    clear_series = bool(data.get("clear_series"))
    clear_tags = bool(data.get("clear_tags"))
    clear_description = bool(data.get("clear_description"))

    if not book_id:
        return jsonify({"success": False, "error": "Missing book_id"}), 400
    if not title:
        return jsonify({"success": False, "error": "Title is required"}), 400

    tags_value = ",".join(tag.strip() for tag in tags if isinstance(tag, str) and tag.strip())

    try:
        update_calibre_metadata(
            book_id,
            title=title,
            author=author,
            description="" if clear_description else description,
            publisher="" if clear_publisher else publisher,
            series="" if clear_series else series,
            tags="" if clear_tags else tags_value
        )
        kobo_server.add_history("metadata", "success", f"Updated metadata for book ID {book_id}")
        return jsonify({"success": True})
    except subprocess.TimeoutExpired:
        kobo_server.add_history("metadata", "error", "Metadata update timed out")
        return jsonify({"success": False, "error": "Metadata update timed out"}), 504
    except subprocess.CalledProcessError as e:
        error = (e.stderr or e.stdout or str(e)).strip()
        kobo_server.add_history("metadata", "error", error)
        return jsonify({"success": False, "error": error}), 500
    except Exception as e:
        kobo_server.add_history("metadata", "error", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/calibre_bulk_update_metadata', methods=['POST'])
def api_calibre_bulk_update_metadata():
    data = request.json or {}
    book_ids = data.get("book_ids") or []
    author = data.get("author")
    publisher = data.get("publisher")
    series = data.get("series")
    tags = data.get("tags") or []
    description = data.get("description")
    clear_publisher = bool(data.get("clear_publisher"))
    clear_series = bool(data.get("clear_series"))
    clear_tags = bool(data.get("clear_tags"))
    clear_description = bool(data.get("clear_description"))

    if not book_ids:
        return jsonify({"success": False, "error": "No book IDs provided"}), 400

    author = author.strip() if isinstance(author, str) else None
    publisher = publisher.strip() if isinstance(publisher, str) else None
    series = series.strip() if isinstance(series, str) else None
    description = description.strip() if isinstance(description, str) else None
    tags_value = ",".join(tag.strip() for tag in tags if isinstance(tag, str) and tag.strip())

    if not author and not publisher and not series and not tags_value and not description and not clear_publisher and not clear_series and not clear_tags and not clear_description:
        return jsonify({"success": False, "error": "Nothing to update"}), 400

    updated = 0
    errors = []

    for book_id in book_ids:
        try:
            update_calibre_metadata(
                book_id,
                author=author if author else None,
                publisher="" if clear_publisher else (publisher if publisher else None),
                series="" if clear_series else (series if series else None),
                tags="" if clear_tags else (tags_value if tags_value else None),
                description="" if clear_description else (description if description else None)
            )
            updated += 1
        except subprocess.TimeoutExpired:
            errors.append(f"Book {book_id}: metadata update timed out")
        except subprocess.CalledProcessError as e:
            error = (e.stderr or e.stdout or str(e)).strip()
            errors.append(f"Book {book_id}: {error}")
        except Exception as e:
            errors.append(f"Book {book_id}: {str(e)}")

    if updated > 0:
        kobo_server.add_history("metadata", "success", f"Bulk updated metadata for {updated} book(s)")
    if errors:
        kobo_server.add_history("metadata", "error", errors[0])

    return jsonify({
        "success": updated > 0,
        "count": updated,
        "errors": errors
    }), (200 if updated > 0 else 500)

@api_bp.route('/upload', methods=['POST'])
def api_upload():
    """Nhận file ebook từ UI và thêm trực tiếp vào Calibre."""
    uploads = [f for f in request.files.getlist('file') if f and f.filename]
    if not uploads:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    results = []
    success_count = 0

    for upload in uploads:
        if not is_allowed_upload(upload.filename):
            results.append({
                "filename": upload.filename,
                "success": False,
                "error": "Only EPUB/KEPUB files are supported"
            })
            continue

        safe_name = secure_filename(upload.filename) or "uploaded_book.epub"
        _, ext = os.path.splitext(safe_name)
        if safe_name.lower().endswith('.kepub.epub'):
            ext = '.kepub.epub'

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_path = temp_file.name
            upload.save(temp_path)

            metadata = extract_epub_metadata(temp_path)
            duplicate = find_duplicate_book(metadata["title"], metadata["author"])
            if duplicate:
                results.append({
                    "filename": upload.filename,
                    "success": False,
                    "error": f"Duplicate detected: {duplicate['title']} by {duplicate['author']} (ID {duplicate['id']})"
                })
                kobo_server.add_history("upload", "error", f"Duplicate skipped: {upload.filename}")
                continue

            run_calibredb_command(['add', temp_path])
            success_count += 1
            results.append({
                "filename": upload.filename,
                "success": True
            })
            kobo_server.add_history("upload", "success", f"Added {upload.filename} to Calibre")
        except subprocess.TimeoutExpired:
            results.append({
                "filename": upload.filename,
                "success": False,
                "error": "Calibre add timed out"
            })
            kobo_server.add_history("upload", "error", f"Upload timed out: {upload.filename}")
        except subprocess.CalledProcessError as e:
            error = (e.stderr or e.stdout or str(e)).strip()
            results.append({
                "filename": upload.filename,
                "success": False,
                "error": error
            })
            kobo_server.add_history("upload", "error", f"{upload.filename}: {error}")
        except Exception as e:
            results.append({
                "filename": upload.filename,
                "success": False,
                "error": str(e)
            })
            kobo_server.add_history("upload", "error", f"{upload.filename}: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    if success_count == 0:
        first_error = next((item["error"] for item in results if not item["success"]), "Upload failed")
        return jsonify({
            "success": False,
            "error": first_error,
            "results": results
        }), 500

    return jsonify({
        "success": True,
        "count": success_count,
        "results": results
    })

@api_bp.route('/calibre_update_cover', methods=['POST'])
def api_calibre_update_cover():
    book_id = request.form.get('book_id', type=int)
    cover_file = request.files.get('cover')

    if not book_id:
        return jsonify({"success": False, "error": "Missing book_id"}), 400
    if not cover_file or not cover_file.filename:
        return jsonify({"success": False, "error": "No cover uploaded"}), 400

    book_folder = get_book_folder_path(book_id)
    if not book_folder:
        return jsonify({"success": False, "error": "Book not found"}), 404

    cover_path = os.path.join(book_folder, 'cover.jpg')
    try:
        image = Image.open(cover_file.stream)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        elif image.mode == 'L':
            image = image.convert('RGB')
        image.save(cover_path, format='JPEG', quality=92)
        kobo_server.add_history("metadata", "success", f"Updated cover for book ID {book_id}")
        return jsonify({"success": True})
    except Exception as e:
        kobo_server.add_history("metadata", "error", f"Cover update failed for {book_id}: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# --- System Endpoints ---

@api_bp.route('/status/stream')
def api_status_stream():
    """SSE Stream để Dashboard cập nhật thời gian thực mà không cần polling."""
    def event_stream():
        last_state = None
        while True:
            current_snapshot = kobo_server.state_snapshot()
            current_state = json.dumps(current_snapshot, sort_keys=True)
            if current_state != last_state:
                yield f"data: {current_state}\n\n"
                last_state = current_state
            time.sleep(1)
    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["X-Accel-Buffering"] = "no"
    return response

@api_bp.route('/disconnect', methods=['POST'])
def api_disconnect():
    kobo_server.disconnect_trigger = True
    kobo_server.add_history("system", "info", "Disconnect requested for Kobo device")
    return jsonify({"success": True})

@api_bp.route('/toggle_auto_sync', methods=['POST'])
def api_toggle_auto_sync():
    data = request.json or {}
    auto_sync = data.get("auto_sync")

    if not isinstance(auto_sync, bool):
        return jsonify({"success": False, "error": "auto_sync must be a boolean"}), 400

    kobo_server.state["auto_sync"] = auto_sync
    kobo_server.save_settings()
    kobo_server.add_history("system", "info", f"Auto-Sync {'enabled' if auto_sync else 'disabled'}")
    return jsonify({"success": True, "auto_sync": kobo_server.state["auto_sync"]})

@api_bp.route('/download', methods=['POST'])
def api_download():
    """Tải truyện từ web và đẩy vào Calibre library."""
    data = request.json or {}
    url = data.get("url")
    if not url:
        return jsonify({"success": False, "error": "No URL"})

    def worker_loop():
        global DOWNLOAD_WORKER_RUNNING
        while True:
            with DOWNLOAD_QUEUE_LOCK:
                if not DOWNLOAD_QUEUE:
                    DOWNLOAD_WORKER_RUNNING = False
                    kobo_server.update_state(download_queue_count=0, current_download_url="")
                    if kobo_server.state_snapshot().get("task_status") not in {"running", "queued"}:
                        kobo_server.update_state(task_status="idle", task_message="", task_error="", download_progress=0)
                    return
                next_url = DOWNLOAD_QUEUE.popleft()
                remaining = len(DOWNLOAD_QUEUE)

            kobo_server.update_state(
                download_queue_count=remaining,
                current_download_url=next_url,
                task_status="queued",
                task_message=f"Starting queued download ({remaining} remaining)...",
                task_error="",
            )
            task = ScraperTask(next_url)
            task.run()

            with DOWNLOAD_QUEUE_LOCK:
                kobo_server.update_state(download_queue_count=len(DOWNLOAD_QUEUE))

    global DOWNLOAD_WORKER_RUNNING
    with DOWNLOAD_QUEUE_LOCK:
        DOWNLOAD_QUEUE.append(url)
        queue_position = len(DOWNLOAD_QUEUE)
        queue_count = len(DOWNLOAD_QUEUE)
        kobo_server.update_state(download_queue_count=queue_count)
        kobo_server.add_history("download", "info", f"Queued download ({queue_position}) for {url}")
        should_start_worker = not DOWNLOAD_WORKER_RUNNING
        if should_start_worker:
            DOWNLOAD_WORKER_RUNNING = True

    if should_start_worker:
        threading.Thread(target=worker_loop, daemon=True).start()

    return jsonify({
        "success": True,
        "message": f"Download queued at position {queue_position}",
        "queue_position": queue_position,
        "queue_count": queue_count
    })

# --- Reader Route ---
@reader_bp.route('/<int:book_id>')
def reader_view(book_id):
    if not session.get('logged_in'):
        from flask import redirect, url_for
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        return "Calibre library not found", 404

    try:
        cursor = conn.cursor()
        query = '''
            SELECT b.title
            FROM books b
            JOIN data d ON b.id = d.book
            WHERE b.id = ? AND d.format = "EPUB"
            LIMIT 1
        '''
        cursor.execute(query, (book_id,))
        row = cursor.fetchone()

        if not row:
            return "EPUB not found for this book", 404

        return render_template('reader.html', book_id=book_id, title=row[0])
    except Exception as e:
        return f"Reader error: {e}", 500
    finally:
        conn.close()

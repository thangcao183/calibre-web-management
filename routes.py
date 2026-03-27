import os
import sqlite3
import json
import time
from flask import Blueprint, jsonify, request, send_file, Response, session
from libs.kobo_device import kobo_server
from libs.scraper_task import ScraperTask

# --- Configuration ---
CALIBRE_LIBRARY_DIR = os.path.expanduser("~/Calibre Library")

api_bp = Blueprint('api', __name__, url_prefix='/api')
reader_bp = Blueprint('reader', __name__, url_prefix='/reader')

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

# --- Library Endpoints ---

@api_bp.route('/calibre_books')
def api_calibre_books():
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Calibre library not found"})
    
    try:
        cursor = conn.cursor()
        # Lấy metadata cơ bản và description (comments)
        query = '''
            SELECT b.id, b.title, b.author_sort, b.path, b.has_cover, c.text
            FROM books b
            LEFT JOIN comments c ON b.id = c.book
            ORDER BY b.timestamp DESC
        '''
        cursor.execute(query)
        books = []
        for row in cursor.fetchall():
            book_id, title, author, path, has_cover, desc = row
            
            # Lấy danh sách định dạng file hiện có
            cursor.execute('SELECT format FROM data WHERE book = ?', (book_id,))
            formats = [f[0].lower() for f in cursor.fetchall()]
            
            books.append({
                "id": book_id,
                "title": title,
                "author": author,
                "has_cover": bool(has_cover),
                "formats": formats,
                "description": desc or ""
            })
        return jsonify({"success": True, "books": books})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        conn.close()

@api_bp.route('/calibre/cover/<int:book_id>')
def api_calibre_cover(book_id):
    conn = get_db_connection()
    if not conn: return "Not found", 404
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT path FROM books WHERE id = ?', (book_id,))
        row = cursor.fetchone()
        if row:
            cover_path = os.path.join(CALIBRE_LIBRARY_DIR, row[0], 'cover.jpg')
            if os.path.exists(cover_path):
                return send_file(cover_path, mimetype='image/jpeg')
    except: pass
    finally: conn.close()
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
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        if conn: conn.close()

@api_bp.route('/calibre_delete', methods=['POST'])
def api_calibre_delete():
    book_id = (request.json or {}).get("book_id")
    if not book_id: return jsonify({"success": False, "error": "Missing ID"})
    try:
        import subprocess
        subprocess.run(['calibredb', 'remove', str(book_id)], check=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@api_bp.route('/calibre_bulk_delete', methods=['POST'])
def api_calibre_bulk_delete():
    ids = (request.json or {}).get("book_ids", [])
    if not ids: return jsonify({"success": False, "error": "No IDs"})
    try:
        import subprocess
        subprocess.run(['calibredb', 'remove', ",".join(map(str, ids))], check=True)
        return jsonify({"success": True, "count": len(ids)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- System Endpoints ---

@api_bp.route('/status/stream')
def api_status_stream():
    """SSE Stream để Dashboard cập nhật thời gian thực mà không cần polling."""
    def event_stream():
        last_state = None
        while True:
            current_state = json.dumps(kobo_server.state)
            if current_state != last_state:
                yield f"data: {current_state}\n\n"
                last_state = current_state
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

@api_bp.route('/disconnect', methods=['POST'])
def api_disconnect():
    kobo_server.disconnect_trigger = True
    return jsonify({"success": True})

@api_bp.route('/download', methods=['POST'])
def api_download():
    """Tải truyện từ web và đẩy vào Calibre library."""
    data = request.json or {}
    url, add_calibre = data.get("url"), data.get("add_to_calibre", False)
    if not url: return jsonify({"success": False, "error": "No URL"})
    
    task = ScraperTask(url, add_to_calibre=add_calibre)
    threading.Thread(target=task.run, daemon=True).start()
    return jsonify({"success": True, "message": "Download started"})

import threading # Cần cho api_download phía trên

# --- Reader Route ---
@reader_bp.route('/<int:book_id>')
def reader_view(book_id):
    if not session.get('logged_in'):
        from flask import redirect, url_for
        return redirect(url_for('login'))
    return send_file('templates/reader.html') # Hoặc render_template nếu có jinja 

import os
import json
import time
import sqlite3
import threading
import urllib.request
import zipfile
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Add ttv_api path
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_api.ttv.story import coerce_story_list, build_story_cover_url


DB_PATH = Path(__file__).resolve().parents[2] / "ttv_stories.db"
MAX_DELTA = 500  # Upper bound, will stop early if no more stories

_sync_lock = threading.Lock()
_sync_status = {
    "running": False,
    "last_sync": None,
    "progress": "",
    "total_stories": 0,
    "error": "",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


VALID_SORT_COLS = {
    "count_chapter": "count_chapter DESC",
    "avg_rate": "avg_rate DESC",
    "nominated_month": "nominated_month DESC",
    "convert_month": "convert_month DESC",
    "time_fix": "time_fix DESC",
    "name": "name ASC",
}

TTV_TAG_MAP = {}  # Will be populated from JSON/API

def load_tags_from_cache():
    global TTV_TAG_MAP
    tag_cache = Path(__file__).resolve().parent / "ttv_tags.json"
    if tag_cache.exists():
        try:
            with open(tag_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
                TTV_TAG_MAP.update(data)
            print(f"[TTV DB] Loaded {len(TTV_TAG_MAP)} tags from ttv_tags.json.")
        except Exception as e:
            print(f"[TTV DB] Failed to load tags.json: {e}")

# Initial load
load_tags_from_cache()

def sync_tags(client=None):
    """Fetch all categories from TTV API (fallback/update)."""
    global TTV_TAG_MAP
    # We already have a good list from the user's HTML, 
    # but we can try to supplement it from API if needed.
    try:
        if not client:
            client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
            client.get_token()
        res = client.get_category()
        if res.get("status") == 1:
            cats = res.get("category") or res.get("categories") or []
            new_count = 0
            for c in cats:
                cid = str(c.get("id") or "")
                name = c.get("name") or c.get("category_name")
                if cid and name and cid not in TTV_TAG_MAP:
                    TTV_TAG_MAP[cid] = name
                    new_count += 1
            if new_count > 0:
                print(f"[TTV DB] Added {new_count} new tags from API.")
                tag_cache = Path(__file__).resolve().parent / "ttv_tags.json"
                with open(tag_cache, "w", encoding="utf-8") as f:
                    json.dump(TTV_TAG_MAP, f, ensure_ascii=False, indent=2)
    except: pass

def get_tag_name(tag_id: str) -> str:
    return TTV_TAG_MAP.get(str(tag_id), f"Tag {tag_id}")

def get_tag_list() -> List[Dict[str, str]]:
    """Return list of unique tag names with their first found ID for UI. Restricted to 1-12."""
    name_to_id = {}
    valid_ids = {str(i) for i in range(1, 13)}
    for tid, name in TTV_TAG_MAP.items():
        if tid in valid_ids:
            if name not in name_to_id:
                name_to_id[name] = tid
    
    tags = [{"id": tid, "name": name} for name, tid in name_to_id.items()]
    return sorted(tags, key=lambda x: int(x["id"]))

def init_db():
    """Create the stories table if it doesn't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            introduce TEXT NOT NULL DEFAULT '',
            china_name TEXT NOT NULL DEFAULT '',
            count_chapter INTEGER DEFAULT 0,
            finish INTEGER DEFAULT 0,
            image TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            avg_rate REAL DEFAULT 0,
            nominated_month INTEGER DEFAULT 0,
            convert_month INTEGER DEFAULT 0,
            time_fix TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)
    # Migrate: add columns if missing (for existing DBs)
    for col, coldef in [("nominated_month", "INTEGER DEFAULT 0"), ("convert_month", "INTEGER DEFAULT 0")]:
        try:
            conn.execute(f"ALTER TABLE stories ADD COLUMN {col} {coldef}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def get_last_sync() -> Optional[str]:
    """Return ISO timestamp of the last successful sync, or None."""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM sync_meta WHERE key='last_sync'").fetchone()
    conn.close()
    return row["value"] if row else None


def get_story_count() -> int:
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM stories").fetchone()
    conn.close()
    return row["cnt"] if row else 0


API_MODES = {"HotMonth", "NominatedMonth", "New", "Update", "Like", "Follow", "CommentCount"}

def _format_api_stories(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for s in stories:
        results.append({
            "id": s.get("id"),
            "name": s.get("name") or "",
            "author": s.get("author") or "",
            "count_chapter": s.get("count_chapter") or 0,
            "finish": "1" if s.get("finish") else "0",
            "description": s.get("introduce") or "",
            "category": s.get("tags") or s.get("category") or "",
            "china_name": s.get("china_name") or "",
            "avg_rate": s.get("avg_rate") or 0,
            "nominated_month": s.get("nominated_month") or 0,
            "convert_month": s.get("convert_month") or 0,
            "time_fix": s.get("time_fix") or "",
            "cover_url": build_story_cover_url(s.get("image")),
        })
    return results

def search_stories(query: str = "", finish: str = "", tag: str = "", sort: str = "count_chapter", limit: int = 200) -> List[Dict[str, Any]]:
    """Search local DB or proxy to API based on filters."""
    client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
    client.get_token()

    if tag and tag != "none":
        res = client.get_list_story_type(type_id=tag, offset=str(limit), page="0")
        if res.get("status") == 1:
            return _format_api_stories(coerce_story_list(res))
        return []

    if sort in API_MODES:
        res = client.get_list_story(mode=sort, delta="0", finish=finish if finish != "none" else "none")
        if res.get("status") == 1:
            return _format_api_stories(coerce_story_list(res))
        return []

    conn = _get_conn()
    conditions = []
    params = []

    if query:
        conditions.append("(name LIKE ? OR author LIKE ? OR china_name LIKE ?)")
        q = f"%{query}%"
        params.extend([q, q, q])

    if finish and finish != "none":
        conditions.append("finish = ?")
        params.append(int(finish))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order = VALID_SORT_COLS.get(sort, "count_chapter DESC")
    if sort not in VALID_SORT_COLS:
        order = "count_chapter DESC"

    sql = f"SELECT * FROM stories {where} ORDER BY {order} LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        raw_tags = r["tags"]
        tag_names = []
        if raw_tags:
            for tid in str(raw_tags).split(','):
                tid = tid.strip()
                if tid:
                    tag_names.append(get_tag_name(tid))
        
        results.append({
            "id": r["id"],
            "name": r["name"],
            "author": r["author"],
            "count_chapter": r["count_chapter"],
            "finish": "1" if r["finish"] else "0",
            "description": r["introduce"],
            "category": ", ".join(tag_names),
            "china_name": r["china_name"],
            "avg_rate": r["avg_rate"],
            "nominated_month": r["nominated_month"],
            "convert_month": r["convert_month"],
            "time_fix": r["time_fix"],
            "cover_url": build_story_cover_url(r["image"]),
        })
    return results


def get_sync_status() -> Dict[str, Any]:
    return dict(_sync_status)


def run_full_sync():
    """Download stories.zip and bulk update into SQLite."""
    global _sync_status

    if not _sync_lock.acquire(blocking=False):
        return  # Already running

    try:
        _sync_status["running"] = True
        _sync_status["error"] = ""
        _sync_status["progress"] = "Downloading stories.zip..."

        init_db()

        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "story.zip")
        urllib.request.urlretrieve('https://nae.vn/ttv/ttv_apiv2/public/get_json_story', zip_path)
        
        _sync_status["progress"] = "Extracting stories.zip..."
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(tmp_dir)

        json_path = os.path.join(tmp_dir, "stories.json")
        if not os.path.exists(json_path):
            raise Exception("stories.json not found in zip")

        _sync_status["progress"] = "Parsing stories.json..."
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)

        stories = data.get("story", [])
        if not stories:
            raise Exception("No stories found in JSON")

        _sync_status["progress"] = f"Updating database with {len(stories)} stories..."
        conn = _get_conn()
        
        rows = []
        for s in stories:
            rows.append((
                s.get("id"),
                s.get("name") or "",
                s.get("author") or "",
                s.get("china_name") or "",
                s.get("count_chapter") or 0,
                s.get("image") or "",
                json.dumps(s, ensure_ascii=False)
            ))
            
        conn.execute("BEGIN TRANSACTION")
        conn.executemany("""
            INSERT INTO stories (id, name, author, china_name, count_chapter, image, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                author=excluded.author,
                china_name=excluded.china_name,
                count_chapter=excluded.count_chapter,
                image=excluded.image,
                raw_json=excluded.raw_json
        """, rows)
        
        conn.commit()
        
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO sync_meta (key, value) VALUES ('last_sync', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now,),
        )
        conn.commit()
        conn.close()

        shutil.rmtree(tmp_dir)

        _sync_status["last_sync"] = now
        _sync_status["total_stories"] = len(stories)
        _sync_status["progress"] = f"Done! {len(stories)} stories synced."
        print(f"[TTV DB] Sync complete: {len(stories)} stories.")

    except Exception as e:
        _sync_status["error"] = str(e)
        print(f"[TTV DB] Sync error: {e}")
    finally:
        _sync_status["running"] = False
        _sync_lock.release()


def start_sync_thread():
    """Start sync in a background thread."""
    thread = threading.Thread(target=run_full_sync, daemon=True)
    thread.start()
    return thread


def maybe_auto_sync():
    """Start sync if last sync was more than 24 hours ago or DB is empty."""
    init_db()
    
    # Always try to sync tags on startup
    threading.Thread(target=sync_tags, daemon=True).start()

    last = get_last_sync()
    count = get_story_count()

    if count == 0:
        print("[TTV DB] No stories in DB, starting initial sync...")
        start_sync_thread()
        return

    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.now() - last_dt < timedelta(hours=24):
                _sync_status["last_sync"] = last
                _sync_status["total_stories"] = count
                print(f"[TTV DB] Last sync: {last}, {count} stories. Skipping auto-sync.")
                return
        except Exception:
            pass

    print("[TTV DB] Auto-sync triggered (>24h since last sync).")
    start_sync_thread()

import os
import json
import time
import sqlite3
import threading
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

TTV_TAG_MAP = {}  # Will be populated from API

def sync_tags(client=None):
    """Fetch all categories from TTV and update the local map."""
    global TTV_TAG_MAP
    try:
        if not client:
            client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
            client.get_token()
        
        res = client.get_category()
        if res.get("status") == 1:
            cats = res.get("category", [])
            new_map = {}
            for c in cats:
                cid = str(c.get("id"))
                name = c.get("name")
                if cid and name:
                    new_map[cid] = name
            
            if new_map:
                TTV_TAG_MAP.update(new_map)
                print(f"[TTV DB] Synced {len(TTV_TAG_MAP)} tags from API.")
                
                # Save to a local json for persistence if you want
                tag_cache = DB_PATH.parent / "ttv_tags.json"
                with open(tag_cache, "w", encoding="utf-8") as f:
                    json.dump(TTV_TAG_MAP, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TTV DB] Failed to sync tags: {e}")
        # Try to load from cache
        load_tags_from_cache()

def load_tags_from_cache():
    global TTV_TAG_MAP
    tag_cache = DB_PATH.parent / "ttv_tags.json"
    if tag_cache.exists():
        try:
            with open(tag_cache, "r", encoding="utf-8") as f:
                TTV_TAG_MAP.update(json.load(f))
            print(f"[TTV DB] Loaded {len(TTV_TAG_MAP)} tags from cache.")
        except: pass

# Load immediately on import
load_tags_from_cache()

def get_tag_name(tag_id: str) -> str:
    return TTV_TAG_MAP.get(str(tag_id), f"Tag {tag_id}")

def get_tag_list() -> List[Dict[str, str]]:
    if not TTV_TAG_MAP:
        sync_tags()
    # Return sorted list of tags for UI
    tags = [{"id": k, "name": v} for k, v in TTV_TAG_MAP.items()]
    return sorted(tags, key=lambda x: x["name"])

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


def search_stories(query: str = "", finish: str = "", tag: str = "", sort: str = "count_chapter", limit: int = 200) -> List[Dict[str, Any]]:
    """Search local DB for stories matching query and filters."""
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

    if tag and tag != "none":
        # Tags are stored as "162,115". Use LIKE to find the tag ID.
        # We wrap in commas to ensure we don't match partial IDs (e.g. "1" in "162")
        # But since they are stored as comma-sep, we check for ",ID," or start/end
        conditions.append("(',' || tags || ',') LIKE ?")
        params.append(f"%,{tag},%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order = VALID_SORT_COLS.get(sort, "count_chapter DESC")
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
    """Crawl all pages of get_list_story and upsert into SQLite."""
    global _sync_status

    if not _sync_lock.acquire(blocking=False):
        return  # Already running

    try:
        _sync_status["running"] = True
        _sync_status["error"] = ""
        _sync_status["progress"] = "Authenticating..."

        client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
        token_res = client.get_token()
        if token_res.get("status") != 1:
            _sync_status["error"] = "Failed to get TTV token"
            return

        init_db()
        conn = _get_conn()
        total_inserted = 0

        # Crawl both unfinished (none) and finished (full) stories
        for finish_status in ["none", "full"]:
            for delta in range(MAX_DELTA):
                _sync_status["progress"] = f"Fetching {finish_status} page {delta + 1}... ({total_inserted} total)"

                try:
                    res = client.get_list_story(mode="HotMonth", delta=str(delta), finish=finish_status)
                except Exception as e:
                    print(f"[TTV DB] Error on delta={delta}: {e}")
                    continue

                if res.get("status") != 1:
                    break

                stories = coerce_story_list(res)
                if not stories:
                    break

                for s in stories:
                    sid = s.get("id")
                    if not sid:
                        continue
                    conn.execute("""
                        INSERT INTO stories (id, name, author, introduce, china_name, count_chapter, finish, image, tags, avg_rate, nominated_month, convert_month, time_fix, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,
                            author=excluded.author,
                            introduce=excluded.introduce,
                            china_name=excluded.china_name,
                            count_chapter=excluded.count_chapter,
                            finish=excluded.finish,
                            image=excluded.image,
                            tags=excluded.tags,
                            avg_rate=excluded.avg_rate,
                            nominated_month=excluded.nominated_month,
                            convert_month=excluded.convert_month,
                            time_fix=excluded.time_fix,
                            raw_json=excluded.raw_json
                    """, (
                        sid,
                        s.get("name") or "",
                        s.get("author") or "",
                        s.get("introduce") or "",
                        s.get("china_name") or "",
                        s.get("count_chapter") or 0,
                        s.get("finish") or 0,
                        s.get("image") or "",
                        s.get("tags") or "",
                        s.get("avg_rate") or 0,
                        s.get("nominated_month") or 0,
                        s.get("convert_month") or 0,
                        s.get("time_fix") or "",
                        json.dumps(s, ensure_ascii=False),
                    ))
                    total_inserted += 1

            conn.commit()

            # Small delay to avoid hammering the server
            time.sleep(0.3)

        # Update sync metadata
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO sync_meta (key, value) VALUES ('last_sync', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now,),
        )
        conn.commit()
        conn.close()

        _sync_status["last_sync"] = now
        _sync_status["total_stories"] = get_story_count()
        _sync_status["progress"] = f"Done! {total_inserted} stories synced."
        print(f"[TTV DB] Sync complete: {total_inserted} stories.")

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

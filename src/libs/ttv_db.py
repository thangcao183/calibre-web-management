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


def search_stories(query: str = "", finish: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    """Search local DB for stories matching query."""
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
    sql = f"SELECT * FROM stories {where} ORDER BY count_chapter DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "name": r["name"],
            "author": r["author"],
            "count_chapter": r["count_chapter"],
            "finish": "1" if r["finish"] else "0",
            "description": r["introduce"],
            "category": r["tags"],
            "china_name": r["china_name"],
            "avg_rate": r["avg_rate"],
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

        for delta in range(MAX_DELTA):
            _sync_status["progress"] = f"Fetching page {delta + 1}... ({total_inserted} stories so far)"

            try:
                res = client.get_list_story(mode="HotMonth", delta=str(delta), finish="none")
            except Exception as e:
                print(f"[TTV DB] Error on delta={delta}: {e}")
                # Try to continue
                continue

            if res.get("status") != 1:
                # Possibly end of pages or error
                print(f"[TTV DB] Stopped at delta={delta}: {res.get('message')}")
                break

            stories = coerce_story_list(res)
            if not stories:
                print(f"[TTV DB] Empty page at delta={delta}, stopping.")
                break

            for s in stories:
                sid = s.get("id")
                if not sid:
                    continue
                conn.execute("""
                    INSERT INTO stories (id, name, author, introduce, china_name, count_chapter, finish, image, tags, avg_rate, time_fix, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

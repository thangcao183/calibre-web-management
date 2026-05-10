import os
import sys
import threading
import time
from flask import Blueprint, jsonify, request, current_app

from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_api.ttv.story import filter_story_list, coerce_story_list, build_story_cover_url
from libs.ttv_scraper_task import TTVScraperTask
from libs.kobo_device import kobo_server

ttv_bp = Blueprint('ttv', __name__, url_prefix='/api/ttv')

CACHE_TTL = 300  # 5 minutes
story_cache = {}
MAX_PAGES = 5  # Load delta 0..4 for ~5x more stories

def _make_client():
    client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
    token_res = client.get_token()
    if token_res.get('status') != 1:
        raise Exception("Failed to get TTV token")
    return client

def _format_stories(stories):
    results = []
    for s in stories:
        results.append({
            "id": s.get("id", ""),
            "name": s.get("name", "Unknown Title"),
            "author": s.get("author", "Unknown Author"),
            "count_chapter": s.get("count_chapter", "?"),
            "finish": s.get("finish", ""),
            "description": s.get("description") or s.get("synopsis") or "",
            "category": s.get("category") or s.get("genres") or s.get("tags") or "",
            "cover_url": build_story_cover_url(s.get("image", ""))
        })
    return results

def _fetch_stories(client, mode, finish):
    """Fetch stories: Home mode uses GET endpoint, others load multiple pages."""
    if mode == "Home":
        res = client.get_list_story_home()
        return coerce_story_list(res) if res.get('status') == 1 else []

    all_stories = []
    seen_ids = set()
    for delta in range(MAX_PAGES):
        res = client.get_list_story(mode=mode, delta=str(delta), finish=finish)
        if res.get('status') != 1:
            break
        page = coerce_story_list(res)
        if not page:
            break
        for s in page:
            sid = s.get("id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_stories.append(s)
    return all_stories

@ttv_bp.route('/search', methods=['GET'])
def api_ttv_search():
    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'HotMonth').strip()
    finish = request.args.get('finish', 'none').strip()

    global story_cache
    current_time = time.time()

    # Load stories (shared cache for both browse and search)
    cache_key = f"{mode}_{finish}"
    cache_entry = story_cache.get(cache_key)
    if cache_entry is None or current_time - cache_entry['timestamp'] > CACHE_TTL:
        try:
            client = _make_client()
            stories = _fetch_stories(client, mode, finish)
            story_cache[cache_key] = {'data': stories, 'timestamp': current_time}
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    else:
        stories = cache_entry['data']

    # If user typed a query, filter locally
    if query:
        stories = filter_story_list(stories, query=query)

    return jsonify({"success": True, "stories": _format_stories(stories), "total": len(stories)})

@ttv_bp.route('/download', methods=['POST'])
def api_ttv_download():
    data = request.json or {}
    id_story = data.get("id_story")
    title = data.get("title")
    author = data.get("author")
    cover_url = data.get("cover_url")
    description = data.get("description", "")
    tags = data.get("tags", [])
    
    if not id_story:
        return jsonify({"success": False, "error": "Missing id_story"}), 400
        
    try:
        task = TTVScraperTask(
            id_story=id_story,
            title=title,
            author=author,
            cover_url=cover_url,
            description=description,
            tags=tags
        )
        
        # We need to queue this or run it in background. 
        # The main app has a DOWNLOAD_QUEUE, but we can also just run it in a thread like we do with ScraperTask.
        # Actually, ScraperTask uses kobo_server directly and is often put in DOWNLOAD_QUEUE in routes.py
        # But for simplicity, we'll run it in a background thread and update state directly.
        def run_task():
            # If main DOWNLOAD_WORKER_RUNNING logic is strictly used, we might want to respect it
            # But the task sets kobo_server state properly
            kobo_server.add_history("system", "info", f"Started TTV download for ID {id_story}")
            task.run()
            
        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True, "message": "Download queued"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

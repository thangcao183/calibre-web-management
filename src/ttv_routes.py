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

# Simple memory cache to avoid hammering TTV API
CACHE_TTL = 300 # 5 minutes
story_cache = {}

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

@ttv_bp.route('/search', methods=['GET'])
def api_ttv_search():
    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'HotMonth').strip()
    finish = request.args.get('finish', 'none').strip()

    global story_cache
    current_time = time.time()

    # --- Branch 1: user typed a search query → call native get_search_story ---
    if query:
        cache_key = f"search_{query}"
        cache_entry = story_cache.get(cache_key)
        if cache_entry is None or current_time - cache_entry['timestamp'] > CACHE_TTL:
            try:
                client = _make_client()
                res = client.get_search_story(key=query)
                if res.get('status') == 1:
                    stories = coerce_story_list(res)
                    story_cache[cache_key] = {'data': stories, 'timestamp': current_time}
                else:
                    # Fallback: native search failed (possibly wrong hash), filter from browse list
                    print(f"[TTV] get_search_story failed ({res.get('message')}), falling back to local filter")
                    fallback_key = f"{mode}_{finish}"
                    fb = story_cache.get(fallback_key)
                    if fb is None or current_time - fb['timestamp'] > CACHE_TTL:
                        fb_res = client.get_list_story(mode=mode, delta="0", finish=finish)
                        stories = coerce_story_list(fb_res) if fb_res.get('status') == 1 else []
                        story_cache[fallback_key] = {'data': stories, 'timestamp': current_time}
                    else:
                        stories = fb['data']
                    story_cache[cache_key] = {'data': stories, 'timestamp': current_time}
            except Exception as e:
                return jsonify({"success": False, "error": str(e)})
        else:
            stories = cache_entry['data']

        # Apply local filter as secondary pass in case API returned broad results
        filtered = filter_story_list(stories, query=query)
        return jsonify({"success": True, "stories": _format_stories(filtered), "total": len(filtered)})

    # --- Branch 2: no query → browse by mode/finish (get_list_story) ---
    cache_key = f"{mode}_{finish}"
    cache_entry = story_cache.get(cache_key)
    if cache_entry is None or current_time - cache_entry['timestamp'] > CACHE_TTL:
        try:
            client = _make_client()
            story_res = client.get_list_story(mode=mode, delta="0", finish=finish)
            if story_res.get('status') != 1:
                return jsonify({"success": False, "error": f"Failed to get story list: {story_res.get('message')}"})
            stories = coerce_story_list(story_res)
            story_cache[cache_key] = {'data': stories, 'timestamp': current_time}
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    else:
        stories = cache_entry['data']

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

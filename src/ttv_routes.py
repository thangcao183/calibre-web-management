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

# Simple memory cache for get_list_story to avoid spamming the endpoint on every search keypress
CACHE_TTL = 300 # 5 minutes
story_cache = {}

@ttv_bp.route('/search', methods=['GET'])
def api_ttv_search():
    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'HotMonth').strip()
    finish = request.args.get('finish', 'none').strip()
    
    global story_cache
    current_time = time.time()
    
    cache_key = f"{mode}_{finish}"
    cache_entry = story_cache.get(cache_key)
    
    if cache_entry is None or current_time - cache_entry['timestamp'] > CACHE_TTL:
        try:
            client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
            token_res = client.get_token()
            if token_res.get('status') != 1:
                return jsonify({"success": False, "error": "Failed to get TTV token"})
            
            story_res = client.get_list_story(mode=mode, delta="0", finish=finish)
            if story_res.get('status') != 1:
                return jsonify({"success": False, "error": f"Failed to get story list: {story_res.get('message')}"})
            
            stories = coerce_story_list(story_res)
            story_cache[cache_key] = {
                'data': stories,
                'timestamp': current_time
            }
            cache_entry = story_cache[cache_key]
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
            
    stories = cache_entry['data']
    
    # Filter using ttv.story logic
    filtered = filter_story_list(stories, query=query)
    
    # Format the response
    results = []
    for s in filtered:
        results.append({
            "id": s.get("id", ""),
            "name": s.get("name", "Unknown Title"),
            "author": s.get("author", "Unknown Author"),
            "count_chapter": s.get("count_chapter", "?"),
            "finish": s.get("finish", ""),
            "cover_url": build_story_cover_url(s.get("image", ""))
        })
        
    return jsonify({
        "success": True,
        "stories": results,
        "total": len(results)
    })

@ttv_bp.route('/download', methods=['POST'])
def api_ttv_download():
    data = request.json or {}
    id_story = data.get("id_story")
    title = data.get("title")
    author = data.get("author")
    cover_url = data.get("cover_url")
    
    if not id_story:
        return jsonify({"success": False, "error": "Missing id_story"}), 400
        
    try:
        task = TTVScraperTask(
            id_story=id_story,
            title=title,
            author=author,
            cover_url=cover_url
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

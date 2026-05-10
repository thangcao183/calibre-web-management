import os
import sys
import threading
import time
from flask import Blueprint, jsonify, request

from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_api.ttv.story import filter_story_list, coerce_story_list, build_story_cover_url
from libs.ttv_scraper_task import TTVScraperTask
from libs.ttv_db import search_stories, get_sync_status, start_sync_thread, maybe_auto_sync, get_story_count, get_tag_list
from libs.kobo_device import kobo_server

ttv_bp = Blueprint('ttv', __name__, url_prefix='/api/ttv')


@ttv_bp.route('/search', methods=['GET'])
def api_ttv_search():
    query = request.args.get('query', '').strip()
    finish = request.args.get('finish', 'none').strip()
    tag = request.args.get('tag', '').strip()
    sort = request.args.get('sort', 'count_chapter').strip()
    limit = request.args.get('limit', '200', type=str)

    try:
        limit_int = int(limit)
    except ValueError:
        limit_int = 200

    stories = search_stories(query=query, finish=finish, tag=tag, sort=sort, limit=limit_int)
    return jsonify({"success": True, "stories": stories, "total": len(stories)})


@ttv_bp.route('/tags', methods=['GET'])
def api_ttv_tags():
    """Get list of available TTV tags."""
    return jsonify({"success": True, "tags": get_tag_list()})


@ttv_bp.route('/sync', methods=['POST'])
def api_ttv_sync():
    """Manually trigger a full sync."""
    status = get_sync_status()
    if status["running"]:
        return jsonify({"success": False, "error": "Sync already in progress", "status": status})

    start_sync_thread()
    return jsonify({"success": True, "message": "Sync started"})


@ttv_bp.route('/sync/status', methods=['GET'])
def api_ttv_sync_status():
    """Get current sync status."""
    status = get_sync_status()
    status["total_stories"] = get_story_count()
    return jsonify(status)


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

        def run_task():
            kobo_server.add_history("system", "info", f"Started TTV download for ID {id_story}")
            task.run()

        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()

        return jsonify({"success": True, "message": "Download queued"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

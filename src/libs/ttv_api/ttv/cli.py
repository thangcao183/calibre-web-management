import argparse
import json

from .client import TTVClient
from .story import (
    coerce_story_list,
    find_story_by_id,
    print_story_detail,
    print_story_list,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TTV crawler without Frida")
    parser.add_argument("--imei", default="21bab69a53e003ff", help="Device IMEI used by app")
    parser.add_argument("--token-adr", default="fcm_ttv::test", help="FCM token (can be placeholder)")
    parser.add_argument("--mode", default="HotMonth", help="Legacy alias for --story-mode")
    parser.add_argument("--story-mode", default="HotMonth", help="get_list_story mode")
    parser.add_argument("--story-delta", default="0", help="get_list_story delta")
    parser.add_argument("--story-finish", default="none", help="get_list_story finish flag")
    parser.add_argument("--story-limit", type=int, default=10, help="How many stories to print")
    parser.add_argument("--story-info-id", default="", help="Print a single story by id_story")
    parser.add_argument("--story-query", default="", help="Filter story names by substring")
    parser.add_argument("--story-author", default="", help="Filter authors by substring")
    parser.add_argument("--story-finish-filter", default="", help="Filter exact finish value")
    parser.add_argument("--min-chapters", type=int, default=None, help="Minimum chapter count")
    parser.add_argument("--max-chapters", type=int, default=None, help="Maximum chapter count")
    parser.add_argument(
        "--list-stories",
        action="store_true",
        help="Only fetch and print the story list, then exit",
    )
    parser.add_argument("--id-story", default="39346", help="Story id to crawl")
    parser.add_argument(
        "--show-content",
        action="store_true",
        help="Fetch content of first chapter and print first 500 chars",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print full JSON responses with real unicode characters",
    )
    return parser.parse_args()


def run_cli() -> int:
    args = parse_args()
    client = TTVClient(imei=args.imei, token_adr=args.token_adr)

    token_result = client.get_token()
    print("[get_token]", json.dumps(token_result, ensure_ascii=False)[:300])
    if args.print_json:
        print(json.dumps(token_result, ensure_ascii=False, indent=2))
    if token_result.get("status") != 1 or not client.token:
        print("[ERROR] cannot obtain token")
        return 1

    story_mode = args.story_mode or args.mode
    story_result = client.get_list_story(mode=story_mode, delta=args.story_delta, finish=args.story_finish)
    print("[get_list_story] status=", story_result.get("status"), "message=", story_result.get("message"))
    if args.print_json:
        print(json.dumps(story_result, ensure_ascii=False, indent=2)[:3000])

    stories = coerce_story_list(story_result)
    if args.story_info_id:
        story = find_story_by_id(stories, args.story_info_id)
        if story is None:
            print(f"[WARN] story id not found: {args.story_info_id}")
            return 0
        print_story_detail(story)
        return 0

    print_story_list(
        story_result,
        limit=args.story_limit,
        query=args.story_query,
        author=args.story_author,
        finish=args.story_finish_filter,
        min_chapters=args.min_chapters,
        max_chapters=args.max_chapters,
    )

    if args.list_stories:
        return 0

    chapter_result = client.get_list_chapter(id_story=args.id_story)
    print("[get_list_chapter] status=", chapter_result.get("status"), "message=", chapter_result.get("message"))
    if args.print_json:
        print(json.dumps(chapter_result, ensure_ascii=False, indent=2)[:3000])

    chapters = chapter_result.get("chapter") or []
    if not chapters:
        print("[WARN] no chapters found")
        return 0

    first = chapters[0]
    print("[first_chapter] id=", first.get("id"), "title=", first.get("name_id_chapter"))

    if args.show_content:
        content_result = client.get_content_chapter(str(first.get("id")), str(args.id_story))
        print("[get_content_chapter] status=", content_result.get("status"), "message=", content_result.get("message"))
        if args.print_json:
            print(json.dumps(content_result, ensure_ascii=False, indent=2)[:3000])
        content = ""
        content_list = content_result.get("content_chapter") or []
        if content_list and isinstance(content_list[0], dict):
            content = content_list[0].get("content", "")
        print("[content_preview]", str(content)[:500])

    return 0

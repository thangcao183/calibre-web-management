import json
from typing import Any, Dict

from .constants import STORY_COVER_BASE
from .utils import to_int


def coerce_story_list(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    stories = payload.get("list_stories")
    if isinstance(stories, list):
        return [story for story in stories if isinstance(story, dict)]

    for key in ("stories", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [story for story in value if isinstance(story, dict)]

    return []


def filter_story_list(
    stories: list[Dict[str, Any]],
    query: str = "",
    author: str = "",
    finish: str = "",
    min_chapters: int | None = None,
    max_chapters: int | None = None,
) -> list[Dict[str, Any]]:
    query_text = query.casefold().strip()
    author_text = author.casefold().strip()
    finish_text = finish.strip()

    filtered: list[Dict[str, Any]] = []
    for story in stories:
        name = str(story.get("name", ""))
        story_author = str(story.get("author", ""))
        story_finish = str(story.get("finish", ""))
        count_chapter = to_int(story.get("count_chapter"))

        if query_text and query_text not in name.casefold():
            continue
        if author_text and author_text not in story_author.casefold():
            continue
        if finish_text and story_finish != finish_text:
            continue
        if min_chapters is not None and (count_chapter is None or count_chapter < min_chapters):
            continue
        if max_chapters is not None and (count_chapter is None or count_chapter > max_chapters):
            continue

        filtered.append(story)

    return filtered


def find_story_by_id(stories: list[Dict[str, Any]], story_id: str) -> Dict[str, Any] | None:
    target_id = str(story_id).strip()
    for story in stories:
        if str(story.get("id", "")).strip() == target_id:
            return story
    return None


def build_story_cover_url(image_hash: Any) -> str:
    image_value = str(image_hash).strip()
    if not image_value or image_value == "0":
        return ""
    if image_value.startswith("http://") or image_value.startswith("https://"):
        return image_value
    return f"{STORY_COVER_BASE}/{image_value}.jpg"


def print_story_list(
    payload: Dict[str, Any],
    limit: int = 10,
    query: str = "",
    author: str = "",
    finish: str = "",
    min_chapters: int | None = None,
    max_chapters: int | None = None,
) -> None:
    stories = filter_story_list(
        coerce_story_list(payload),
        query=query,
        author=author,
        finish=finish,
        min_chapters=min_chapters,
        max_chapters=max_chapters,
    )
    if not stories:
        print("[WARN] no stories found")
        return

    print(f"[story_list] total={len(stories)} showing={min(limit, len(stories))}")
    for index, story in enumerate(stories[:limit], start=1):
        story_id = story.get("id", "")
        name = story.get("name", "")
        story_author = story.get("author", "")
        count_chapter = story.get("count_chapter", "")
        story_finish = story.get("finish", "")
        print(
            f"{index:02d}. id={story_id} | chapters={count_chapter} | finish={story_finish} | {name} | {story_author}"
        )


def print_story_detail(story: Dict[str, Any]) -> None:
    story_detail = dict(story)
    story_detail["cover_url"] = build_story_cover_url(story.get("image"))
    print(json.dumps(story_detail, ensure_ascii=False, indent=2))

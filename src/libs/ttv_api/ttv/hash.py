import hashlib

SECRET = "174587236491eyoruwoiernzwueyquhszsadhajsdha8"


def gen_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_get_stories_follow(imei: str) -> str:
    return gen_hash(imei + SECRET)


def hash_get_list_story(mode: str, delta: str, finish: str, user_id: str) -> str:
    return gen_hash(mode + delta + finish + user_id + SECRET)


def hash_get_list_chapter(token: str, id_story: str, delta: str, all_value: str) -> str:
    return gen_hash(token + id_story + delta + all_value + SECRET)


def hash_get_content_chapter(token: str, id_chapter: str, id_story: str, user_id: str) -> str:
    return gen_hash(token + id_chapter + id_story + user_id + SECRET)

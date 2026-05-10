import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from .hash import (
    hash_get_content_chapter,
    hash_get_list_chapter,
    hash_get_list_story,
    hash_get_search_story,
    hash_get_json_story,
)

from .constants import BASE
from .utils import decode_unicode_escapes, normalize_unicode


class TTVClient:
    def __init__(self, imei: str, token_adr: str, token_ios: str = ""):
        self.imei = imei
        self.token_adr = token_adr
        self.token_ios = token_ios
        self.token = ""
        self.userid = "0"
        self.appname = "ttv"

    def _headers(self, with_token: bool = True) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "python-ttv-crawler/1.0",
        }
        if with_token and self.token:
            headers.update(
                {
                    "token": self.token,
                    "userid": self.userid,
                    "appname": self.appname,
                }
            )
        return headers

    def _post_form_json(
        self, endpoint: str, form_key: str, payload: Dict[str, Any], with_token: bool = True
    ) -> Dict[str, Any]:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        data = urllib.parse.urlencode({form_key: raw}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}/{endpoint}",
            data=data,
            headers=self._headers(with_token=with_token),
            method="POST",
        )
        return self._send(req)

    @staticmethod
    def _send(req: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "ignore")
                return normalize_unicode(json.loads(body))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore") if e.fp else str(e)
            return {"status": 0, "message": f"HTTP {e.code}", "detail": decode_unicode_escapes(detail)}
        except json.JSONDecodeError:
            return {"status": 0, "message": "Non-JSON response", "detail": "response is not json"}
        except Exception as e:  # noqa: BLE001
            return {"status": 0, "message": f"Request error: {e}"}

    def get_token(self) -> Dict[str, Any]:
        payload = {
            "imei": self.imei,
            "token_adr": self.token_adr,
            "token_ios": self.token_ios,
        }
        result = self._post_form_json("get_token", "get_token", payload, with_token=False)
        if result.get("status") == 1:
            self.token = result.get("imei", {}).get("remember_token", "")
        return result

    def get_list_story(self, mode: str = "", delta: str = "0", finish: str = "none") -> Dict[str, Any]:
        payload = {
            "mode": mode,
            "delta": delta,
            "finish": finish,
            "user_id": self.userid,
            "hash": hash_get_list_story(mode, delta, finish, self.userid),
        }
        return self._post_form_json("get_list_story", "get_list_story", payload, with_token=True)

    def get_list_chapter(self, id_story: str, delta: str = "0", all_value: str = "all") -> Dict[str, Any]:
        payload = {
            "id_story": id_story,
            "delta": delta,
            "all": all_value,
            "hash": hash_get_list_chapter(self.token, id_story, delta, all_value),
        }
        return self._post_form_json("get_list_chapter", "get_list_chapter", payload, with_token=True)

    def get_content_chapter(self, id_chapter: str, id_story: str) -> Dict[str, Any]:
        payload = {
            "id_chapter": id_chapter,
            "id_story": id_story,
            "user_id": self.userid,
            "hash": hash_get_content_chapter(self.token, id_chapter, id_story, self.userid),
        }
        return self._post_form_json("get_content_chapter", "get_content_chapter", payload, with_token=True)

    def get_search_story(self, key: str, delta: str = "0") -> Dict[str, Any]:
        payload = {
            "key": key,
            "delta": delta,
            "hash": hash_get_search_story(key, delta),
        }
        return self._post_form_json("get_search_story", "get_search_story", payload, with_token=True)

    def get_json_story(self, id_story: str) -> Dict[str, Any]:
        payload = {
            "id_story": id_story,
            "user_id": self.userid,
            "hash": hash_get_json_story(id_story, self.userid),
        }
        return self._post_form_json("get_json_story", "get_json_story", payload, with_token=True)

    def get_list_story_home(self) -> Dict[str, Any]:
        """GET endpoint – no hash required, returns stories on homepage."""
        req = urllib.request.Request(
            f"{BASE}/get_list_story_home",
            headers=self._headers(with_token=True),
            method="GET",
        )
        return self._send(req)

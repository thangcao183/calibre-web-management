import sys
sys.path.insert(0, '/home/wolf/CODE/Python/Ebook/KOBO/calibre-web-management/src')
from libs.ttv_api.ttv.client import TTVClient
from libs.ttv_db import search_stories, run_full_sync

print("Testing TTVClient get_list_story_type...")
c = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
c.get_token()
res = c.get_list_story_type(type_id="1")
print(res.get("status"), len(res.get("story", [])))

print("Testing search_stories proxy...")
s = search_stories(sort="HotMonth", limit=5)
print(len(s), s[0]['name'] if s else "None")


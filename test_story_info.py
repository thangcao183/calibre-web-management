import sys
sys.path.append('src/libs/ttv_api')
from ttv.client import TTVClient
import json

client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
client.get_token()

# Try to get story metadata
res = client._post_form_json("get_json_story", "get_json_story", {"id_story": "39346"}, with_token=True)
print("--- get_json_story ---")
print(json.dumps(res, ensure_ascii=False)[:1000])

# Try to get chapter list
chap_res = client.get_list_chapter("39346", "0", "all")
print("\n--- get_list_chapter ---")
chaps = chap_res.get("chapter", [])
if chaps:
    print(json.dumps(chaps[0], ensure_ascii=False))

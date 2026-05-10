import sys, json
sys.path.append('src/libs/ttv_api')
from ttv.client import TTVClient
client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
try:
    client.get_token()
    res = client.get_list_chapter("39346")
    with open("ttv_test_chap.json", "w", encoding="utf-8") as f:
        json.dump(res.get("chapter", [])[:2], f, ensure_ascii=False, indent=2)
except Exception as e:
    with open("ttv_test_err.txt", "w") as f:
        f.write(str(e))

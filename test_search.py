import sys
sys.path.append('ttv_api')
from ttv.client import TTVClient
client = TTVClient(imei="21bab69a53e003ff", token_adr="fcm_ttv::test")
client.get_token()
print("token:", client.token)

res = client._post_form_json("get_search_story", "get_search_story", {"key": "nguyên", "delta": "0"}, with_token=True)
print(str(res)[:500])

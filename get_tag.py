import requests
import re
from bs4 import BeautifulSoup as bs

url = "https://tangthuvien.top/tong-hop?ctg=" # URL chính, không có /the-loai/
def get_tags():
    res = {}
    for i in range(1, 13):
        new_url = url + str(i)
        re = requests.get(new_url)
        soup = bs(re.text, "lxml")
        tag = soup.select("div.type-list p:nth-child(2) a")
        for t in tag:
            if t.text:
                res[t.get("data-value")] = t.text.strip()
    return res

# Chạy hàm
if __name__ == "__main__":
    tags = get_tags()
    print(tags)
    exit()
    
    # Lưu ra file JSON để dễ dùng
    # if tags:  
    #     import json
    #     with open('ttv_tags.json', 'w', encoding='utf-8') as f:
    #         json.dump(tags, f, ensure_ascii=False, indent=2)
    #     print("\nĐã lưu danh sách tag vào ttv_tags.json")
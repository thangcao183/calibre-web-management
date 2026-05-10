import urllib.request
import re
import json
import time
from pathlib import Path

def fetch_tags():
    temp_file = Path("../temp.txt")
    if not temp_file.exists():
        print("temp.txt not found")
        return

    urls = [line.strip() for line in temp_file.read_text().splitlines() if line.strip()]
    tag_map = {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Pattern to find: <a href="https://tangthuvien.top/the-loai/162" ...>Tiên Hiệp</a>
    # or similar structure in sub-type-wrap
    tag_pattern = re.compile(r'href="https?://tangthuvien\.top/the-loai/(\d+)"[^>]*>([^<]+)</a>')

    for url in urls:
        print(f"Fetching {url}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')
                
                # Look for the sub-type-wrap section to be more precise
                start_idx = html.find('sub-type-wrap')
                if start_idx != -1:
                    end_idx = html.find('</div>', start_idx + 1000) # search reasonable chunk
                    section = html[start_idx:start_idx+5000] # take a large enough chunk
                    matches = tag_pattern.findall(section)
                    for tid, tname in matches:
                        tname = tname.strip()
                        if tid and tname:
                            tag_map[tid] = tname
                            print(f"  Found: {tid} -> {tname}")
                else:
                    # Try general search if section not found
                    matches = tag_pattern.findall(html)
                    for tid, tname in matches:
                        tag_map[tid] = tname.strip()
            
            time.sleep(1) # Be nice
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    if tag_map:
        output_path = Path("ttv_tags_scraped.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tag_map, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(tag_map)} tags to {output_path}")
        return tag_map
    else:
        print("No tags found.")
        return None

if __name__ == "__main__":
    fetch_tags()

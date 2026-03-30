import time
import os
import threading
from libs.kobo_device import kobo_server
from libs.epub_fixer import fix_epub
import kepubify

def background_watcher():
    print("[Watcher] Started auto-ingest / sync watcher thread.")
    while True:
        try:
            # Auto sync to Kobo
            if kobo_server.state.get("auto_sync", False) and kobo_server.client_socket and not kobo_server.books_to_sync and not kobo_server.working:
                device_lpaths = [b.get("lpath") for b in kobo_server.state.get("books_on_device", [])]
                files = os.listdir(kobo_server.ebook_dir)
                for f in files:
                    if f.endswith('.epub'): # Look for EPUB instead of KEPUB
                        if f not in device_lpaths and f not in kobo_server.books_to_sync:
                            print(f"[Watcher] Auto-syncing un-synced book: {f}")
                            kobo_server.books_to_sync.append(f)
                            break
                            
        except Exception as e:
            print(f"[Watcher] Error: {e}")
        time.sleep(5)

def start_watcher():
    threading.Thread(target=background_watcher, daemon=True).start()

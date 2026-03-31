import socket
import json
import time
import os
import uuid
import traceback
import threading

OP_OK = 0
OP_GET_DEVICE_INFO = 3
OP_FREE_SPACE = 5
OP_GET_BOOK_COUNT = 6
OP_SEND_BOOK = 8
OP_GET_INIT_INFO = 9
OP_NOOP = 12
OP_SET_LIBRARY_INFO = 19

class KoboSyncServer:
    def __init__(self):
        self.settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app_settings.json')
        self.state_lock = threading.Lock()
        self.state_condition = threading.Condition(self.state_lock)
        self.state_version = 0
        self.state = {
            "status": "Listening",
            "client_address": None,
            "last_ping": None,
            "books_on_device": [],
            "device_info": "Unknown",
            "free_space": 0,
            "auto_sync": False,
            "download_progress": 0,
            "task_status": "idle",
            "task_message": "",
            "task_error": "",
            "last_downloaded_file": "",
            "current_download_id": "",
            "download_queue_urls": [],
            "download_queue_items": [],
            "task_history": []
        }
        self.client_socket = None
        self.books_to_sync = []
        self.sync_trigger = False
        self.disconnect_trigger = False
        self.working = False
        self.ebook_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'EBOOK')
        os.makedirs(self.ebook_dir, exist_ok=True)
        self.load_settings()

    def load_settings(self):
        """Load persisted runtime settings if available."""
        try:
            if not os.path.exists(self.settings_path):
                return
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if isinstance(settings.get("auto_sync"), bool):
                self.state["auto_sync"] = settings["auto_sync"]
        except Exception as e:
            print(f"[Settings] Failed to load settings: {e}")

    def save_settings(self):
        """Persist runtime settings changed from the dashboard."""
        settings = {
            "auto_sync": self.state["auto_sync"]
        }
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=True, indent=2)
        except Exception as e:
            print(f"[Settings] Failed to save settings: {e}")

    def add_history(self, kind, status, message):
        """Keep a small in-memory history for the dashboard activity panel."""
        entry = {
            "time": time.strftime('%H:%M:%S'),
            "kind": kind,
            "status": status,
            "message": message
        }
        with self.state_condition:
            history = self.state.setdefault("task_history", [])
            if history:
                latest = history[0]
                if latest["kind"] == entry["kind"] and latest["status"] == entry["status"] and latest["message"] == entry["message"]:
                    latest["time"] = entry["time"]
                    self.state_version += 1
                    self.state_condition.notify_all()
                    return
            history.insert(0, entry)
            del history[20:]
            self.state_version += 1
            self.state_condition.notify_all()

    def update_state(self, **kwargs):
        with self.state_condition:
            changed = False
            for key, value in kwargs.items():
                if self.state.get(key) != value:
                    self.state[key] = value
                    changed = True
            if changed:
                self.state_version += 1
                self.state_condition.notify_all()

    def state_snapshot(self):
        with self.state_lock:
            return dict(self.state)

    def wait_for_state_change(self, last_seen_version, timeout=20):
        with self.state_condition:
            changed = self.state_condition.wait_for(
                lambda: self.state_version != last_seen_version,
                timeout=timeout,
            )
            return self.state_version, dict(self.state), changed

    def _read_packet(self, sock, timeout=10):
        try:
            sock.settimeout(timeout)
            length_str = b''
            while True:
                char = sock.recv(1)
                if not char:
                    return None, None
                if char == b'[':
                    break
                length_str += char
                if len(length_str) > 20:
                    print(f"[TCP] Warning: Invalid length prefix received, Got: {length_str}")
                    return None, None
                    
            packet_len = int(length_str.decode('utf-8'))
            data = b'['
            remaining = packet_len - 1
            while remaining > 0:
                chunk = sock.recv(min(remaining, 4096))
                if not chunk:
                    return None, None
                data += chunk
                remaining -= len(chunk)

            packet = json.loads(data.decode('utf-8'))
            return packet[0], packet[1]
        except socket.timeout:
            print("[TCP] Socket timeout while reading packet")
            return None, None
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            print(f"[TCP] Error parsing packet: {e}")
            return None, None
        except Exception as e:
            print(f"[TCP] Unexpected error reading packet: {e}")
            return None, None

    def _send_packet(self, sock, opcode, payload):
        try:
            packet = [opcode, payload]
            json_str = json.dumps(packet).replace(" ", "")
            data = f"{len(json_str)}{json_str}".encode('utf-8')
            sock.sendall(data)
        except Exception as e:
            print(f"[TCP] Error sending packet: {e}")
            raise

    def handle_client(self, sock, addr):
        self.client_socket = sock
        self.update_state(
            status="Connected",
            client_address=f"{addr[0]}:{addr[1]}",
            last_ping=time.strftime('%H:%M:%S')
        )
        self.sync_trigger = False
        self.disconnect_trigger = False

        try:
            # 1. Init Info (faster timeout for init)
            self._send_packet(sock, OP_GET_INIT_INFO, {"passwordChallenge": ""})
            op, data = self._read_packet(sock, timeout=5)
            if op != OP_OK or data is None:
                print("[TCP] Init failed: no valid response from device")
                return
            self.update_state(device_info=data.get("deviceName", "Unknown Kobo"))

            # 2. Device Info
            self._send_packet(sock, OP_GET_DEVICE_INFO, {})
            op, data = self._read_packet(sock)

            # 3. Free space
            self._send_packet(sock, OP_FREE_SPACE, {})
            op, data = self._read_packet(sock, timeout=5)
            if data and "free_space_on_device" in data:
                self.update_state(free_space=data["free_space_on_device"])

            # 4. Get Book Count
            self._send_packet(sock, OP_GET_BOOK_COUNT, {
                "canStream": True,
                "canScan": True,
                "willUseCachedMetadata": True,
                "supportsSync": True,
                "canSupportBookFormatSync": True
            })
            op, data = self._read_packet(sock)
            if data and isinstance(data, dict) and "count" in data:
                count = data["count"]
                books = []
                for _ in range(count):
                    b_op, b_data = self._read_packet(sock, timeout=5)
                    if b_data:
                        books.append(b_data)
                self.update_state(books_on_device=books)

            # 5. Set Library Info
            self._send_packet(sock, OP_SET_LIBRARY_INFO, {
                "libraryName": "Calibre Web Management",
                "libraryUuid": "12345-abcde",
                "fieldMetadata": {}
            })
            op, data = self._read_packet(sock)

            print("[TCP] Handshake completed. Entered Idle Loop.")
            # Idle Loop
            while True:
                if self.disconnect_trigger:
                    print("[TCP] Disconnect triggered by user.")
                    break
                    
                if self.books_to_sync:
                    filename = self.books_to_sync.pop(0)
                    self.working = True
                    self.run_sync(sock, filename)
                    self.working = False
                    
                # Send NOOP to keep alive
                if not self.working:
                    try:
                        self._send_packet(sock, OP_NOOP, {})
                        op, data = self._read_packet(sock, timeout=15)
                        if op is None: break
                        self.update_state(last_ping=time.strftime('%H:%M:%S'))
                    except Exception as noop_err:
                        print(f"[TCP] NOOP error: {noop_err}")
                        break
                
                # Check quickly
                for _ in range(30):
                    if self.books_to_sync or self.disconnect_trigger: break
                    time.sleep(0.1)

        except Exception as e:
            print(f"[TCP] Handler error: {e}")
            traceback.print_exc()
        finally:
            self.update_state(status="Listening", client_address=None)
            self.client_socket = None
            sock.close()
            print("[TCP] Disconnected Client.")

    def run_sync(self, sock, filename):
        filepath = os.path.join(self.ebook_dir, filename)
        if not os.path.exists(filepath):
            print(f"[TCP] File not found: {filename}")
            return
            
        print(f"[TCP] Starting sync of {filename}")
        
        device_books = self.state.get("books_on_device", [])
        if not isinstance(device_books, list):
            device_books = []
            
        device_lpaths = [b.get("lpath") for b in device_books if isinstance(b, dict)]
        if filename in device_lpaths:
            print("[TCP] Book already on device.")
            return

        file_size = os.path.getsize(filepath)
        
        metadata = {
            "title": filename.replace(".epub", "").replace(".kepub", "").replace("_", " "),
            "authors": ["Local Book"],
            "lpath": filename,
            "uuid": str(uuid.uuid4()),
            "size": file_size,
            "languages": ["vi"]
        }
        
        send_req = {
            "totalBooks": 1,
            "thisBook": 0,
            "willStreamBinary": True,
            "canSupportLpathChanges": True,
            "length": file_size,
            "willStreamBooks": True,
            "wantsSendOkToSendbook": True,
            "lpath": filename,
            "metadata": metadata
        }
        
        print(f"[TCP] Telling Kobo to prepare for {filename}")
        self._send_packet(sock, OP_SEND_BOOK, send_req)
        
        # Wait for OK-to-send
        op, data = self._read_packet(sock)
        
        print(f"[TCP] Streaming binary for {filename} ({file_size} bytes)...")
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                sock.sendall(chunk)
        print(f"[TCP] Finished sending {filename}")
        
        # Add to local list immediately
        current_books = list(self.state_snapshot().get("books_on_device", []))
        current_books.append({"lpath": filename})
        self.update_state(books_on_device=current_books)

kobo_server = KoboSyncServer()

def start_tcp_listener(host='0.0.0.0', port=9090):
    def listener():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"[TCP] Listening on {host}:{port}")

        while True:
            try:
                client, addr = server_socket.accept()
                print(f"[TCP] Accepted {addr}")
                if kobo_server.client_socket:
                    client.close()
                    continue
                kobo_server.handle_client(client, addr)
            except Exception as e:
                print(f"[TCP] Listener error: {e}")

    threading.Thread(target=listener, daemon=True).start()

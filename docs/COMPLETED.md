# Project Achievements - Kobo-UNCaGED Dashboard

Hệ thống quản lý sách và đồng bộ không dây cho Kobo tích hợp thư viện Calibre.

## 1. Tích hợp Thư viện Calibre (Core Backend)
- **Calibre as Backend**: Chuyển đổi từ quản lý file local sang sử dụng cơ sở dữ liệu Calibre làm trung tâm.
- **SQLite Integration**: Truy vấn trực tiếp `metadata.db` của Calibre để lấy thông tin sách, tác giả và bìa sách (Cover) với tốc độ cao.
- **Calibredb Automation**: Sử dụng lệnh `calibredb` để thực hiện các thao tác thêm (`add`) và xóa (`remove`) sách một cách chính xác.
- **Search & Pagination**: 
    - Hỗ trợ phân trang (24 sách/trang) giúp quản lý thư viện hàng ngàn cuốn mượt mà.
    - Chức năng tìm kiếm theo Tên sách hoặc Tác giả.
- **Latest First**: Tự động sắp xếp sách theo thời gian thêm vào (mới nhất lên đầu).

## 2. Các Tính năng Web Dashboard
- **Giao diện Hiện đại (Glassmorphism)**: Thiết kế tối giản, hiệu ứng kính mờ, hỗ trợ Dark Mode.
- **Book Action Modal**: Khi nhấn vào sách, hiện menu thông minh:
    - **Xóa sách**: Xóa vĩnh viễn khỏi Calibre.
    - **Gửi EPUB**: Đồng bộ file gốc sang Kobo.
    - **Convert & Send KEPUB**: Tự động chuyển đổi sang định dạng Kobo (.kepub.epub) trước khi gửi.
- **File Upload**: Nút "Add Ebook" cho phép tải file trực tiếp từ máy tính lên Server và đưa vào Calibre.
- **Auto-Ingest Scraper**: Tích hợp công cụ tải truyện từ link URL, tự động xử lý (Fix EPUB, Convert KEPUB) và add vào thư viện.

## 3. Đồng bộ không dây (Wireless Kobo Sync)
- **Smart Connection Card**: Thẻ thông tin kết nối thiết bị chỉ hiển thị khi có Kobo kết nối vào Port 9090, giúp giao diện gọn gàng.
- **Automated Sync**: Tự động phát hiện sách mới trong thư mục hàng chờ và đẩy sang thiết bị.
- **Kepubify Integration**: Sử dụng module Python `kepubify` để tối ưu hóa trải nghiệm đọc trên Kobo (tốc độ lật trang, thống kê chương).

## 4. Tối ưu hóa Hệ thống & Cấu trúc
- **Modular Refactoring**: Tách file `server.py` khổng lồ thành các module chuyên biệt:
    - `routes.py`: Quản lý API.
    - `libs/kobo_device.py`: Logic giao tiếp Kobo qua TCP.
    - `libs/watcher.py`: Luồng theo dõi file và auto-convert ngầm.
    - `libs/scraper_task.py`: Xử lý tải và phân tích truyện.
    - `libs/epub_fixer.py`: Sửa lỗi cấu trúc file EPUB.
- **EPUB Standard Fixer**: 
    - Đảm bảo file EPUB tuân thủ chuẩn (mimetype không nén, nằm đầu file zip).
    - Tự động sửa lỗi thiếu encoding UTF-8 trong XML để tránh lỗi font trên thiết bị.
    - Giúp tương thích tốt hơn với các Plugin Calibre (như DeDRM).

## 5. Cấu trúc thư mục hiện tại
```text
WebServer/
├── server.py           # Entry point
├── routes.py           # API Endpoints
├── libs/
│   ├── kobo_device.py  # TCP Sync Logic
│   ├── watcher.py      # Background tasks
│   ├── scraper_task.py # URL Downloader logic
│   ├── epub_fixer.py   # Zip/Encoding fixer
│   └── ...             # Other helpers
├── static/
│   ├── main.js         # Frontend logic
│   └── style.css       # UI Styling
└── templates/
    └── index.html      # Main Dashboard
```

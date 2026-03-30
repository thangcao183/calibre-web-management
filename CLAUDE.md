# UNCaGED Dashboard — Calibre Web Management

## Tổng quan
Dashboard web quản lý thư viện Calibre và đồng bộ không dây với máy đọc sách Kobo.
Hệ thống cho phép: duyệt thư viện, upload/download ebook, chỉnh sửa metadata, đồng bộ sách sang Kobo qua TCP.

## Tech Stack
- **Backend**: Python 3, Flask, Waitress (production WSGI)
- **Frontend**: Vanilla HTML/CSS/JS (Glassmorphism dark UI, SweetAlert2)
- **Database**: Calibre `metadata.db` (read-only SQLite), write qua `calibredb` CLI
- **Device Sync**: TCP socket server (port 9090) cho Kobo UNCaGED
- **Ebook Processing**: ebooklib, kepubify (Python), epub_fixer
- **Image**: Real-ESRGAN NCNN (upscale cover)

## Cấu trúc dự án
```
├── CLAUDE.md              # File này — context cho AI
├── .env / .env.example    # Cấu hình môi trường
├── requirements.txt       # Python dependencies
├── start.sh               # Script khởi động production
├── calibre-web.service    # Systemd unit file
├── nginx.conf             # Nginx reverse proxy config
│
├── src/                   # Source code chính
│   ├── server.py          # Flask app entry point (dev)
│   ├── server_prod.py     # Waitress entry point (production)
│   ├── routes.py          # Tất cả API endpoints
│   ├── kepubify.py        # EPUB → KEPUB converter
│   ├── libs/              # Business logic modules
│   │   ├── kobo_device.py # TCP sync với Kobo (port 9090)
│   │   ├── watcher.py     # Background file watcher
│   │   ├── scraper_task.py# Download truyện từ URL
│   │   ├── book_gen.py    # EPUB generator (ebooklib)
│   │   ├── epub_fixer.py  # Fix EPUB chuẩn
│   │   ├── cover_upscale.py # Upscale cover bằng Real-ESRGAN
│   │   ├── scrapefactory.py # Factory pattern cho scrapers
│   │   ├── ttc.py / ttv.py / mtc.py # Scrapers (TruyenTangCao, TruyenTienViet, MeTruyenChu)
│   │   ├── basescraper.py # Base class cho scrapers
│   │   ├── lib_types.py   # Shared data types (BookInfor)
│   │   ├── text_proc.py   # Text processing utils
│   │   ├── fonts/         # Font files cho EPUB
│   │   ├── styles/        # CSS cho EPUB
│   │   └── models/        # AI models (Real-ESRGAN)
│   ├── static/            # Frontend assets
│   │   ├── main.js        # Dashboard logic
│   │   └── style.css      # UI styling
│   └── templates/         # Jinja2 templates
│       ├── index.html     # Main dashboard
│       ├── login.html     # Login page
│       └── reader.html    # EPUB reader
│
├── docs/                  # Tài liệu kiến trúc
│   ├── COMPLETED.md       # Tính năng đã hoàn thành
│   └── implementation_plan.md # Backlog & roadmap
│
└── .agents/workflows/     # Reusable AI workflows
```

## Quy tắc quan trọng

### Code Style
- Python: dùng f-string, type hints khi có thể
- JS: vanilla, không framework
- CSS: vanilla, dark mode mặc định
- Comments: tiếng Việt hoặc tiếng Anh đều OK

### Architecture Decisions
1. **Read path**: Truy vấn trực tiếp SQLite `metadata.db` (read-only, nhanh)
2. **Write path**: Dùng `calibredb` CLI (an toàn, không gây corrupt)
3. **Không dùng** direct SQLite writes vào metadata.db (sẽ corrupt)
4. **Download flow**: URL → Scrape → EPUB only (không KEPUB) → Auto add Calibre
5. **Upload flow**: File → Duplicate check → `calibredb add`
6. **Sync flow**: Calibre → Copy file → TCP push to Kobo

### Conventions
- Tất cả API routes bắt đầu bằng `/api/`
- Calibre library mặc định: `~/Calibre Library`
- Ebook temp dir: `EBOOK/` (relative to project root)
- Entry point dev: `src/server.py`, production: `src/server_prod.py`
- Chạy từ thư mục `src/` để relative imports hoạt động

### Lưu ý khi sửa code
- Khi thêm scraper mới: kế thừa `BaseScraper`, đăng ký trong `ScraperFactory`
- Khi gọi `calibredb`: luôn dùng `--with-library ~/Calibre\ Library`
- Khi thêm route mới: đăng ký trong blueprint `api_bp` hoặc `reader_bp`
- Background tasks chạy trong daemon threads

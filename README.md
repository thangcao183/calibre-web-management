# UNCaGED Dashboard — Calibre & Kobo Management

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/framework-Flask-green.svg)

A high-performance, modern web management dashboard for your **Calibre Library** with native support for wireless **Kobo UNCaGED** sync.

---

## 🌟 Features

- **🚀 Performance-First**: Backend-side pagination and optimized SQL queries ensure smooth handling of libraries with 10,000+ books.
- **📱 Wireless Kobo Sync**: Native TCP socket server (port 9090) to sync books directly to Kobo devices running UNCaGED.
- **🖼️ AI Cover Upscale**: Automatically upscales low-resolution book covers using **Real-ESRGAN (4x-UltraSharp)**.
- **📥 One-Click Web Scraper**: Download novels directly from popular Vietnamese sites (ttc, ttv, mtc) with auto-metada extraction and Calibre ingestion.
- **📖 Embedded Reader**: Read your EPUBs directly in the browser via a sleek, dark-themed reader.
- **🛠️ Library Management**: Bulk edit metadata, manage tags, and delete books with a multi-select interface.
- **🎨 Modern UI**: Premium glassmorphism dark-mode interface built with vanilla JS and CSS.

---

## 🏗️ Tech Stack

- **Backend**: Python 3.10+, Flask, Waitress (Production WSGI)
- **Database**: SQLite (Calibre `metadata.db`) + `calibredb` CLI for writes.
- **Ebook Logic**: `ebooklib`, `kepubify` (internal port), `epub-fixer`.
- **AI Upscaling**: `torch`, `spandrel`, `PIL` (Real-ESRGAN models).
- **Frontend**: Vanilla HTML5, CSS3 (Modern Glassmorphism), ES6 JS, SweetAlert2, Bootstrap 5.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- **Calibre** must be installed and `calibredb` available in your PATH.
- `libgl1` (for OpenCV/Upscaler if using GPU).

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-repo/calibre-web-management.git
   cd calibre-web-management
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and Calibre path
   nano .env
   ```

3. **Install Dependencies & Start:**
   Using the provided bash script (automatically handles venv and requirements):
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

---

## 🏁 Production Deployment

### 1. Systemd Service
Create a background service to keep the app running:
```bash
sudo cp calibre-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable calibre-web
sudo systemctl start calibre-web
```

### 2. Nginx Reverse Proxy
Copy the provided `nginx.conf` and link it:
```bash
sudo cp nginx.conf /etc/nginx/sites-available/calibre-web
sudo ln -s /etc/nginx/sites-available/calibre-web /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 📁 Project Structure

```text
├── src/                  # Direct execution folder (cd here to run)
│   ├── server_prod.py    # Production entry point
│   ├── routes.py         # All API and Reader routes
│   ├── libs/             # Core business logic (Sync, Scrapers, AI)
│   ├── static/           # Frontend Assets (JS/CSS/Images)
│   └── templates/        # HTML Templates (Jinja2)
├── docs/                 # Architecture & Backlog
├── .agents/workflows/    # AI-assisted development workflows
├── start.sh              # Universal helper script
└── calibre-web.service   # Systemd unit file
```

---

## 📝 Important Notes

- **Read/Write Policy**: The app reads the Calibre database directly (Read-Only) for speed, but always uses `calibredb` for writing to prevent library corruption.
- **Kobo Connection**: Ensure your Kobo device and the server are on the same Wi-Fi network. The Kobo connects to the server on port `9090`.
- **Large Libraries**: If the dashboard feels slow on initial load, it's usually due to generating thumbnails. Once cached by the browser, it is extremely fast.

---

## 🤝 Contributing
For adding new scrapers or modifying the core sync logic, please refer to the documents in `/docs/`.

---

## 📜 License
MIT License - Copyright (c) 2026.

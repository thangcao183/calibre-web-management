# Calibre-Web-Automated Inspired Improvements

Based on the [Calibre-Web-Automated (CWA) project](https://github.com/crocodilestick/Calibre-Web-Automated), here are the most impactful and suitable features we can implement to improve your UNCaGED Kobo Dashboard.

## Proposed Features

### 1. Automatic Ingest & Conversion Watcher
**Concept:** Similar to CWA's Automatic Ingest and Conversion services.
**Implementation:** 
- Add a background thread in [server.py](file:///home/wolf/CODE/Python/Ebook/KOBO/WebServer/server.py) using `watchdog` (or a simple polling loop if we want to avoid new dependencies) that monitors the `EBOOK` directory for any newly added `.epub` files (like books added via SMB/FTP, outside of the web UI).
- When a new EPUB is detected, automatically trigger `kepubify.convert_to_kepub` to generate the KEPUB version.
- If the "Auto Add to Calibre" setting is enabled globally, automatically run `calibredb add` on the new files.

### 2. EPUB Fixer Service
**Concept:** Inspired by CWA's Automatic EPUB Fixer Service.
**Implementation:**
- Scraped books often have malformed HTML/XML, missing utf-8 declarations, or broken TOC (`ncx`).
- We can add an EPUB cleaning utility in [server.py](file:///home/wolf/CODE/Python/Ebook/KOBO/WebServer/server.py) (using `zipfile` and `lxml` or regex) to:
  - Add UTF-8 encoding declarations.
  - Fix invalid/missing language tags.
  - Remove empty `<img>` tags.
- Run this tool automatically on newly scraped books before saving and before KEPUB conversion.

### 3. Metadata Auto-Fetch & Enrichment
**Concept:** CWA's Automatic Metadata Fetch on Ingest.
**Implementation:**
- When an EPUB is added or scraped without full metadata, we can query an open API (like Google Books API or OpenLibrary API) to fetch high-quality covers, correct Author names, and ISBNs.
- Provide a UI button to "Refresh Metadata" for existing files.

### 4. Auto-Send to Kobo
**Concept:** CWA's Auto-Send to eReader.
**Implementation:**
- Add a toggle in the Web UI: "Auto-sync to Kobo when connected".
- If enabled, whenever the Kobo pings the server (and `books_to_sync` is empty), the server will check if there are any local `.kepub.epub` files that are *not* on the device, and automatically queue them for sync without needing manual clicks on the Web UI.

## User Review Required

> [!IMPORTANT]
> Please review the proposed features above. Which of these features would you like me to implement first?
> 
> 1. Auto-Ingest & Conversion (Background Watcher)
> 2. EPUB Fixer (Clean up html/xml inside EPUBs)
> 3. Metadata Auto-Fetch (Update covers & authorship)
> 4. Auto-Send to Kobo (Sync without clicks)
> 5. Everything!

## Proposed File Changes

#### [MODIFY] server.py
- Add background watcher loop for `EBOOK` directory.
- Add EPUB fix logic.
- Add Auto-sync logic in the event loop.

#### [MODIFY] templates/index.html & static/main.js
- Add settings toggles for "Auto-Sync to Kobo" and "Auto-Convert added EPUBs".

## Verification Plan
### Automated Tests
- Drop a normal `.epub` file into `EBOOK` and verify it automatically gets a `.kepub.epub` generated.
- View terminal logs to ensure background threads run without exhausting resources.
### Manual Verification
- Connect the Kobo and verify auto-sync behavior if enabled.

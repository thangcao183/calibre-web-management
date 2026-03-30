# UNCaGED Improvement Backlog

This file is the single source of truth for planned improvements to the dashboard. It is organized as a prioritized backlog so feature work can be tracked, implemented, and reviewed without scattering ideas across multiple docs.

## Research Conclusions

### Current architecture
- Read operations currently query Calibre's `metadata.db` directly in read-only mode, which is fast and appropriate for library browsing.
- Write operations currently rely on `calibredb` for add/remove flows, which is the safest active path in this repo today.
- Kobo sync, background scraping, EPUB fixing, and KEPUB conversion already have a working foundation in the existing codebase.

### Write-path decision
- `Do not use`: direct SQLite writes to `metadata.db`.
  - Reason: Calibre maintains library logic above raw SQLite. Writing directly risks corrupting metadata, book paths, or library invariants.
- `Use now`: `calibredb`.
  - Reason: stable, explicit, already wired into add/remove flows.
- `Prepare gradually`: Calibre Python DB API.
  - Candidate direction: `from calibre.library import db; db(path).new_api`
  - Goal: introduce an adapter layer so write operations can eventually move away from shelling out to `calibredb`.
- `Not a write-path replacement`: Calibre Content server.
  - Useful for browsing, reading, search, remote access, and integration ideas.
  - Not the primary candidate for add/remove/update write operations in this app.

### Runtime feasibility note
- Environment check result: Python cannot currently import `calibre` in this runtime (`ModuleNotFoundError: No module named 'calibre'`).
- Conclusion: keep `calibredb` as the default write engine for now and treat DB API work as a staged migration path.

### Official references
- Calibre DB API: https://manual.calibre-ebook.com/sv/db_api.html
- calibredb CLI: https://manual.calibre-ebook.com/zh_HK/generated/en/calibredb.html
- Content server: https://manual.calibre-ebook.com/server.html
- Editing metadata: https://manual.calibre-ebook.com/metadata.html
- Virtual libraries: https://manual.calibre-ebook.com/virtual_libraries.html
- GUI search and saved searches: https://manual.calibre-ebook.com/gui.html

## Backlog Structure

Each item tracks:
- Goal
- Value
- Difficulty
- Dependencies
- Status
- Acceptance criteria

Status values:
- `todo`
- `in-progress`
- `blocked`
- `done`

Difficulty values:
- `S`
- `M`
- `L`

## Now

### 1. Finish Auto-Sync Toggle
- Goal: complete the existing auto-sync flow already hinted by the UI and watcher.
- Value: high, because most of the groundwork already exists.
- Difficulty: `S`
- Dependencies: current `kobo_server.state`, watcher loop, frontend checkbox.
- Status: `todo`
- Implementation notes:
  - Add `/api/toggle_auto_sync` backend route.
  - Persist toggle in memory first; persistence can come later.
  - Ensure SSE broadcasts the updated `auto_sync` state.
- Acceptance criteria:
  - Toggling the checkbox updates backend state immediately.
  - Watcher respects the toggle without server restart.
  - UI stays in sync after reconnects and refreshes.

### 2. Fix Reader Route and Template Wiring
- Goal: make the existing EPUB reader usable end to end.
- Value: high, because the reader UI is already built but the route is not passing template context.
- Difficulty: `S`
- Dependencies: Calibre metadata lookup, EPUB endpoint, current `reader.html`.
- Status: `todo`
- Implementation notes:
  - Replace `send_file` with `render_template`.
  - Pass `book_id` and `title` into the template.
  - Handle missing EPUB gracefully.
- Acceptance criteria:
  - Clicking `Read` opens a working reader.
  - Reader title and book ID render correctly.
  - Books without EPUB show a clear error state.

### 3. Add Task Status and Progress for Download / Scrape / Add
- Goal: align the dashboard with the actual state of background work.
- Value: high, because current UX reports success too early.
- Difficulty: `M`
- Dependencies: SSE status stream, scraper task lifecycle, UI status components.
- Status: `todo`
- Implementation notes:
  - Extend shared state with task phase, message, and error fields.
  - Publish `queued`, `running`, `success`, and `error` states.
  - Stop showing download completion before background work truly finishes.
- Acceptance criteria:
  - Users can see whether a task is queued, running, done, or failed.
  - Failed scrape or add operations show a clear error message.
  - Progress display no longer implies completion prematurely.

### 4. Move Library Pagination and Search to Backend
- Goal: stop loading the full library into the browser for every refresh.
- Value: high for scale and responsiveness.
- Difficulty: `M`
- Dependencies: Calibre book listing query, frontend book grid, pagination UI.
- Status: `todo`
- Implementation notes:
  - Support `page`, `limit`, `search`, and sort parameters in the API.
  - Return `total`, `page`, and `pages`.
  - Keep client rendering simple and driven by backend results.
- Acceptance criteria:
  - Dashboard no longer fetches a hard-coded giant page.
  - Search works against title/author from the server.
  - Pagination stays responsive with large libraries.

### 5. Multi-file Upload
- Goal: let users add multiple EPUB/KEPUB files in one action.
- Value: high for real-world import workflows.
- Difficulty: `M`
- Dependencies: upload endpoint, frontend file input, `calibredb add`.
- Status: `todo`
- Implementation notes:
  - Allow selecting multiple files in the input.
  - Upload remains `add to Calibre only`, with no automatic Kobo sync.
  - Aggregate per-file success/failure feedback.
- Acceptance criteria:
  - Multiple files can be uploaded in one action.
  - UI reports how many succeeded and which failed.
  - Library refreshes correctly after batch upload.

### 6. Duplicate Detection Before Add
- Goal: reduce accidental duplicate imports.
- Value: high for upload and scrape flows.
- Difficulty: `M`
- Dependencies: Calibre metadata lookup, upload flow, potential hash or metadata heuristics.
- Status: `todo`
- Implementation notes:
  - Start with metadata-based heuristics (title/author).
  - Upgrade to file hash or Calibre-native duplicate checks later if needed.
  - Warn first; hard blocking can be configurable later.
- Acceptance criteria:
  - Likely duplicates trigger a clear warning before add.
  - Users can still choose to continue if policy allows.
  - Duplicate checks do not noticeably slow normal uploads.

### 7. SweetAlert2 Standardization
- Goal: remove remaining browser-native confirms and centralize modal behavior.
- Value: medium, but improves consistency and polish immediately.
- Difficulty: `S`
- Dependencies: frontend action flows in `static/main.js`.
- Status: `done`
- Implementation notes:
  - Added shared helpers for `confirmAction`, `showError`, and `showSuccess`.
  - Replaced the remaining native `confirm()` flow for single-book deletion.
  - Standardized upload, delete, sync, download, and disconnect feedback around SweetAlert2.
- Acceptance criteria:
  - No browser-native `alert()` or `confirm()` remains in dashboard actions.
  - Destructive actions use consistent confirmation UI.
  - Errors and success messages use a single shared pattern.

## Next

### 8. Metadata Edit and Bulk Edit
- Goal: manage book metadata directly from the dashboard.
- Value: high for library maintenance.
- Difficulty: `L`
- Dependencies: write adapter, Calibre metadata operations, UI forms.
- Status: `todo`
- Implementation notes:
  - Start with single-book edit: title, author, tags, series, publisher, description, cover.
  - Add bulk edit after single-book flow is stable.
- Acceptance criteria:
  - Metadata changes persist correctly in Calibre.
  - Cover changes are reflected in the dashboard.
  - Bulk edit supports at least one shared field safely.

### 9. Saved Filters and Virtual-Library-Like Views
- Goal: help users manage large libraries with reusable views.
- Value: medium-high once library size grows.
- Difficulty: `M`
- Dependencies: backend search, frontend filter UI, local persistence or server storage.
- Status: `todo`
- Implementation notes:
  - Start with saved filter presets and search shortcuts.
  - Do not attempt a full clone of Calibre virtual libraries in v1.
- Acceptance criteria:
  - Users can save and re-apply named filter presets.
  - Presets support at least title, author, tags, and format filters.

### 10. Audit Log and Log Viewer
- Goal: make failures visible without watching the terminal.
- Value: medium-high for remote operation and support.
- Difficulty: `M`
- Dependencies: task status model, backend logging strategy, UI panel.
- Status: `todo`
- Implementation notes:
  - Show recent upload, scrape, delete, and sync activity.
  - Include timestamps, status, and error summaries.
- Acceptance criteria:
  - Users can inspect recent operational history from the dashboard.
  - Failed actions retain a readable error record.

### 11. Search, Sort, and Library Controls Expansion
- Goal: expose more of Calibre's library-management power in the dashboard.
- Value: medium-high.
- Difficulty: `M`
- Dependencies: backend search API, richer query options, UI controls.
- Status: `todo`
- Implementation notes:
  - Add sort by title, author, date added, and available formats.
  - Add tag and format filters as follow-up to backend pagination.
- Acceptance criteria:
  - Sort order is consistent across pages.
  - Users can filter by more than free-text search.

### 12. Metadata Enrichment and Refresh
- Goal: improve incomplete books after upload or scrape.
- Value: medium.
- Difficulty: `L`
- Dependencies: metadata providers, cover refresh flow, write adapter.
- Status: `todo`
- Implementation notes:
  - Explore OpenLibrary or Google Books as optional enrichment sources.
  - Keep this opt-in and explicit per book or per batch.
- Acceptance criteria:
  - Users can trigger a metadata refresh from the UI.
  - Updated metadata and cover are reflected in Calibre and in the dashboard.

## Later

### 13. Write Adapter Abstraction for Calibre Operations
- Goal: isolate write operations behind a stable service interface.
- Value: high strategically, because it unlocks a future move away from direct shell calls.
- Difficulty: `M`
- Dependencies: existing add/remove flows, future metadata edit work.
- Status: `todo`
- Implementation notes:
  - Define service methods such as `add_book`, `remove_book`, `update_metadata`, `set_cover`, and `search_books`.
  - Default adapter calls `calibredb`.
  - Add an optional adapter for Calibre DB API when runtime support exists.
- Acceptance criteria:
  - Route handlers stop calling `calibredb` directly.
  - Swapping the write backend requires changing only the adapter wiring.

### 14. Calibre DB API Feasibility Check
- Goal: confirm whether DB API migration is practical in deployment environments.
- Value: high for long-term maintainability.
- Difficulty: `M`
- Dependencies: adapter abstraction, runtime packaging strategy, test library.
- Status: `todo`
- Implementation notes:
  - Re-run import checks in the target runtime, not just local dev.
  - If import works, build a proof of concept for add/remove/update metadata on a test library.
  - If import does not work, document packaging blockers and keep `calibredb`.
- Acceptance criteria:
  - There is a written go/no-go decision for DB API migration.
  - The repo documents any packaging or deployment constraints clearly.

### 15. Custom Fields Roadmap
- Goal: prepare room for richer library workflows.
- Value: medium.
- Difficulty: `L`
- Dependencies: metadata edit support, UI forms, write adapter.
- Status: `todo`
- Implementation notes:
  - Plan for series, rating, tags, and future custom columns.
  - Potential use cases: source tracking, sync priority, reading status, internal labels.
- Acceptance criteria:
  - Backlog includes a defined first set of custom fields to support.
  - UI and backend plans account for extensibility.

### 16. Extra Files and Attachments
- Goal: support supplementary files associated with a book.
- Value: medium.
- Difficulty: `L`
- Dependencies: Calibre support model, file storage rules, UI attachment flow.
- Status: `todo`
- Implementation notes:
  - Explore attaching notes, alternate covers, or supplementary files.
  - Keep this behind a clear scope definition to avoid accidental file sprawl.
- Acceptance criteria:
  - There is a documented attachment model before implementation starts.
  - Attached files are visible and manageable from the dashboard.

### 17. Content-Server-Inspired Remote Features
- Goal: borrow the best remote-library ideas from Calibre's content server without replacing the app.
- Value: medium.
- Difficulty: `L`
- Dependencies: auth, reverse proxy guidance, reader improvements, backend search.
- Status: `todo`
- Implementation notes:
  - Consider better remote reading, safer reverse-proxy deployment guidance, and mobile-friendly browsing patterns.
  - Treat content server as a feature reference, not the core write engine.
- Acceptance criteria:
  - Remote-access improvements are documented and implementable in phases.
  - Security notes accompany any public-network feature.

## Tracking Notes

### Product assumptions
- Upload remains `add to Calibre only`, with no automatic Kobo sync.
- SweetAlert2 is the standard modal layer for dashboard actions.
- `calibredb` remains the default write path in the near term.
- Long-term write-path replacement, if any, should target the Calibre Python DB API rather than direct SQLite or the content server.

### Follow-up engineering checks
- Confirm whether deployment images can install or expose the `calibre` Python package.
- Decide whether background task state should live only in memory or also be persisted.
- Decide whether saved filters should be per-browser, per-user, or stored server-side once authentication expands.

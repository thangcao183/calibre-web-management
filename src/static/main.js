// ── State ──
let currentPage = 1;
let currentBookId = null;
let currentSearch = '';
let currentFormatFilter = '';
let allBooks = [];
let filteredBooks = [];
const PAGE_SIZE = 24;
let bookModal = null;
let isSelectMode = false;
let selectedIds = new Set();
let lastTaskStatus = 'idle';
let currentBookDetail = null;
let modalRequestToken = 0;
const SAVED_FILTERS_KEY = 'saved_calibre_filters_v1';

// ── SweetAlert helpers ──
function showSuccess(title, text = '') {
    return Swal.fire({
        icon: 'success',
        title,
        text,
        timer: 1800,
        showConfirmButton: false
    });
}

function showError(title, text = 'Something went wrong.') {
    return Swal.fire({
        icon: 'error',
        title,
        text,
        confirmButtonText: 'OK'
    });
}

async function confirmAction(title, text, confirmButtonText = 'Confirm') {
    const result = await Swal.fire({
        title,
        text,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        confirmButtonText,
        cancelButtonText: 'Cancel'
    });
    return result.isConfirmed;
}

// ── Bootstrap Modal helper ──
function getModal() {
    if (!bookModal) bookModal = new bootstrap.Modal(document.getElementById('bookModal'));
    return bookModal;
}

function stripHtml(html) {
    return (html || '').replace(/<[^>]*>?/gm, ' ').replace(/\s+/g, ' ').trim();
}

function getSavedFilters() {
    try {
        return JSON.parse(localStorage.getItem(SAVED_FILTERS_KEY) || '[]');
    } catch (e) {
        return [];
    }
}

function setSavedFilters(filters) {
    localStorage.setItem(SAVED_FILTERS_KEY, JSON.stringify(filters));
}

function renderSavedFilterOptions() {
    const select = document.getElementById('saved-filter-select');
    if (!select) return;

    const filters = getSavedFilters();
    select.innerHTML = '<option value="">Saved filters</option>';
    filters.forEach(filter => {
        const option = document.createElement('option');
        option.value = filter.name;
        option.textContent = filter.name;
        select.appendChild(option);
    });
}

function renderTaskHistory(history) {
    const list = document.getElementById('task-history-list');
    if (!list) return;

    if (!history?.length) {
        list.innerHTML = '<div class="text-secondary text-center py-3">No activity yet.</div>';
        return;
    }

    list.innerHTML = history.map(item => `
        <div class="task-history-item is-${item.status || 'info'}">
            <div class="task-history-time">${item.time || '--:--:--'}</div>
            <div class="task-history-kind">${item.kind || 'task'}</div>
            <div class="task-history-message">${item.message || ''}</div>
        </div>
    `).join('');
}

// ── Status Update (called by SSE) ──
function handleStatusUpdate(data) {
    const dot = document.getElementById('connection-indicator');
    const txt = document.getElementById('status-text');
    const card = document.getElementById('connection-card');

    if (data.status === 'Connected') {
        if (card) card.style.display = 'block';
        dot.classList.add('connected');
        txt.textContent = 'Connected';
        txt.className = 'small fw-semibold text-success';

        document.getElementById('client-ip').textContent = data.client_address || 'Unknown';
        document.getElementById('client-ip').className = 'ms-2 fw-semibold';
        document.getElementById('last-ping').textContent = data.last_ping || '--:--:--';
        document.getElementById('last-ping').className = 'ms-2 fw-semibold';
        document.getElementById('device-type').textContent = data.device_info || 'Kobo UNCaGED';
        document.getElementById('device-type').className = 'ms-2 fw-semibold';
        document.getElementById('instruction-box').style.opacity = '0.4';
        document.getElementById('eject-btn').style.display = 'inline-block';
    } else {
        if (card) card.style.display = 'none';
        dot.classList.remove('connected');
        txt.textContent = 'Listening (Port 9090)';
        txt.className = 'small fw-semibold text-light';
        document.getElementById('instruction-box').style.opacity = '1';
        document.getElementById('eject-btn').style.display = 'none';
    }

    if (data.auto_sync !== undefined) {
        const cb = document.getElementById('auto-sync-cb');
        if (cb && document.activeElement !== cb) cb.checked = data.auto_sync;
    }

    renderTaskHistory(data.task_history || []);

    // Download progress
    const pc = document.getElementById('download-progress-container');
    const pb = document.getElementById('download-progress-bar');
    const msg = document.getElementById('download-message');
    const btn = document.getElementById('download-btn');
    const taskStatus = data.task_status || 'idle';
    const taskMessage = data.task_message || '';
    const taskError = data.task_error || '';
    const queueCount = Number(data.download_queue_count || 0);
    const queueBadge = document.getElementById('download-queue-badge');

    if (queueBadge) {
        if (queueCount > 0) {
            queueBadge.style.display = 'inline-flex';
            queueBadge.textContent = `Queue: ${queueCount}`;
        } else {
            queueBadge.style.display = 'none';
            queueBadge.textContent = 'Queue: 0';
        }
    }

    if (data.download_progress > 0) {
        if (pc) pc.style.display = 'flex';
        if (pb) pb.style.width = data.download_progress + '%';
    } else {
        if (pc) pc.style.display = 'none';
        if (pb) pb.style.width = '0%';
    }

    if (msg) {
        if (taskStatus === 'queued' || taskStatus === 'running') {
            const suffix = queueCount > 0 ? ` (${queueCount} waiting)` : '';
            msg.textContent = (taskMessage || 'Processing...') + suffix;
            msg.className = 'small mt-2 fw-medium text-primary';
        } else if (taskStatus === 'success') {
            msg.textContent = taskMessage || 'Completed successfully.';
            msg.className = 'small mt-2 fw-medium text-success';
        } else if (taskStatus === 'error') {
            msg.textContent = taskError ? `Error: ${taskError}` : (taskMessage || 'Task failed.');
            msg.className = 'small mt-2 fw-medium text-danger';
        }
    }

    if (btn) btn.disabled = false;

    if (taskStatus !== lastTaskStatus) {
        if (taskStatus === 'success') {
            fetchCalibreBooks();
            showSuccess('Download complete', taskMessage || 'Book processing finished.');
        } else if (taskStatus === 'error') {
            showError('Task failed', taskError || taskMessage || 'Background task failed.');
        }
        lastTaskStatus = taskStatus;
    }

}

// ── Search / Filter ──
function onSearchInput() {
    currentSearch = document.getElementById('calibre-search').value.trim().toLowerCase();
    currentPage = 1;
    fetchCalibreBooks(); // Gọi trực tiếp API
}

function onFormatFilterChange() {
    currentFormatFilter = document.getElementById('calibre-format-filter').value;
    currentPage = 1;
    fetchCalibreBooks(); // Gọi trực tiếp API
}

function updateActiveFilterBadge() {
    const badge = document.getElementById('active-filter-badge');
    if (!badge) return;

    const active = [];
    if (currentSearch) active.push(`Search: ${currentSearch}`);
    if (currentFormatFilter) active.push(`Format: ${currentFormatFilter.toUpperCase()}`);

    if (!active.length) {
        badge.style.display = 'none';
        badge.textContent = '';
        return;
    }

    badge.style.display = 'inline-block';
    badge.textContent = active.join(' | ');
}

function clearFilters() {
    currentSearch = '';
    currentFormatFilter = '';
    currentPage = 1;
    document.getElementById('calibre-search').value = '';
    document.getElementById('calibre-format-filter').value = '';
    document.getElementById('saved-filter-select').value = '';
    fetchCalibreBooks();
}

function applyFilterAndRender() {
    // Không còn lọc client-side nữa, chỉ fetch lại
    fetchCalibreBooks();
}

async function saveCurrentFilter() {
    const query = document.getElementById('calibre-search').value.trim();
    const format = document.getElementById('calibre-format-filter').value;
    if (!query && !format) {
        showError('Cannot save filter', 'Enter a search query or choose a format first.');
        return;
    }

    const result = await Swal.fire({
        title: 'Save Filter',
        input: 'text',
        inputLabel: 'Filter name',
        inputPlaceholder: 'For example: Romance, New books, Vietnamese authors',
        showCancelButton: true,
        inputValidator: (value) => {
            if (!value.trim()) return 'Filter name is required';
        }
    });

    if (!result.isConfirmed || !result.value) return;

    const name = result.value.trim();
    const filters = getSavedFilters().filter(item => item.name !== name);
    filters.push({ name, query, format });
    filters.sort((a, b) => a.name.localeCompare(b.name));
    setSavedFilters(filters);
    renderSavedFilterOptions();
    document.getElementById('saved-filter-select').value = name;
    showSuccess('Filter saved', `Saved "${name}".`);
}

function applySavedFilter(name) {
    if (!name) return;
    const filter = getSavedFilters().find(item => item.name === name);
    if (!filter) return;
    document.getElementById('calibre-search').value = filter.query;
    document.getElementById('calibre-format-filter').value = filter.format || '';
    currentSearch = (filter.query || '').toLowerCase();
    currentFormatFilter = filter.format || '';
    currentPage = 1;
    fetchCalibreBooks();
}

async function deleteSavedFilter() {
    const select = document.getElementById('saved-filter-select');
    const name = select?.value;
    if (!name) {
        showError('No filter selected', 'Choose a saved filter to delete.');
        return;
    }

    const confirmed = await confirmAction('Delete saved filter?', `Remove the filter "${name}"?`, 'Delete');
    if (!confirmed) return;

    const filters = getSavedFilters().filter(item => item.name !== name);
    setSavedFilters(filters);
    renderSavedFilterOptions();
    showSuccess('Filter deleted', `Removed "${name}".`);
}

// ── Render books ──
function renderCalibreBooks(data) {
    const list = document.getElementById('calibre-book-list');
    list.innerHTML = '';

    const books = data.books || [];
    const totalCount = data.total_count || 0;
    const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

    const label = currentSearch ? `${totalCount} results` : `${totalCount} books`;
    document.getElementById('calibre-count').textContent = label;
    document.getElementById('calibre-page-info').textContent = `${currentPage} / ${totalPages}`;
    document.getElementById('calibre-prev').disabled = currentPage <= 1;
    document.getElementById('calibre-next').disabled = currentPage >= totalPages;

    if (!books.length) {
        list.innerHTML = currentSearch || currentFormatFilter
            ? '<div class="library-empty-state"><strong>No books match the current filters.</strong>Try clearing search text or choosing a different format.</div>'
            : '<div class="library-empty-state"><strong>No books in the library yet.</strong>Add or download books to get started.</div>';
        return;
    }

    books.forEach(book => {
        const cover = book.has_cover ? `/api/calibre/cover/${book.id}` : '/static/placeholder.jpg';
        const te = book.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const ae = book.author.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const fmts = book.formats.join(',');
        const isSelected = selectedIds.has(book.id);

        list.innerHTML += `
            <div class="calibre-book ${isSelected ? 'selected' : ''}" onclick="handleBookClick(event, ${book.id},'${te}','${ae}','${fmts}')">
                <div class="book-checkbox"></div>
                <img src="${cover}" class="calibre-cover" loading="lazy" alt="" onerror="this.src='/static/placeholder.jpg'">
                <div class="calibre-title" title="${te}">${book.title}</div>
                <div class="calibre-author">${book.author}</div>
            </div>`;
    });
}

function handleBookClick(e, id, te, ae, fmts) {
    if (isSelectMode) {
        if (selectedIds.has(id)) selectedIds.delete(id);
        else selectedIds.add(id);
        updateSelectionUI();
        renderCalibreBooks();
    } else {
        openModal(id, te, ae, fmts);
    }
}

function toggleSelectMode() {
    isSelectMode = !isSelectMode;
    selectedIds.clear();
    const btn = document.getElementById('btn-batch-select');
    const list = document.getElementById('calibre-book-list');
    const bar = document.getElementById('selection-bar');

    if (isSelectMode) {
        btn.innerHTML = '<i class="bi bi-x-lg"></i> Cancel';
        btn.classList.replace('btn-outline-info', 'btn-info');
        list.classList.add('select-mode');
        bar.style.display = 'block';
    } else {
        btn.innerHTML = '<i class="bi bi-check2-square"></i> Select';
        btn.classList.replace('btn-info', 'btn-outline-info');
        list.classList.remove('select-mode');
        bar.style.display = 'none';
    }
    updateSelectionUI();
    renderCalibreBooks();
}

function updateSelectionUI() {
    document.getElementById('selected-count').textContent = selectedIds.size;
}

async function bulkDelete() {
    if (selectedIds.size === 0) return;
    const confirmed = await confirmAction(
        'Delete multiple books?',
        `You are about to delete ${selectedIds.size} books permanently.`,
        'Yes, delete them!'
    );

    if (confirmed) {
        Swal.fire({ title: 'Deleting...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
        try {
            const res = await fetch('/api/calibre_bulk_delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ book_ids: Array.from(selectedIds) })
            });
            const data = await res.json();
            if (data.success) {
                await showSuccess('Deleted!', `${data.count} books removed.`);
                toggleSelectMode();
                fetchCalibreBooks();
            } else {
                showError('Delete failed', data.error);
            }
        } catch (e) {
            showError('Delete failed', 'Failed to delete books.');
        }
    }
}

async function bulkEditMetadata() {
    if (selectedIds.size === 0) return;

    const result = await Swal.fire({
        title: `Bulk Edit ${selectedIds.size} Books`,
        html: `
            <input id="swal-bulk-author" class="swal2-input" placeholder="New author (leave blank to keep current)">
            <input id="swal-bulk-publisher" class="swal2-input" placeholder="New publisher (leave blank to keep current)">
            <input id="swal-bulk-series" class="swal2-input" placeholder="New series (leave blank to keep current)">
            <input id="swal-bulk-tags" class="swal2-input" placeholder="New tags (comma separated, leave blank to keep current)">
            <div class="swal-clear-row">
                <label><input type="checkbox" id="swal-clear-publisher"> Clear publisher</label>
                <label><input type="checkbox" id="swal-clear-series"> Clear series</label>
                <label><input type="checkbox" id="swal-clear-tags"> Clear tags</label>
                <label><input type="checkbox" id="swal-clear-description"> Clear description</label>
            </div>
            <textarea id="swal-bulk-description" class="swal2-textarea" placeholder="New description (leave blank to keep current)"></textarea>
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Apply',
        preConfirm: () => {
            const author = document.getElementById('swal-bulk-author').value.trim();
            const publisher = document.getElementById('swal-bulk-publisher').value.trim();
            const series = document.getElementById('swal-bulk-series').value.trim();
            const tags = document.getElementById('swal-bulk-tags').value.split(',').map(tag => tag.trim()).filter(Boolean);
            const description = document.getElementById('swal-bulk-description').value.trim();
            const clearPublisher = document.getElementById('swal-clear-publisher').checked;
            const clearSeries = document.getElementById('swal-clear-series').checked;
            const clearTags = document.getElementById('swal-clear-tags').checked;
            const clearDescription = document.getElementById('swal-clear-description').checked;
            if (!author && !publisher && !series && tags.length === 0 && !description && !clearPublisher && !clearSeries && !clearTags && !clearDescription) {
                Swal.showValidationMessage('Enter at least one field to update');
                return false;
            }
            return { author, publisher, series, tags, description, clearPublisher, clearSeries, clearTags, clearDescription };
        }
    });

    if (!result.isConfirmed || !result.value) return;

    try {
        const res = await fetch('/api/calibre_bulk_update_metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                book_ids: Array.from(selectedIds),
                author: result.value.author,
                publisher: result.value.publisher,
                series: result.value.series,
                tags: result.value.tags,
                description: result.value.description,
                clear_publisher: result.value.clearPublisher,
                clear_series: result.value.clearSeries,
                clear_tags: result.value.clearTags,
                clear_description: result.value.clearDescription
            })
        });
        const data = await res.json();
        if (!data.success) {
            showError('Bulk edit failed', data.errors?.[0] || data.error || 'Failed to update metadata.');
            return;
        }

        await fetchCalibreBooks();
        if (data.errors?.length) {
            showError('Bulk edit partially completed', `${data.count} book(s) updated. First error: ${data.errors[0]}`);
        } else {
            showSuccess('Bulk edit complete', `${data.count} book(s) updated.`);
        }
        toggleSelectMode();
    } catch (e) {
        showError('Bulk edit failed', 'Failed to update metadata.');
    }
}

function changeCalibrePage(dir) { currentPage += dir; fetchCalibreBooks(); }

// ── Fetch all books ──
// ── Fetch books with pagination ──
async function fetchCalibreBooks() {
    try {
        const queryParams = new URLSearchParams({
            page: currentPage,
            limit: PAGE_SIZE,
            search: currentSearch,
            format: currentFormatFilter
        });
        
        const res = await fetch(`/api/calibre_books?${queryParams.toString()}`);
        const data = await res.json();
        
        if (!data.success) {
            document.getElementById('calibre-book-list').innerHTML = `<p class="text-secondary">${data.error}</p>`;
            return;
        }

        updateActiveFilterBadge();
        renderCalibreBooks(data);
    } catch (e) {
        document.getElementById('calibre-book-list').innerHTML = '<p class="text-secondary">Error loading library.</p>';
    }
}

// ── Upload ──
function uploadEbook(input) {
    if (!input.files?.length) return;
    const fd = new FormData();
    Array.from(input.files).forEach(file => fd.append('file', file));
    document.getElementById('calibre-count').textContent = `Uploading ${input.files.length} file(s)...`;
    fetch('/api/upload', { method: 'POST', body: fd })
        .then(async r => ({ status: r.status, data: await r.json() }))
        .then(({ data }) => {
            if (data.success) {
                const failed = (data.results || []).filter(item => !item.success);
                fetchCalibreBooks();
                if (failed.length) {
                    showError(
                        'Upload partially completed',
                        `${data.count} file(s) added, ${failed.length} failed. First error: ${failed[0].error}`
                    );
                } else {
                    showSuccess('Upload complete', `${data.count} file(s) added to Calibre.`);
                }
            } else {
                showError('Upload failed', data.error);
            }
        })
        .finally(() => input.value = '');
}

// ── Modal ──
async function openModal(id, title, author, fmtsStr) {
    const requestToken = ++modalRequestToken;
    currentBookId = id;
    currentBookDetail = {
        id,
        title,
        author,
        description: '',
        formats: fmtsStr ? fmtsStr.split(',').filter(Boolean) : [],
        publisher: '',
        series: '',
        tags: []
    };
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-author').textContent = author;
    document.getElementById('modal-cover').src = `/api/calibre/cover/${id}`;
    document.getElementById('modal-cover').onerror = function () { this.src = '/static/placeholder.jpg'; };
    document.getElementById('modal-formats').innerHTML = fmtsStr
        ? fmtsStr.split(',').filter(Boolean).map(fmt => `<span class="modal-format-badge">${fmt}</span>`).join('')
        : '<span class="text-secondary">No formats</span>';
    document.getElementById('modal-path').textContent = 'Path: Loading...';
    document.getElementById('modal-publisher').textContent = 'Publisher: Loading...';
    document.getElementById('modal-series').textContent = 'Series: Loading...';
    document.getElementById('modal-tags').innerHTML = '<span class="text-secondary">Tags: Loading...</span>';
    document.getElementById('modal-description').textContent = 'Loading metadata...';

    const fmts = fmtsStr ? fmtsStr.split(',') : [];
    const hasEpub = fmts.includes('epub');
    const hasKepub = fmts.includes('kepub');

    document.getElementById('btn-send-epub').style.display = hasEpub ? '' : 'none';
    document.getElementById('btn-send-kepub').style.display = (hasEpub || hasKepub) ? '' : 'none';
    document.getElementById('btn-send-kepub').textContent = hasKepub ? 'Send KEPUB' : 'Convert & Send KEPUB';

    getModal().show();

    try {
        const res = await fetch(`/api/calibre/book/${id}`);
        const data = await res.json();
        if (requestToken !== modalRequestToken || currentBookId !== id) return;
        if (!data.success) {
            document.getElementById('modal-path').textContent = 'Path: --';
            document.getElementById('modal-publisher').textContent = 'Publisher: --';
            document.getElementById('modal-series').textContent = 'Series: --';
            document.getElementById('modal-tags').innerHTML = '<span class="text-secondary">Tags: --</span>';
            document.getElementById('modal-description').textContent = data.error || 'Failed to load metadata.';
            return;
        }

        const book = data.book;
        const cleanDescription = stripHtml(book.description);
        currentBookDetail = {
            id: book.id,
            title: book.title,
            author: book.author,
            description: cleanDescription,
            formats: book.formats || [],
            path: book.path || '',
            publisher: book.publisher || '',
            series: book.series || '',
            tags: book.tags || []
        };
        document.getElementById('modal-formats').innerHTML = book.formats?.length
            ? book.formats.map(fmt => `<span class="modal-format-badge">${fmt}</span>`).join('')
            : '<span class="text-secondary">No formats</span>';
        document.getElementById('modal-path').textContent = book.path ? `Path: ${book.path}` : 'Path: --';
        document.getElementById('modal-publisher').textContent = book.publisher ? `Publisher: ${book.publisher}` : 'Publisher: --';
        document.getElementById('modal-series').textContent = book.series ? `Series: ${book.series}` : 'Series: --';
        document.getElementById('modal-tags').innerHTML = book.tags?.length
            ? book.tags.map(tag => `<span class="modal-format-badge">${tag}</span>`).join('')
            : '<span class="text-secondary">Tags: --</span>';
        document.getElementById('modal-description').textContent = cleanDescription || 'No description available.';
    } catch (e) {
        if (requestToken !== modalRequestToken || currentBookId !== id) return;
        document.getElementById('modal-path').textContent = 'Path: --';
        document.getElementById('modal-publisher').textContent = 'Publisher: --';
        document.getElementById('modal-series').textContent = 'Series: --';
        document.getElementById('modal-tags').innerHTML = '<span class="text-secondary">Tags: --</span>';
        document.getElementById('modal-description').textContent = 'Failed to load metadata.';
    }
}

function closeModal() {
    getModal().hide();
    modalRequestToken += 1;
    currentBookId = null;
    currentBookDetail = null;
    const coverInput = document.getElementById('cover-upload-input');
    if (coverInput) coverInput.value = '';
}

function refreshCoverImages(bookId) {
    const cacheBust = `?t=${Date.now()}`;
    const modalCover = document.getElementById('modal-cover');
    if (modalCover && currentBookId === bookId) {
        modalCover.src = `/api/calibre/cover/${bookId}${cacheBust}`;
    }
}

function uploadCover(input) {
    if (!currentBookId || !input.files?.length) return;

    const fd = new FormData();
    fd.append('book_id', String(currentBookId));
    fd.append('cover', input.files[0]);

    fetch('/api/calibre_update_cover', { method: 'POST', body: fd })
        .then(async r => ({ status: r.status, data: await r.json() }))
        .then(async ({ data }) => {
            if (!data.success) {
                showError('Cover update failed', data.error);
                return;
            }

            refreshCoverImages(currentBookId);
            await fetchCalibreBooks();
            showSuccess('Cover updated', 'Book cover has been saved.');
        })
        .catch(() => showError('Cover update failed', 'Failed to upload cover image.'))
        .finally(() => {
            input.value = '';
        });
}

async function editMetadata() {
    if (!currentBookId || !currentBookDetail) return;

    const result = await Swal.fire({
        title: 'Edit Metadata',
        html: `
            <input id="swal-title" class="swal2-input" placeholder="Title">
            <input id="swal-author" class="swal2-input" placeholder="Author">
            <input id="swal-publisher" class="swal2-input" placeholder="Publisher">
            <input id="swal-series" class="swal2-input" placeholder="Series">
            <input id="swal-tags" class="swal2-input" placeholder="Tags (comma separated)">
            <div class="swal-clear-row">
                <label><input type="checkbox" id="swal-clear-publisher"> Clear publisher</label>
                <label><input type="checkbox" id="swal-clear-series"> Clear series</label>
                <label><input type="checkbox" id="swal-clear-tags"> Clear tags</label>
                <label><input type="checkbox" id="swal-clear-description"> Clear description</label>
            </div>
            <textarea id="swal-description" class="swal2-textarea" placeholder="Description"></textarea>
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Save',
        didOpen: () => {
            document.getElementById('swal-title').value = currentBookDetail.title || '';
            document.getElementById('swal-author').value = currentBookDetail.author || '';
            document.getElementById('swal-publisher').value = currentBookDetail.publisher || '';
            document.getElementById('swal-series').value = currentBookDetail.series || '';
            document.getElementById('swal-tags').value = (currentBookDetail.tags || []).join(', ');
            document.getElementById('swal-description').value = currentBookDetail.description || '';
        },
        preConfirm: () => {
            const title = document.getElementById('swal-title').value.trim();
            const author = document.getElementById('swal-author').value.trim();
            const publisher = document.getElementById('swal-publisher').value.trim();
            const series = document.getElementById('swal-series').value.trim();
            const tags = document.getElementById('swal-tags').value.split(',').map(tag => tag.trim()).filter(Boolean);
            const description = document.getElementById('swal-description').value.trim();
            const clearPublisher = document.getElementById('swal-clear-publisher').checked;
            const clearSeries = document.getElementById('swal-clear-series').checked;
            const clearTags = document.getElementById('swal-clear-tags').checked;
            const clearDescription = document.getElementById('swal-clear-description').checked;

            if (!title) {
                Swal.showValidationMessage('Title is required');
                return false;
            }

            return { title, author, publisher, series, tags, description, clearPublisher, clearSeries, clearTags, clearDescription };
        }
    });

    if (!result.isConfirmed || !result.value) return;

    try {
        const res = await fetch('/api/calibre_update_metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                book_id: currentBookId,
                title: result.value.title,
                author: result.value.author,
                publisher: result.value.publisher,
                series: result.value.series,
                tags: result.value.tags,
                description: result.value.description,
                clear_publisher: result.value.clearPublisher,
                clear_series: result.value.clearSeries,
                clear_tags: result.value.clearTags,
                clear_description: result.value.clearDescription
            })
        });
        const data = await res.json();
        if (!data.success) {
            showError('Metadata update failed', data.error);
            return;
        }

        showSuccess('Metadata updated', 'Book metadata has been saved.');
        await fetchCalibreBooks();
        await openModal(currentBookId, result.value.title, result.value.author, (currentBookDetail.formats || []).join(','));
    } catch (e) {
        showError('Metadata update failed', 'Failed to save metadata.');
    }
}

// ── Sync / Delete / Disconnect ──
function syncCalibre(convertKepub) {
    if (!currentBookId) return;
    const btn = event.target;
    const orig = btn.textContent;
    btn.textContent = 'Sending...';
    btn.disabled = true;
    fetch('/api/sync_calibre', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: currentBookId, convert_kepub: convertKepub })
    })
    .then(r => r.json())
    .then(d => { 
        if (d.success) { 
            showSuccess('Queued', 'Book has been queued for sync!');
            closeModal(); 
        } else {
            showError('Sync failed', d.error);
        }
    })
    .finally(() => { btn.textContent = orig; btn.disabled = false; });
}

async function deleteCalibreBook() {
    if (!currentBookId) return;
    const confirmed = await confirmAction(
        'Delete this book?',
        'This will permanently remove the book from Calibre.',
        'Delete'
    );
    if (!confirmed) return;

    fetch('/api/calibre_delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_id: currentBookId })
    })
    .then(r => r.json())
    .then(d => { 
        if (d.success) { 
            fetchCalibreBooks(); 
            closeModal(); 
        } else {
            showError('Delete failed', d.error);
        }
    })
    .catch(() => showError('Delete failed', 'Failed to delete the selected book.'));
}

function disconnectKobo() {
    fetch('/api/disconnect', { method: 'POST' })
        .then(r => r.json())
        .then(d => { 
            if (d.success) showSuccess('Ejected', 'Đã ngắt kết nối! Kobo sẽ nạp lại sách.');
            else showError('Disconnect failed', d.error || 'Failed to disconnect Kobo.');
        });
}

function toggleAutoSync(cb) {
    fetch('/api/toggle_auto_sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_sync: cb.checked })
    })
    .then(r => r.json())
    .then(d => { if (!d.success) cb.checked = !cb.checked; })
    .catch(() => cb.checked = !cb.checked);
}

// ── Download ──
async function downloadBook() {
    const url = document.getElementById('download-url').value.trim();
    const msg = document.getElementById('download-message');
    const btn = document.getElementById('download-btn');

    if (!url) { msg.textContent = 'Please enter a URL.'; msg.className = 'small mt-2 fw-medium text-danger'; return; }

    msg.textContent = 'Queueing download...';
    msg.className = 'small mt-2 fw-medium text-primary';
    btn.disabled = true;

    try {
        const addToCalibre = document.getElementById('add-calibre').checked;
        const res = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, add_to_calibre: addToCalibre })
        });
        const data = await res.json();
        if (data.success) {
            const queueText = data.queue_position ? `Queued at position ${data.queue_position}.` : 'Download queued.';
            msg.textContent = data.message || queueText;
            msg.className = 'small mt-2 fw-medium text-primary';
            document.getElementById('download-url').value = '';
        } else {
            msg.textContent = 'Error: ' + data.error;
            msg.className = 'small mt-2 fw-medium text-danger';
            showError('Download failed', data.error);
        }
    } catch (e) {
        msg.textContent = 'Network error.';
        msg.className = 'small mt-2 fw-medium text-danger';
        showError('Download failed', 'Network error.');
    } finally {
        btn.disabled = false;
    }
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    renderSavedFilterOptions();
    fetchCalibreBooks();

    // SSE — server pushes status only when it changes
    const evtSource = new EventSource('/api/status/stream');
    evtSource.onopen = () => {
        const status = document.getElementById('status-text');
        if (status && status.textContent === 'Connecting...') {
            status.textContent = 'Listening (Port 9090)';
            status.className = 'small fw-semibold text-light';
        }
    };
    evtSource.onmessage = (e) => {
        try { handleStatusUpdate(JSON.parse(e.data)); } catch(err) {}
    };
    evtSource.onerror = () => {
        // SSE disconnected — show offline
        document.getElementById('status-text').textContent = 'Server Offline';
        document.getElementById('status-text').className = 'small fw-semibold text-danger';
    };
});

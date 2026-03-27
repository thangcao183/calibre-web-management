// ── State ──
let currentPage = 1;
let currentBookId = null;
let currentSearch = '';
let allBooks = [];
let filteredBooks = [];
const PAGE_SIZE = 24;
let bookModal = null;
let isSelectMode = false;
let selectedIds = new Set();

// ── Bootstrap Modal helper ──
function getModal() {
    if (!bookModal) bookModal = new bootstrap.Modal(document.getElementById('bookModal'));
    return bookModal;
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

    // Download progress
    const pc = document.getElementById('download-progress-container');
    const pb = document.getElementById('download-progress-bar');
    const msg = document.getElementById('download-message');
    if (data.download_progress > 0) {
        if (pc) pc.style.display = 'flex';
        if (pb) pb.style.width = data.download_progress + '%';
        if (msg && msg.textContent.includes('Downloading'))
            msg.textContent = `Downloading... ${data.download_progress}%`;
    } else {
        if (pc) pc.style.display = 'none';
        if (pb) pb.style.width = '0%';
    }
}

// ── Search / Filter ──
function onSearchInput() {
    currentSearch = document.getElementById('calibre-search').value.trim().toLowerCase();
    currentPage = 1;
    applyFilterAndRender();
}

function applyFilterAndRender() {
    filteredBooks = currentSearch
        ? allBooks.filter(b => b.title.toLowerCase().includes(currentSearch) || b.author.toLowerCase().includes(currentSearch))
        : allBooks;
    renderCalibreBooks();
}

// ── Render books ──
function renderCalibreBooks() {
    const list = document.getElementById('calibre-book-list');
    list.innerHTML = '';

    const total = Math.max(1, Math.ceil(filteredBooks.length / PAGE_SIZE));
    if (currentPage > total) currentPage = total;

    const start = (currentPage - 1) * PAGE_SIZE;
    const page = filteredBooks.slice(start, start + PAGE_SIZE);

    const label = currentSearch ? `${filteredBooks.length} kết quả` : `${allBooks.length} books`;
    document.getElementById('calibre-count').textContent = label;
    document.getElementById('calibre-page-info').textContent = `${currentPage} / ${total}`;
    document.getElementById('calibre-prev').disabled = currentPage <= 1;
    document.getElementById('calibre-next').disabled = currentPage >= total;

    if (!page.length) {
        list.innerHTML = '<p class="text-secondary text-center py-3">Không tìm thấy kết quả.</p>';
        return;
    }

    page.forEach(book => {
        const cover = book.has_cover ? `/api/calibre/cover/${book.id}` : '/static/placeholder.jpg';
        const te = book.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const ae = book.author.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const fmts = book.formats.join(',');
        const isSelected = selectedIds.has(book.id);
        
        // Strip HTML if any (Calibre comments usually have HTML)
        const rawDesc = book.description || "";
        const cleanDesc = rawDesc.replace(/<[^>]*>?/gm, ' ').substring(0, 300) + (rawDesc.length > 300 ? '...' : '');

        list.innerHTML += `
            <div class="calibre-book ${isSelected ? 'selected' : ''}" onclick="handleBookClick(event, ${book.id},'${te}','${ae}','${fmts}')">
                <div class="book-checkbox"></div>
                <div class="calibre-desc">
                    <div class="calibre-desc-title">${book.title}</div>
                    <div>${cleanDesc}</div>
                </div>
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
    const confirm = await Swal.fire({
        title: 'Delete multiple books?',
        text: `You are about to delete ${selectedIds.size} books permanently.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        confirmButtonText: 'Yes, delete them!'
    });

    if (confirm.isConfirmed) {
        Swal.fire({ title: 'Deleting...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
        try {
            const res = await fetch('/api/calibre_bulk_delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ book_ids: Array.from(selectedIds) })
            });
            const data = await res.json();
            if (data.success) {
                await Swal.fire({ icon: 'success', title: 'Deleted!', text: `${data.count} books removed.`, timer: 1500 });
                toggleSelectMode();
                fetchCalibreBooks();
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: data.error });
            }
        } catch (e) {
            Swal.fire({ icon: 'error', title: 'Error', text: 'Failed to delete books.' });
        }
    }
}

function changeCalibrePage(dir) { currentPage += dir; renderCalibreBooks(); }

// ── Fetch all books ──
async function fetchCalibreBooks() {
    try {
        const res = await fetch('/api/calibre_books?page=1&limit=9999');
        const data = await res.json();
        if (!data.success) {
            document.getElementById('calibre-book-list').innerHTML = `<p class="text-secondary">${data.error}</p>`;
            return;
        }
        allBooks = data.books;
        currentPage = 1;
        applyFilterAndRender();
    } catch (e) {
        document.getElementById('calibre-book-list').innerHTML = '<p class="text-secondary">Error loading library.</p>';
    }
}

// ── Upload ──
function uploadEbook(input) {
    if (!input.files?.length) return;
    const fd = new FormData();
    fd.append('file', input.files[0]);
    document.getElementById('calibre-count').textContent = 'Uploading...';
    fetch('/api/upload', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(d => { 
            if (d.success) fetchCalibreBooks(); 
            else Swal.fire({ icon: 'error', title: 'Upload Failed', text: d.error }); 
        })
        .finally(() => input.value = '');
}

// ── Modal ──
function openModal(id, title, author, fmtsStr) {
    currentBookId = id;
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-author').textContent = author;

    const fmts = fmtsStr ? fmtsStr.split(',') : [];
    const hasEpub = fmts.includes('epub');
    const hasKepub = fmts.includes('kepub');

    document.getElementById('btn-send-epub').style.display = hasEpub ? '' : 'none';
    document.getElementById('btn-send-kepub').style.display = (hasEpub || hasKepub) ? '' : 'none';
    document.getElementById('btn-send-kepub').textContent = hasKepub ? 'Send KEPUB' : 'Convert & Send KEPUB';

    getModal().show();
}

function closeModal() { getModal().hide(); currentBookId = null; }

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
            Swal.fire({ icon: 'success', title: 'Success', text: 'Queued for sync!', timer: 2000, showConfirmButton: false }); 
            closeModal(); 
        } else {
            Swal.fire({ icon: 'error', title: 'Sync Error', text: d.error });
        }
    })
    .finally(() => { btn.textContent = orig; btn.disabled = false; });
}

function deleteCalibreBook() {
    if (!currentBookId || !confirm('Delete this book from Calibre?')) return;
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
            Swal.fire({ icon: 'error', title: 'Delete Error', text: d.error });
        }
    });
}

function disconnectKobo() {
    fetch('/api/disconnect', { method: 'POST' })
        .then(r => r.json())
        .then(d => { 
            if (d.success) Swal.fire({ icon: 'success', title: 'Ejected', text: 'Đã ngắt kết nối! Kobo sẽ nạp lại sách.' }); 
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

    msg.textContent = 'Downloading and generating KEPUB...';
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
            msg.textContent = 'Done! ' + (data.filename || '');
            msg.className = 'small mt-2 fw-medium text-success';
            document.getElementById('download-url').value = '';
            fetchCalibreBooks();
        } else {
            msg.textContent = 'Error: ' + data.error;
            msg.className = 'small mt-2 fw-medium text-danger';
        }
    } catch (e) {
        msg.textContent = 'Network error.';
        msg.className = 'small mt-2 fw-medium text-danger';
    } finally {
        btn.disabled = false;
    }
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    fetchCalibreBooks();

    // SSE — server pushes status only when it changes
    const evtSource = new EventSource('/api/status/stream');
    evtSource.onmessage = (e) => {
        try { handleStatusUpdate(JSON.parse(e.data)); } catch(err) {}
    };
    evtSource.onerror = () => {
        // SSE disconnected — show offline
        document.getElementById('status-text').textContent = 'Server Offline';
        document.getElementById('status-text').className = 'small fw-semibold text-danger';
    };
});

function showLibrarySetupBanner(message) {
    const banner = document.getElementById('library-setup-banner');
    const messageEl = document.getElementById('library-setup-message');
    if (!banner) return;

    banner.classList.remove('d-none');
    if (messageEl && message) messageEl.textContent = message;
}

function hideLibrarySetupBanner() {
    const banner = document.getElementById('library-setup-banner');
    if (!banner) return;
    banner.classList.add('d-none');
}

async function setupCalibreLibrary() {
    let statusData = null;
    try {
        const statusRes = await fetch('/api/library/status');
        statusData = await statusRes.json();
    } catch (e) {
        // Continue with defaults if status endpoint is temporarily unavailable.
    }

    const defaultDir = statusData?.configured_library_dir || '/home/wolf/Calibre Library';
    const result = await Swal.fire({
        title: 'Setup Calibre Library',
        html: `
            <div class="text-start small mb-2">If an existing library is found, it will be attached automatically.</div>
            <input id="swal-library-dir" class="swal2-input" placeholder="Library path" value="${defaultDir}">
            <label class="swal2-checkbox" style="display:flex;align-items:center;justify-content:flex-start;gap:8px;">
                <input id="swal-auto-detect-lib" type="checkbox" checked>
                <span>Auto-detect existing metadata.db before creating new</span>
            </label>
        `,
        showCancelButton: true,
        confirmButtonText: 'Apply',
        preConfirm: () => {
            const path = document.getElementById('swal-library-dir')?.value?.trim() || '';
            const autoDetect = Boolean(document.getElementById('swal-auto-detect-lib')?.checked);
            if (!path) {
                Swal.showValidationMessage('Library path is required');
                return false;
            }
            return { path, autoDetect };
        }
    });

    if (!result.isConfirmed || !result.value) return;

    const setupBtn = document.getElementById('btn-init-library');
    if (setupBtn) setupBtn.disabled = true;

    try {
        const res = await fetch('/api/library/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                library_dir: result.value.path,
                auto_detect: result.value.autoDetect
            })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || `HTTP ${res.status}`);
        }

        hideLibrarySetupBanner();
        await showSuccess('Library ready', data.message || `Using ${data.library_dir}`);
        currentPage = 1;
        fetchCalibreBooks();
    } catch (e) {
        showLibrarySetupBanner('Library setup failed. Please verify path and permissions, then retry.');
        showError('Library setup failed', e.message || 'Could not initialize Calibre library.');
    } finally {
        if (setupBtn) setupBtn.disabled = false;
    }
}

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
            <div class="calibre-book ${isSelected ? 'selected' : ''}" data-book-id="${book.id}" data-book-title="${te}" data-book-author="${ae}" data-book-fmts="${fmts}">
                <div class="book-checkbox"></div>
                <img src="${cover}" class="calibre-cover" loading="lazy" alt="">
                <div class="calibre-title" title="${te}">${book.title}</div>
                <div class="calibre-author">${book.author}</div>
            </div>`;
    });

    list.querySelectorAll('.calibre-cover').forEach((img) => {
        img.addEventListener('error', () => {
            img.src = '/static/placeholder.jpg';
        }, { once: true });
    });
}

function handleBookClick(e, id, te, ae, fmts) {
    if (isSelectMode) {
        if (selectedIds.has(id)) selectedIds.delete(id);
        else selectedIds.add(id);
        updateSelectionUI();
        fetchCalibreBooks();
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
    fetchCalibreBooks();
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

function changeCalibrePage(dir) {
    currentPage += dir;
    fetchCalibreBooks();
}

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
            const message = String(data.error || 'Library error');
            if (message.toLowerCase().includes('library not found')) {
                showLibrarySetupBanner('No metadata.db detected. Auto-detect an existing library or create a new one.');
                document.getElementById('calibre-book-list').innerHTML = '<div class="library-empty-state"><strong>Calibre library not found.</strong>Use the Setup Library button to continue.</div>';
            } else {
                document.getElementById('calibre-book-list').innerHTML = `<p class="text-secondary">${message}</p>`;
            }
            return;
        }

        hideLibrarySetupBanner();
        updateActiveFilterBadge();
        renderCalibreBooks(data);
    } catch (e) {
        document.getElementById('calibre-book-list').innerHTML = '<p class="text-secondary">Error loading library.</p>';
    }
}

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
                    showError('Upload partially completed', `${data.count} file(s) added, ${failed.length} failed. First error: ${failed[0].error}`);
                } else {
                    showSuccess('Upload complete', `${data.count} file(s) added to Calibre.`);
                }
            } else {
                showError('Upload failed', data.error);
            }
        })
        .finally(() => {
            input.value = '';
        });
}

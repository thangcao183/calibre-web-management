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

    const updateSendButtons = (formats) => {
        const normalized = (formats || []).map((fmt) => String(fmt || '').toLowerCase());
        const hasSendable = normalized.some((fmt) => ['epub', 'kepub', 'cbz', 'mobi', 'pdf'].includes(fmt));
        const hasEpub = normalized.includes('epub');
        const hasKepub = normalized.includes('kepub');

        const sendEbookBtn = document.getElementById('btn-send-ebook');
        const sendKepubBtn = document.getElementById('btn-send-kepub');

        if (sendEbookBtn) {
            sendEbookBtn.style.display = hasSendable ? '' : 'none';
            sendEbookBtn.innerHTML = '<i class="bi bi-send me-1"></i>Send Ebook';
        }
        if (sendKepubBtn) {
            sendKepubBtn.style.display = (hasEpub || hasKepub) ? '' : 'none';
            sendKepubBtn.textContent = hasKepub ? 'Send KEPUB' : 'Convert & Send KEPUB';
        }
    };

    const fmts = fmtsStr ? fmtsStr.split(',') : [];
    updateSendButtons(fmts);

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
        updateSendButtons(book.formats || []);
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

function syncCalibre(convertKepub, triggerBtn = null) {
    if (!currentBookId) return;
    const btn = triggerBtn || document.getElementById(convertKepub ? 'btn-send-kepub' : 'btn-send-ebook');
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
            const formatLabel = d.format ? ` (${d.format})` : '';
            showSuccess('Queued', `Book has been queued for sync${formatLabel}!`);
            closeModal();
        } else {
            showError('Sync failed', d.error);
        }
    })
    .finally(() => {
        btn.textContent = orig;
        btn.disabled = false;
    });
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
            if (d.success) showSuccess('Ejected', 'Da ngat ket noi! Kobo se nap lai sach.');
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
    .then(d => {
        if (!d.success) cb.checked = !cb.checked;
    })
    .catch(() => {
        cb.checked = !cb.checked;
    });
}

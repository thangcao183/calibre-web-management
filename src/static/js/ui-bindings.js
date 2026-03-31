function initSidebarNavigation() {
    const navLinks = Array.from(document.querySelectorAll('.cwa-nav-item[data-section]'));
    if (!navLinks.length) return;

    const sectionMap = navLinks
        .map((link) => {
            const sectionId = link.dataset.section;
            const sectionEl = document.getElementById(sectionId);
            return sectionEl ? { link, sectionEl } : null;
        })
        .filter(Boolean);

    if (!sectionMap.length) return;

    navLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const sectionId = link.dataset.section;
            const target = document.getElementById(sectionId);
            if (!target) return;

            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            navLinks.forEach((item) => item.classList.remove('active'));
            link.classList.add('active');
        });
    });

}

function bindUiEvents() {
    const calibreSearch = document.getElementById('calibre-search');
    if (calibreSearch) calibreSearch.addEventListener('input', onSearchInput);

    const formatFilter = document.getElementById('calibre-format-filter');
    if (formatFilter) formatFilter.addEventListener('change', onFormatFilterChange);

    const clearFiltersBtn = document.getElementById('btn-clear-filters');
    if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', clearFilters);

    const savedFilterSelect = document.getElementById('saved-filter-select');
    if (savedFilterSelect) {
        savedFilterSelect.addEventListener('change', (e) => applySavedFilter(e.target.value));
    }

    const saveFilterBtn = document.getElementById('btn-save-filter');
    if (saveFilterBtn) saveFilterBtn.addEventListener('click', saveCurrentFilter);

    const deleteFilterBtn = document.getElementById('btn-delete-filter');
    if (deleteFilterBtn) deleteFilterBtn.addEventListener('click', deleteSavedFilter);

    const autoSyncCb = document.getElementById('auto-sync-cb');
    if (autoSyncCb) autoSyncCb.addEventListener('change', () => toggleAutoSync(autoSyncCb));

    const uploadInput = document.getElementById('upload-ebook-file');
    if (uploadInput) uploadInput.addEventListener('change', () => uploadEbook(uploadInput));

    const uploadTriggerBtn = document.getElementById('btn-upload-trigger');
    if (uploadTriggerBtn && uploadInput) {
        uploadTriggerBtn.addEventListener('click', () => uploadInput.click());
    }

    const selectModeBtn = document.getElementById('btn-batch-select');
    if (selectModeBtn) selectModeBtn.addEventListener('click', toggleSelectMode);

    const prevBtn = document.getElementById('calibre-prev');
    if (prevBtn) prevBtn.addEventListener('click', () => changeCalibrePage(-1));

    const nextBtn = document.getElementById('calibre-next');
    if (nextBtn) nextBtn.addEventListener('click', () => changeCalibrePage(1));

    const refreshBtn = document.getElementById('btn-refresh-books');
    if (refreshBtn) refreshBtn.addEventListener('click', fetchCalibreBooks);

    const settingsRefreshBtn = document.getElementById('btn-settings-refresh');
    if (settingsRefreshBtn) settingsRefreshBtn.addEventListener('click', fetchCalibreBooks);

    const setupLibraryBtn = document.getElementById('btn-init-library');
    if (setupLibraryBtn) setupLibraryBtn.addEventListener('click', setupCalibreLibrary);

    const settingsLibraryBtn = document.getElementById('btn-settings-library');
    if (settingsLibraryBtn) settingsLibraryBtn.addEventListener('click', setupCalibreLibrary);

    const ejectBtn = document.getElementById('eject-btn');
    if (ejectBtn) ejectBtn.addEventListener('click', disconnectKobo);

    const settingsDisconnectBtn = document.getElementById('btn-settings-disconnect');
    if (settingsDisconnectBtn) settingsDisconnectBtn.addEventListener('click', disconnectKobo);

    const densityCompactBtn = document.getElementById('btn-density-compact');
    if (densityCompactBtn) densityCompactBtn.addEventListener('click', () => applyDensityPreset('compact'));

    const densityComfortableBtn = document.getElementById('btn-density-comfortable');
    if (densityComfortableBtn) densityComfortableBtn.addEventListener('click', () => applyDensityPreset('comfortable'));

    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) downloadBtn.addEventListener('click', downloadBook);

    const coverInput = document.getElementById('cover-upload-input');
    if (coverInput) coverInput.addEventListener('change', () => uploadCover(coverInput));

    const changeCoverBtn = document.getElementById('btn-change-cover');
    if (changeCoverBtn && coverInput) changeCoverBtn.addEventListener('click', () => coverInput.click());

    const editMetadataBtn = document.getElementById('btn-edit-metadata');
    if (editMetadataBtn) editMetadataBtn.addEventListener('click', editMetadata);

    const readBtn = document.getElementById('btn-read');
    if (readBtn) {
        readBtn.addEventListener('click', () => {
            if (!currentBookId) return;
            window.open('/reader/' + currentBookId, '_blank');
        });
    }

    const downloadBookBtn = document.getElementById('btn-download-book');
    if (downloadBookBtn) {
        downloadBookBtn.addEventListener('click', () => {
            if (!currentBookId) return;
            const title = currentBookDetail?.title || '';
            downloadCalibreBook(currentBookId, title);
        });
    }

    const sendEbookBtn = document.getElementById('btn-send-ebook');
    if (sendEbookBtn) sendEbookBtn.addEventListener('click', () => syncCalibre(false, sendEbookBtn));

    const sendKepubBtn = document.getElementById('btn-send-kepub');
    if (sendKepubBtn) sendKepubBtn.addEventListener('click', () => syncCalibre(true, sendKepubBtn));

    const deleteBookBtn = document.getElementById('btn-delete-book');
    if (deleteBookBtn) deleteBookBtn.addEventListener('click', deleteCalibreBook);

    const bulkEditBtn = document.getElementById('btn-bulk-edit');
    if (bulkEditBtn) bulkEditBtn.addEventListener('click', bulkEditMetadata);

    const selectCancelBtn = document.getElementById('btn-select-cancel');
    if (selectCancelBtn) selectCancelBtn.addEventListener('click', toggleSelectMode);

    const bulkDeleteBtn = document.getElementById('btn-bulk-delete');
    if (bulkDeleteBtn) bulkDeleteBtn.addEventListener('click', bulkDelete);

    const bookList = document.getElementById('calibre-book-list');
    if (bookList) {
        bookList.addEventListener('click', (event) => {
            const card = event.target.closest('.calibre-book');
            if (!card || !bookList.contains(card)) return;
            const id = Number(card.dataset.bookId || 0);
            const title = card.dataset.bookTitle || '';
            const author = card.dataset.bookAuthor || '';
            const fmts = card.dataset.bookFmts || '';
            if (id) handleBookClick(event, id, title, author, fmts);
        });
    }

    const queueList = document.getElementById('download-queue-list');
    if (queueList) {
        queueList.addEventListener('click', (event) => {
            const cancelBtn = event.target.closest('.queue-cancel-btn');
            if (!cancelBtn) return;
            const queueId = cancelBtn.dataset.queueId;
            if (queueId) cancelQueuedDownload(queueId);
        });
    }

    initSidebarNavigation();
    initDensityPreset();
}

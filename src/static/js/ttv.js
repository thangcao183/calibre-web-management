// TTV Browser - DB-powered search with sort & detail modal
(function () {
    const searchInput = document.getElementById('ttv-search-input');
    const statusSelect = document.getElementById('ttv-status-select');
    const tagSelect = document.getElementById('ttv-tag-select');
    const sortSelect = document.getElementById('ttv-sort-select');
    const resultsContainer = document.getElementById('ttv-results-container');
    const dbCountBadge = document.getElementById('ttv-db-count');
    const syncStatusEl = document.getElementById('ttv-sync-status');
    const btnSync = document.getElementById('btn-ttv-sync');

    if (!searchInput || !resultsContainer) return;

    // Load tags on init
    const loadTags = async () => {
        try {
            const res = await fetch('/api/ttv/tags');
            const data = await res.json();
            if (data.success && data.tags) {
                // Clear existing except first
                tagSelect.innerHTML = '<option value="none">Tất cả thể loại</option>';
                data.tags.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = t.name;
                    tagSelect.appendChild(opt);
                });
            }
        } catch (e) { console.error('Load tags error:', e); }
    };
    loadTags();

    // Keep last fetched stories for detail modal
    let lastStories = [];

    // Search handler
    const doSearch = async () => {
        const query = searchInput.value.trim();
        const finish = statusSelect.value;
        const tag = tagSelect.value;
        const sort = sortSelect.value;

        resultsContainer.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Đang tìm kiếm...</div></div>';

        try {
            const params = new URLSearchParams();
            if (query) params.append('query', query);
            if (finish && finish !== 'none') params.append('finish', finish);
            if (tag && tag !== 'none') params.append('tag', tag);
            params.append('sort', sort);
            params.append('limit', '200');

            const response = await fetch(`/api/ttv/search?${params.toString()}`);
            const data = await response.json();

            if (!data.success) {
                resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Lỗi không xác định'}</div>`;
                return;
            }

            if (!data.stories || data.stories.length === 0) {
                resultsContainer.innerHTML = '<div class="text-secondary text-center py-4">Không tìm thấy truyện nào.</div>';
                return;
            }

            lastStories = data.stories;
            renderStories(data.stories);
        } catch (err) {
            console.error('TTV Search Error:', err);
            resultsContainer.innerHTML = `<div class="alert alert-danger">Lỗi: ${err.message}</div>`;
        }
    };

    const renderStories = (stories) => {
        let html = `<div class="small text-secondary mb-2">Tìm thấy ${stories.length} truyện</div>`;
        html += '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">';
        stories.forEach((story, idx) => {
            const coverUrl = story.cover_url || '/static/placeholder.jpg';
            html += `
            <div class="col">
                <div class="card h-100 bg-dark border-secondary ttv-story-card" data-story-idx="${idx}" role="button" style="cursor:pointer; transition: border-color 0.2s;">
                    <div class="row g-0 h-100">
                        <div class="col-4 p-2">
                            <img src="${coverUrl}" class="img-fluid rounded" alt="${story.name}" style="object-fit: cover; height: 100%; max-height: 160px; width: 100%;" onerror="this.src='/static/placeholder.jpg'">
                        </div>
                        <div class="col-8">
                            <div class="card-body p-2 d-flex flex-column h-100">
                                <h6 class="card-title text-truncate mb-1" title="${story.name}">${story.name}</h6>
                                ${story.china_name ? `<p class="card-text small text-muted mb-1" style="font-size:0.7rem;">${story.china_name}</p>` : ''}
                                <p class="card-text small text-secondary mb-1"><i class="bi bi-person me-1"></i>${story.author}</p>
                                <p class="card-text small mb-1">
                                    <span class="badge bg-secondary">${story.count_chapter} chương</span>
                                    <span class="badge ${story.finish === '1' ? 'bg-success' : 'bg-info'}">${story.finish === '1' ? 'Hoàn thành' : 'Đang ra'}</span>
                                    ${story.avg_rate ? `<span class="badge bg-warning text-dark">★ ${story.avg_rate}</span>` : ''}
                                </p>
                                <div class="mt-auto">
                                    <button class="btn btn-sm btn-primary w-100 btn-ttv-download" data-story-idx="${idx}">
                                        <i class="bi bi-download me-1"></i> Download
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        });
        html += '</div>';
        resultsContainer.innerHTML = html;

        // Click on card → open detail modal
        document.querySelectorAll('.ttv-story-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't open modal if user clicked the download button
                if (e.target.closest('.btn-ttv-download')) return;
                const idx = parseInt(card.getAttribute('data-story-idx'));
                openDetailModal(lastStories[idx]);
            });
        });

        // Download buttons
        document.querySelectorAll('.btn-ttv-download').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.getAttribute('data-story-idx'));
                const story = lastStories[idx];
                downloadStory(story, btn);
            });
        });
    };

    // ── Detail Modal ──
    const openDetailModal = (story) => {
        if (!story) return;
        const coverUrl = story.cover_url || '/static/placeholder.jpg';

        document.getElementById('ttv-modal-title').textContent = story.name;
        document.getElementById('ttv-modal-cover').src = coverUrl;
        document.getElementById('ttv-modal-author').textContent = story.author;
        document.getElementById('ttv-modal-china-name').textContent = story.china_name || '';

        // Badges
        let badges = `
            <span class="badge bg-secondary">${story.count_chapter} chương</span>
            <span class="badge ${story.finish === '1' ? 'bg-success' : 'bg-info'}">${story.finish === '1' ? 'Hoàn thành' : 'Đang ra'}</span>
        `;
        if (story.avg_rate) badges += `<span class="badge bg-warning text-dark">★ ${story.avg_rate}</span>`;
        if (story.nominated_month) badges += `<span class="badge bg-primary">Đề cử: ${story.nominated_month}</span>`;
        if (story.convert_month) badges += `<span class="badge bg-info text-dark">Convert: ${story.convert_month}</span>`;
        if (story.time_fix) badges += `<span class="badge bg-dark border border-secondary">Cập nhật: ${story.time_fix}</span>`;
        document.getElementById('ttv-modal-badges').innerHTML = badges;

        // Description
        const desc = story.description ? story.description.replace(/\r\n/g, '<br>').replace(/\n/g, '<br>') : 'Không có mô tả.';
        document.getElementById('ttv-modal-desc').innerHTML = desc;

        // Download button in modal
        const modalDlBtn = document.getElementById('ttv-modal-download-btn');
        modalDlBtn.className = 'btn btn-primary btn-sm';
        modalDlBtn.innerHTML = '<i class="bi bi-download me-1"></i> Download EPUB';
        modalDlBtn.disabled = false;
        modalDlBtn.onclick = () => downloadStory(story, modalDlBtn);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('ttvDetailModal'));
        modal.show();
    };

    // ── Download ──
    const downloadStory = async (story, btnElement) => {
        const coverUrl = story.cover_url || '/static/placeholder.jpg';
        const originalHtml = btnElement.innerHTML;
        btnElement.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Đang xếp hàng...';
        btnElement.disabled = true;

        try {
            const response = await fetch('/api/ttv/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_story: story.id,
                    title: story.name,
                    author: story.author,
                    cover_url: coverUrl,
                    description: story.description || '',
                    tags: story.category ? String(story.category).split(',').map(s => s.trim()) : []
                })
            });
            const data = await response.json();

            if (data.success) {
                btnElement.classList.replace('btn-primary', 'btn-success');
                btnElement.innerHTML = '<i class="bi bi-check-circle me-1"></i> Đã xếp hàng';
                if (typeof Swal !== 'undefined') {
                    Swal.fire({ icon: 'success', title: 'Đã thêm vào hàng đợi', text: `"${story.name}" đang được tải.`, timer: 2000, showConfirmButton: false, toast: true, position: 'top-end' });
                }
            } else {
                btnElement.innerHTML = originalHtml;
                btnElement.disabled = false;
                alert('Lỗi: ' + (data.error || 'Không xác định'));
            }
        } catch (err) {
            console.error('TTV Download Error:', err);
            btnElement.innerHTML = originalHtml;
            btnElement.disabled = false;
            if (typeof Swal !== 'undefined') {
                Swal.fire({ icon: 'error', title: 'Lỗi tải truyện', text: err.message });
            }
        }
    };

    // ── Sync ──
    let syncPollInterval = null;

    const pollSyncStatus = async () => {
        try {
            const res = await fetch('/api/ttv/sync/status');
            const status = await res.json();
            dbCountBadge.textContent = `${status.total_stories || 0} truyện`;

            if (status.running) {
                syncStatusEl.style.display = 'block';
                syncStatusEl.innerHTML = `<i class="bi bi-arrow-repeat spin me-1"></i> ${status.progress || 'Đang đồng bộ...'}`;
                btnSync.disabled = true;
                btnSync.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Đang sync...';
            } else {
                btnSync.disabled = false;
                btnSync.innerHTML = '<i class="bi bi-arrow-repeat"></i> Sync DB';

                if (status.error) {
                    syncStatusEl.style.display = 'block';
                    syncStatusEl.innerHTML = `<i class="bi bi-exclamation-triangle text-danger me-1"></i> Lỗi: ${status.error}`;
                } else if (status.last_sync) {
                    syncStatusEl.style.display = 'block';
                    const dt = new Date(status.last_sync);
                    syncStatusEl.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i> Đồng bộ lần cuối: ${dt.toLocaleString('vi-VN')} · ${status.total_stories} truyện`;
                } else {
                    syncStatusEl.style.display = 'none';
                }

                if (syncPollInterval) {
                    clearInterval(syncPollInterval);
                    syncPollInterval = null;
                }
            }
        } catch (e) {
            console.error('Sync status error:', e);
        }
    };

    btnSync.addEventListener('click', async () => {
        try {
            btnSync.disabled = true;
            btnSync.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Đang bắt đầu...';
            await fetch('/api/ttv/sync', { method: 'POST' });
            syncPollInterval = setInterval(pollSyncStatus, 3000);
            pollSyncStatus();
        } catch (e) {
            console.error('Sync start error:', e);
            btnSync.disabled = false;
            btnSync.innerHTML = '<i class="bi bi-arrow-repeat"></i> Sync DB';
        }
    });

    // Event listeners
    document.getElementById('btn-ttv-search').addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') doSearch(); });

    // On load: check sync status
    pollSyncStatus();
})();

// TTV Browser - DB-powered search
(function () {
    const searchInput = document.getElementById('ttv-search-input');
    const statusSelect = document.getElementById('ttv-status-select');
    const resultsContainer = document.getElementById('ttv-results-container');
    const dbCountBadge = document.getElementById('ttv-db-count');
    const syncStatusEl = document.getElementById('ttv-sync-status');
    const btnSync = document.getElementById('btn-ttv-sync');

    if (!searchInput || !resultsContainer) return;

    // Search handler
    const doSearch = async () => {
        const query = searchInput.value.trim();
        const finish = statusSelect.value;

        resultsContainer.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Đang tìm kiếm...</div></div>';

        try {
            const params = new URLSearchParams();
            if (query) params.append('query', query);
            if (finish && finish !== 'none') params.append('finish', finish);
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

            renderStories(data.stories);
        } catch (err) {
            console.error('TTV Search Error:', err);
            resultsContainer.innerHTML = `<div class="alert alert-danger">Lỗi: ${err.message}</div>`;
        }
    };

    const renderStories = (stories) => {
        let html = `<div class="small text-secondary mb-2">Tìm thấy ${stories.length} truyện</div>`;
        html += '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">';
        stories.forEach(story => {
            const coverUrl = story.cover_url || '/static/placeholder.jpg';
            html += `
            <div class="col">
                <div class="card h-100 bg-dark border-secondary">
                    <div class="row g-0 h-100">
                        <div class="col-4 p-2">
                            <img src="${coverUrl}" class="img-fluid rounded" alt="${story.name}" style="object-fit: cover; height: 100%; max-height: 160px; width: 100%;" onerror="this.src='/static/placeholder.jpg'">
                        </div>
                        <div class="col-8">
                            <div class="card-body p-2 d-flex flex-column h-100">
                                <h6 class="card-title text-truncate mb-1" title="${story.name}">${story.name}</h6>
                                ${story.china_name ? `<p class="card-text small text-muted mb-1" style="font-size:0.7rem;">${story.china_name}</p>` : ''}
                                <p class="card-text small text-secondary mb-1"><i class="bi bi-person me-1"></i>${story.author}</p>
                                <p class="card-text small mb-2"><span class="badge bg-secondary">${story.count_chapter} chương</span> <span class="badge ${story.finish === '1' ? 'bg-success' : 'bg-info'}">${story.finish === '1' ? 'Hoàn thành' : 'Đang ra'}</span>${story.avg_rate ? ` <span class="badge bg-warning text-dark">★ ${story.avg_rate}</span>` : ''}</p>
                                <div class="mt-auto">
                                    <button class="btn btn-sm btn-primary w-100 btn-ttv-download" data-id="${story.id}" data-title="${encodeURIComponent(story.name)}" data-author="${encodeURIComponent(story.author)}" data-cover="${encodeURIComponent(coverUrl)}" data-desc="${encodeURIComponent(story.description || '')}" data-cat="${encodeURIComponent(story.category || '')}">
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

        // Attach download handlers
        document.querySelectorAll('.btn-ttv-download').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const btnEl = e.currentTarget;
                const storyId = btnEl.getAttribute('data-id');
                const title = decodeURIComponent(btnEl.getAttribute('data-title'));
                const author = decodeURIComponent(btnEl.getAttribute('data-author'));
                const coverUrl = decodeURIComponent(btnEl.getAttribute('data-cover'));
                const description = decodeURIComponent(btnEl.getAttribute('data-desc'));
                const catStr = decodeURIComponent(btnEl.getAttribute('data-cat'));
                const tags = catStr ? catStr.split(',').map(s => s.trim()) : [];
                downloadStory(storyId, title, author, coverUrl, description, tags, btnEl);
            });
        });
    };

    const downloadStory = async (storyId, title, author, coverUrl, description, tags, btnElement) => {
        const originalHtml = btnElement.innerHTML;
        btnElement.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Đang xếp hàng...';
        btnElement.disabled = true;

        try {
            const response = await fetch('/api/ttv/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id_story: storyId,
                    title: title,
                    author: author,
                    cover_url: coverUrl,
                    description: description,
                    tags: tags
                })
            });
            const data = await response.json();

            if (data.success) {
                btnElement.classList.replace('btn-primary', 'btn-success');
                btnElement.innerHTML = '<i class="bi bi-check-circle me-1"></i> Đã xếp hàng';

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Đã thêm vào hàng đợi',
                        text: `"${title}" đang được tải xuống.`,
                        timer: 2000,
                        showConfirmButton: false,
                        toast: true,
                        position: 'top-end'
                    });
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
                Swal.fire({
                    icon: 'error',
                    title: 'Lỗi tải truyện',
                    text: err.message,
                });
            }
        }
    };

    // Sync handler
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

    // On load: check sync status and show DB count
    pollSyncStatus();
})();

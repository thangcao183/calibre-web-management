document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('ttv-search-input');
    const searchBtn = document.getElementById('btn-ttv-search');
    const resultsContainer = document.getElementById('ttv-results-container');

    if (!searchInput || !searchBtn || !resultsContainer) return;

    const performSearch = async () => {
        const query = searchInput.value.trim();
        resultsContainer.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2 text-secondary">Searching TangThuVien...</div></div>';
        
        try {
            const url = query ? `/api/ttv/search?query=${encodeURIComponent(query)}` : '/api/ttv/search';
            const response = await fetch(url);
            const data = await response.json();
            
            if (!data.success) {
                resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Unknown error occurred'}</div>`;
                return;
            }
            
            if (!data.stories || data.stories.length === 0) {
                resultsContainer.innerHTML = '<div class="text-secondary text-center py-4">No stories found.</div>';
                return;
            }
            
            renderStories(data.stories);
        } catch (err) {
            console.error('TTV Search Error:', err);
            resultsContainer.innerHTML = `<div class="alert alert-danger">Failed to fetch stories: ${err.message}</div>`;
        }
    };

    const renderStories = (stories) => {
        let html = '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">';
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
                                <p class="card-text small text-secondary mb-1"><i class="bi bi-person me-1"></i>${story.author}</p>
                                <p class="card-text small mb-2"><span class="badge bg-secondary">${story.count_chapter} chapters</span> <span class="badge ${story.finish === 'full' ? 'bg-success' : 'bg-info'}">${story.finish || 'ongoing'}</span></p>
                                <div class="mt-auto">
                                    <button class="btn btn-sm btn-primary w-100 btn-ttv-download" data-id="${story.id}">
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
        
        // Attach event listeners to download buttons
        document.querySelectorAll('.btn-ttv-download').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const storyId = e.currentTarget.getAttribute('data-id');
                downloadStory(storyId, e.currentTarget);
            });
        });
    };

    const downloadStory = async (storyId, btnElement) => {
        const originalHtml = btnElement.innerHTML;
        btnElement.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Queueing...';
        btnElement.disabled = true;
        
        try {
            const response = await fetch('/api/ttv/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ id_story: storyId })
            });
            const data = await response.json();
            
            if (data.success) {
                // Change to success state
                btnElement.classList.replace('btn-primary', 'btn-success');
                btnElement.innerHTML = '<i class="bi bi-check2 me-1"></i> Queued';
                
                // Show notification via sweetalert if available
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        toast: true,
                        position: 'bottom-end',
                        icon: 'success',
                        title: 'TTV Download Queued',
                        text: 'Check the Download/Activity tab for progress.',
                        showConfirmButton: false,
                        timer: 3000
                    });
                }
            } else {
                throw new Error(data.error || 'Failed to queue download');
            }
        } catch (err) {
            console.error('TTV Download Error:', err);
            btnElement.innerHTML = originalHtml;
            btnElement.disabled = false;
            
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Download Failed',
                    text: err.message
                });
            } else {
                alert(`Download failed: ${err.message}`);
            }
        }
    };

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
});

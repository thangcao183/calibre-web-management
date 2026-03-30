async function downloadBook() {
    const url = document.getElementById('download-url').value.trim();
    const msg = document.getElementById('download-message');
    const btn = document.getElementById('download-btn');

    if (!url) {
        msg.textContent = 'Please enter a URL.';
        msg.className = 'small mt-2 fw-medium text-danger';
        return;
    }

    msg.textContent = 'Queueing download...';
    msg.className = 'small mt-2 fw-medium text-primary';
    btn.disabled = true;

    try {
        const addToCalibreElem = document.getElementById('add-calibre');
        const addToCalibre = addToCalibreElem ? addToCalibreElem.checked : true;

        const res = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, add_to_calibre: addToCalibre })
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

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
        console.error('Download error:', e);
        msg.textContent = 'Error: ' + e.message;
        msg.className = 'small mt-2 fw-medium text-danger';
        showError('Download failed', e.message || 'Network error.');
    } finally {
        btn.disabled = false;
    }
}

async function cancelQueuedDownload(queueId) {
    if (!queueId) return;

    const msg = document.getElementById('download-message');
    try {
        const res = await fetch('/api/download/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ queue_id: queueId })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || `HTTP ${res.status}`);
        }
        if (msg) {
            msg.textContent = `Cancelled queued item ${queueId}.`;
            msg.className = 'small mt-2 fw-medium text-warning';
        }
    } catch (e) {
        if (msg) {
            msg.textContent = `Error: ${e.message}`;
            msg.className = 'small mt-2 fw-medium text-danger';
        }
        showError('Cancel failed', e.message || 'Failed to cancel queued item.');
    }
}

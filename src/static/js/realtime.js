const liveState = {};
let liveRenderScheduled = false;
const dirtyDomains = {
    connection: false,
    device: false,
    download: false,
    history: false
};

function markDomainDirty(domain) {
    if (domain === 'state') {
        dirtyDomains.connection = true;
        dirtyDomains.device = true;
        dirtyDomains.download = true;
        dirtyDomains.history = true;
        return;
    }
    if (dirtyDomains[domain] !== undefined) dirtyDomains[domain] = true;
}

function resetDirtyDomains() {
    dirtyDomains.connection = false;
    dirtyDomains.device = false;
    dirtyDomains.download = false;
    dirtyDomains.history = false;
}

function scheduleLiveRender() {
    if (liveRenderScheduled) return;
    liveRenderScheduled = true;
    requestAnimationFrame(() => {
        liveRenderScheduled = false;
        renderLiveDomains();
        resetDirtyDomains();
    });
}

function applyLivePatch(patch, domain = 'state') {
    if (!patch || typeof patch !== 'object') return;
    Object.assign(liveState, patch);
    markDomainDirty(domain);
    scheduleLiveRender();
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

function renderDownloadQueue(data) {
    const queueWrap = document.getElementById('download-queue-list');
    if (!queueWrap) return;

    const current = data.current_download_url || '';
    const queuedItems = Array.isArray(data.download_queue_items) ? data.download_queue_items : [];
    const queued = queuedItems.length
        ? queuedItems
        : (Array.isArray(data.download_queue_urls)
            ? data.download_queue_urls.map((url, idx) => ({ id: '', url, _fallbackIndex: idx + 1 }))
            : []);

    const isWorking = (data.task_status === 'queued' || data.task_status === 'running') && current;

    if (!isWorking && queued.length === 0) {
        queueWrap.style.display = 'none';
        queueWrap.innerHTML = '';
        return;
    }

    const rows = [];
    if (isWorking) {
        rows.push(`
            <div class="download-queue-item current">
                <span class="queue-pill">Now</span>
                <span class="queue-url" title="${escapeHtml(current)}">${escapeHtml(shortQueueLabel(current))}</span>
            </div>
        `);
    }

    queued.slice(0, 5).forEach((item, idx) => {
        const queueId = item.id || '';
        const queueUrl = item.url || '';
        const queueLabel = queueId ? `#${idx + 1}` : `#${item._fallbackIndex || idx + 1}`;
        const cancelAction = queueId
            ? `<button class="btn btn-sm btn-outline-danger queue-cancel-btn" data-queue-id="${escapeHtml(queueId)}">Cancel</button>`
            : '';

        rows.push(`
            <div class="download-queue-item">
                <span class="queue-pill">${queueLabel}</span>
                <span class="queue-url" title="${escapeHtml(queueUrl)}">${escapeHtml(shortQueueLabel(queueUrl))}</span>
                ${cancelAction}
            </div>
        `);
    });

    if (queued.length > 5) {
        rows.push(`<div class="small text-secondary mt-1">+${queued.length - 5} more in queue</div>`);
    }

    queueWrap.style.display = 'block';
    queueWrap.innerHTML = rows.join('');
}

function renderConnectionState(data) {
    const dot = document.getElementById('connection-indicator');
    const txt = document.getElementById('status-text');
    const card = document.getElementById('connection-card');
    if (!dot || !txt) return;

    if (data.status === 'Connected') {
        if (card) card.style.display = 'block';
        dot.classList.add('connected');
        txt.textContent = 'Connected';
        txt.className = 'small fw-semibold text-success';

        const clientIp = document.getElementById('client-ip');
        if (clientIp) {
            clientIp.textContent = data.client_address || 'Unknown';
            clientIp.className = 'ms-2 fw-semibold';
        }

        const lastPing = document.getElementById('last-ping');
        if (lastPing) {
            lastPing.textContent = data.last_ping || '--:--:--';
            lastPing.className = 'ms-2 fw-semibold';
        }

        const instructionBox = document.getElementById('instruction-box');
        if (instructionBox) instructionBox.style.opacity = '0.4';
        const ejectBtn = document.getElementById('eject-btn');
        if (ejectBtn) ejectBtn.style.display = 'inline-block';
    } else {
        if (card) card.style.display = 'none';
        dot.classList.remove('connected');
        txt.textContent = 'Listening (Port 9090)';
        txt.className = 'small fw-semibold text-light';
        const instructionBox = document.getElementById('instruction-box');
        if (instructionBox) instructionBox.style.opacity = '1';
        const ejectBtn = document.getElementById('eject-btn');
        if (ejectBtn) ejectBtn.style.display = 'none';
    }

    if (data.auto_sync !== undefined) {
        const cb = document.getElementById('auto-sync-cb');
        if (cb && document.activeElement !== cb) cb.checked = data.auto_sync;
    }
}

function renderDeviceState(data) {
    const deviceType = document.getElementById('device-type');
    if (!deviceType) return;
    deviceType.textContent = data.device_info || 'Kobo UNCaGED';
    deviceType.className = 'ms-2 fw-semibold';
}

function renderHistoryState(data) {
    renderTaskHistory(data.task_history || []);
}

function renderDownloadState(data) {
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

    renderDownloadQueue(data);

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

function renderLiveDomains() {
    if (dirtyDomains.connection) renderConnectionState(liveState);
    if (dirtyDomains.device) renderDeviceState(liveState);
    if (dirtyDomains.download) renderDownloadState(liveState);
    if (dirtyDomains.history) renderHistoryState(liveState);
}

function initRealtime() {
    const evtSource = new EventSource('/api/status/stream');

    const parseSsePayload = (domain) => (e) => {
        try {
            applyLivePatch(JSON.parse(e.data), domain);
        } catch (err) {
            // ignore malformed payload
        }
    };

    evtSource.addEventListener('state', parseSsePayload('state'));
    evtSource.addEventListener('connection', parseSsePayload('connection'));
    evtSource.addEventListener('device', parseSsePayload('device'));
    evtSource.addEventListener('download', parseSsePayload('download'));
    evtSource.addEventListener('history', parseSsePayload('history'));

    evtSource.onopen = () => {
        const status = document.getElementById('status-text');
        if (status) {
            status.textContent = 'Listening (Port 9090)';
            status.className = 'small fw-semibold text-light';
        }
    };

    evtSource.onmessage = parseSsePayload('state');

    evtSource.onerror = () => {
        const status = document.getElementById('status-text');
        if (status) {
            status.textContent = 'Server Offline';
            status.className = 'small fw-semibold text-danger';
        }
    };
}

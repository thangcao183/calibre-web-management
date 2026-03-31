// Shared state
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
const DENSITY_PRESET_KEY = 'cwa_density_preset_v1';
const DENSITY_PRESET_LOCK_KEY = 'cwa_density_preset_locked_v1';

function nowTimeLabel() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function pulseMiniStatValue(el) {
    if (!el) return;
    el.classList.remove('pulse');
    void el.offsetWidth;
    el.classList.add('pulse');
}

function updateMiniStatHint(kind, source) {
    const hintEl = document.getElementById(`mini-stat-${kind}-hint`);
    const wrapEl = document.getElementById(`mini-stat-${kind}-wrap`);
    if (!hintEl || !wrapEl) return;

    const shortSource = source === 'api' ? 'API' : 'SSE';
    const at = nowTimeLabel();
    hintEl.textContent = `${shortSource} • ${at}`;
    wrapEl.title = `Source: ${source === 'api' ? '/api/calibre_books' : '/api/status/stream'} | Updated: ${at}`;
}

function updateMiniStatsBooks(total, source = 'api') {
    const el = document.getElementById('mini-stat-books');
    if (!el) return;
    const value = Number.isFinite(Number(total)) ? Number(total) : 0;
    if (el.textContent !== String(value)) pulseMiniStatValue(el);
    el.textContent = String(value);
    updateMiniStatHint('books', source);
}

function updateMiniStatsQueue(total, source = 'sse') {
    const el = document.getElementById('mini-stat-queue');
    if (!el) return;
    const value = Number.isFinite(Number(total)) ? Number(total) : 0;
    if (el.textContent !== String(value)) pulseMiniStatValue(el);
    el.textContent = String(value);
    updateMiniStatHint('queue', source);
}

function updateMiniStatsDevice(statusText, source = 'sse') {
    const el = document.getElementById('mini-stat-device');
    if (!el) return;
    const raw = String(statusText || 'Idle').trim();
    if (!raw) {
        if (el.textContent !== 'Idle') pulseMiniStatValue(el);
        el.textContent = 'Idle';
        updateMiniStatHint('device', source);
        return;
    }
    const nextValue = raw.length > 14 ? `${raw.slice(0, 14)}...` : raw;
    if (el.textContent !== nextValue) pulseMiniStatValue(el);
    el.textContent = nextValue;
    updateMiniStatHint('device', source);
}

function getViewportSuggestedPreset() {
    const w = window.innerWidth || document.documentElement.clientWidth || 0;
    if (w >= 1200) return 'compact';
    if (w >= 768) return 'comfortable';
    return 'comfortable';
}

function getDensityPreset() {
    const storedPreset = localStorage.getItem(DENSITY_PRESET_KEY);
    if (storedPreset === 'compact' || storedPreset === 'comfortable') {
        return storedPreset;
    }
    return getViewportSuggestedPreset();
}

function syncDensityPresetButtons(preset) {
    const compactBtn = document.getElementById('btn-density-compact');
    const comfortableBtn = document.getElementById('btn-density-comfortable');
    if (compactBtn) compactBtn.classList.toggle('active', preset === 'compact');
    if (comfortableBtn) comfortableBtn.classList.toggle('active', preset === 'comfortable');
}

function applyDensityPreset(preset, persist = true) {
    const normalized = preset === 'compact' ? 'compact' : 'comfortable';
    document.body.dataset.density = normalized;
    syncDensityPresetButtons(normalized);
    if (persist) {
        localStorage.setItem(DENSITY_PRESET_KEY, normalized);
        localStorage.setItem(DENSITY_PRESET_LOCK_KEY, '1');
    }
}

function initDensityPreset() {
    const hasLockedPreset = localStorage.getItem(DENSITY_PRESET_LOCK_KEY) === '1';
    const preset = getDensityPreset();
    applyDensityPreset(preset, false);

    if (!hasLockedPreset) {
        localStorage.setItem(DENSITY_PRESET_KEY, preset);
    }
}

Object.defineProperty(window, 'currentBookId', {
    get: () => currentBookId,
    set: (value) => { currentBookId = value; }
});

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

function shortQueueLabel(url) {
    try {
        const parsed = new URL(url);
        const path = parsed.pathname && parsed.pathname !== '/' ? parsed.pathname : '';
        return `${parsed.hostname}${path}`;
    } catch (e) {
        return url || 'Unknown URL';
    }
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

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

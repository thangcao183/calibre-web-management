function renderSavedFilterOptions() {
    const select = document.getElementById('saved-filter-select');
    if (!select) return;

    const filters = getSavedFilters();
    select.innerHTML = '<option value="">Saved filters</option>';
    filters.forEach(filter => {
        const option = document.createElement('option');
        option.value = filter.name;
        option.textContent = filter.name;
        select.appendChild(option);
    });
}

function onSearchInput() {
    currentSearch = document.getElementById('calibre-search').value.trim().toLowerCase();
    currentPage = 1;
    fetchCalibreBooks();
}

function onFormatFilterChange() {
    currentFormatFilter = document.getElementById('calibre-format-filter').value;
    currentPage = 1;
    fetchCalibreBooks();
}

function updateActiveFilterBadge() {
    const badge = document.getElementById('active-filter-badge');
    if (!badge) return;

    const active = [];
    if (currentSearch) active.push(`Search: ${currentSearch}`);
    if (currentFormatFilter) active.push(`Format: ${currentFormatFilter.toUpperCase()}`);

    if (!active.length) {
        badge.style.display = 'none';
        badge.textContent = '';
        return;
    }

    badge.style.display = 'inline-block';
    badge.textContent = active.join(' | ');
}

function clearFilters() {
    currentSearch = '';
    currentFormatFilter = '';
    currentPage = 1;
    document.getElementById('calibre-search').value = '';
    document.getElementById('calibre-format-filter').value = '';
    document.getElementById('saved-filter-select').value = '';
    fetchCalibreBooks();
}

function applyFilterAndRender() {
    fetchCalibreBooks();
}

async function saveCurrentFilter() {
    const query = document.getElementById('calibre-search').value.trim();
    const format = document.getElementById('calibre-format-filter').value;
    if (!query && !format) {
        showError('Cannot save filter', 'Enter a search query or choose a format first.');
        return;
    }

    const result = await Swal.fire({
        title: 'Save Filter',
        input: 'text',
        inputLabel: 'Filter name',
        inputPlaceholder: 'For example: Romance, New books, Vietnamese authors',
        showCancelButton: true,
        inputValidator: (value) => {
            if (!value.trim()) return 'Filter name is required';
        }
    });

    if (!result.isConfirmed || !result.value) return;

    const name = result.value.trim();
    const filters = getSavedFilters().filter(item => item.name !== name);
    filters.push({ name, query, format });
    filters.sort((a, b) => a.name.localeCompare(b.name));
    setSavedFilters(filters);
    renderSavedFilterOptions();
    document.getElementById('saved-filter-select').value = name;
    showSuccess('Filter saved', `Saved "${name}".`);
}

function applySavedFilter(name) {
    if (!name) return;
    const filter = getSavedFilters().find(item => item.name === name);
    if (!filter) return;
    document.getElementById('calibre-search').value = filter.query;
    document.getElementById('calibre-format-filter').value = filter.format || '';
    currentSearch = (filter.query || '').toLowerCase();
    currentFormatFilter = filter.format || '';
    currentPage = 1;
    fetchCalibreBooks();
}

async function deleteSavedFilter() {
    const select = document.getElementById('saved-filter-select');
    const name = select?.value;
    if (!name) {
        showError('No filter selected', 'Choose a saved filter to delete.');
        return;
    }

    const confirmed = await confirmAction('Delete saved filter?', `Remove the filter "${name}"?`, 'Delete');
    if (!confirmed) return;

    const filters = getSavedFilters().filter(item => item.name !== name);
    setSavedFilters(filters);
    renderSavedFilterOptions();
    showSuccess('Filter deleted', `Removed "${name}".`);
}

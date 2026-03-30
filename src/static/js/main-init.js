document.addEventListener('DOMContentLoaded', () => {
    bindUiEvents();
    renderSavedFilterOptions();
    fetchCalibreBooks();
    initRealtime();
});

const BOOK_ID = Number(document.body.dataset.bookId || 0);
const STORE_KEY = `reader_${BOOK_ID}`;

const THEMES = {
    dark: {
        bg: '#1b1e25',
        fg: '#e5e9f0',
        heading: '#f4f6fa',
        link: '#ffb74d',
        panel: '#262b34',
        panelText: '#e5e9f0',
        progressTrack: 'rgba(255,255,255,0.06)'
    },
    sepia: {
        bg: '#f2e8d4',
        fg: '#4e3f2a',
        heading: '#2f2517',
        link: '#a86c13',
        panel: '#e7d9bf',
        panelText: '#4e3f2a',
        progressTrack: 'rgba(60,40,15,0.12)'
    },
    light: {
        bg: '#f5f7fb',
        fg: '#1f2937',
        heading: '#111827',
        link: '#d97706',
        panel: '#e9edf5',
        panelText: '#1f2937',
        progressTrack: 'rgba(17,24,39,0.12)'
    }
};

let fontSize = 100;
let fontFamily = "'Lora', Georgia, serif";
let currentTheme = 'dark';
let book = null;
let rendition = null;

function calculateReaderViewport() {
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

    let sidePadding = 96;
    let maxReadWidth = 920;

    if (viewportWidth <= 768) {
        sidePadding = 44;
        maxReadWidth = viewportWidth - sidePadding;
    } else if (viewportWidth <= 1199) {
        sidePadding = 120;
        maxReadWidth = 860;
    }

    const width = Math.max(320, Math.min(maxReadWidth, viewportWidth - sidePadding));
    const height = Math.max(320, viewportHeight - 50);
    return { width, height };
}

try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY + '_prefs') || '{}');
    if (saved.fontSize) fontSize = saved.fontSize;
    if (saved.fontFamily) fontFamily = saved.fontFamily;
    if (saved.theme) currentTheme = saved.theme;
} catch (e) {}

function savePrefs() {
    localStorage.setItem(STORE_KEY + '_prefs', JSON.stringify({ fontSize, fontFamily, theme: currentTheme }));
}

function buildCSS() {
    const t = THEMES[currentTheme];
    return `
        html, body {
            background: ${t.bg} !important; color: ${t.fg} !important;
            font-family: ${fontFamily} !important;
            line-height: 1.85 !important;
            text-align: justify !important;
            word-wrap: break-word !important; overflow-wrap: break-word !important;
            hyphens: auto !important;
            padding: 1.2rem 2.2rem !important;
            -webkit-font-smoothing: antialiased !important;
        }
        p { margin: 0 0 0.65em !important; text-align: justify !important; }
        h1,h2,h3,h4,h5,h6 { color: ${t.heading} !important; text-align: left !important; margin: 1.2em 0 0.5em !important; }
        a { color: ${t.link} !important; }
        img { max-width: 100% !important; height: auto !important; display: block !important; margin: 0.8rem auto !important; }
        blockquote { border-left: 3px solid ${t.link} !important; padding-left: 1rem !important; margin: 0.8em 0 !important; font-style: italic !important; }
        pre, code { font-size: 0.85em !important; background: rgba(128,128,128,0.15) !important; border-radius: 4px !important; padding: 0.15em 0.3em !important; }
        ::selection { background: ${t.link} !important; color: #fff !important; }
    `;
}

function injectStyles() {
    if (!rendition) return;
    rendition.getContents().forEach((c) => {
        let el = c.document.getElementById('_custom_style');
        if (!el) {
            el = c.document.createElement('style');
            el.id = '_custom_style';
            c.document.head.appendChild(el);
        }
        el.textContent = buildCSS();
    });
}

function applyFontSize() {
    if (!rendition) return;
    rendition.themes.fontSize(fontSize + '%');
    rendition.getContents().forEach((c) => {
        let el = c.document.getElementById('_fs_fix');
        if (!el) {
            el = c.document.createElement('style');
            el.id = '_fs_fix';
            c.document.head.appendChild(el);
        }
        el.textContent = 'p,div,span,li,td,blockquote,dd,dt{font-size:inherit!important}';
    });
}

function changeFontSize(delta) {
    fontSize = Math.max(60, Math.min(250, fontSize + delta));
    document.getElementById('font-val').textContent = fontSize + '%';
    injectStyles();
    applyFontSize();
    savePrefs();
}

function changeFont(f) {
    fontFamily = f;
    injectStyles();
    applyFontSize();
    savePrefs();
}

function applyTheme(name) {
    currentTheme = name;
    const t = THEMES[name];
    document.body.style.background = t.bg;
    document.getElementById('reader').style.background = t.bg;
    const bar = document.getElementById('topbar');
    bar.style.background = t.panel;
    bar.style.color = t.panelText;
    bar.querySelectorAll('.btn, span').forEach((el) => {
        el.style.color = t.panelText;
    });
    document.getElementById('progress-bar').style.background = t.progressTrack;
    injectStyles();
    savePrefs();
}

function goBack() {
    if (history.length > 1) {
        history.back();
    } else {
        location.href = '/';
    }
}

function goPrev() {
    if (rendition) rendition.prev();
}

function goNext() {
    if (rendition) rendition.next();
}

function toggleTOC() {
    const panel = document.getElementById('toc-panel');
    const overlay = document.getElementById('toc-overlay');
    const open = panel.classList.toggle('open');
    overlay.style.display = open ? 'block' : 'none';
}

function renderTOC(toc) {
    const list = document.getElementById('toc-list');
    list.innerHTML = '';

    function addItems(items, level) {
        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'toc-item' + (level > 0 ? ' sub' : '');
            div.textContent = item.label.trim();
            div.addEventListener('click', () => {
                rendition.display(item.href);
                toggleTOC();
            });
            list.appendChild(div);
            if (item.subitems?.length) addItems(item.subitems, level + 1);
        });
    }

    addItems(toc, 0);
}

function bindUiEvents() {
    const backBtn = document.getElementById('btn-back');
    if (backBtn) backBtn.addEventListener('click', goBack);

    const tocToggleBtn = document.getElementById('btn-toc-toggle');
    if (tocToggleBtn) tocToggleBtn.addEventListener('click', toggleTOC);

    const tocCloseBtn = document.getElementById('btn-toc-close');
    if (tocCloseBtn) tocCloseBtn.addEventListener('click', toggleTOC);

    const tocOverlay = document.getElementById('toc-overlay');
    if (tocOverlay) tocOverlay.addEventListener('click', toggleTOC);

    const prevBtn = document.getElementById('prev-btn');
    if (prevBtn) prevBtn.addEventListener('click', goPrev);

    const nextBtn = document.getElementById('next-btn');
    if (nextBtn) nextBtn.addEventListener('click', goNext);

    const fontDecBtn = document.getElementById('btn-font-dec');
    if (fontDecBtn) fontDecBtn.addEventListener('click', () => changeFontSize(-8));

    const fontIncBtn = document.getElementById('btn-font-inc');
    if (fontIncBtn) fontIncBtn.addEventListener('click', () => changeFontSize(8));

    const themeSelect = document.getElementById('sel-theme');
    if (themeSelect) themeSelect.addEventListener('change', (e) => applyTheme(e.target.value));

    const fontSelect = document.getElementById('sel-font');
    if (fontSelect) fontSelect.addEventListener('change', (e) => changeFont(e.target.value));
}

function initTopbarVisibility() {
    const topbar = document.getElementById('topbar');
    const hoverZone = document.getElementById('topbar-hover-zone');
    if (!topbar || !hoverZone) return;

    if (window.matchMedia && window.matchMedia('(hover: none)').matches) {
        document.body.classList.add('topbar-visible');
        return;
    }

    let hideTimer = null;

    const showTopbar = () => {
        if (hideTimer) {
            clearTimeout(hideTimer);
            hideTimer = null;
        }
        document.body.classList.add('topbar-visible');
    };

    const hideTopbarSoon = () => {
        if (hideTimer) clearTimeout(hideTimer);
        hideTimer = setTimeout(() => {
            document.body.classList.remove('topbar-visible');
        }, 120);
    };

    hoverZone.addEventListener('mouseenter', showTopbar);
    topbar.addEventListener('mouseenter', showTopbar);
    hoverZone.addEventListener('mouseleave', hideTopbarSoon);
    topbar.addEventListener('mouseleave', hideTopbarSoon);
}

function saveLoc(cfi) {
    try {
        localStorage.setItem(STORE_KEY, cfi);
    } catch (e) {}
}

function loadLoc() {
    try {
        return localStorage.getItem(STORE_KEY);
    } catch (e) {
        return null;
    }
}

async function loadBook() {
    try {
        const res = await fetch(`/api/calibre/epub/${BOOK_ID}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buffer = await res.arrayBuffer();
        document.getElementById('loader').remove();

        const viewport = calculateReaderViewport();

        book = ePub(buffer);
        rendition = book.renderTo('reader', {
            width: viewport.width,
            height: viewport.height,
            spread: 'none',
            flow: 'paginated',
            allowScriptedContent: true
        });

        const keyNav = (e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                goNext();
                e.preventDefault();
            }
            if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                goPrev();
                e.preventDefault();
            }
            if (e.key === 'Escape') toggleTOC();
        };
        document.addEventListener('keydown', keyNav);

        rendition.on('rendered', (section, view) => {
            try {
                const iframe = view?.iframe || view?.document?.defaultView?.frameElement;
                if (iframe) {
                    iframe.style.overflow = 'hidden';
                    iframe.scrolling = 'no';
                }
            } catch (e) {}

            injectStyles();

            try {
                const doc = rendition.getContents()?.[0]?.document;
                if (doc) {
                    doc.removeEventListener('keydown', keyNav);
                    doc.addEventListener('keydown', keyNav);
                }
            } catch (e) {}

            const readerEl = document.getElementById('reader');
            readerEl.classList.remove('page-turn');
            void readerEl.offsetWidth;
            readerEl.classList.add('page-turn');
        });

        rendition.on('relocated', (loc) => {
            const pct = Math.round((loc.start.percentage || 0) * 100);
            document.getElementById('progress').textContent = `${pct}%`;
            document.getElementById('progress-fill').style.width = `${pct}%`;
            saveLoc(loc.start.cfi);
        });

        book.loaded.navigation.then((nav) => {
            if (nav.toc?.length) renderTOC(nav.toc);
        });

        const saved = loadLoc();
        await rendition.display(saved || undefined);
        applyFontSize();

        window.addEventListener('resize', () => {
            const nextViewport = calculateReaderViewport();
            rendition.resize(nextViewport.width, nextViewport.height);
        });
    } catch (err) {
        document.getElementById('loader').innerHTML =
            `<p style="color:#ef4444;font-size:0.9rem">Failed to load:<br>${err.message}</p>`;
    }
}

function initReader() {
    if (!BOOK_ID) {
        document.getElementById('loader').innerHTML = '<p style="color:#ef4444;font-size:0.9rem">Missing book ID</p>';
        return;
    }

    document.getElementById('font-val').textContent = fontSize + '%';
    document.getElementById('sel-theme').value = currentTheme;
    document.querySelectorAll('#sel-font option').forEach((opt) => {
        if (opt.value === fontFamily) opt.selected = true;
    });

    bindUiEvents();
    initTopbarVisibility();
    applyTheme(currentTheme);
    loadBook();
}

document.addEventListener('DOMContentLoaded', initReader);

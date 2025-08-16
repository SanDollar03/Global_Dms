// サイドバーの開閉制御。開時は .is-open と aria-expanded="true" を付与し、CSS が×化に反応する。
(function () {
  const btn = document.getElementById('menuToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  if (!btn || !sidebar || !overlay) return;

  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ];

  let lastFocused = null;

  function openSidebar() {
    lastFocused = document.activeElement;
    btn.classList.add('is-open');                 // ← ハンバーガー×化のフラグ
    sidebar.classList.add('is-open');
    overlay.classList.add('is-active');
    overlay.hidden = false;

    btn.setAttribute('aria-expanded', 'true');    // ← ハンバーガー×化のフラグ
    sidebar.setAttribute('aria-hidden', 'false');

    const focusables = sidebar.querySelectorAll(focusableSelectors.join(','));
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      sidebar.focus({ preventScroll: true });
    }

    document.documentElement.style.overflow = 'hidden'; // 背景スクロール抑制
  }

  function closeSidebar() {
    btn.classList.remove('is-open');
    sidebar.classList.remove('is-open');
    overlay.classList.remove('is-active');

    btn.setAttribute('aria-expanded', 'false');
    sidebar.setAttribute('aria-hidden', 'true');

    setTimeout(() => { overlay.hidden = true; }, 200);

    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus();
    } else {
      btn.focus();
    }

    document.documentElement.style.overflow = '';
  }

  function toggleSidebar() {
    const open = sidebar.classList.contains('is-open');
    open ? closeSidebar() : openSidebar();
  }

  btn.addEventListener('click', toggleSidebar);
  overlay.addEventListener('click', closeSidebar);

  // ESC で閉じる / TAB でフォーカストラップ
  document.addEventListener('keydown', (e) => {
    if (!sidebar.classList.contains('is-open')) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      closeSidebar();
      return;
    }

    if (e.key === 'Tab') {
      const focusables = sidebar.querySelectorAll(focusableSelectors.join(','));
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    }
  });
})();

// ロゴ画像の natural サイズを読み取り、幅・高さとも「元の50%」を CSS 変数へ。
// CSS はこの値を「上限」として使い、vmin 基準の可変と組み合わせる。
(function () {
  function applyHalfSize(img) {
    if (img.naturalWidth && img.naturalHeight) {
      const halfW = Math.max(1, Math.round(img.naturalWidth / 2));
      const halfH = Math.max(1, Math.round(img.naturalHeight / 2));
      img.style.setProperty('--logo-max-w', halfW + 'px');
      img.style.setProperty('--logo-max-h', halfH + 'px');
    }
  }

  function onReady() {
    const img = document.getElementById('centerLogo');
    if (!img) return;

    if (img.complete && img.naturalWidth) {
      applyHalfSize(img);
    } else {
      img.addEventListener('load', () => applyHalfSize(img), { once: true });
      img.addEventListener('error', () => console.warn('Logo image failed to load'));
    }

    // 高DPI切替やズーム変化に備えてリサイズ時も再評価
    window.addEventListener('resize', () => applyHalfSize(img));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
})();

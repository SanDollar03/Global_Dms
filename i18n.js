// 軽量 i18n（日本語/英語） - data-i18n / data-i18n-attr に対応
(() => {
  const SUPPORTED = ["ja", "en"];
  const DEFAULT_LANG = "ja";
  const STORE_KEY = "app.lang";
  const LOCALES_PATH = window.__LOCALES_PATH__ || "/static/locales";

  let current = DEFAULT_LANG;
  let dict = {};

  const interpolate = (str, vars = {}) =>
    String(str).replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));

  const t = (key, vars) => {
    const raw = dict[key];
    return interpolate(raw ?? key, vars);
  };

  function translateElement(el) {
    const key = el.getAttribute("data-i18n");
    if (key) el.textContent = t(key);
    const attrMap = el.getAttribute("data-i18n-attr");
    if (attrMap) {
      attrMap.split(";").forEach(pair => {
        const [attr, k] = pair.split(":").map(s => s && s.trim()).filter(Boolean);
        if (attr && k) el.setAttribute(attr, t(k));
      });
    }
  }

  function translatePage() {
    document.documentElement.setAttribute("lang", current);
    document.querySelectorAll("[data-i18n], [data-i18n-attr]").forEach(translateElement);
  }

  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      m.addedNodes.forEach(node => {
        if (node.nodeType !== 1) return;
        if (node.hasAttribute?.("data-i18n") || node.hasAttribute?.("data-i18n-attr")) {
          translateElement(node);
        }
        node.querySelectorAll?.("[data-i18n], [data-i18n-attr]").forEach(translateElement);
      });
    }
  });

  async function loadDict(lang) {
    const res = await fetch(`${LOCALES_PATH}/${lang}.json`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load ${lang}.json`);
    dict = await res.json();
  }

  function normalize(lang) {
    if (!lang) return DEFAULT_LANG;
    const base = lang.toLowerCase().split("-")[0];
    return SUPPORTED.includes(base) ? base : DEFAULT_LANG;
  }

  async function setLanguage(lang) {
    const normalized = normalize(lang);
    if (normalized === current && Object.keys(dict).length) return;
    await loadDict(normalized);
    current = normalized;
    localStorage.setItem(STORE_KEY, current);
    translatePage();
    document.dispatchEvent(new CustomEvent("i18n:changed", { detail: { lang: current } }));
  }

  async function init() {
    const saved = localStorage.getItem(STORE_KEY);
    const fallback = saved || navigator.language || DEFAULT_LANG;
    await setLanguage(fallback);
    mo.observe(document.body, { childList: true, subtree: true });
  }

  window.AppI18n = {
    t, setLanguage,
    get current() { return current; },
    format: {
      number(n, opt){ return new Intl.NumberFormat(current, opt).format(n); },
      date(d, opt){ return new Intl.DateTimeFormat(current, opt).format(d instanceof Date ? d : new Date(d)); }
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

// Tiny DOM helper. Text is ALWAYS set with textContent / text nodes, never innerHTML, so user data can never inject markup.
import { ICONS } from '../ui/icons.js';

const SVG = 'http://www.w3.org/2000/svg';

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs) || typeof attrs === 'string')) { kids.unshift(attrs); attrs = null; }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, String(v));
  }
  add(el, kids);
  return el;
}

export function add(el, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false) continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}

// Icons that point somewhere are drawn for left-to-right; in Arabic (RTL) they are mirrored by CSS (.mirror).
const DIRECTIONAL = new Set(['arrow-right', 'arrow-left', 'chevron-right', 'chevron-left', 'log-out', 'panel-left', 'panel-right', 'undo-2']);

export function icon(name, cls = '') {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', 'icon ' + (DIRECTIONAL.has(name) ? 'mirror ' : '') + cls);
  svg.setAttribute('aria-hidden', 'true');
  // ICONS holds our own bundled Lucide path strings (not user data), so innerHTML on the SVG namespace is safe here.
  svg.innerHTML = ICONS[name] || ICONS.circle;
  return svg;
}

export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
export function mount(el, ...kids) { clear(el); return add(el, kids); }
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function debounce(fn, ms = 200) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

let uid = 0;
export const nextId = (p = 'id') => `${p}-${++uid}`;

// Keeps keyboard focus inside a dialog and gives it back when the dialog closes.
export function trapFocus(root, onEscape) {
  const before = document.activeElement;
  const sel = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  const key = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); onEscape && onEscape(); return; }
    if (e.key !== 'Tab') return;
    const f = $$(sel, root).filter((x) => x.offsetParent !== null);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  root.addEventListener('keydown', key);
  return () => { root.removeEventListener('keydown', key); before && before.focus && before.focus(); };
}

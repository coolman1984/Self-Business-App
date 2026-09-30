// Keyboard shortcuts. One registry so the "?" sheet, the palette and the code always agree.
import { h } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { modal } from './overlay.js';

const defs = [];   // {keys: 'g t', k: 'i18n key', run}
let pending = '', timer;

export function shortcut(keys, k, run) { defs.push({ keys, k, run }); }
export const shortcuts = () => defs.slice();

function typing(e) {
  const el = e.target;
  return el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
}

export function initKeys() {
  addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); const d = defs.find((x) => x.keys === 'mod+k'); d && d.run(); }
      return;
    }
    if (typing(e) || document.querySelector('.modal,.drawer,.palette')) { if (e.key === '?' && !typing(e)) return; return; }
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    pending = pending ? `${pending} ${key}` : key;
    clearTimeout(timer); timer = setTimeout(() => { pending = ''; }, 900);
    const hit = defs.find((d) => d.keys === pending);
    if (hit) { e.preventDefault(); pending = ''; hit.run(); return; }
    if (!defs.some((d) => d.keys.startsWith(pending + ' '))) pending = '';
  });
}

export function showShortcuts() {
  const rows = defs.map((d) => h('div', { class: 'list-item' }, h('span', { class: 'grow' }, t(d.k)),
    h('span', { class: 'row' }, ...d.keys.split(' ').map((k) => h('kbd', k === 'mod+k' ? 'Ctrl K' : k.toUpperCase())))));
  modal({ title: t('keys.title'), body: h('div', ...rows) });
}

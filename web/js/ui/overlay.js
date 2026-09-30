// Modal, side panel (drawer), toast with undo, menu, confirm. Focus is trapped while open and restored on close.
import { h, icon, trapFocus, $ } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { button } from './kit.js';

function open(kind, { title, body, footer, wide, onClose }) {
  const overlay = h('div', { class: 'overlay', onClick: () => close() });
  const titleId = 'ttl-' + Math.random().toString(36).slice(2, 7);
  const closeBtn = button('', { kind: 'ghost', ico: 'x', title: t('action.close'), onClick: () => close() });
  const box = kind === 'modal'
    ? h('div', { class: 'modal' + (wide ? ' wide' : '') }, h('div', { class: 'box', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId },
        h('header', h('h2', { id: titleId }, title), closeBtn), h('div', { class: 'body' }, body), footer ? h('footer', ...[].concat(footer)) : null))
    : h('aside', { class: 'drawer' + (wide ? ' wide' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId },
        h('header', h('h2', { id: titleId }, title), closeBtn), h('div', { class: 'body' }, body), footer ? h('footer', ...[].concat(footer)) : null);
  document.body.append(overlay, box);
  document.body.style.overflow = 'hidden';
  const release = trapFocus(box, () => close());
  const first = $('[autofocus], input, select, textarea', box) || $('button', box.querySelector('.body') || box);
  (first || closeBtn).focus();
  let done = false;
  function close(result) {
    if (done) return;
    done = true;
    overlay.remove(); box.remove(); release();
    document.body.style.overflow = '';
    onClose && onClose(result);
  }
  return { close, el: box };
}
export const modal = (o) => open('modal', o);
export const drawer = (o) => open('drawer', o);

// asks before anything risky; resolves true/false
export function confirmBox({ title, text, yes = t('action.confirm'), danger = false }) {
  return new Promise((resolve) => {
    const m = modal({
      title, body: h('p', text), onClose: (r) => resolve(!!r),
      footer: [button(t('action.cancel'), { onClick: () => m.close(false) }), button(yes, { kind: danger ? 'danger' : 'primary', onClick: () => m.close(true) })],
    });
  });
}

// ---- toasts. Undo is the safety net of the product: a destructive action shows "Undo" for 8 seconds.
let host;
export function toast(text, { kind = '', undo, ms = 4500 } = {}) {
  if (!host) { host = h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite' }); document.body.append(host); }
  const el = h('div', { class: 'toast ' + kind }, icon(kind === 'bad' ? 'circle-alert' : 'circle-check'), h('span', text));
  if (undo) el.append(button(t('action.undo'), { kind: 'ghost', onClick: async () => { el.remove(); await undo(); } }));
  host.append(el);
  setTimeout(() => el.remove(), undo ? Math.max(ms, 8000) : ms);
  return el;
}

// small dropdown next to a button: items = [{label, ico, onClick, danger}] or '-' for a separator
export function menu(anchor, items) {
  document.querySelectorAll('.menu').forEach((m) => m.remove());
  const el = h('div', { class: 'menu', role: 'menu' }, ...items.map((it) => it === '-' ? h('hr') :
    h('button', { role: 'menuitem', type: 'button', onClick: () => { close(); it.onClick(); } }, it.ico ? icon(it.ico) : null, it.label)));
  const r = anchor.getBoundingClientRect();
  document.body.append(el);
  el.style.top = `${r.bottom + scrollY + 4}px`;
  el.style.left = '0px';
  const w = el.getBoundingClientRect().width;
  // line the menu up with the button's start edge, then keep it fully inside the window (the button is often at the edge)
  const start = document.documentElement.dir === 'rtl' ? r.right - w : r.left;
  el.style.left = `${Math.min(Math.max(8, start), Math.max(8, innerWidth - w - 8)) + scrollX}px`;
  if (r.bottom + el.getBoundingClientRect().height + 8 > innerHeight && r.top > el.getBoundingClientRect().height + 8) el.style.top = `${r.top + scrollY - el.getBoundingClientRect().height - 4}px`;
  const close = () => { el.remove(); document.removeEventListener('mousedown', away, true); document.removeEventListener('keydown', esc, true); };
  const away = (e) => { if (!el.contains(e.target)) close(); };
  const esc = (e) => { if (e.key === 'Escape') { close(); anchor.focus(); } };
  setTimeout(() => document.addEventListener('mousedown', away, true));
  document.addEventListener('keydown', esc, true);
  el.querySelector('button')?.focus();
  return close;
}

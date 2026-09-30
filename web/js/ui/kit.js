// UI kit: small building blocks used by every screen. No screen builds its own button or table.
import { h, icon, nextId } from '../core/dom.js';
import { t } from '../i18n/index.js';

export function button(label, { kind = '', ico, onClick, type = 'button', disabled, small, title, href, id } = {}) {
  const cls = ['btn', kind, small ? 'small' : '', !label ? 'icon-only' : ''].filter(Boolean).join(' ');
  const kids = [ico ? icon(ico) : null, label ? h('span', label) : null];
  const el = href ? h('a', { class: cls, href, title, id }, ...kids) : h('button', { class: cls, type, disabled, title, id, 'aria-label': !label ? title : null }, ...kids);
  if (onClick) el.addEventListener('click', async (e) => {
    if (el.classList.contains('busy')) return;
    const r = onClick(e);
    if (r && r.then) { el.classList.add('busy'); try { await r; } finally { el.classList.remove('busy'); } }
  });
  return el;
}

// label + control + hint + error, wired together for screen readers
export function field(label, control, { hint, error, full } = {}) {
  const id = control.id || nextId('f');
  control.id = id;
  const hintEl = hint ? h('div', { class: 'hint', id: id + '-hint' }, hint) : null;
  if (hintEl) control.setAttribute('aria-describedby', id + '-hint');
  const wrap = h('div', { class: 'field' + (full ? ' full' : '') + (error ? ' invalid' : '') }, h('label', { for: id }, label), control, hintEl, error ? h('div', { class: 'error', role: 'alert' }, error) : null);
  wrap.setError = (msg) => {
    wrap.classList.toggle('invalid', !!msg);
    let e = wrap.querySelector('.error');
    if (!msg) { e && e.remove(); control.removeAttribute('aria-invalid'); return; }
    if (!e) { e = h('div', { class: 'error', role: 'alert' }); wrap.append(e); }
    e.textContent = msg; control.setAttribute('aria-invalid', 'true');
  };
  return wrap;
}
export const input = (attrs = {}) => h('input', { class: 'input', type: 'text', ...attrs });
export const textarea = (attrs = {}) => h('textarea', { class: 'textarea', ...attrs });
export function select(options, value, attrs = {}) {
  const el = h('select', { class: 'select', ...attrs }, ...options.map(([v, label]) => h('option', { value: v, selected: v === value }, label)));
  return el;
}

export const chip = (text, kind = '') => h('span', { class: 'chip ' + kind }, text);
export const card = (attrs, ...kids) => h('section', { ...attrs, class: 'card ' + ((attrs && attrs.class) || '') }, ...kids);
export const avatar = (text, org) => h('span', { class: 'avatar' + (org ? ' org' : ''), 'aria-hidden': 'true' }, text);

export function emptyState({ ico = 'inbox', title, text, action } = {}) {
  return h('div', { class: 'empty' }, h('div', { class: 'ico' }, icon(ico)), h('h3', title), text ? h('p', text) : null, action || null);
}
export function errorBox(message, retry) {
  return h('div', { class: 'error-box', role: 'alert' }, icon('circle-alert'), h('div', { class: 'grow' }, h('strong', t('state.error')), h('div', message)),
    retry ? button(t('action.retry'), { small: true, ico: 'refresh-cw', onClick: retry }) : null);
}
export function skeleton(lines = 3) {
  return h('div', { class: 'col', 'aria-busy': 'true', 'aria-label': t('state.loading') },
    ...Array.from({ length: lines }, (_, i) => h('div', { class: 'skeleton', style: { height: '1.1rem', width: i % 3 === 2 ? '55%' : '100%' } })));
}

// tabs with arrow-key support: items = [{id, label}], onSelect(id)
export function tabs(items, active, onSelect) {
  const el = h('div', { class: 'tabs', role: 'tablist' });
  const paint = (id) => [...el.children].forEach((b) => b.setAttribute('aria-selected', String(b.dataset.id === id)));
  items.forEach((it) => el.append(h('button', {
    role: 'tab', type: 'button', dataset: { id: it.id }, 'aria-selected': String(it.id === active), onClick: () => { paint(it.id); onSelect(it.id); },
    onKeydown: (e) => {
      const b = [...el.children], i = b.indexOf(e.currentTarget), rtl = document.documentElement.dir === 'rtl';
      const step = e.key === 'ArrowRight' ? (rtl ? -1 : 1) : e.key === 'ArrowLeft' ? (rtl ? 1 : -1) : 0;
      if (step) { e.preventDefault(); const n = b[(i + step + b.length) % b.length]; n.focus(); n.click(); }
    },
  }, it.label)));
  return el;
}

export function segmented(options, value, onChange) {
  const el = h('div', { class: 'seg', role: 'group' });
  const paint = (v) => [...el.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === v)));
  options.forEach(([v, label]) => el.append(h('button', { type: 'button', dataset: { v }, 'aria-pressed': String(v === value), onClick: () => { paint(v); onChange(v); } }, label)));
  return el;
}

export function switchInput(checked, onChange, label) {
  const inp = h('input', { type: 'checkbox', checked, 'aria-label': label, onChange: () => onChange(inp.checked) });
  return h('span', { class: 'switch' }, inp, h('span'));
}

// data table. cols = [{key, label, render(row), num, sortable}], rows = array. onOpen(row) makes rows clickable.
export function table(cols, rows, { onOpen, sort, onSort, empty } = {}) {
  if (!rows.length) return empty || emptyState({ title: t('state.empty') });
  const head = h('tr', ...cols.map((c) => h('th', {
    class: (c.num ? 'num ' : '') + (c.sortable ? 'sortable' : ''), scope: 'col',
    'aria-sort': sort && sort.key === c.key ? (sort.desc ? 'descending' : 'ascending') : null,
    onClick: c.sortable && onSort ? () => onSort(c.key) : null,
  }, c.label, sort && sort.key === c.key ? icon(sort.desc ? 'arrow-down' : 'arrow-up') : null)));
  const body = rows.map((r) => {
    const tr = h('tr', { tabindex: onOpen ? '0' : null, dataset: onOpen ? { open: '1' } : null },
      ...cols.map((c) => h('td', { class: c.num ? 'num' : '' }, c.render ? c.render(r) : r[c.key])));
    if (onOpen) {
      tr.addEventListener('click', (e) => { if (!e.target.closest('a,button,input,select')) onOpen(r); });
      tr.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target === tr) onOpen(r); });
    }
    return tr;
  });
  return h('div', { class: 'table-wrap' }, h('table', { class: 'table' }, h('thead', head), h('tbody', ...body)));
}

export function pageHeader(title, { sub, actions, crumbs } = {}) {
  return h('header', { class: 'page-head' },
    crumbs ? h('nav', { class: 'crumbs', 'aria-label': 'breadcrumb' }, ...crumbs) : null,
    h('div', { class: 'page-head-row' }, h('div', { class: 'grow' }, h('h1', title), sub ? h('p', { class: 'muted' }, sub) : null), actions ? h('div', { class: 'row wrap' }, ...actions) : null));
}

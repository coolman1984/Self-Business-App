// Command palette (Ctrl+K): jump to a screen, run an action, or find any record. Results for records come from the server
// search, which already applies the user's permissions and data scope.
import { h, icon, debounce, $, trapFocus } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { get } from '../core/api.js';
import { go } from '../core/router.js';
import { can } from '../core/session.js';
import { matches } from '../core/textnorm.js';

const RECORD_ICON = { parties: 'user', projects: 'briefcase', tasks: 'square-check-big', opportunities: 'target', appointments: 'calendar', notes: 'notebook-pen', services: 'tag', attachments: 'paperclip', activities: 'phone', inbox: 'inbox' };
const commands = [];   // {k: i18n key, ico, run, words?}
export const registerCommand = (c) => commands.push(c);

export function openPalette() {
  if ($('.palette')) return;
  const overlay = h('div', { class: 'overlay', onClick: () => close() });
  const list = h('ul', { role: 'listbox', id: 'pal-list' });
  const input = h('input', { type: 'text', placeholder: t('palette.placeholder'), 'aria-label': t('palette.placeholder'), 'aria-controls': 'pal-list', autocomplete: 'off', role: 'combobox', 'aria-expanded': 'true' });
  const foot = h('footer', h('span', h('kbd', '↑↓'), ' ', t('palette.move')), h('span', h('kbd', 'Enter'), ' ', t('palette.open')), h('span', h('kbd', 'Esc'), ' ', t('palette.close')));
  const box = h('div', { class: 'palette', role: 'dialog', 'aria-modal': 'true', 'aria-label': t('palette.title') }, input, list, foot);
  document.body.append(overlay, box);
  const release = trapFocus(box, () => close());
  input.focus();
  let items = [], sel = 0, seq = 0;

  function close() { overlay.remove(); box.remove(); release(); }
  function paint() {
    list.replaceChildren();
    let lastGroup = null;
    items.forEach((it, i) => {
      if (it.group !== lastGroup) { lastGroup = it.group; list.append(h('li', { class: 'group', role: 'presentation' }, t(it.group))); }
      list.append(h('li', { role: 'option', 'aria-selected': String(i === sel), id: 'pal-' + i, onClick: () => run(it), onMouseenter: () => { sel = i; mark(); } },
        icon(it.ico || 'circle'), h('span', it.label), it.hint ? h('span', { class: 'kind' }, it.hint) : null));
    });
    if (!items.length) list.append(h('li', { role: 'presentation', class: 'muted' }, t('palette.none')));
    input.setAttribute('aria-activedescendant', 'pal-' + sel);
  }
  function mark() { [...list.querySelectorAll('[role=option]')].forEach((li, i) => li.setAttribute('aria-selected', String(i === sel))); input.setAttribute('aria-activedescendant', 'pal-' + sel); }
  function run(it) { close(); it.run(); }
  function local(q) {
    const s = q.trim().toLowerCase();
    return commands.filter((c) => !c.perm || can(...[].concat(c.perm))).map((c) => ({ label: t(c.k), ico: c.ico, run: c.run, group: 'palette.g.go', words: (c.words || '') })).filter((c) => !s || matches(c.label + ' ' + c.words, s));
  }
  const remote = debounce(async (q) => {
    if (q.trim().length < 2) return;
    const my = ++seq;
    try {
      const hits = await get('/api/search?q=' + encodeURIComponent(q) + '&limit=8', { quiet: true });
      if (my !== seq) return;
      const rec = hits.map((x) => ({ label: x.title || x.id, hint: x.subtitle || x.entity, ico: RECORD_ICON[x.entity] || 'file-text', group: 'palette.g.records', run: () => import('../views/open.js').then((m) => m.openRecord(x.entity, x.id)) }));
      items = [...local(q), ...rec]; sel = Math.min(sel, Math.max(0, items.length - 1)); paint();
    } catch (e) { /* offline or not allowed: local commands still work */ }
  }, 180);
  input.addEventListener('input', () => { sel = 0; items = local(input.value); paint(); remote(input.value); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, items.length - 1); mark(); list.querySelector('[aria-selected=true]')?.scrollIntoView({ block: 'nearest' }); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); mark(); list.querySelector('[aria-selected=true]')?.scrollIntoView({ block: 'nearest' }); }
    else if (e.key === 'Enter' && items[sel]) { e.preventDefault(); run(items[sel]); }
  });
  items = local(''); paint();
}

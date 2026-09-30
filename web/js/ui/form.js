// Schema-driven forms: one description per screen, one look everywhere. Values come back ready for the server
// (money in piastres, dates as ISO text, empty text as undefined). Nothing here knows a business word.
import { h, debounce } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { field, input, textarea, select, button, chip } from './kit.js';
import { modal, drawer, toast } from './overlay.js';
import { get, friendly } from '../core/api.js';
import { parseMoney, moneyInput, partyName } from '../core/domain.js';
import { norm } from '../core/textnorm.js';

// ---- a searchable picker for people/companies (or any entity with a search index)
export function picker({ entity = 'parties', value, label, onChange, placeholder, exclude }) {
  const box = h('div', { class: 'picker' });
  const shown = input({ placeholder: placeholder || t('picker.search'), autocomplete: 'off', role: 'combobox', 'aria-expanded': 'false' });
  const list = h('ul', { class: 'picker-list', role: 'listbox', hidden: true });
  const clear = button('', { kind: 'ghost small', ico: 'x', title: t('action.clear'), onClick: () => set(null, '') });
  let current = value || null;
  shown.value = label || '';
  clear.hidden = !current;
  function set(id, text) {
    current = id; shown.value = text; clear.hidden = !id; list.hidden = true; shown.setAttribute('aria-expanded', 'false');
    onChange && onChange(id, text);
  }
  const find = debounce(async () => {
    const q = shown.value.trim();
    if (q.length < 1) { list.hidden = true; return; }
    try {
      let hits = await get(`/api/search?e=${entity}&q=${encodeURIComponent(q)}&limit=8`, { quiet: true });
      hits = hits.filter((x) => x.id !== exclude);
      list.replaceChildren(...hits.map((x) => h('li', { role: 'option', tabindex: '0', onClick: () => set(x.id, x.title), onKeydown: (e) => { if (e.key === 'Enter') set(x.id, x.title); } },
        h('b', x.title), x.subtitle ? h('span', { class: 'muted small' }, ' ' + x.subtitle) : null)));
      if (!hits.length) list.replaceChildren(h('li', { class: 'muted', role: 'presentation' }, t('picker.none')));
      list.hidden = false; shown.setAttribute('aria-expanded', 'true');
    } catch (e) { /* offline: keep typing */ }
  }, 200);
  shown.addEventListener('input', () => { if (current) { current = null; clear.hidden = true; onChange && onChange(null, ''); } find(); });
  shown.addEventListener('keydown', (e) => { if (e.key === 'Escape') list.hidden = true; if (e.key === 'ArrowDown') list.querySelector('li[tabindex]')?.focus(); });
  box.append(shown, clear, list);
  box.get = () => current;
  box.control = shown;
  return box;
}

const kinds = {
  text: (f, v) => input({ value: v ?? '', maxlength: f.max || 200, placeholder: f.placeholder, inputmode: f.mode, dir: f.dir, autocomplete: 'off' }),
  textarea: (f, v) => textarea({ rows: f.rows || 3 }, ),
  number: (f, v) => input({ type: 'text', inputmode: 'numeric', value: v ?? '' }),
  money: (f, v) => input({ type: 'text', inputmode: 'decimal', value: moneyInput(v), placeholder: '0' }),
  date: (f, v) => input({ type: 'date', value: v ? String(v).slice(0, 10) : '' }),
  datetime: (f, v) => input({ type: 'datetime-local', value: v ? String(v).slice(0, 16) : '' }),
  select: (f, v) => select([['', f.blank || '—'], ...f.options], v ?? f.default ?? ''),
};

// fields: [{key, label, type, required, options, hint, full, show(values)}]; returns {el, values(), errors(map)}
export function buildForm(fields, initial = {}) {
  const inputs = {}, wraps = {}, pickers = {};
  const el = h('div', { class: 'form-grid' });
  for (const f of fields) {
    let ctl, wrap;
    if (f.type === 'party') {
      ctl = picker({ entity: f.entity || 'parties', value: initial[f.key], label: f.labelText, placeholder: f.placeholder, exclude: f.exclude });
      pickers[f.key] = ctl;
      wrap = h('div', { class: 'field' + (f.full ? ' full' : '') }, h('label', { for: ctl.control.id || (ctl.control.id = 'pk-' + f.key) }, f.label + (f.required ? ' *' : '')), ctl, f.hint ? h('div', { class: 'hint' }, f.hint) : null);
      wrap.setError = (msg) => { wrap.classList.toggle('invalid', !!msg); let e = wrap.querySelector('.error'); if (!msg) { e && e.remove(); return; } if (!e) { e = h('div', { class: 'error', role: 'alert' }); wrap.append(e); } e.textContent = msg; };
    } else if (f.type === 'check') {
      const cb = h('input', { type: 'checkbox', checked: !!initial[f.key] });
      ctl = cb; wrap = h('div', { class: 'field' + (f.full ? ' full' : '') }, h('label', { class: 'checkbox' }, cb, h('span', f.label)), f.hint ? h('div', { class: 'hint' }, f.hint) : null);
      wrap.setError = () => {};
    } else if (f.type === 'checklist') {
      ctl = null;
      wrap = h('div', { class: 'field full' }); wrap.setError = () => {};
      const items = (initial[f.key] || []).map((x) => ({ ...x }));
      const holder = h('div', { class: 'col' });
      const paint = () => holder.replaceChildren(...items.map((it, i) => h('div', { class: 'row' },
        h('input', { type: 'checkbox', checked: !!it.d, 'aria-label': t('task.check'), onChange: (e) => { it.d = e.target.checked; } }),
        input({ value: it.t, class: 'input grow', 'aria-label': t('task.item'), onInput: (e) => { it.t = e.target.value; } }),
        button('', { kind: 'ghost small', ico: 'x', title: t('action.remove'), onClick: () => { items.splice(i, 1); paint(); } }))));
      paint();
      wrap.append(h('span', { class: 'label' }, f.label), holder, button(t('task.add.item'), { small: true, ico: 'plus', onClick: () => { items.push({ t: '', d: false }); paint(); holder.querySelectorAll('input.input').item(items.length - 1)?.focus(); } }));
      inputs[f.key] = { get value() { return items.filter((x) => x.t.trim()).map((x) => ({ t: x.t.trim(), d: !!x.d })); } };
      wraps[f.key] = wrap; el.append(wrap); continue;
    } else {
      ctl = kinds[f.type || 'text'](f, initial[f.key]);
      if (f.type === 'textarea') ctl.value = initial[f.key] ?? '';
      wrap = field(f.label + (f.required ? ' *' : ''), ctl, { hint: f.hint, full: f.full || f.type === 'textarea' });
    }
    inputs[f.key] = ctl; wraps[f.key] = wrap; el.append(wrap);
  }
  const conditional = () => fields.forEach((f) => { if (f.show) wraps[f.key].hidden = !f.show(read(true)); });
  function read(raw) {
    const v = {};
    for (const f of fields) {
      const c = inputs[f.key];
      if (f.type === 'party') v[f.key] = pickers[f.key].get() || undefined;
      else if (f.type === 'check') v[f.key] = c.checked;
      else if (f.type === 'checklist') v[f.key] = c.value;
      else if (f.type === 'money') { const m = parseMoney(c.value); v[f.key] = Number.isNaN(m) ? NaN : (m ?? undefined); }
      else if (f.type === 'number') { const s = norm(c.value); v[f.key] = s === '' ? undefined : Number(s); }
      else if (f.type === 'datetime') v[f.key] = c.value ? c.value : undefined;
      else v[f.key] = String(c.value ?? '').trim() === '' ? undefined : String(c.value).trim();
    }
    return raw ? v : Object.fromEntries(Object.entries(v).filter(([k]) => !wraps[k].hidden));
  }
  el.addEventListener('input', conditional); el.addEventListener('change', conditional);
  conditional();
  function validate() {
    const v = read(false);
    let ok = true, first = null;
    for (const f of fields) {
      if (wraps[f.key].hidden) continue;
      let msg = '';
      if (f.required && (v[f.key] === undefined || (Array.isArray(v[f.key]) && !v[f.key].length))) msg = t('err.required');
      else if (Number.isNaN(v[f.key])) msg = t('err.bad_amount');
      else if (f.type === 'number' && v[f.key] !== undefined && Number.isNaN(v[f.key])) msg = t('err.bad_number');
      wraps[f.key].setError && wraps[f.key].setError(msg);
      if (msg) { ok = false; first = first || (f.type === 'party' ? pickers[f.key].control : inputs[f.key].focus ? inputs[f.key] : null); }
    }
    first && first.focus();
    return ok ? v : null;
  }
  return { el, read: () => read(false), validate, inputs, wraps, pickers };
}

// dialog with a form; onSave(values) may throw (message shown under the buttons); returns the dialog
export function formDialog({ title, fields, values = {}, save = t('action.save'), side = false, wide = false, onSave, extra, danger, onReady }) {
  const form = buildForm(fields, values);
  const msg = h('div', { class: 'error', role: 'alert', hidden: true });
  const doSave = async (e) => {
    e && e.preventDefault();
    const v = form.validate();
    if (!v) return;
    msg.hidden = true;
    try { await onSave(v, form); dlg.close(true); } catch (err) { msg.textContent = friendly(err); msg.hidden = false; }
  };
  const body = h('form', { onSubmit: doSave }, form.el, extra || null, msg, h('button', { type: 'submit', hidden: true }));
  const cancel = button(t('action.cancel'), { onClick: () => dlg.close(false) });
  const ok = button(save, { kind: 'primary', ico: 'check', onClick: doSave });
  const footer = [...(danger ? [button(danger.label, { kind: 'danger', ico: 'trash-2', onClick: async () => { try { await danger.run(); dlg.close(true); } catch (err) { msg.textContent = friendly(err); msg.hidden = false; } } })] : []), cancel, ok];
  const dlg = (side ? drawer : modal)({ title, body, footer, wide });
  onReady && onReady(form, dlg);
  return dlg;
}

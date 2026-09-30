// The timeline of a client: one line per change, in the owner's words. Built from the change log by the server; here only text.
import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { ago, dateTime, date, money } from '../core/format.js';
import { enumText, ENUM_KEYS } from '../core/domain.js';

const ICON = { parties: 'user', party_roles: 'tag', party_relations: 'link', opportunities: 'target', projects: 'briefcase', tasks: 'square-check-big',
  appointments: 'calendar', notes: 'notebook-pen', activities: 'phone', attachments: 'paperclip', services: 'tag' };
const KIND = { tasks: '', notes: 'note', opportunities: '', appointments: '' };
const MONEY = new Set(['value_minor', 'budget_minor', 'price_minor']);
const SKIP = new Set(['sample', 'import_batch', 'merged_into', 'checklist', 'closed_at', 'done_at']);
const DATES = new Set(['due', 'start', 'expected_close', 'next_step_at', 'birthday']);

function valueText(entity, field, v) {
  if (v === null || v === undefined || v === '') return t('tl.empty');
  if (MONEY.has(field)) return money(v);
  if (DATES.has(field)) return date(v);
  if (field === 'starts_at' || field === 'ends_at' || field === 'at') return dateTime(v);
  if (typeof v === 'boolean') return v ? t('yes') : t('no');
  return ENUM_KEYS[`${entity}/${field}`] ? enumText(entity, field, v) : String(v);
}
const label = (entity, field) => t(`f.${field}`);

function line(e) {
  const name = (e.after && (e.after.name || e.after.title || e.after.summary || e.after.body || e.after.role)) || '';
  const short = String(name).length > 80 ? String(name).slice(0, 77) + '…' : name;
  if (e.op === 'insert') return { text: t('tl.insert.' + e.entity, { name: short }), detail: null };
  if (e.op === 'delete') return { text: t('tl.delete.' + e.entity), detail: null };
  const rows = Object.entries(e.changes || {}).filter(([k]) => !SKIP.has(k));
  if (!rows.length) return { text: t('tl.update.' + e.entity), detail: null };
  const parts = rows.slice(0, 4).map(([k, [a, b]]) => h('div', { class: 'small' }, h('span', { class: 'muted' }, label(e.entity, k) + ': '), a !== undefined && a !== null && a !== '' ? [h('s', { class: 'muted' }, valueText(e.entity, k, a)), ' ← '] : '', h('b', valueText(e.entity, k, b))));
  return { text: t('tl.update.' + e.entity), detail: parts };
}

export function timelineView(events) {
  if (!events.length) return h('p', { class: 'muted' }, t('tl.none'));
  return h('ol', { class: 'timeline' }, ...events.map((e) => {
    const { text, detail } = line(e);
    return h('li', { class: 'tl-item ' + (KIND[e.entity] || '') },
      h('div', { class: 'row' }, icon(ICON[e.entity] || 'circle'), h('span', { class: 'grow' }, text)),
      detail, h('div', { class: 'when' }, `${e.by || ''} · ${ago(e.at)}`, h('span', { class: 'sr-only' }, dateTime(e.at))));
  }));
}

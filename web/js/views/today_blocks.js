// What the business puts on the Today screen. Each block is one plain question: what is late, what is today, what is coming.
import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { card, chip, button, emptyState } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';
import { money, num, date, time } from '../core/format.js';
import { updateRecord, queryAll, dueState, META } from '../core/domain.js';
import { href, go } from '../core/router.js';
import { registerTodayBlock, todayData } from './today.js';
import { taskDialog, appointmentDialog, opportunityDialog } from './dialogs.js';

const refresh = () => go('/?r=' + Date.now());

function taskRow(x, names, ctx = {}) {
  const box = h('input', { class: 'check', type: 'checkbox', 'aria-label': x.title, disabled: !can('tasks.edit'), onChange: async (e) => {
    try { await updateRecord(t('task.edit'), 'tasks', x, { status: 'done' }); toast(t('task.done.toast'), { undo: async () => { const fresh = (await queryAll('tasks', { filters: [['id', 'eq', x.id]] }))[0]; await updateRecord(t('task.edit'), 'tasks', fresh, { status: 'todo' }); refresh(); } }); refresh(); }
    catch (err) { e.target.checked = false; toast(String(err.message), { kind: 'bad' }); }
  } });
  return h('div', { class: 'list-item' }, box, h('a', { class: 'grow', href: '#', onClick: (e) => { e.preventDefault(); taskDialog(x, refresh); } }, h('div', x.title), names[x.party_id] ? h('div', { class: 'muted small' }, names[x.party_id]) : null),
    x.priority === 'urgent' || x.priority === 'high' ? chip(t('prio.' + x.priority), x.priority === 'urgent' ? 'bad' : 'warn') : null,
    x.due ? h('span', { class: 'small due-' + dueState(x.due) }, x.due.length > 10 && ctx.time ? time(x.due) : date(x.due)) : null);
}
const apptRow = (a, names) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); appointmentDialog(a, refresh); } }, icon('calendar'),
  h('span', { class: 'small num muted', style: { minInlineSize: '3.4rem' } }, a.starts_at.length > 10 ? time(a.starts_at) : t('appt.allday')),
  h('span', { class: 'grow' }, h('div', a.title), names[a.party_id] ? h('div', { class: 'muted small' }, names[a.party_id]) : null), a.location ? h('span', { class: 'muted small' }, a.location) : null);

// numbers at the top
registerTodayBlock({ id: 'numbers', order: 1, async render() {
  const d = await todayData();
  const tiles = [['users', t('nav.clients'), d.counts.clients, '/clients'], ['briefcase', t('today.projects.active'), d.counts.projects, '/projects'], ['square-check-big', t('today.tasks.open'), d.counts.tasks, '/tasks'], ['user-plus', t('today.new.week'), d.newClients, '/clients']].filter(([, , n]) => n !== null && n !== undefined);
  if (!tiles.length || (d.counts.clients === 0 && !d.counts.tasks)) return null;
  return h('div', { class: 'stats' }, ...tiles.map(([ico, label, n, path]) => card({ class: 'stat' }, h('div', { class: 'top' }, h('div', h('div', { class: 'label' }, label), h('div', { class: 'value num' }, num(n))), h('span', { class: 'ico' }, icon(ico))), h('a', { class: 'small', href: href(path) }, t('action.open')))));
} });

// needs you now: late tasks, follow-ups due, the inbox
registerTodayBlock({ id: 'attention', order: 10, async render() {
  const d = await todayData();
  const late = d.overdue.length + d.followUps.length + d.urgentUndated.length;
  if (!late && !d.inbox) return null;
  return card({ class: 'accent', id: 'block-attention' }, h('div', { class: 'card-head' }, h('h2', t('today.attention')), chip(String(late + (d.inbox ? 1 : 0)), 'warn')),
    ...d.overdue.map((x) => taskRow(x, d.names)),
    ...d.followUps.map((o) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); opportunityDialog(o, refresh); } }, icon('target'), h('span', { class: 'grow' }, h('div', o.title), h('div', { class: 'muted small' }, [d.names[o.party_id], o.next_step].filter(Boolean).join(' · '))), chip(t('today.followup'), 'accent'), h('span', { class: 'small due-late' }, date(o.next_step_at)))),
    ...d.urgentUndated.map((x) => taskRow(x, d.names)),
    d.inbox ? h('a', { class: 'list-item', href: href('/inbox') }, icon('inbox'), h('span', { class: 'grow' }, t('today.inbox', { n: d.inbox })), icon('chevron-right')) : null);
} });

// today's schedule
registerTodayBlock({ id: 'schedule', order: 20, async render() {
  const d = await todayData();
  return card({ id: 'block-today' }, h('div', { class: 'card-head' }, h('h2', t('today.schedule')), can('calendar.create') ? button('', { small: true, kind: 'ghost', ico: 'plus', title: t('appt.new'), onClick: () => appointmentDialog(null, refresh, { starts_at: d.today + 'T09:00' }) }) : null),
    d.appointmentsToday.length || d.dueToday.length ? h('div', ...d.appointmentsToday.map((a) => apptRow(a, d.names)), ...d.dueToday.map((x) => taskRow(x, d.names, { time: true }))) : emptyState({ ico: 'sparkles', title: t('today.free.title'), text: t('today.free.text') }));
} });

// coming days
registerTodayBlock({ id: 'coming', order: 30, async render() {
  const d = await todayData();
  if (!d.appointmentsNext.length && !d.upcoming.length) return null;
  return card({}, h('div', { class: 'card-head' }, h('h2', t('today.coming')), h('a', { class: 'small', href: href('/calendar') }, t('nav.calendar'))),
    ...d.appointmentsNext.map((a) => h('div', { class: 'list-item' }, icon('calendar'), h('span', { class: 'grow' }, a.title), h('span', { class: 'small muted' }, date(a.starts_at, { weekday: 'short', day: 'numeric', month: 'short' }) + (a.starts_at.length > 10 ? ' · ' + time(a.starts_at) : '')))),
    ...d.upcoming.slice(0, 6).map((x) => h('div', { class: 'list-item' }, icon('square-check-big'), h('span', { class: 'grow' }, x.title), h('span', { class: 'small muted' }, date(x.due, { weekday: 'short', day: 'numeric', month: 'short' })))));
} });

// the pipeline in one glance
registerTodayBlock({ id: 'pipeline', order: 40, async render() {
  const d = await todayData();
  if (!can('sales.view')) return null;
  const total = META.openStages.reduce((a, s) => a + ((d.pipeline[s] || {}).count || 0), 0);
  if (!total) return null;
  const max = Math.max(...META.openStages.map((s) => (d.pipeline[s] || {}).count || 0), 1);
  return card({}, h('div', { class: 'card-head' }, h('h2', t('today.pipeline')), h('a', { class: 'small', href: href('/sales') }, t('nav.sales'))),
    ...META.openStages.map((s) => { const b = d.pipeline[s] || { count: 0 }; return h('div', { class: 'list-item' }, h('span', { style: { minInlineSize: '6rem' } }, t('stage.' + s)), h('div', { class: 'progress grow' }, h('i', { style: { width: Math.round(b.count * 100 / max) + '%' } })), h('span', { class: 'num small', style: { minInlineSize: '2rem', textAlign: 'end' } }, num(b.count)), b.value !== undefined ? h('span', { class: 'num small muted', style: { minInlineSize: '7rem', textAlign: 'end' } }, money(b.value)) : null); }),
    d.stalled.length ? h('p', { class: 'muted small', style: { marginBlockStart: '.6rem' } }, t('today.stalled', { n: d.stalled.length })) : null);
} });

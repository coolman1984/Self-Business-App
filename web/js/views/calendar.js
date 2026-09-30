// Calendar: a month grid (appointments and task due dates) and the day's list underneath.
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { card, chip, button, pageHeader, emptyState } from '../ui/kit.js';
import { date, time } from '../core/format.js';
import { queryAll, isoDate, addDays } from '../core/domain.js';
import { go } from '../core/router.js';
import { here } from '../core/router.js';
import { appointmentDialog, taskDialog } from './dialogs.js';

const pad = (n) => String(n).padStart(2, '0');

export async function calendarView({ query: q }) {
  const now = new Date();
  let y = Number((q.m || '').split('-')[0]) || now.getFullYear(), m = Number((q.m || '').split('-')[1]) || now.getMonth() + 1;
  const first = new Date(y, m - 1, 1);
  const startOffset = (first.getDay() + 1) % 7;            // the week starts on Saturday (Egypt); Saturday = 0
  const gridStart = new Date(y, m - 1, 1 - startOffset);
  const from = isoDate(gridStart), to = isoDate(new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + 42));
  const [appts, tasks] = await Promise.all([
    can('calendar.view') ? queryAll('appointments', { filters: [['starts_at', 'gte', from], ['starts_at', 'lt', to]], sort: 'starts_at' }) : [],
    can('tasks.view') ? queryAll('tasks', { filters: [['due', 'gte', from], ['due', 'lt', to], ['status', 'in', ['todo', 'doing', 'waiting']]] }) : [],
  ]);
  const byDay = {};
  appts.forEach((a) => (byDay[a.starts_at.slice(0, 10)] = byDay[a.starts_at.slice(0, 10)] || { a: [], t: [] }).a.push(a));
  tasks.forEach((x) => (byDay[x.due.slice(0, 10)] = byDay[x.due.slice(0, 10)] || { a: [], t: [] }).t.push(x));
  let selected = q.d || (now.getFullYear() === y && now.getMonth() + 1 === m ? isoDate(now) : `${y}-${pad(m)}-01`);
  const reload = () => go(`/calendar?m=${y}-${pad(m)}&d=${selected}&r=${Date.now()}`);
  const dayList = h('div');
  const monthLabel = date(`${y}-${pad(m)}-01`, { month: 'long', year: 'numeric' });
  const dows = Array.from({ length: 7 }, (_, i) => date(`2024-01-${pad(6 + i)}`, { weekday: 'short' }));   // 6 Jan 2024 = Saturday

  function paintDay() {
    const d = byDay[selected] || { a: [], t: [] };
    mount(dayList, card({}, h('div', { class: 'card-head' }, h('h2', date(selected, { weekday: 'long', day: 'numeric', month: 'long' })),
      h('div', { class: 'row' }, can('calendar.create') ? button(t('appt.new'), { small: true, ico: 'plus', onClick: () => appointmentDialog(null, reload, { starts_at: `${selected}T09:00` }) }) : null)),
      d.a.length || d.t.length ? h('div', ...d.a.map((a) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); appointmentDialog(a, reload); } },
        icon('calendar'), h('span', { class: 'small num muted', style: { minInlineSize: '3.2rem' } }, a.ends_at || a.starts_at.length > 10 ? time(a.starts_at) : t('appt.allday')), h('span', { class: 'grow' }, a.title), a.location ? h('span', { class: 'muted small' }, a.location) : null,
        a.status !== 'scheduled' ? chip(t('astatus.' + a.status), a.status === 'done' ? 'ok' : 'bad') : null)),
      ...d.t.map((x) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); taskDialog(x, reload); } }, icon('square-check-big'), h('span', { class: 'small muted', style: { minInlineSize: '3.2rem' } }, t('nav.tasks')), h('span', { class: 'grow' }, x.title)))) : h('p', { class: 'muted' }, t('cal.nothing'))));
  }
  const cells = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
    const iso = isoDate(d), info = byDay[iso] || { a: [], t: [] };
    const evs = [...info.a.map((a) => ({ text: (a.starts_at.length > 10 ? time(a.starts_at) + ' ' : '') + a.title, c: '' })), ...info.t.map((x) => ({ text: x.title, c: 'task' }))];
    const cell = h('div', { class: 'day' + (d.getMonth() + 1 !== m ? ' other' : '') + (iso === isoDate(now) ? ' today' : ''), role: 'button', tabindex: '0', 'aria-label': date(iso) + (evs.length ? ` (${evs.length})` : ''),
      onClick: () => { selected = iso; paintDay(); cells.forEach((c) => c.classList.toggle('sel', c.dataset.d === iso)); }, dataset: { d: iso },
      onKeydown: (e) => { if (e.key === 'Enter') e.currentTarget.click(); } },
    h('span', { class: 'n' }, String(d.getDate())), ...evs.slice(0, 3).map((e) => h('span', { class: 'ev ' + e.c }, e.text)), evs.length > 3 ? h('span', { class: 'more' }, '+' + (evs.length - 3)) : null,
    evs.length ? h('span', { class: 'dot-row' }, ...evs.slice(0, 4).map((e) => h('i', { class: 'dot ' + (e.c ? 'warn' : 'info') }))) : null);
    cells.push(cell);
  }
  const step = (n) => { const d = new Date(y, m - 1 + n, 1); go(`/calendar?m=${d.getFullYear()}-${pad(d.getMonth() + 1)}`); };
  paintDay();
  return h('div', pageHeader(t('nav.calendar'), { sub: t('cal.sub'), actions: [
    button('', { ico: 'chevron-left', title: t('cal.prev'), kind: 'ghost', onClick: () => step(-1) }), h('b', { style: { minInlineSize: '9rem', textAlign: 'center' } }, monthLabel),
    button('', { ico: 'chevron-right', title: t('cal.next'), kind: 'ghost', onClick: () => step(1) }), button(t('cal.today'), { onClick: () => go('/calendar') }),
    can('calendar.create') ? button(t('appt.new'), { kind: 'primary', ico: 'plus', onClick: () => appointmentDialog(null, reload, { starts_at: `${selected}T09:00` }) }) : null] }),
  h('div', { class: 'cal', role: 'grid' }, ...dows.map((d) => h('div', { class: 'dow' }, d)), ...cells), h('div', { style: { marginBlockStart: '1rem' } }, dayList));
}

// Tasks: what to do, by when. Tick to finish (with Undo), type a title and press Enter to add.
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can, session } from '../core/session.js';
import { friendly } from '../core/api.js';
import { card, chip, button, emptyState, pageHeader, table } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';
import { date } from '../core/format.js';
import { matches } from '../core/textnorm.js';
import { queryAll, updateRecord, createRecord, dueState, isoDate, addDays, namesOf } from '../core/domain.js';
import { refresh } from '../core/router.js';
import { taskDialog } from './dialogs.js';

const kept = { f: 'open', q: '', focusQuick: false };       // the filter and the search text survive a refresh of the list
const PRIO = { urgent: 'bad', high: 'warn', normal: '', low: '' };

export async function tasksView() {
  const tasks = await queryAll('tasks', { sort: 'rowid', desc: true });
  const [pn, jn] = await Promise.all([namesOf('parties', 'name', tasks.map((x) => x.party_id)), namesOf('projects', 'title', tasks.map((x) => x.project_id))]);
  const state = kept;
  const root = h('div');
  const today = isoDate();
  const reload = () => refresh();
  const FILTERS = [['open', t('filter.open')], ['today', t('filter.today')], ['late', t('filter.late')], ['week', t('filter.week')], ['done', t('filter.done')], ['all', t('filter.all')]];
  const pass = (x) => {
    const live = ['todo', 'doing', 'waiting'].includes(x.status);
    if (state.q && !matches(`${x.title} ${pn[x.party_id] || ''} ${jn[x.project_id] || ''}`, state.q)) return false;
    switch (state.f) {
      case 'open': return live;
      case 'today': return live && x.due && x.due.slice(0, 10) === today;
      case 'late': return live && x.due && x.due.slice(0, 10) < today;
      case 'week': return live && x.due && x.due.slice(0, 10) >= today && x.due.slice(0, 10) <= addDays(today, 7);
      case 'done': return x.status === 'done';
      default: return x.status !== 'cancelled';
    }
  };
  async function tick(x, on, box) {
    try {
      const before = x.status;
      await updateRecord(t('task.edit'), 'tasks', x, { status: on ? 'done' : 'todo' });
      if (on) toast(t('task.done.toast'), { undo: async () => { const fresh = (await queryAll('tasks', { filters: [['id', 'eq', x.id]] }))[0]; await updateRecord(t('task.edit'), 'tasks', fresh, { status: before === 'done' ? 'todo' : before }); reload(); } });
      reload();
    } catch (e) { box.checked = !on; toast(friendly(e), { kind: 'bad' }); }
  }
  function paint() {
    const rows = tasks.filter(pass).sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999'));
    mount(root, rows.length ? card({ class: 'flush' }, table([
      { key: 'done', label: '', render: (x) => h('input', { class: 'check', type: 'checkbox', checked: x.status === 'done', disabled: !can('tasks.edit'), 'aria-label': x.title, onChange: (e) => tick(x, e.target.checked, e.target) }) },
      { key: 'title', label: t('f.task'), render: (x) => h('div', h('b', { class: x.status === 'done' ? 'done-text' : '' }, x.title), h('div', { class: 'muted small' }, [pn[x.party_id], jn[x.project_id]].filter(Boolean).join(' · '))) },
      { key: 'due', label: t('f.due'), render: (x) => (x.due ? h('span', { class: x.status === 'done' ? 'muted' : 'due-' + dueState(x.due) }, date(x.due)) : h('span', { class: 'muted' }, '—')) },
      { key: 'prio', label: t('f.priority'), render: (x) => (x.priority && x.priority !== 'normal' ? chip(t('prio.' + x.priority), PRIO[x.priority]) : '') },
      { key: 'status', label: t('f.status'), render: (x) => (['doing', 'waiting'].includes(x.status) ? chip(t('tstatus.' + x.status), 'info') : '') },
    ], rows, { onOpen: can('tasks.edit') ? (x) => taskDialog(x, reload) : null }))
      : emptyState({ ico: 'square-check-big', title: tasks.length ? t('tasks.none.filter') : t('tasks.empty.title'), text: tasks.length ? '' : t('tasks.empty.text') }));
  }
  const quick = h('input', { class: 'input', placeholder: t('task.quick'), 'aria-label': t('task.quick'), id: 'task-quick', onKeydown: async (e) => {
    if (e.key === 'Enter' && quick.value.trim()) {
      try { await createRecord(t('task.new'), 'tasks', { title: quick.value.trim(), status: 'todo', priority: 'normal', kind: 'task', due: state.f === 'today' ? today : undefined }); state.focusQuick = true; reload(); } catch (err) { toast(friendly(err), { kind: 'bad' }); }
    }
  } });
  const filters = h('div', { class: 'filters', role: 'group' }, ...FILTERS.map(([id, label]) => h('button', { type: 'button', dataset: { v: id }, 'aria-pressed': String(state.f === id), onClick: () => { state.f = id; [...filters.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === id))); paint(); } }, label)));
  const search = h('input', { class: 'input', type: 'search', value: state.q, placeholder: t('tasks.search'), 'aria-label': t('tasks.search'), onInput: (e) => { state.q = e.target.value; paint(); } });
  paint();
  if (state.focusQuick) { state.focusQuick = false; setTimeout(() => document.getElementById('task-quick')?.focus(), 60); }
  return h('div', pageHeader(t('nav.tasks'), { sub: t('tasks.sub'), actions: [can('tasks.create') ? button(t('task.new'), { kind: 'primary', ico: 'plus', onClick: () => taskDialog(null, reload) }) : null] }),
    can('tasks.create') ? card({ style: { marginBlockEnd: '1rem' } }, quick) : null,
    h('div', { class: 'toolbar' }, filters, h('div', { class: 'searchbox' }, icon('search'), search)), root);
}

// Projects: list with progress (from their tasks) and a project page with its own tasks.
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { card, chip, button, emptyState, pageHeader, table, errorBox } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';
import { money, date } from '../core/format.js';
import { META, queryAll, getRecord, updateRecord, dueState, createRecord } from '../core/domain.js';
import { href, go } from '../core/router.js';
import { projectDialog, taskDialog } from './dialogs.js';

const CLASS = { done: 'ok', active: 'info', paused: 'warn', cancelled: 'bad' };
const progressBar = (done, total) => h('div', { class: 'row', style: { gap: '.5rem', minInlineSize: '7rem' } }, h('div', { class: 'progress grow', role: 'progressbar', 'aria-valuenow': String(total ? Math.round(done * 100 / total) : 0), 'aria-valuemin': '0', 'aria-valuemax': '100' }, h('i', { style: { width: (total ? Math.round(done * 100 / total) : 0) + '%' } })), h('span', { class: 'small muted num' }, `${done}/${total}`));

async function names(ids) {
  const out = {};
  const list = [...new Set(ids.filter(Boolean))];
  for (let i = 0; i < list.length; i += 200) (await queryAll('parties', { filters: [['id', 'in', list.slice(i, i + 200)]] })).forEach((p) => (out[p.id] = p.name));
  return out;
}

export async function projectsView() {
  const [projs, tasks] = await Promise.all([queryAll('projects', { sort: 'rowid', desc: true }), can('tasks.view') ? queryAll('tasks', { filters: [['project_id', 'notnull', '']] }) : []]);
  const nm = await names(projs.map((p) => p.party_id));
  const counts = {};
  tasks.forEach((x) => { const c = (counts[x.project_id] = counts[x.project_id] || { done: 0, total: 0 }); if (x.status !== 'cancelled') { c.total++; if (x.status === 'done') c.done++; } });
  const state = { status: 'open' };
  const root = h('div');
  const reload = () => go('/projects?r=' + Date.now());
  function paint() {
    const rows = projs.filter((p) => (state.status === 'open' ? ['planned', 'active', 'paused'].includes(p.status) : state.status === 'all' ? true : p.status === state.status));
    mount(root, rows.length ? card({ class: 'flush' }, table([
      { key: 'title', label: t('f.project'), render: (p) => h('div', h('b', p.title), h('div', { class: 'muted small' }, nm[p.party_id] || '')) },
      { key: 'status', label: t('f.status'), render: (p) => chip(t('pstatus.' + p.status), CLASS[p.status] || '') },
      { key: 'progress', label: t('f.progress'), render: (p) => (counts[p.id] ? progressBar(counts[p.id].done, counts[p.id].total) : h('span', { class: 'muted' }, '—')) },
      { key: 'due', label: t('f.due_project'), render: (p) => (p.due ? h('span', { class: p.status === 'done' ? '' : 'due-' + dueState(p.due) }, date(p.due)) : '') },
      ...(can('money.view') ? [{ key: 'budget', label: t('f.budget'), num: true, render: (p) => (p.budget_minor != null ? money(p.budget_minor) : '') }] : []),
    ], rows, { onOpen: (p) => go('/projects/' + encodeURIComponent(p.id)) }))
      : emptyState({ ico: 'briefcase', title: t('project.empty.title'), text: t('project.empty.text'), action: can('projects.create') ? button(t('project.new'), { kind: 'primary', ico: 'plus', onClick: () => projectDialog(null, reload) }) : null }));
  }
  const filters = h('div', { class: 'filters', role: 'group' }, ...[['open', t('filter.open')], ['done', t('pstatus.done')], ['cancelled', t('pstatus.cancelled')], ['all', t('filter.all')]].map(([id, label]) =>
    h('button', { type: 'button', dataset: { v: id }, 'aria-pressed': String(state.status === id), onClick: () => { state.status = id; [...filters.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === id))); paint(); } }, label)));
  paint();
  return h('div', pageHeader(t('nav.projects'), { sub: t('projects.sub'), actions: [can('projects.create') ? button(t('project.new'), { kind: 'primary', ico: 'plus', onClick: () => projectDialog(null, reload) }) : null] }), h('div', { class: 'toolbar' }, filters), root);
}

export async function projectView({ params }) {
  const p = await getRecord('projects', params.id);
  const [tasks, party] = await Promise.all([can('tasks.view') ? queryAll('tasks', { filters: [['project_id', 'eq', p.id]], sort: 'due' }) : [], p.party_id && can('clients.view') ? getRecord('parties', p.party_id).catch(() => null) : null]);
  const reload = (what) => (what === 'deleted' ? go('/projects') : go('/projects/' + encodeURIComponent(p.id) + '?r=' + Date.now()));
  const live = tasks.filter((x) => x.status !== 'cancelled');
  const doneN = live.filter((x) => x.status === 'done').length;
  const quick = h('input', { class: 'input', placeholder: t('task.quick'), 'aria-label': t('task.quick'), onKeydown: async (e) => {
    if (e.key === 'Enter' && quick.value.trim()) { await createRecord(t('task.new'), 'tasks', { title: quick.value.trim(), project_id: p.id, party_id: p.party_id, status: 'todo', priority: 'normal', kind: 'task' }); reload(); }
  } });
  const toggle = async (x, on) => { await updateRecord(t('task.edit'), 'tasks', x, { status: on ? 'done' : 'todo' }); reload(); };
  return h('div', h('div', { class: 'record-head' }, h('div', { class: 'grow' },
    h('div', { class: 'crumbs' }, h('a', { href: href('/projects') }, t('nav.projects')), icon('chevron-right', 'mirror'), h('span', p.title)),
    h('h1', p.title), h('div', { class: 'row wrap', style: { marginBlockStart: '.35rem' } }, chip(t('pstatus.' + p.status), CLASS[p.status] || ''),
      party ? h('a', { href: href('/clients/' + encodeURIComponent(party.id)) }, party.name) : null)),
    can('projects.edit') ? button(t('action.edit'), { ico: 'pencil', onClick: () => projectDialog(p, reload) }) : null),
  h('div', { class: 'stats', style: { marginBlockEnd: '1rem' } },
    card({ class: 'stat' }, h('div', { class: 'label' }, t('f.progress')), h('div', { class: 'value num' }, live.length ? Math.round(doneN * 100 / live.length) + '%' : '—'), progressBar(doneN, live.length)),
    card({ class: 'stat' }, h('div', { class: 'label' }, t('f.due_project')), h('div', { class: 'value', style: { fontSize: '1.4rem' } }, p.due ? date(p.due) : '—'), p.start ? h('div', { class: 'muted small' }, t('f.start') + ': ' + date(p.start)) : null),
    p.budget_minor != null ? card({ class: 'stat' }, h('div', { class: 'label' }, t('f.budget')), h('div', { class: 'value num', style: { fontSize: '1.5rem' } }, money(p.budget_minor))) : null),
  p.description ? card({ style: { marginBlockEnd: '1rem' } }, h('p', { style: { whiteSpace: 'pre-wrap' } }, p.description)) : null,
  card({}, h('div', { class: 'card-head' }, h('h2', t('nav.tasks')), can('tasks.create') ? button(t('task.new'), { small: true, ico: 'plus', onClick: () => taskDialog(null, reload, { project_id: p.id, party_id: p.party_id }) }) : null),
    can('tasks.create') ? h('div', { style: { marginBlockEnd: '.8rem' } }, quick) : null,
    tasks.length ? h('div', ...tasks.map((x) => h('div', { class: 'list-item' }, h('input', { class: 'check', type: 'checkbox', checked: x.status === 'done', disabled: !can('tasks.edit'), 'aria-label': x.title, onChange: (e) => toggle(x, e.target.checked) }),
      h('a', { class: 'grow' + (x.status === 'done' ? ' done-text' : ''), href: '#', onClick: (e) => { e.preventDefault(); taskDialog(x, reload); } }, x.title), x.due ? h('span', { class: 'small due-' + (x.status === 'done' ? '' : dueState(x.due)) }, date(x.due)) : null))) : h('p', { class: 'muted' }, t('state.empty'))));
}

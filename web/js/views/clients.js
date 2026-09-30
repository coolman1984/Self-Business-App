// People and companies: the list and the living client file (overview, timeline, work, notes, files).
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { session, can } from '../core/session.js';
import { get, post, api, uuid, commit, friendly } from '../core/api.js';
import { here, go, href } from '../core/router.js';
import { card, chip, button, emptyState, errorBox, pageHeader, skeleton, table, tabs, avatar, segmented } from '../ui/kit.js';
import { menu, toast, confirmBox, modal } from '../ui/overlay.js';
import { timelineView } from '../ui/timeline.js';
import { date, dateTime, ago, money, initials } from '../core/format.js';
import { matches, norm } from '../core/textnorm.js';
import { META, queryAll, getRecord, updateRecord, createRecord, phoneShow, telHref, waHref, mailHref, enumText, opPut, opDel, dueState, isoDate, stripped } from '../core/domain.js';
import { partyDialog, opportunityDialog, projectDialog, taskDialog, appointmentDialog, activityDialog, relationDialog, removeRecord } from './dialogs.js';
import { formDialog } from '../ui/form.js';

const partyAvatar = (p, big) => h('span', { class: 'avatar' + (p.kind === 'org' ? ' org' : '') + (big ? ' lg' : ''), 'aria-hidden': 'true' }, p.kind === 'org' ? icon('building-2') : initials(p.name));

// ---------------------------------------------------------------------------------------------- list
export async function clientsView() {
  const [parties, roles] = await Promise.all([
    queryAll('parties', { filters: [['status', 'ne', 'merged']], sort: 'name' }),
    queryAll('party_roles', {}),
  ]);
  const rolesOf = {};
  roles.forEach((r) => (rolesOf[r.party_id] = rolesOf[r.party_id] || []).push(r.role));
  const state = { q: '', role: 'all', kind: 'all', archived: false };
  const body = h('div');
  const count = h('span', { class: 'muted' });

  function filtered() {
    return parties.filter((p) => {
      if (!!(p.status === 'archived') !== state.archived) return false;
      if (state.role !== 'all' && !(rolesOf[p.id] || []).includes(state.role)) return false;
      if (state.kind !== 'all' && p.kind !== state.kind) return false;
      if (!state.q) return true;
      const digits = norm(state.q).replace(/\D/g, '');
      return matches([p.name, p.name_en, p.legal_name, p.email, p.city, p.tags, p.phone, p.phone2].join(' '), state.q)
        || (digits.length >= 4 && [p.phone, p.phone2].some((x) => (x || '').replace(/\D/g, '').includes(digits.replace(/^0/, ''))));
    });
  }
  function paint() {
    const rows = filtered();
    count.textContent = t('list.count', { n: rows.length });
    mount(body, rows.length ? table([
      { key: 'name', label: t('f.name'), render: (p) => h('div', { class: 'pcell' }, partyAvatar(p), h('div', { class: 'truncate' }, h('b', p.name), h('span', { class: 'muted' }, [p.kind === 'org' ? t('pkind.org') : null, p.city].filter(Boolean).join(' · ')))) },
      { key: 'phone', label: t('f.phone'), render: (p) => (p.phone ? h('span', { class: 'ltr num' }, phoneShow(p.phone)) : h('span', { class: 'muted' }, '—')) },
      { key: 'role', label: t('f.role'), render: (p) => h('div', { class: 'row wrap', style: { gap: '.3rem' } }, ...(rolesOf[p.id] || []).map((r) => chip(t('role.' + r), r === 'client' ? 'ok' : r === 'lead' ? 'accent' : ''))) },
      { key: '_created', label: t('f.added'), render: (p) => h('span', { class: 'muted small' }, date(p._created)) },
    ], rows, { onOpen: (p) => go('/clients/' + encodeURIComponent(p.id)) })
      : (parties.length ? emptyState({ ico: 'search', title: t('list.nomatch'), text: t('list.nomatch.text') })
        : emptyState({ ico: 'users', title: t('clients.empty.title'), text: t('clients.empty.text'), action: can('clients.create') ? button(t('client.new'), { kind: 'primary', ico: 'plus', onClick: newClient }) : null })));
  }
  const newClient = () => partyDialog(null, (id) => go('/clients/' + encodeURIComponent(id)));
  const search = h('input', { class: 'input', type: 'search', placeholder: t('clients.search'), 'aria-label': t('clients.search'), onInput: (e) => { state.q = e.target.value; paint(); } });
  const roleFilter = h('div', { class: 'filters', role: 'group', 'aria-label': t('f.role') }, ...[['all', t('filter.all')], ...META.roles.slice(0, 4).map((r) => [r, t('role.' + r)])].map(([id, label]) =>
    h('button', { type: 'button', 'aria-pressed': String(state.role === id), dataset: { v: id }, onClick: (e) => { state.role = id; [...roleFilter.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === id))); paint(); } }, label)));
  const kindSeg = segmented([['all', t('filter.all')], ['person', t('pkind.person')], ['org', t('pkind.org')]], 'all', (v) => { state.kind = v; paint(); });
  const archBtn = button(t('filter.archived'), { small: true, kind: 'ghost', ico: 'folder', onClick: () => { state.archived = !state.archived; archBtn.classList.toggle('primary', state.archived); paint(); } });
  paint();
  return h('div', pageHeader(t('nav.clients'), { sub: t('clients.sub'), actions: [
    can('data.import') ? button(t('import.title'), { ico: 'upload', href: href('/import') }) : null,
    can('clients.view') ? button(t('dup.title'), { ico: 'copy', href: href('/duplicates') }) : null,
    can('clients.create') ? button(t('client.new'), { kind: 'primary', ico: 'plus', id: 'new-client', onClick: newClient }) : null] }),
  card({ class: 'flush' }, h('div', { class: 'toolbar', style: { padding: '1rem 1rem 0' } }, h('div', { class: 'searchbox' }, icon('search'), search), roleFilter, kindSeg, archBtn, count), body));
}

// ---------------------------------------------------------------------------------------------- record page
const TAB_IDS = ['overview', 'timeline', 'work', 'notes', 'files'];

export async function clientView({ params, query: q }) {
  const p = await getRecord('parties', params.id);
  if (p.merged_into) { go('/clients/' + encodeURIComponent(p.merged_into)); return h('div'); }
  const [roles, fields] = await Promise.all([queryAll('party_roles', { filters: [['party_id', 'eq', p.id]] }), can('clients.view') ? queryAll('custom_field_defs', { filters: [['entity', 'eq', 'parties']] }) : []]);
  const reload = () => go(location.hash.slice(1).split('?')[0] + '?tab=' + active + '&r=' + Date.now());
  let active = TAB_IDS.includes(q.tab) ? q.tab : 'overview';
  const body = h('div', { style: { marginBlockStart: '1.1rem' } });
  const ctx = { p, roles, fields, reload };

  const more = (e) => menu(e.currentTarget, [
    can('clients.edit') ? { label: t('client.roles'), ico: 'tag', onClick: () => rolesDialog(p, roles, reload) } : null,
    can('clients.edit') ? { label: t('rel.new'), ico: 'link', onClick: () => relationDialog(p, reload) } : null,
    can('clients.edit') ? { label: t('merge.title'), ico: 'copy', onClick: () => mergeDialog(p, roles) } : null,
    can('clients.edit') ? { label: p.status === 'archived' ? t('client.unarchive') : t('client.archive'), ico: 'folder', onClick: async () => { await updateRecord(t('client.archive'), 'parties', p, { status: p.status === 'archived' ? 'active' : 'archived' }); toast(t('toast.saved')); reload(); } } : null,
    '-',
    can('clients.delete') ? { label: t('action.delete'), ico: 'trash-2', onClick: async () => { if (await removeRecord(t('client.delete'), 'parties', p, () => {})) go('/clients'); } } : null,
  ].filter(Boolean));

  const head = h('div', { class: 'record-head' }, partyAvatar(p, true),
    h('div', { class: 'grow' }, h('div', { class: 'crumbs' }, h('a', { href: href('/clients') }, t('nav.clients')), icon('chevron-right', 'mirror'), h('span', p.name)),
      h('h1', p.name), h('div', { class: 'row wrap', style: { marginBlockStart: '.35rem', gap: '.35rem' } },
        ...roles.map((r) => chip(t('role.' + r.role), r.role === 'client' ? 'ok' : r.role === 'lead' ? 'accent' : '')), p.status === 'archived' ? chip(t('partystatus.archived')) : null,
        ...(p.tags ? p.tags.split(/[,،]/).map((x) => x.trim()).filter(Boolean).map((x) => h('span', { class: 'tag' }, '#' + x)) : []))),
    h('div', { class: 'contact-btns' },
      p.phone ? button(t('contact.call'), { ico: 'phone', href: telHref(p.phone) }) : null,
      p.phone ? button('WhatsApp', { ico: 'message-circle', href: waHref(p.phone), title: t('contact.whatsapp') }) : null,
      p.email ? button(t('contact.email'), { ico: 'mail', href: mailHref(p.email) }) : null,
      can('clients.edit') ? button(t('action.edit'), { ico: 'pencil', onClick: () => partyDialog(p, reload) }) : null,
      button('', { ico: 'ellipsis', title: t('action.more'), onClick: more })));
  // the WhatsApp brand name is a product name, not a translated word; the a11y label above is translated

  const TABS = { overview, timeline, work, notes, files };
  const show = async (id) => {
    active = id;
    mount(body, skeleton(4));
    try { mount(body, h('div', { class: 'page-in' }, await TABS[id](ctx))); } catch (e) { mount(body, errorBox(friendly(e), () => show(id))); }
  };
  const tb = h('div', { class: 'pill-tabs', role: 'tablist' }, ...TAB_IDS.map((id) => h('button', { role: 'tab', type: 'button', 'aria-selected': String(id === active), dataset: { id }, onClick: () => { [...tb.children].forEach((b) => b.setAttribute('aria-selected', String(b.dataset.id === id))); show(id); } }, t('tab.' + id))));
  show(active);
  return h('div', head, tb, body);
}

function kv(pairs) {
  const rows = pairs.filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== false);
  return h('dl', { class: 'kv' }, ...rows.flatMap(([k, v]) => [h('dt', k), h('dd', v)]));
}

// ---- overview: contact data, extra fields, relations, what comes next
async function overview({ p, fields, reload }) {
  const [rels, tasks, appts, values] = await Promise.all([
    Promise.all([queryAll('party_relations', { filters: [['from_party', 'eq', p.id]] }), queryAll('party_relations', { filters: [['to_party', 'eq', p.id]] })]).then(([a, b]) => [...a.map((r) => ({ ...r, other: r.to_party })), ...b.map((r) => ({ ...r, other: r.from_party }))]),
    can('tasks.view') ? queryAll('tasks', { filters: [['party_id', 'eq', p.id], ['status', 'in', META.taskStatus.slice(0, 3)]], sort: 'due' }) : [],
    can('calendar.view') ? queryAll('appointments', { filters: [['party_id', 'eq', p.id], ['status', 'eq', 'scheduled'], ['starts_at', 'gte', isoDate()]], sort: 'starts_at' }) : [],
    fields.length ? queryAll('custom_values', { filters: [['record_id', 'eq', p.id]] }) : [],
  ]);
  const others = rels.length ? await queryAll('parties', { filters: [['id', 'in', [...new Set(rels.map((r) => r.other))]]] }) : [];
  const byId = Object.fromEntries(others.map((o) => [o.id, o]));
  const cv = Object.fromEntries(values.map((v) => [v.key, v]));
  const pinned = can('notes.view') ? (await queryAll('notes', { filters: [['party_id', 'eq', p.id], ['pinned', 'eq', 1]] })) : [];
  const ar = document.documentElement.lang === 'ar';
  const ext = fields.sort((a, b) => (a.order || 0) - (b.order || 0)).map((f) => [ar ? f.label_ar || f.label_en : f.label_en || f.label_ar, (cv[f.key] || {}).text_v || (cv[f.key] || {}).num_v || ((cv[f.key] || {}).date_v ? date(cv[f.key].date_v) : '')]);
  return h('div', { class: 'grid-main' },
    h('div', { class: 'stack-lg' },
      card({}, h('div', { class: 'card-head' }, h('h2', t('client.contact'))), kv([
        [t('f.phone'), p.phone && h('a', { class: 'ltr', href: telHref(p.phone) }, phoneShow(p.phone))], [t('f.phone2'), p.phone2 && h('a', { class: 'ltr', href: telHref(p.phone2) }, phoneShow(p.phone2))],
        [t('f.email'), p.email && h('a', { class: 'ltr', href: mailHref(p.email) }, p.email)], [t('f.address'), [p.address, p.city].filter(Boolean).join('، ')],
        [t('f.website'), p.website && h('a', { class: 'ltr', href: /^https?:/.test(p.website) ? p.website : 'https://' + p.website, target: '_blank', rel: 'noopener noreferrer' }, p.website)],
        [t('f.tax_id'), p.tax_id], [t('f.birthday'), p.birthday && date(p.birthday)], [t('f.national_id'), p.national_id], [t('f.source'), p.source && enumText('parties', 'source', p.source)],
        [t('f.added'), `${date(p._created)} · ${p._created_by || ''}`]])),
      ext.some(([, v]) => v) ? card({}, h('div', { class: 'card-head' }, h('h2', t('client.extra')), can('clients.edit') ? button(t('action.edit'), { small: true, ico: 'pencil', onClick: () => customValuesDialog(p, fields, cv, reload) }) : null), kv(ext)) : (fields.length && can('clients.edit') ? button(t('client.extra.fill'), { ico: 'plus', onClick: () => customValuesDialog(p, fields, cv, reload) }) : null),
      rels.length ? card({}, h('div', { class: 'card-head' }, h('h2', t('client.relations'))), ...rels.map((r) => h('div', { class: 'list-item' }, partyAvatar(byId[r.other] || { name: '?' }), h('div', { class: 'grow' }, h('a', { href: href('/clients/' + encodeURIComponent(r.other)) }, (byId[r.other] || {}).name || '…'), h('div', { class: 'muted small' }, [t('rel.' + r.kind), r.title].filter(Boolean).join(' · '))),
        can('clients.edit') ? button('', { kind: 'ghost small', ico: 'x', title: t('action.remove'), onClick: async () => { await commit(t('rel.remove'), [opDel('party_relations', r.id, r.ver)]); reload(); } }) : null))) : null),
    h('div', { class: 'stack-lg' },
      card({}, h('div', { class: 'card-head' }, h('h2', t('client.next'))),
        ...(tasks.slice(0, 4).map((x) => h('div', { class: 'list-item' }, icon('square-check-big'), h('span', { class: 'grow' }, x.title), x.due ? h('span', { class: 'small due-' + dueState(x.due) }, date(x.due)) : null))),
        ...(appts.slice(0, 3).map((x) => h('div', { class: 'list-item' }, icon('calendar'), h('span', { class: 'grow' }, x.title), h('span', { class: 'small muted' }, dateTime(x.starts_at))))),
        !tasks.length && !appts.length ? h('p', { class: 'muted' }, t('client.next.none')) : null,
        h('div', { class: 'row wrap', style: { marginBlockStart: '.8rem' } },
          can('tasks.create') ? button(t('task.new'), { small: true, ico: 'plus', onClick: () => taskDialog(null, reload, { party_id: p.id }) }) : null,
          can('calendar.create') ? button(t('appt.new'), { small: true, ico: 'calendar', onClick: () => appointmentDialog(null, reload, { party_id: p.id }) }) : null,
          can('notes.create') ? button(t('act.new'), { small: true, ico: 'phone', onClick: () => activityDialog(null, reload, { party_id: p.id }) }) : null)),
      pinned.length ? card({}, h('div', { class: 'card-head' }, h('h2', t('notes.pinned'))), ...pinned.map((n) => h('p', { style: { whiteSpace: 'pre-wrap' } }, n.body))) : null));
}

async function customValuesDialog(p, fields, cv, reload) {
  const lang = document.documentElement.lang;
  const ff = fields.map((f) => ({ key: f.key, label: (lang === 'ar' ? f.label_ar || f.label_en : f.label_en || f.label_ar), required: !!f.required,
    type: f.type === 'choice' ? 'select' : f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text', options: (f.options || []).map((o) => [o, o]) }));
  const vals = Object.fromEntries(fields.map((f) => [f.key, (cv[f.key] || {})[f.type === 'number' ? 'num_v' : f.type === 'date' ? 'date_v' : 'text_v']]));
  formDialog({ title: t('client.extra'), fields: ff, values: vals, onSave: async (v) => {
    const ops = fields.map((f) => {
      const cur = cv[f.key];
      const row = { entity: 'parties', record_id: p.id, key: f.key, [f.type === 'number' ? 'num_v' : f.type === 'date' ? 'date_v' : 'text_v']: v[f.key] };
      return opPut('custom_values', `parties:${p.id}:${f.key}`, row, cur ? cur.ver : undefined);
    });
    await commit(t('client.extra'), ops); toast(t('toast.saved')); reload();
  } });
}

// ---- timeline
async function timeline({ p }) {
  const r = await get('/api/timeline?party=' + encodeURIComponent(p.id) + '&limit=150');
  return card({}, h('div', { class: 'card-head' }, h('h2', t('tab.timeline'))), timelineView(r.events));
}

// ---- work: opportunities, projects, tasks, appointments, follow-ups
async function work({ p, reload }) {
  const [opps, projs, tasks, appts, acts] = await Promise.all(['opportunities', 'projects', 'tasks', 'appointments', 'activities'].map((e, i) =>
    can(['sales', 'projects', 'tasks', 'calendar', 'notes'][i] + '.view') ? queryAll(e, { filters: [['party_id', 'eq', p.id]], sort: ['stage', 'status', 'due', 'starts_at', 'at'][i], desc: i > 2 }) : []));
  const section = (title, ico, items, render, add) => card({}, h('div', { class: 'card-head' }, h('h2', title), add || null),
    items.length ? h('div', ...items.map(render)) : h('p', { class: 'muted' }, t('state.empty')));
  return h('div', { class: 'grid-2' },
    section(t('nav.sales'), 'target', opps, (o) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); opportunityDialog(o, reload); } }, chip(t('stage.' + o.stage), o.stage === 'won' ? 'ok' : o.stage === 'lost' ? 'bad' : 'info'), h('span', { class: 'grow' }, o.title), o.value_minor != null ? h('span', { class: 'num small' }, money(o.value_minor)) : null),
      can('sales.create') ? button('', { small: true, ico: 'plus', title: t('opp.new'), onClick: () => opportunityDialog(null, reload, { party_id: p.id }) }) : null),
    section(t('nav.projects'), 'briefcase', projs, (o) => h('a', { class: 'list-item', href: href('/projects/' + encodeURIComponent(o.id)) }, chip(t('pstatus.' + o.status), o.status === 'done' ? 'ok' : o.status === 'active' ? 'info' : ''), h('span', { class: 'grow' }, o.title), o.due ? h('span', { class: 'small muted' }, date(o.due)) : null),
      can('projects.create') ? button('', { small: true, ico: 'plus', title: t('project.new'), onClick: () => projectDialog(null, reload, { party_id: p.id }) }) : null),
    section(t('nav.tasks'), 'square-check-big', tasks, (o) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); taskDialog(o, reload); } }, chip(t('tstatus.' + o.status), o.status === 'done' ? 'ok' : ''), h('span', { class: 'grow' + (o.status === 'done' ? ' done-text' : '') }, o.title), o.due ? h('span', { class: 'small due-' + dueState(o.due) }, date(o.due)) : null),
      can('tasks.create') ? button('', { small: true, ico: 'plus', title: t('task.new'), onClick: () => taskDialog(null, reload, { party_id: p.id }) }) : null),
    section(t('nav.calendar'), 'calendar', appts, (o) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); appointmentDialog(o, reload); } }, icon('calendar'), h('span', { class: 'grow' }, o.title), h('span', { class: 'small muted' }, dateTime(o.starts_at))),
      can('calendar.create') ? button('', { small: true, ico: 'plus', title: t('appt.new'), onClick: () => appointmentDialog(null, reload, { party_id: p.id }) }) : null),
    section(t('client.followups'), 'phone', acts, (o) => h('a', { class: 'list-item', href: '#', onClick: (e) => { e.preventDefault(); activityDialog(o, reload); } }, chip(t('actkind.' + o.kind)), h('span', { class: 'grow' }, o.summary), h('span', { class: 'small muted' }, date(o.at))),
      can('notes.create') ? button('', { small: true, ico: 'plus', title: t('act.new'), onClick: () => activityDialog(null, reload, { party_id: p.id }) }) : null));
}

// ---- notes
async function notes({ p, reload }) {
  if (!can('notes.view')) return card({}, h('p', { class: 'muted' }, t('err.forbidden')));
  const list = (await queryAll('notes', { filters: [['party_id', 'eq', p.id]], sort: 'rowid', desc: true })).sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0));
  const box = h('textarea', { class: 'textarea', rows: 2, placeholder: t('notes.placeholder'), 'aria-label': t('notes.placeholder') });
  const add = async () => {
    if (!box.value.trim()) return;
    await createRecord(t('notes.new'), 'notes', { body: box.value.trim(), party_id: p.id, subject_ref: 'parties:' + p.id });
    reload();
  };
  box.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') add(); });
  return h('div', { class: 'stack-lg' },
    can('notes.create') ? card({}, h('div', { class: 'compose' }, box, button(t('action.save'), { kind: 'primary', ico: 'check', onClick: add }))) : null,
    list.length ? card({}, ...list.map((n) => h('div', { class: 'list-item', style: { alignItems: 'flex-start' } }, icon(n.pinned ? 'star' : 'notebook-pen'),
      h('div', { class: 'grow' }, h('p', { style: { whiteSpace: 'pre-wrap' } }, n.body), h('div', { class: 'muted small' }, `${n._created_by || ''} · ${ago(n._created)}`)),
      can('notes.edit') ? button('', { kind: 'ghost small', ico: 'star', title: n.pinned ? t('notes.unpin') : t('notes.pin'), onClick: async () => { await updateRecord(t('notes.pin'), 'notes', n, { pinned: !n.pinned }); reload(); } }) : null,
      can('notes.remove') ? button('', { kind: 'ghost small', ico: 'trash-2', title: t('action.delete'), onClick: () => removeRecord(t('notes.delete'), 'notes', n, reload) }) : null)))
      : emptyState({ ico: 'notebook-pen', title: t('notes.empty.title'), text: t('notes.empty.text') }));
}

// ---- files
async function files({ p, reload }) {
  if (!can('files.download')) return card({}, h('p', { class: 'muted' }, t('err.forbidden')));
  const list = await queryAll('attachments', { filters: [['party_id', 'eq', p.id]], sort: 'rowid', desc: true });
  const input = h('input', { type: 'file', hidden: true, onChange: async (e) => {
    for (const f of e.target.files) {
      try {
        const res = await fetch('/api/upload?name=' + encodeURIComponent(f.name), { method: 'POST', body: f, credentials: 'same-origin' });
        const j = await res.json();
        if (!res.ok) throw new Error(j.error || res.statusText);
        await createRecord(t('files.add'), 'attachments', { name: f.name, src: j.src, size: j.size, mime: f.type, party_id: p.id, subject_ref: 'parties:' + p.id });
      } catch (err) { toast(t('files.failed'), { kind: 'bad' }); }
    }
    reload();
  } });
  const size = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');
  return h('div', { class: 'stack-lg' },
    can('files.upload') ? card({}, h('div', { class: 'row' }, input, button(t('files.attach'), { kind: 'primary', ico: 'paperclip', onClick: () => input.click() }), h('span', { class: 'muted small' }, t('files.hint')))) : null,
    list.length ? card({}, ...list.map((f) => h('div', { class: 'list-item' }, icon('file-text'), h('div', { class: 'grow' }, h('a', { href: f.src, target: '_blank', rel: 'noopener' }, f.name), h('div', { class: 'muted small' }, `${size(f.size || 0)} · ${f._created_by || ''} · ${date(f._created)}`)),
      can('files.upload') ? button('', { kind: 'ghost small', ico: 'trash-2', title: t('action.delete'), onClick: () => removeRecord(t('files.remove'), 'attachments', f, reload) }) : null)))
      : emptyState({ ico: 'paperclip', title: t('files.empty.title'), text: t('files.empty.text') }));
}

// ---- roles and merge
function rolesDialog(p, roles, reload) {
  const have = new Set(roles.map((r) => r.role));
  const checks = META.roles.map((r) => [r, h('input', { type: 'checkbox', checked: have.has(r), id: 'role-' + r })]);
  const dlg = modal({ title: t('client.roles'), body: h('div', { class: 'col' }, ...checks.map(([r, cb]) => h('label', { class: 'checkbox', for: 'role-' + r }, cb, h('span', t('role.' + r))))),
    footer: [button(t('action.cancel'), { onClick: () => dlg.close() }), button(t('action.save'), { kind: 'primary', onClick: async () => {
      const ops = [];
      for (const [r, cb] of checks) {
        const cur = roles.find((x) => x.role === r);
        if (cb.checked && !cur) ops.push(opPut('party_roles', `${p.id}:${r}`, { party_id: p.id, role: r, since: isoDate() }));
        if (!cb.checked && cur) ops.push(opDel('party_roles', cur.id, cur.ver));
      }
      if (ops.length) await commit(t('client.roles'), ops);
      dlg.close(); toast(t('toast.saved')); reload();
    } })] });
}

function mergeDialog(p, roles) {
  formDialog({ title: t('merge.title'), save: t('merge.do'), values: {}, fields: [{ key: 'target', label: t('merge.into'), type: 'party', required: true, full: true, exclude: p.id, hint: t('merge.hint', { name: p.name }) }],
    onSave: async (v) => {
      if (v.target === p.id) throw new Error(t('merge.same'));
      const target = await getRecord('parties', v.target);
      const trole = new Set((await queryAll('party_roles', { filters: [['party_id', 'eq', target.id]] })).map((r) => r.role));
      const ops = [opPut('parties', p.id, { ...stripped(p), status: 'merged', merged_into: target.id }, p.ver),
        ...roles.filter((r) => !trole.has(r.role)).map((r) => opPut('party_roles', `${target.id}:${r.role}`, { party_id: target.id, role: r.role, since: r.since }))];
      await commit(t('merge.title'), ops);
      toast(t('merge.done', { name: target.name }));
      go('/clients/' + encodeURIComponent(target.id));
    } });
}

// ---------------------------------------------------------------------------------------------- possible duplicates
export async function duplicatesView() {
  const r = await get('/api/parties/duplicates');
  return h('div', pageHeader(t('dup.title'), { sub: t('dup.sub'), crumbs: [h('a', { href: href('/clients') }, t('nav.clients'))] }),
    r.groups.length ? h('div', { class: 'stack-lg' }, ...r.groups.map((g) => card({}, h('div', { class: 'card-head' }, h('h3', g.strong ? t('dup.strong') : t('dup.weak')), chip(g.why.map((w) => t('dup.by.' + w)).join(' + '), g.strong ? 'warn' : '')),
      ...g.rows.map((x) => h('div', { class: 'list-item' }, partyAvatar({ name: x.name, kind: x.kind }), h('a', { class: 'grow', href: href('/clients/' + encodeURIComponent(x.id)) }, x.name), x.phone ? h('span', { class: 'ltr num muted' }, phoneShow(x.phone)) : null, x.email ? h('span', { class: 'ltr muted small' }, x.email) : null))))) :
      emptyState({ ico: 'circle-check', title: t('dup.none.title'), text: t('dup.none.text') }));
}

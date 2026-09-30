// The forms for creating and editing each kind of record. Every screen opens these (one place to change a form).
import { h, debounce } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { formDialog } from '../ui/form.js';
import { toast, confirmBox } from '../ui/overlay.js';
import { can } from '../core/session.js';
import { createRecord, updateRecord, softDelete, options, META, isoDate, getRecord, opPut, moneyInput } from '../core/domain.js';
import { commit, uuid, get } from '../core/api.js';
import { href } from '../core/router.js';

const done = (cb, id) => cb && cb(id);
const moneyField = (key, label) => (can('money.view') ? [{ key, label, type: 'money', hint: t('f.money.hint') }] : []);

async function partyLabel(values) {
  if (values.party_id && values._partyName === undefined) {
    try { values._partyName = (await getRecord('parties', values.party_id)).name; } catch (e) { values._partyName = ''; }
  }
  return values;
}

// ---- remove with a question first and "Undo" afterwards
export async function removeRecord(label, entity, row, after) {
  const ok = await confirmBox({ title: t('confirm.delete.title'), text: t('confirm.delete.text'), yes: t('action.delete'), danger: true });
  if (!ok) return false;
  const undo = await softDelete(label, entity, row);
  after && after();
  toast(t('toast.deleted'), { undo: async () => { await undo(); toast(t('toast.restored')); after && after(); } });
  return true;
}

// used by the "Delete" button inside an edit form (the form closes itself afterwards)
async function deleteWithUndo(label, entity, row, onDone) {
  const undo = await softDelete(label, entity, row);
  toast(t('toast.deleted'), { undo: async () => { await undo(); toast(t('toast.restored')); done(onDone, 'restored'); } });
  done(onDone, 'deleted');
}

// ---- people and companies
export function partyDialog(row, onDone, defaults = {}) {
  const editing = !!row;
  const fields = [
    { key: 'kind', label: t('f.kind'), type: 'select', options: options('pkind', META.partyKinds), default: 'person' },
    ...(editing ? [{ key: 'status', label: t('f.status'), type: 'select', options: options('partystatus', ['active', 'archived']), default: 'active' }] : [{ key: '_role', label: t('f.role'), type: 'select', options: options('role', META.roles.slice(0, 5)), default: 'lead' }]),
    { key: 'name', label: t('f.name'), required: true, full: true, max: 120 },
    { key: 'phone', label: t('f.phone'), mode: 'tel', dir: 'ltr', placeholder: '01012345678' },
    { key: 'phone2', label: t('f.phone2'), mode: 'tel', dir: 'ltr' },
    { key: 'email', label: t('f.email'), dir: 'ltr', mode: 'email' },
    { key: 'city', label: t('f.city') },
    { key: 'address', label: t('f.address'), full: true },
    { key: 'website', label: t('f.website'), dir: 'ltr' },
    { key: 'source', label: t('f.source'), type: 'select', options: options('source', META.sources) },
    { key: 'tags', label: t('f.tags'), hint: t('f.tags.hint') },
    { key: 'birthday', label: t('f.birthday'), type: 'date', show: (x) => x.kind !== 'org' },
    { key: 'tax_id', label: t('f.tax_id'), show: (x) => x.kind === 'org', dir: 'ltr' },
    ...(can('data.sensitive') ? [{ key: 'national_id', label: t('f.national_id'), dir: 'ltr', show: (x) => x.kind !== 'org' }] : []),
  ];
  const hint = h('div', { class: 'dup-hint', hidden: true, role: 'status' });
  return formDialog({
    title: editing ? t('client.edit') : t('client.new'), fields, values: { kind: 'person', ...defaults, ...(row || {}) }, side: true, extra: hint,
    onReady: (form) => {
      const check = debounce(async () => {
        const v = form.read();
        const q = new URLSearchParams();
        if ((v.name || '').length >= 3) q.set('name', v.name);
        if (v.phone) q.set('phone', v.phone);
        if (v.email) q.set('email', v.email);
        if (row) q.set('self', row.id);
        if (![...q.keys()].some((k) => k !== 'self')) { hint.hidden = true; return; }
        try {
          const m = (await get('/api/parties/duplicates?' + q, { quiet: true })).matches;
          hint.replaceChildren(...(m.length ? [h('b', t('dup.maybe')), ...m.map((x) => h('div', { class: 'row', style: { marginBlockStart: '.3rem' } },
            h('span', { class: 'chip ' + (x.strength === 'same' ? 'warn' : '') }, t(x.strength === 'same' ? 'dup.same.' + x.why : 'dup.similar')),
            h('a', { href: href('/clients/' + encodeURIComponent(x.id)), target: '_blank', rel: 'noopener' }, x.name)))] : []));
          hint.hidden = !m.length;
        } catch (e) { hint.hidden = true; }
      }, 350);
      form.el.addEventListener('input', check);
    },
    onSave: async (val) => {
      const { _role, ...rest } = val;
      if (editing) { await updateRecord(t('client.edit'), 'parties', row, rest); done(onDone, row.id); return; }
      const id = uuid();
      await commit(t('client.new'), [opPut('parties', id, { ...rest, kind: rest.kind || 'person', status: 'active' }),
        opPut('party_roles', `${id}:${_role || 'lead'}`, { party_id: id, role: _role || 'lead', since: isoDate() })]);
      toast(t('toast.saved'));
      done(onDone, id);
    },
  });
}

// ---- sales
export async function opportunityDialog(row, onDone, defaults = {}) {
  const v = await partyLabel({ stage: 'new', ...defaults, ...(row || {}) });
  return formDialog({
    title: row ? t('opp.edit') : t('opp.new'), values: v, side: true, danger: row && can('sales.delete') ? { label: t('action.delete'), run: () => deleteWithUndo(t('opp.delete'), 'opportunities', row, onDone) } : null,
    fields: [
      { key: 'title', label: t('f.title'), required: true, full: true },
      { key: 'party_id', label: t('f.client'), type: 'party', labelText: v._partyName, required: true, full: true },
      { key: 'stage', label: t('f.stage'), type: 'select', options: options('stage', META.stages), default: 'new' },
      ...moneyField('value_minor', t('f.value')),
      { key: 'expected_close', label: t('f.expected_close'), type: 'date' },
      { key: 'source', label: t('f.source'), type: 'select', options: options('source', META.sources) },
      { key: 'next_step', label: t('f.next_step'), full: true },
      { key: 'next_step_at', label: t('f.next_step_at'), type: 'date' },
      { key: 'lost_reason', label: t('f.lost_reason'), full: true, show: (x) => x.stage === 'lost' },
      { key: 'notes', label: t('f.notes'), type: 'textarea' },
    ],
    onSave: async (val) => {
      if (val.stage === 'won' || val.stage === 'lost') val.closed_at = (row && row.closed_at) || isoDate(); else val.closed_at = undefined;
      if (row) await updateRecord(t('opp.edit'), 'opportunities', row, val); else await createRecord(t('opp.new'), 'opportunities', val);
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- projects
export async function projectDialog(row, onDone, defaults = {}) {
  const v = await partyLabel({ status: 'planned', ...defaults, ...(row || {}) });
  return formDialog({
    title: row ? t('project.edit') : t('project.new'), values: v, side: true, danger: row && can('projects.delete') ? { label: t('action.delete'), run: () => deleteWithUndo(t('project.delete'), 'projects', row, onDone) } : null,
    fields: [
      { key: 'title', label: t('f.title'), required: true, full: true },
      { key: 'party_id', label: t('f.client'), type: 'party', labelText: v._partyName, required: true, full: true },
      { key: 'status', label: t('f.status'), type: 'select', options: options('pstatus', META.projectStatus), default: 'planned' },
      { key: 'kind', label: t('f.project_kind') },
      { key: 'start', label: t('f.start'), type: 'date' },
      { key: 'due', label: t('f.due_project'), type: 'date' },
      ...moneyField('budget_minor', t('f.budget')),
      { key: 'billing_mode', label: t('f.billing'), type: 'select', options: options('billing', META.billingModes) },
      { key: 'description', label: t('f.description'), type: 'textarea' },
    ],
    onSave: async (val) => {
      if (row) await updateRecord(t('project.edit'), 'projects', row, val); else { val.currency = 'EGP'; await createRecord(t('project.new'), 'projects', val); }
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- tasks
export async function taskDialog(row, onDone, defaults = {}) {
  const v = await partyLabel({ status: 'todo', priority: 'normal', kind: 'task', ...defaults, ...(row || {}) });
  let projName = '';
  if (v.project_id) { try { projName = (await getRecord('projects', v.project_id)).title; } catch (e) { projName = ''; } }
  return formDialog({
    title: row ? t('task.edit') : t('task.new'), values: v, side: true, danger: row && can('tasks.delete') ? { label: t('action.delete'), run: () => deleteWithUndo(t('task.delete'), 'tasks', row, onDone) } : null,
    fields: [
      { key: 'title', label: t('f.task'), required: true, full: true },
      { key: 'due', label: t('f.due'), type: 'date' },
      { key: 'priority', label: t('f.priority'), type: 'select', options: options('prio', META.taskPriority), default: 'normal' },
      { key: 'party_id', label: t('f.client'), type: 'party', labelText: v._partyName },
      { key: 'project_id', label: t('f.project'), type: 'party', entity: 'projects', labelText: projName },
      { key: 'kind', label: t('f.kind'), type: 'select', options: options('tkind', META.taskKinds), default: 'task' },
      { key: 'status', label: t('f.status'), type: 'select', options: options('tstatus', META.taskStatus), default: 'todo' },
      { key: 'checklist', label: t('f.checklist'), type: 'checklist' },
      { key: 'notes', label: t('f.notes'), type: 'textarea' },
    ],
    onSave: async (val) => {
      if (row) await updateRecord(t('task.edit'), 'tasks', row, val); else await createRecord(t('task.new'), 'tasks', val);
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- appointments
export async function appointmentDialog(row, onDone, defaults = {}) {
  const v = await partyLabel({ kind: 'meeting', status: 'scheduled', ...defaults, ...(row || {}) });
  return formDialog({
    title: row ? t('appt.edit') : t('appt.new'), values: v, side: true, danger: row && can('calendar.delete') ? { label: t('action.delete'), run: () => deleteWithUndo(t('appt.delete'), 'appointments', row, onDone) } : null,
    fields: [
      { key: 'title', label: t('f.title'), required: true, full: true },
      { key: 'starts_at', label: t('f.starts'), type: 'datetime', required: true },
      { key: 'ends_at', label: t('f.ends'), type: 'datetime' },
      { key: 'kind', label: t('f.kind'), type: 'select', options: options('akind', META.appointmentKinds), default: 'meeting' },
      { key: 'status', label: t('f.status'), type: 'select', options: options('astatus', META.appointmentStatus), default: 'scheduled' },
      { key: 'party_id', label: t('f.client'), type: 'party', labelText: v._partyName, full: true },
      { key: 'location', label: t('f.location'), full: true },
      { key: 'notes', label: t('f.notes'), type: 'textarea' },
    ],
    onSave: async (val) => {
      if (row) await updateRecord(t('appt.edit'), 'appointments', row, val); else await createRecord(t('appt.new'), 'appointments', val);
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- follow-up log (a call, a meeting ...)
export async function activityDialog(row, onDone, defaults = {}) {
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  const v = await partyLabel({ kind: 'call', at: now.toISOString().slice(0, 16), ...defaults, ...(row || {}) });
  return formDialog({
    title: row ? t('act.edit') : t('act.new'), values: v,
    fields: [
      { key: 'kind', label: t('f.kind'), type: 'select', options: options('actkind', META.activityKinds), default: 'call' },
      { key: 'at', label: t('f.when'), type: 'datetime', required: true },
      { key: 'party_id', label: t('f.client'), type: 'party', labelText: v._partyName, full: true, required: true },
      { key: 'summary', label: t('f.what_happened'), type: 'textarea', required: true },
      { key: 'outcome', label: t('f.outcome'), full: true },
      { key: 'next_step_at', label: t('f.next_step_at'), type: 'date' },
    ],
    onSave: async (val) => {
      if (row) await updateRecord(t('act.edit'), 'activities', row, val); else await createRecord(t('act.new'), 'activities', val);
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- catalogue
export function serviceDialog(row, onDone) {
  return formDialog({
    title: row ? t('service.edit') : t('service.new'), values: { active: true, ...(row || {}) },
    danger: row && can('services.delete') ? { label: t('action.delete'), run: () => deleteWithUndo(t('service.delete'), 'services', row, onDone) } : null,
    fields: [
      { key: 'name', label: t('f.service'), required: true, full: true },
      { key: 'unit', label: t('f.unit'), type: 'select', options: options('unit', META.serviceUnits) },
      ...moneyField('price_minor', t('f.price')),
      { key: 'category', label: t('f.category') },
      { key: 'active', label: t('f.offered'), type: 'check' },
      { key: 'description', label: t('f.description'), type: 'textarea' },
    ],
    onSave: async (val) => {
      if (row) await updateRecord(t('service.edit'), 'services', row, val); else await createRecord(t('service.new'), 'services', { ...val, currency: 'EGP' });
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- a link between two people/companies ("works at", "contact for" ...)
export function relationDialog(party, onDone) {
  return formDialog({
    title: t('rel.new'), values: { kind: 'works_at' },
    fields: [
      { key: 'kind', label: t('f.relation'), type: 'select', options: options('rel', META.relationKinds), default: 'works_at' },
      { key: 'other', label: t('f.other_party'), type: 'party', required: true, full: true, exclude: party.id },
      { key: 'title', label: t('f.job_title'), full: true },
    ],
    onSave: async (val) => {
      const from = party.kind === 'org' ? val.other : party.id;
      const to = party.kind === 'org' ? party.id : val.other;
      await commit(t('rel.new'), [opPut('party_relations', `${from}:${to}:${val.kind}`, { from_party: from, to_party: to, kind: val.kind, title: val.title })]);
      toast(t('toast.saved')); done(onDone);
    },
  });
}

// ---- one thought, captured in a second
export function captureDialog(onDone) {
  return formDialog({
    title: t('inbox.capture'), save: t('action.save'),
    fields: [{ key: 'text', label: t('inbox.what'), type: 'textarea', required: true, full: true }],
    onSave: async (val) => { await createRecord(t('inbox.capture'), 'inbox', { text: val.text, status: 'new' }); toast(t('toast.saved')); done(onDone); },
  });
}

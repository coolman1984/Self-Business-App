// Everything the business screens share: words (stages, statuses ...), saving records safely, soft delete with undo,
// phone links, money entry, record routes. No screen talks to the API for saving except through here.
import { get, post, commit, query, uuid, ApiError } from './api.js';
import { t } from '../i18n/index.js';
import { session } from './session.js';
import { norm } from './textnorm.js';

export let META = null;
export async function loadMeta() { if (!META) META = await get('/api/business/meta'); return META; }

// ---------- reading
export async function queryAll(entity, { filters = [], sort, desc, search, max = 2000 } = {}) {
  const out = [];
  let cursor;
  do {
    const page = await query(entity, { filters, sort, desc, search, limit: 500, cursor });
    out.push(...page.rows);
    cursor = page.next;
  } while (cursor && out.length < max);
  return out;
}
export async function getRecord(entity, id) { return get(`/api/get/${entity}/${encodeURIComponent(id)}`); }

// ---------- saving. A change is the WHOLE record plus the version we read (so two people never overwrite each other silently).
export const stripped = (row) => Object.fromEntries(Object.entries(row).filter(([k]) => !k.startsWith('_') && k !== 'id' && k !== 'ver'));
export function opPut(entity, id, row, ver) { return { e: entity, id, op: 'put', ver: ver ?? undefined, row: stripped(row) }; }
export function opDel(entity, id, ver) { return { e: entity, id, op: 'del', ver }; }

export async function saveRecord(label, entity, id, row, ver) { return commit(label, [opPut(entity, id, row, ver)]); }
export async function createRecord(label, entity, row, id = uuid()) { await commit(label, [opPut(entity, id, row)]); return id; }
export async function updateRecord(label, entity, current, changes) { return saveRecord(label, entity, current.id, { ...stripped(current), ...changes }, current.ver); }

// deleting is a soft delete; "undo" writes the record back as a new change
export async function softDelete(label, entity, row, extraOps = []) {
  await commit(label, [opDel(entity, row.id, row.ver), ...extraOps]);
  return async () => { await commit(t('undo.label'), [{ e: entity, id: row.id, op: 'put', row: stripped(row) }]); };
}

// ---------- names
export const partyName = (p) => (p && (p.name || p.name_en)) || '';
export const pathFor = { parties: (id) => `/clients/${encodeURIComponent(id)}`, opportunities: () => '/sales', projects: (id) => `/projects/${encodeURIComponent(id)}`,
  tasks: () => '/tasks', appointments: () => '/calendar', services: () => '/services', notes: () => '/clients', inbox: () => '/inbox', activities: () => '/clients' };
export const recordPath = (entity, id) => (pathFor[entity] ? pathFor[entity](id) : '/');

// ---------- phone, WhatsApp, e-mail links
export function phoneDigits(p) { return String(p || '').replace(/[^\d+]/g, ''); }
export function phoneShow(p) {
  const s = String(p || '');
  const m = /^\+20(1\d)(\d{4})(\d{4})$/.exec(s.replace(/\s/g, ''));
  return m ? `0${m[1]} ${m[2]} ${m[3]}` : s;
}
export const telHref = (p) => 'tel:' + phoneDigits(p);
export const waHref = (p) => 'https://wa.me/' + phoneDigits(p).replace(/^\+/, '').replace(/^0/, '20');
export const mailHref = (e) => 'mailto:' + e;

// ---------- money: typed in the main unit (e.g. 1500.50), stored as whole piastres
export function parseMoney(text) {
  const s = norm(String(text ?? '')).replace(/[,\s٬]/g, '').replace(/٫/g, '.');
  if (!s) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return NaN;
  const [a, b = ''] = s.split('.');
  return Number(a) * 100 + Number((b + '00').slice(0, 2));
}
export const moneyInput = (minor) => (minor == null ? '' : (minor % 100 ? (minor / 100).toFixed(2) : String(minor / 100)));
export const currency = () => 'EGP';

// ---------- enumerations shown with translated words: t('stage.new') ...
export const ENUM_KEYS = { 'opportunities/stage': 'stage', 'projects/status': 'pstatus', 'tasks/status': 'tstatus', 'tasks/priority': 'prio', 'tasks/kind': 'tkind',
  'appointments/kind': 'akind', 'appointments/status': 'astatus', 'activities/kind': 'actkind', 'parties/kind': 'pkind', 'parties/status': 'partystatus',
  'party_roles/role': 'role', 'opportunities/source': 'source', 'parties/source': 'source', 'projects/billing_mode': 'billing', 'services/unit': 'unit' };
export function enumText(entity, field, value) {
  const g = ENUM_KEYS[`${entity}/${field}`];
  return g && value ? t(`${g}.${value}`) : value;
}
export const options = (group, ids) => ids.map((id) => [id, t(`${group}.${id}`)]);

// ---------- dates
export const isoDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const addDays = (iso, n) => { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return isoDate(d); };
export const dueState = (due, today = isoDate()) => (!due ? '' : due.slice(0, 10) < today ? 'late' : due.slice(0, 10) === today ? 'today' : 'later');

// ---------- who am I (for "assigned to me" and created-by texts)
export const me = () => session.me || {};
export { ApiError };

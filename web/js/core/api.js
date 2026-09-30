// The only place that talks to the server. Errors come back as plain-words messages; 401 sends the user to the login screen.
export class ApiError extends Error {
  constructor(message, status, body) { super(message); this.status = status; this.body = body; }
}

const listeners = { unauthorized: [], offline: [], online: [] };
export const onApi = (ev, fn) => listeners[ev].push(fn);
let offline = false;

function setOffline(v) {
  if (v === offline) return;
  offline = v;
  (v ? listeners.offline : listeners.online).forEach((f) => f());
}
export const isOffline = () => offline;

export async function api(path, { method = 'GET', body, quiet = false } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method, credentials: 'same-origin',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    setOffline(true);
    throw new ApiError('offline', 0);
  }
  setOffline(false);
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { error: text.slice(0, 200) }; }
  if (!res.ok) {
    if (res.status === 401 && !quiet) listeners.unauthorized.forEach((f) => f());
    throw new ApiError((data && data.error) || res.statusText, res.status, data);
  }
  return data;
}

export const get = (p, o) => api(p, o);
export const post = (p, body, o) => api(p, { ...o, method: 'POST', body: body === undefined ? {} : body });

// list of records: /api/q/<entity>?limit=..&search=..&f=field:op:value
export function query(entity, { limit = 50, cursor, search, sort, desc, filters = [] } = {}) {
  const p = new URLSearchParams();
  p.set('limit', limit);
  if (cursor) p.set('cursor', cursor);
  if (search) p.set('search', search);
  if (sort) p.set('sort', sort);
  if (desc) p.set('desc', '1');
  for (const [f, op, v] of filters) p.append('f', `${f}:${op}:${Array.isArray(v) ? v.join(',') : v}`);
  return get(`/api/q/${encodeURIComponent(entity)}?${p}`);
}

// One change or several as one saved step: ops = [{e,id,op:'put'|'del',ver,row}]
export const commit = (label, ops) => post('/api/commit', { label, ops });
// Saves settings values. An existing setting must be sent with its current version (otherwise the server refuses, so two PCs
// never overwrite each other silently); a new one has none.
export async function saveSettings(label, values) {
  const ops = [];
  for (const [id, value] of Object.entries(values)) {
    let ver;
    try { ver = (await get(`/api/get/settings/${encodeURIComponent(id)}`, { quiet: true })).ver; } catch (e) { if (e.status !== 404) throw e; }
    ops.push({ e: 'settings', id, op: 'put', ver, row: { value } });
  }
  return commit(label, ops);
}
export const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);

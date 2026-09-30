// Hash router: #/clients/abc?tab=notes. Routes are registered by the views; the shell shows whatever the router resolves.
const routes = [];
let current = null;
const subs = [];

export function route(pattern, handler, meta = {}) {
  const keys = [];
  const re = new RegExp('^' + pattern.replace(/:([a-zA-Z]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '/?$');
  routes.push({ re, keys, handler, meta, pattern });
}

export function parse(hash = location.hash) {
  const raw = hash.replace(/^#/, '') || '/';
  const [path, qs = ''] = raw.split('?');
  return { path: path || '/', query: Object.fromEntries(new URLSearchParams(qs)) };
}

export function resolve(hash) {
  const { path, query } = parse(hash);
  for (const r of routes) {
    const m = r.re.exec(path);
    if (m) return { ...r, path, query, params: Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])])) };
  }
  return null;
}

export const go = (path) => { if (location.hash === '#' + path) dispatch(); else location.hash = path; };
export const href = (path) => '#' + path;
export const here = () => current;
export const onRoute = (fn) => subs.push(fn);

export function dispatch(refreshing = false) {
  current = resolve(location.hash);
  subs.forEach((f) => f(current, refreshing));
}
// show the same screen again with fresh data: no new history entry, the scroll position stays
export const refresh = () => dispatch(true);
let started = false;
export function start() {
  if (!started) { started = true; addEventListener('hashchange', () => dispatch(false)); }
  dispatch(false);
}

// remember a screen's small state (tab, day, filter) in the address WITHOUT a new history entry and without redrawing
export function setQuery(values) {
  const { path, query } = parse();
  const q = new URLSearchParams({ ...query, ...values });
  for (const [k, v] of [...q]) if (v === '' || v === 'undefined') q.delete(k);
  history.replaceState(null, '', '#' + path + (q.toString() ? '?' + q : ''));
}

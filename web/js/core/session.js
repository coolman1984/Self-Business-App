// Who is logged in, what the business is called, what this PC is. One object the whole UI reads.
import { get, post } from './api.js';

export const session = { me: null, about: {}, node: {}, hasUsers: false, local: false, sync: { state: 'single' } };
const subs = [];
export const onSession = (fn) => subs.push(fn);
const emit = () => subs.forEach((f) => f(session));

export async function refresh() {
  const s = await get('/api/auth/status', { quiet: true });
  Object.assign(session, { me: s.me, about: s.about || {}, node: s.node || {}, hasUsers: s.hasUsers, local: s.local });
  emit();
  return session;
}
export async function login(username, password) {
  session.me = await post('/api/auth/login', { username, password }, { quiet: true });
  await refresh();
}
export async function setup(d) {
  session.me = await post('/api/auth/setup', d, { quiet: true });
  await refresh();
}
const outSubs = [];
export const onLogout = (fn) => outSubs.push(fn);
export async function logout() {
  try { await post('/api/auth/logout', {}, { quiet: true }); } catch (e) { /* already out */ }
  session.me = null; emit();
  outSubs.forEach((f) => f());
}
export const can = (...perms) => !!session.me && (!perms.length || perms.some((p) => (session.me.perms || []).includes(p)));
export const brandName = () => session.about.brand_name || session.about['brand.name'] || session.about.product || '';
export const brandShort = () => session.about['brand.short'] || [...(brandName() || '?')][0];

export async function pollSync() {
  try {
    const v = await get('/api/version', { quiet: true });
    const next = v.sync || { state: 'single' };
    if (JSON.stringify(next) !== JSON.stringify(session.sync)) { session.sync = next; emit(); }      // repaint only when the light changed (keyboard focus stays where it is)
  } catch (e) { /* offline banner handles it */ }
}

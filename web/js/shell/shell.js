// The frame around every logged-in screen: sidebar (grouped, collapsible, drawer on phones), top bar (search, sync light,
// language, theme, user menu), offline banner, and the place where views are shown.
import { h, icon, mount, $ } from '../core/dom.js';
import { t, tk, onLang } from '../i18n/index.js';
import { session, can, brandName, brandShort, logout, pollSync, onSession } from '../core/session.js';
import { here, href, go, onRoute } from '../core/router.js';
import { getPrefs, setPref, resolvedTheme } from '../core/prefs.js';
import { button, errorBox, skeleton } from '../ui/kit.js';
import { menu } from '../ui/overlay.js';
import { openPalette } from '../ui/palette.js';
import { quickAddItems, openQuickAdd } from '../ui/quick.js';
import { showShortcuts } from '../ui/keys.js';
import { isOffline, onApi, friendly } from '../core/api.js';
import { initials } from '../core/format.js';

// Screens (and later modules) add their own entry here; the shell never hard-codes a business screen.
const NAV = [];
export const GROUPS = [tk('nav.g.main'), tk('nav.g.work'), tk('nav.g.money'), tk('nav.g.system')];
export function registerNav(item) { NAV.push({ order: 50, ...item }); }

let els = {};
let wired = false, pollTimer = null;

export function buildShell() {
  const app = h('div', { class: 'app', dataset: { collapsed: String(getPrefs().sidebar === 'closed'), drawer: 'closed' } });
  const sidebar = h('aside', { class: 'sidebar', id: 'sidebar', 'aria-label': t('nav.label') });
  const banner = h('div', { class: 'banner-host', role: 'status' });
  const top = h('header', { class: 'topbar' });
  const view = h('main', { id: 'view', tabindex: '-1' });
  app.append(sidebar, h('div', { class: 'main' }, banner, top, view),
    h('div', { class: 'overlay only-mobile', id: 'drawer-back', style: { display: 'none' }, onClick: () => drawer(false) }));
  els = { app, sidebar, banner, top, view };
  paintSidebar(); paintTop(); paintBanner();
  if (!wired) {          // the shell can be rebuilt after a new sign-in: listen and poll only once
    wired = true;
    onRoute(showRoute);
    onLang(() => { paintSidebar(); paintTop(); paintBanner(); showRoute(here(), true); });
    onSession(() => { paintSidebar(); paintTop(); });
    onApi('offline', paintBanner); onApi('online', paintBanner);
  }
  clearInterval(pollTimer);
  pollTimer = setInterval(pollSync, 15000);
  pollSync();
  return app;
}

function drawer(open) {
  els.app.dataset.drawer = open ? 'open' : 'closed';
  const back = $('#drawer-back');
  if (back) back.style.display = open ? 'block' : 'none';
}

function toggleCollapse() {
  const now = els.app.dataset.collapsed !== 'true';
  els.app.dataset.collapsed = String(now);
  setPref('sidebar', now ? 'closed' : 'open');
}

function paintSidebar() {
  const cur = here();
  const me = session.me || {};
  const groups = GROUPS.map((g) => [g, NAV.filter((n) => n.group === g && (!n.perm || can(...[].concat(n.perm)))).sort((a, b) => a.order - b.order)]).filter(([, items]) => items.length);
  mount(els.sidebar,
    h('div', { class: 'sb-brand' }, h('div', { class: 'sb-mark' }, brandShort()),
      h('div', { class: 'grow' }, h('div', { class: 'sb-name' }, brandName()))),
    h('nav', { class: 'sb-nav' }, ...groups.map(([g, items]) => h('div', { class: 'sb-group' }, h('h6', t(g)),
      ...items.map((n) => h('a', {
        class: 'sb-link', href: href(n.path), id: 'nav-' + n.id, title: t(n.k),
        'aria-current': cur && (cur.meta.nav === n.id) ? 'page' : null, onClick: () => drawer(false),
      }, icon(n.ico), h('span', t(n.k))))))),
    h('div', { class: 'sb-foot' }, h('span', { class: 'avatar', 'aria-hidden': 'true' }, initials(me.full_name || me.username)),
      h('div', { class: 'who' }, h('b', me.full_name || me.username || ''), h('span', me.role || '')),
      button('', { kind: 'ghost', ico: 'log-out', title: t('auth.logout'), onClick: () => logout() })));
}

const SYNC = { single: ['ok', 'sync.single'], ok: ['ok', 'sync.ok'], pending: ['warn', 'sync.pending'], offline: ['warn', 'sync.offline'], problem: ['bad', 'sync.problem'] };

function paintTop() {
  const p = getPrefs();
  const [dot, key] = SYNC[(session.sync || {}).state] || SYNC.single;
  const themeIco = resolvedTheme() === 'morning' || resolvedTheme() === 'navy' ? 'moon' : 'sun';
  mount(els.top,
    button('', { kind: 'ghost only-mobile', ico: 'menu', title: t('nav.menu'), onClick: () => drawer(true) }),
    button('', { kind: 'ghost only-desktop', ico: 'panel-left', title: t('nav.collapse'), onClick: toggleCollapse }),
    h('div', { class: 'tb-search' }, h('button', { type: 'button', id: 'tb-search', onClick: openPalette }, icon('search'), h('span', t('palette.hint')), h('kbd', 'Ctrl K'))),
    h('div', { class: 'tb-spacer' }),
    quickAddItems().length ? button(t('today.quick'), { kind: 'primary', ico: 'plus', id: 'tb-add', small: true, onClick: (e) => openQuickAdd(e.currentTarget) }) : null,
    h('span', { class: 'sync-pill', id: 'sync-pill', title: t(key) }, h('i', { class: 'dot ' + dot }), h('span', t(key))),
    button('', { kind: 'ghost', ico: themeIco, title: t('theme.quick'), onClick: () => setPref('theme', themeIco === 'moon' ? (resolvedTheme() === 'navy' ? 'navynight' : 'evening') : (resolvedTheme() === 'navynight' ? 'navy' : 'morning')) }),
    button(p.lang === 'ar' ? 'EN' : 'ع', { kind: 'ghost', title: t('lang.switch'), onClick: () => setPref('lang', p.lang === 'ar' ? 'en' : 'ar') }),
    button('', { kind: 'ghost hide-mobile', ico: 'keyboard', title: t('keys.title'), onClick: showShortcuts }),
    button('', { kind: 'ghost', ico: 'circle-help', title: t('nav.help'), onClick: (e) => menu(e.currentTarget, [
      { label: t('help.center'), ico: 'circle-help', onClick: () => go('/help') },
      { label: t('tour.restart'), ico: 'sparkles', onClick: () => { setPref('tour', 'todo'); go('/'); location.reload(); } },
      { label: t('keys.title'), ico: 'keyboard', onClick: showShortcuts }]) }));
}

function paintBanner() {
  mount(els.banner, isOffline() ? h('div', { class: 'banner bad' }, icon('wifi-off'), h('span', t('offline.banner'))) : null);
}

let token = 0;
export async function showRoute(r, refreshing = false) {
  if (!els.view) return;
  const my = ++token;
  const y = scrollY;
  paintSidebar();
  if (!r) { mount(els.view, h('div', { class: 'page-in' }, errorBox(t('state.notfound'), () => go('/')))); return; }
  document.title = `${t(r.meta.title || 'nav.today')} · ${brandName()}`;
  if (!refreshing) mount(els.view, skeleton(5));          // a refresh keeps the old screen until the new one is ready (no flicker, no jump)
  try {
    const node = await r.handler({ params: r.params, query: r.query, view: els.view });
    if (my !== token) return;
    mount(els.view, h('div', { class: refreshing ? '' : 'page-in' }, node));
  } catch (e) {
    if (my !== token) return;
    mount(els.view, errorBox(friendly(e), () => showRoute(r)));
  }
  if (refreshing) { scrollTo(0, y); return; }
  els.view.focus({ preventScroll: true });
  scrollTo(0, 0);
}

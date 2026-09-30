// Boot: decide between login / first-run setup / the app, wire the shell, shortcuts, palette and tour.
import { h, mount, $ } from './core/dom.js';
import { t } from './i18n/index.js';
import { apply, getPrefs } from './core/prefs.js';
import { refresh, session, onLogout } from './core/session.js';
import { onApi } from './core/api.js';
import { route, start, go, dispatch } from './core/router.js';
import { buildShell, registerNav } from './shell/shell.js';
import { loginView, setupView } from './views/auth.js';
import { todayView } from './views/today.js';
import { settingsView } from './views/settings.js';
import { helpView } from './views/help.js';
import { shortcut, initKeys } from './ui/keys.js';
import { registerCommand, openPalette } from './ui/palette.js';
import { startTour } from './ui/tour.js';
import { openQuickAdd } from './ui/quick.js';
import { errorBox } from './ui/kit.js';

apply();

// core screens
registerNav({ id: 'today', k: 'nav.today', ico: 'layout-dashboard', group: 'nav.g.main', path: '/', order: 1 });
registerNav({ id: 'settings', k: 'nav.settings', ico: 'settings', group: 'nav.g.system', path: '/settings', order: 90, perm: ['settings.view', 'settings.edit'] });
registerNav({ id: 'help', k: 'nav.help', ico: 'circle-help', group: 'nav.g.system', path: '/help', order: 99 });
route('/', todayView, { nav: 'today', title: 'nav.today' });
route('/settings', settingsView, { nav: 'settings', title: 'nav.settings' });
route('/help', helpView, { nav: 'help', title: 'nav.help' });

shortcut('mod+k', 'keys.palette', openPalette);
shortcut('/', 'keys.search', openPalette);
shortcut('n', 'keys.new', () => openQuickAdd($('#tb-add')));
shortcut('g t', 'keys.go.today', () => go('/'));
shortcut('g s', 'keys.go.settings', () => go('/settings'));
shortcut('?', 'keys.sheet', () => import('./ui/keys.js').then((m) => m.showShortcuts()));
registerCommand({ k: 'nav.today', ico: 'layout-dashboard', run: () => go('/'), words: 'today home' });
registerCommand({ k: 'nav.settings', ico: 'settings', run: () => go('/settings'), words: 'settings' });
registerCommand({ k: 'nav.help', ico: 'circle-help', run: () => go('/help'), words: 'help' });
initKeys();

const root = $('#app');
let shellBuilt = false;

async function render() {
  try { await refresh(); } catch (e) {
    mount(root, h('div', { style: { padding: '2rem', maxInlineSize: '36rem', margin: 'auto' } }, errorBox(e.message === 'offline' ? t('offline.banner') : e.message, render)));
    return;
  }
  document.title = session.about['brand.name'] || session.about.product || 'App';
  if (!session.hasUsers) { shellBuilt = false; mount(root, setupView(render)); return; }
  if (!session.me) { shellBuilt = false; mount(root, loginView(render)); return; }
  if (!shellBuilt) { mount(root, buildShell()); shellBuilt = true; start(); }
  else dispatch();
  if (session.me.must_change) go('/settings?tab=account');
  if (getPrefs().tour === 'todo') setTimeout(() => startTour([
    { title: 'tour.1.t', text: 'tour.1.d' },
    { target: '#sidebar', title: 'tour.2.t', text: 'tour.2.d' },
    { target: '#tb-search', title: 'tour.3.t', text: 'tour.3.d' },
    { target: '#sync-pill', title: 'tour.4.t', text: 'tour.4.d' }]), 600);
}

onApi('unauthorized', () => { if (session.me) { session.me = null; render(); } });
onLogout(() => { location.hash = '/'; render(); });
render();

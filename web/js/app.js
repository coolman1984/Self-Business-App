// Boot: decide between login / first-run setup / the app, wire the shell, shortcuts, palette and tour.
import { h, mount, $ } from './core/dom.js';
import { t } from './i18n/index.js';
import { apply, getPrefs } from './core/prefs.js';
import { refresh as refreshSession, session, onLogout } from './core/session.js';
import { onApi } from './core/api.js';
import { route, start, go, dispatch, refresh } from './core/router.js';
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
import { loadMeta } from './core/domain.js';
import { clientsView, clientView, duplicatesView } from './views/clients.js';
import { salesView } from './views/sales.js';
import { projectsView, projectView } from './views/projects.js';
import { tasksView } from './views/tasks.js';
import { calendarView } from './views/calendar.js';
import { servicesView } from './views/services.js';
import { inboxView } from './views/inbox.js';
import { importView } from './views/import.js';
import './views/today_blocks.js';
import { registerQuickAdd } from './ui/quick.js';
import { partyDialog, taskDialog, appointmentDialog, opportunityDialog, projectDialog, activityDialog, captureDialog } from './views/dialogs.js';

apply();

// core screens
registerNav({ id: 'today', k: 'nav.today', ico: 'layout-dashboard', group: 'nav.g.main', path: '/', order: 1 });
registerNav({ id: 'settings', k: 'nav.settings', ico: 'settings', group: 'nav.g.system', path: '/settings', order: 90 });
registerNav({ id: 'help', k: 'nav.help', ico: 'circle-help', group: 'nav.g.system', path: '/help', order: 99 });
registerNav({ id: 'inbox', k: 'nav.inbox', ico: 'inbox', group: 'nav.g.main', path: '/inbox', order: 2, perm: 'tasks.view' });
registerNav({ id: 'clients', k: 'nav.clients', ico: 'users', group: 'nav.g.work', path: '/clients', order: 10, perm: 'clients.view' });
registerNav({ id: 'sales', k: 'nav.sales', ico: 'target', group: 'nav.g.work', path: '/sales', order: 20, perm: 'sales.view' });
registerNav({ id: 'projects', k: 'nav.projects', ico: 'briefcase', group: 'nav.g.work', path: '/projects', order: 30, perm: 'projects.view' });
registerNav({ id: 'tasks', k: 'nav.tasks', ico: 'square-check-big', group: 'nav.g.work', path: '/tasks', order: 40, perm: 'tasks.view' });
registerNav({ id: 'calendar', k: 'nav.calendar', ico: 'calendar-days', group: 'nav.g.work', path: '/calendar', order: 50, perm: 'calendar.view' });
registerNav({ id: 'services', k: 'nav.services', ico: 'tag', group: 'nav.g.work', path: '/services', order: 60, perm: 'services.view' });
route('/', todayView, { nav: 'today', title: 'nav.today' });
route('/inbox', inboxView, { nav: 'inbox', title: 'nav.inbox' });
route('/clients', clientsView, { nav: 'clients', title: 'nav.clients' });
route('/clients/:id', clientView, { nav: 'clients', title: 'nav.clients' });
route('/duplicates', duplicatesView, { nav: 'clients', title: 'dup.title' });
route('/import', importView, { nav: 'clients', title: 'import.title' });
route('/sales', salesView, { nav: 'sales', title: 'nav.sales' });
route('/projects', projectsView, { nav: 'projects', title: 'nav.projects' });
route('/projects/:id', projectView, { nav: 'projects', title: 'nav.projects' });
route('/tasks', tasksView, { nav: 'tasks', title: 'nav.tasks' });
route('/calendar', calendarView, { nav: 'calendar', title: 'nav.calendar' });
route('/services', servicesView, { nav: 'services', title: 'nav.services' });

const afterAdd = () => refresh();
registerQuickAdd({ k: 'client.new', ico: 'user-plus', perm: 'clients.create', run: () => partyDialog(null, (id) => go('/clients/' + encodeURIComponent(id))) });
registerQuickAdd({ k: 'task.new', ico: 'square-check-big', perm: 'tasks.create', run: () => taskDialog(null, afterAdd) });
registerQuickAdd({ k: 'appt.new', ico: 'calendar', perm: 'calendar.create', run: () => appointmentDialog(null, afterAdd) });
registerQuickAdd({ k: 'opp.new', ico: 'target', perm: 'sales.create', run: () => opportunityDialog(null, afterAdd) });
registerQuickAdd({ k: 'project.new', ico: 'briefcase', perm: 'projects.create', run: () => projectDialog(null, afterAdd) });
registerQuickAdd({ k: 'act.new', ico: 'phone', perm: 'notes.create', run: () => activityDialog(null, afterAdd) });
registerQuickAdd({ k: 'inbox.capture', ico: 'inbox', perm: 'tasks.create', run: () => captureDialog(afterAdd) });
for (const [keys, path, k] of [['g c', '/clients', 'keys.go.clients'], ['g o', '/sales', 'keys.go.sales'], ['g p', '/projects', 'keys.go.projects'], ['g k', '/tasks', 'keys.go.tasks'], ['g a', '/calendar', 'keys.go.calendar'], ['g i', '/inbox', 'keys.go.inbox']]) shortcut(keys, k, () => go(path));
for (const [path, k, ico, words, perm] of [['/clients', 'nav.clients', 'users', 'clients customers people عملاء', 'clients.view'], ['/sales', 'nav.sales', 'target', 'sales opportunities leads فرص مبيعات', 'sales.view'], ['/projects', 'nav.projects', 'briefcase', 'projects مشاريع', 'projects.view'],
  ['/tasks', 'nav.tasks', 'square-check-big', 'tasks todo مهام', 'tasks.view'], ['/calendar', 'nav.calendar', 'calendar-days', 'calendar appointments مواعيد تقويم', 'calendar.view'], ['/inbox', 'nav.inbox', 'inbox', 'inbox capture وارد', 'tasks.view'],
  ['/services', 'nav.services', 'tag', 'services prices خدمات اسعار', 'services.view'], ['/import', 'import.title', 'upload', 'import excel استيراد اكسل', 'data.import'], ['/duplicates', 'dup.title', 'copy', 'duplicates merge مكرر دمج', 'clients.view']])
  registerCommand({ k, ico, run: () => go(path), words, perm });
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
  try { await refreshSession(); } catch (e) {
    mount(root, h('div', { style: { padding: '2rem', maxInlineSize: '36rem', margin: 'auto' } }, errorBox(e.message === 'offline' ? t('offline.banner') : e.message, render)));
    return;
  }
  document.title = session.about['brand.name'] || session.about.product || 'App';
  if (!session.hasUsers) { shellBuilt = false; mount(root, setupView(render)); return; }
  if (!session.me) { shellBuilt = false; mount(root, loginView(render)); return; }
  if (!shellBuilt) {
    try { await loadMeta(); } catch (e) { mount(root, h('div', { style: { padding: '2rem', maxInlineSize: '36rem', margin: 'auto' } }, errorBox(e.message, render))); return; }
    mount(root, buildShell()); shellBuilt = true; start();
  }
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

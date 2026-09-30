// Today Command Center. Phase 2 shows the frame and a getting-started card; Phase 3 fills it with what needs the owner now
// (through `registerTodayBlock`, so every module adds its own block and this file never learns a business word).
import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { session } from '../core/session.js';
import { get } from '../core/api.js';
import { date, weekday, greeting } from '../core/format.js';
import { card, emptyState, button, errorBox } from '../ui/kit.js';
import { friendly, post as apiPost, get as apiGet } from '../core/api.js';
import { can } from '../core/session.js';
import { confirmBox, toast } from '../ui/overlay.js';
import { go } from '../core/router.js';
import { resolve, href } from '../core/router.js';
import { quickAddItems, openQuickAdd } from '../ui/quick.js';

const blocks = [];   // {id, order, render(): Node|Promise<Node>|null}
export const registerTodayBlock = (b) => blocks.push({ order: 50, ...b });

// one request for all blocks of one visit
let dataPromise = null;
export const todayData = () => (dataPromise = dataPromise || get('/api/today'));

export async function todayView() {
  dataPromise = null;
  const name = ((session.me && (session.me.full_name || session.me.username)) || '').split(' ')[0];
  const now = new Date().toISOString();
  const d = await todayData().catch(() => null);
  const seen = d ? [d.counts.clients, d.counts.tasks, d.counts.projects].filter((n) => n !== null && n !== undefined) : [];
  const fresh = !!d && seen.every((n) => !n) && !d.appointmentsToday.length && !d.followUps.length && !d.inbox && !d.appointmentsNext.length && !Object.keys(d.pipeline).length;
  const parts = fresh ? [] : await Promise.all(blocks.sort((a, b) => a.order - b.order).map(async (b) => {
    try { return await b.render(); } catch (e) { return card({}, errorBox(friendly(e))); }
  }));
  const content = parts.filter(Boolean);
  return h('div', { class: 'stack-lg' },
    hero(name ? t('greet.named', { greet: t(greeting()), name }) : t(greeting()), `${weekday(now)} · ${date(now)}`, fresh ? null : d),
    fresh || !content.length ? startCard() : h('div', { class: 'today-grid' }, ...content));
}

// the top of Today: greeting, one sentence about the day, the next actions, and how much of the day is behind you
function hero(title, when, d) {
  let line = null, ring = null;
  if (d) {
    const late = d.overdue.length + d.followUps.length;
    const items = [...d.appointmentsToday.map((a) => a.starts_at), ...d.dueToday.map((x) => x.due)];
    line = late || items.length
      ? h('div', { class: 'hero-pills' },
          late ? h('span', { class: 'hero-pill late' }, icon('triangle-alert'), h('b', { class: 'num' }, String(late)), t('today.pill.late')) : null,
          h('span', { class: 'hero-pill' }, icon('calendar-days'), h('b', { class: 'num' }, String(items.length)), t('today.pill.today')))
      : h('p', { class: 'hero-line' }, t('today.summary.free'));
    if (items.length) {
      const nowIso = d.now || new Date().toISOString().slice(0, 16);
      const done = items.filter((x) => x && x.length > 10 && x.slice(0, 16) <= nowIso).length;
      const r = 52, c = 2 * Math.PI * r, part = done / items.length;
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 120 120');
      svg.setAttribute('aria-hidden', 'true');
      for (const [cls, off] of [['track', 0], ['bar', c * (1 - part)]]) {
        const el = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        Object.entries({ cx: 60, cy: 60, r, fill: 'none', 'stroke-width': 10, 'stroke-linecap': 'round', class: cls, 'stroke-dasharray': c, 'stroke-dashoffset': off }).forEach(([k, v]) => el.setAttribute(k, v));
        svg.append(el);
      }
      ring = h('div', { class: 'hero-ring', role: 'img', 'aria-label': t('today.ring', { done, total: items.length }) }, svg,
        h('div', { class: 'in' }, h('div', h('b', { class: 'num' }, `${done}/${items.length}`), h('span', t('today.ring.label')))));
    }
  }
  const actions = h('div', { class: 'hero-actions' },
    quickAddItems().length ? button(t('today.quick'), { kind: 'primary', ico: 'plus', onClick: (e) => openQuickAdd(e.currentTarget) }) : null,
    can('calendar.view') ? button(t('nav.calendar'), { ico: 'calendar-days', href: href('/calendar') }) : null,
    can('tasks.view') ? button(t('nav.tasks'), { ico: 'square-check-big', href: href('/tasks') }) : null);
  return h('section', { class: 'hero', 'aria-label': title }, h('div', h('h1', title), h('div', { class: 'hero-date' }, when), line, actions), ring);
}

function startCard() {
  const steps = [
    ['settings', 'today.s1', '/settings'],
    ['users', 'today.s2', '/clients'],
    ['calendar-days', 'today.s3', '/calendar'],
  ];
  return h('div', { class: 'grid-main' },
    card({}, h('div', { class: 'card-head' }, h('h2', t('today.start.title')), h('span', { class: 'chip accent' }, t('today.start.chip'))),
      h('p', { class: 'muted', style: { marginBlockEnd: '1rem' } }, t('today.start.text')),
      ...steps.map(([ico, k, path], i) => {
        const ok = !!resolve(path);
        return h('div', { class: 'list-item' }, h('span', { class: 'step-num' }, String(i + 1)), h('span', { class: 'grow' }, t(k)),
          ok ? button(t('action.open'), { small: true, href: href(path), ico: 'arrow-right' }) : h('span', { class: 'chip' }, t('state.soon')));
      })),
    card({}, h('div', { class: 'card-head' }, h('h2', t('demo.title'))),
      emptyState({ ico: 'sparkles', title: t('demo.try'), text: t('demo.try.text'), action: can('data.import') ? button(t('demo.load'), { kind: 'primary', ico: 'download', onClick: loadDemo }) : null })));
}

export async function loadDemo() {
  let kinds = [];
  try { kinds = (await apiGet('/api/get/settings/business.kinds', { quiet: true })).value || []; } catch (e) { /* not set */ }
  try {
    await apiPost('/api/demo/load', { lang: document.documentElement.lang, kinds });
    toast(t('demo.loaded'));
    go('/');
  } catch (e) { toast(friendly(e), { kind: 'bad' }); }
}

// Today Command Center. Phase 2 shows the frame and a getting-started card; Phase 3 fills it with what needs the owner now
// (through `registerTodayBlock`, so every module adds its own block and this file never learns a business word).
import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { session } from '../core/session.js';
import { get } from '../core/api.js';
import { date, weekday, greeting } from '../core/format.js';
import { card, emptyState, button, pageHeader, errorBox } from '../ui/kit.js';
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
    pageHeader(name ? t('greet.named', { greet: t(greeting()), name }) : t(greeting()), { sub: `${weekday(now)} · ${date(now)}` }),
    fresh || !content.length ? startCard() : h('div', { class: 'today-grid' }, ...content));
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

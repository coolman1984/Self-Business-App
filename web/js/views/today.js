// Today Command Center. Phase 2 shows the frame and a getting-started card; Phase 3 fills it with what needs the owner now
// (through `registerTodayBlock`, so every module adds its own block and this file never learns a business word).
import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { session } from '../core/session.js';
import { date, weekday, greeting } from '../core/format.js';
import { card, emptyState, button, pageHeader, errorBox } from '../ui/kit.js';
import { resolve, href } from '../core/router.js';
import { quickAddItems, openQuickAdd } from '../ui/quick.js';

const blocks = [];   // {id, order, render(): Node|Promise<Node>|null}
export const registerTodayBlock = (b) => blocks.push({ order: 50, ...b });

export async function todayView() {
  const name = ((session.me && (session.me.full_name || session.me.username)) || '').split(' ')[0];
  const now = new Date().toISOString();
  const parts = await Promise.all(blocks.sort((a, b) => a.order - b.order).map(async (b) => {
    try { return await b.render(); } catch (e) { return card({}, errorBox(e.message)); }
  }));
  const content = parts.filter(Boolean);
  return h('div', { class: 'stack-lg' },
    pageHeader(`${t(greeting())}${name ? '، ' + name : ''}`, { sub: `${weekday(now)} · ${date(now)}`,
      actions: quickAddItems().length ? [button(t('today.quick'), { kind: 'primary', ico: 'plus', id: 'quick-add', onClick: (e) => openQuickAdd(e.currentTarget) })] : [] }),
    content.length ? h('div', { class: 'stack-lg' }, ...content) : startCard());
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
    card({}, h('div', { class: 'card-head' }, h('h2', t('today.nothing.title'))),
      emptyState({ ico: 'sparkles', title: t('today.nothing.h'), text: t('today.nothing.text') })));
}

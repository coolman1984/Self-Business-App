// Opportunities: a board with one column per stage. Drag a card to move it, or use the "Move" button (keyboard friendly).
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { friendly } from '../core/api.js';
import { card, chip, button, emptyState, pageHeader, table, segmented, errorBox } from '../ui/kit.js';
import { menu, toast } from '../ui/overlay.js';
import { money, date } from '../core/format.js';
import { META, queryAll, updateRecord, namesOf, dueState, isoDate } from '../core/domain.js';
import { opportunityDialog } from './dialogs.js';

export async function salesView() {
  const opps = await queryAll('opportunities', { sort: 'rowid', desc: true });
  const names = await namesOf('parties', 'name', opps.map((o) => o.party_id));
  let mode = 'board', showClosed = false;
  const root = h('div');
  const subEl = h('span');
  const showMoney = can('money.view');
  const reload = async () => { const fresh = await queryAll('opportunities', { sort: 'rowid', desc: true }); opps.splice(0, opps.length, ...fresh); Object.assign(names, await namesOf('parties', 'name', fresh.map((o) => o.party_id))); paint(); };

  async function move(o, stage) {
    if (o.stage === stage) return;
    try {
      const row = { stage, closed_at: stage === 'won' || stage === 'lost' ? isoDate() : undefined };
      await updateRecord(t('opp.move'), 'opportunities', o, row);
      if (stage === 'lost') toast(t('opp.lost.hint'));
      await reload();
    } catch (e) { toast(friendly(e), { kind: 'bad' }); reload(); }
  }
  function cardEl(o) {
    const el = h('div', { class: 'kcard', draggable: can('sales.edit') ? 'true' : 'false', tabindex: '0', role: 'group', 'aria-label': o.title, dataset: { id: o.id } },
      h('div', { class: 'title' }, o.title), h('div', { class: 'muted small' }, names[o.party_id] || ''),
      h('div', { class: 'row', style: { justifyContent: 'space-between' } }, showMoney && o.value_minor != null ? h('b', { class: 'num small' }, money(o.value_minor)) : h('span'),
        o.next_step_at ? h('span', { class: 'small due-' + dueState(o.next_step_at) }, icon('clock'), ' ' + date(o.next_step_at)) : null),
      can('sales.edit') ? h('div', { class: 'row', style: { justifyContent: 'flex-end' } }, button(t('opp.move'), { kind: 'ghost small', ico: 'arrow-right', onClick: (e) => { e.stopPropagation(); menu(e.currentTarget, META.stages.map((s) => ({ label: t('stage.' + s), ico: s === o.stage ? 'check' : undefined, onClick: () => move(o, s) }))); } })) : null);
    if (can('sales.edit')) {
      el.addEventListener('click', (e) => { if (!e.target.closest('button')) opportunityDialog(o, reload); });
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target === el) opportunityDialog(o, reload); });
    }
    el.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', o.id); el.classList.add('dragging'); });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
    return el;
  }
  function board() {
    const stages = META.stages.filter((s) => showClosed || META.openStages.includes(s));
    return h('div', { class: 'board' }, ...stages.map((s) => {
      const items = opps.filter((o) => o.stage === s);
      const total = items.reduce((a, o) => a + (o.value_minor || 0), 0);
      const lane = h('div', { class: 'lane', dataset: { stage: s }, 'aria-label': t('stage.' + s) },
        h('h4', h('span', t('stage.' + s)), h('span', { class: 'row', style: { gap: '.4rem' } }, showMoney && total ? h('span', { class: 'muted small num' }, money(total)) : null, chip(String(items.length)))),
        h('div', { class: 'cards' }, ...items.map(cardEl)),
        can('sales.create') ? button(t('opp.new'), { kind: 'ghost small', ico: 'plus', onClick: () => opportunityDialog(null, reload, { stage: s }) }) : null);
      lane.addEventListener('dragover', (e) => { e.preventDefault(); lane.classList.add('over'); });
      lane.addEventListener('dragleave', () => lane.classList.remove('over'));
      lane.addEventListener('drop', (e) => { e.preventDefault(); lane.classList.remove('over'); const o = opps.find((x) => x.id === e.dataTransfer.getData('text/plain')); if (o) move(o, s); });
      return lane;
    }));
  }
  function list() {
    return card({ class: 'flush' }, table([
      { key: 'title', label: t('f.title'), render: (o) => h('div', h('b', o.title), h('div', { class: 'muted small' }, names[o.party_id] || '')) },
      { key: 'stage', label: t('f.stage'), render: (o) => chip(t('stage.' + o.stage), o.stage === 'won' ? 'ok' : o.stage === 'lost' ? 'bad' : 'info') },
      ...(showMoney ? [{ key: 'value', label: t('f.value'), num: true, render: (o) => (o.value_minor != null ? money(o.value_minor) : '') }] : []),
      { key: 'next', label: t('f.next_step'), render: (o) => (o.next_step ? h('div', o.next_step, o.next_step_at ? h('div', { class: 'small due-' + dueState(o.next_step_at) }, date(o.next_step_at)) : null) : '') },
    ], opps.filter((o) => showClosed || META.openStages.includes(o.stage)), { onOpen: can('sales.edit') ? (o) => opportunityDialog(o, reload) : null }));
  }
  function paint() {
    const open = opps.filter((o) => META.openStages.includes(o.stage));
    subEl.textContent = showMoney ? t('opp.sub.money', { n: open.length, v: money(open.reduce((a, o) => a + (o.value_minor || 0), 0)) }) : t('opp.sub', { n: open.length });
    mount(root, opps.length ? (mode === 'board' ? board() : list()) : emptyState({ ico: 'target', title: t('opp.empty.title'), text: t('opp.empty.text'), action: can('sales.create') ? button(t('opp.new'), { kind: 'primary', ico: 'plus', onClick: () => opportunityDialog(null, reload) }) : null }));
  }
  paint();
  return h('div', pageHeader(t('nav.sales'), { sub: subEl, actions: [
    segmented([['board', t('view.board')], ['list', t('view.list')]], mode, (v) => { mode = v; paint(); }),
    button(t('opp.closed'), { ico: 'circle-check', onClick: (e) => { showClosed = !showClosed; e.currentTarget.classList.toggle('primary', showClosed); paint(); } }),
    can('sales.create') ? button(t('opp.new'), { kind: 'primary', ico: 'plus', onClick: () => opportunityDialog(null, reload) }) : null] }), root);
}

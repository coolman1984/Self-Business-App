import { h, icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { card, pageHeader, button } from '../ui/kit.js';
import { showShortcuts } from '../ui/keys.js';
import { setPref } from '../core/prefs.js';
import { go } from '../core/router.js';

const TOPICS = [['zap', 'help.t1', 'help.d1'], ['search', 'help.t2', 'help.d2'], ['shield-check', 'help.t3', 'help.d3'], ['wifi-off', 'help.t4', 'help.d4'], ['palette', 'help.t5', 'help.d5']];

export function helpView() {
  return h('div', pageHeader(t('help.center'), { sub: t('help.sub'), actions: [
    button(t('tour.restart'), { ico: 'sparkles', onClick: () => { setPref('tour', 'todo'); go('/'); location.reload(); } }), button(t('keys.title'), { ico: 'keyboard', onClick: showShortcuts })] }),
  h('div', { class: 'grid-2' }, ...TOPICS.map(([ico, a, b]) => card({}, h('div', { class: 'row', style: { marginBlockEnd: '.5rem' } }, h('span', { class: 'stat' }, h('span', { class: 'ico' }, icon(ico))), h('h3', t(a))), h('p', { class: 'muted' }, t(b))))));
}

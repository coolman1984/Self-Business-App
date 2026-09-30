// Guided tour: a spotlight and a small card, one step at a time. Steps point at shell parts by CSS selector.
import { h, $, trapFocus } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { button } from './kit.js';
import { setPref } from '../core/prefs.js';

export function startTour(steps) {
  let i = 0;
  const spot = h('div', { class: 'tour-spot' });
  const pop = h('div', { class: 'tour-pop', role: 'dialog', 'aria-modal': 'true', 'aria-live': 'polite' });
  document.body.append(spot, pop);
  const release = trapFocus(pop, () => end());
  function end() { spot.remove(); pop.remove(); release(); removeEventListener('resize', place); setPref('tour', 'done'); }
  function place() {
    const s = steps[i];
    const target = s.target && $(s.target);
    const vis = target && target.offsetParent !== null ? target.getBoundingClientRect() : null;
    if (vis) {
      Object.assign(spot.style, { display: '', top: vis.top - 6 + 'px', left: vis.left - 6 + 'px', width: vis.width + 12 + 'px', height: vis.height + 12 + 'px' });
      const w = Math.min(352, innerWidth * 0.92), rtl = document.documentElement.dir === 'rtl';
      pop.style.transform = '';
      if (vis.height > innerHeight * 0.5 && innerWidth > 900) {   // tall target (the menu): put the card next to it
        pop.style.top = '120px';
        pop.style.left = Math.min(Math.max(12, rtl ? vis.left - w - 16 : vis.right + 16), innerWidth - w - 12) + 'px';
      } else {
        const below = vis.bottom + 12 + 190 < innerHeight;
        pop.style.top = (below ? vis.bottom + 14 : Math.max(12, vis.top - 200)) + 'px';
        pop.style.left = Math.min(Math.max(12, vis.left), innerWidth - w - 12) + 'px';
      }
    } else {
      Object.assign(spot.style, { display: '', top: '50%', left: '50%', width: '0px', height: '0px' });   // no target: only dim the page
      Object.assign(pop.style, { top: '30vh', left: '50%', transform: 'translateX(-50%)' });
    }
  }
  function show() {
    const s = steps[i];
    pop.replaceChildren(
      h('div', { class: 'row', style: { marginBlockEnd: '.5rem' } }, h('h3', t(s.title)),
        h('span', { class: 'steps', 'aria-label': `${i + 1}/${steps.length}` }, ...steps.map((_, n) => h('i', { class: n === i ? 'on' : '' })))),
      h('p', { class: 'muted' }, t(s.text)),
      h('div', { class: 'row', style: { marginBlockStart: '1rem', justifyContent: 'space-between' } },
        button(t('tour.skip'), { kind: 'ghost', small: true, onClick: end }),
        h('div', { class: 'row' },
          i > 0 ? button(t('action.back'), { small: true, onClick: () => { i--; show(); } }) : null,
          button(i === steps.length - 1 ? t('tour.done') : t('action.next'), { kind: 'primary', small: true, onClick: () => { if (i === steps.length - 1) end(); else { i++; show(); } } }))));
    place();
    $('.btn.primary', pop).focus();
  }
  addEventListener('resize', place);
  show();
}

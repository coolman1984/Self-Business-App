// Settings: how it looks (theme, font, size, density, motion, language) with a live preview, the business name, the account.
import { h, icon } from '../core/dom.js';
import { t, tk } from '../i18n/index.js';
import { session, can, refresh } from '../core/session.js';
import { saveSettings, post } from '../core/api.js';
import { getPrefs, setPref, CHOICES } from '../core/prefs.js';
import { card, tabs, segmented, field, input, button, pageHeader, chip } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';
import { here } from '../core/router.js';

const THEMES = [['morning', tk('theme.morning')], ['evening', tk('theme.evening')], ['navy', tk('theme.navy')], ['navynight', tk('theme.navynight')], ['contrast', tk('theme.contrast')]];

function setting(title, desc, control) {
  return h('div', { class: 'setting' }, h('div', { class: 'head' }, h('div', h('b', title), desc ? h('div', { class: 'desc' }, desc) : null)), control);
}

function themeCards() {
  const wrap = h('div', { class: 'opt-grid', role: 'group', 'aria-label': t('settings.theme') });
  const auto = ['auto', tk('theme.auto')];
  [auto, ...THEMES].forEach(([id, k]) => {
    wrap.append(h('button', { type: 'button', class: 'opt', dataset: { v: id }, 'aria-pressed': String(getPrefs().theme === id), onClick: () => { setPref('theme', id); paint(); } },
      id === 'auto'
        ? h('div', { class: 'sw', style: { display: 'grid', placeItems: 'center' } }, icon('sparkles'))
        : h('div', { class: 'sw', dataset: { theme: id }, style: { background: 'var(--canvas)', color: 'var(--ink)', '--sw-accent': 'var(--accent)' } },
            h('i', { style: { background: 'var(--sidebar-bg)' } }), h('b')),
      h('span', { class: 'name' }, t(k))));
  });
  function paint() { [...wrap.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === getPrefs().theme))); }
  return wrap;
}

function optionButtons(key, labels, extra) {
  const wrap = h('div', { class: 'opt-grid', role: 'group' });
  CHOICES[key].forEach((v) => wrap.append(h('button', { type: 'button', class: 'opt', dataset: { v }, 'aria-pressed': String(getPrefs()[key] === v),
    onClick: () => { setPref(key, v); [...wrap.children].forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === v))); } },
    extra ? extra(v) : null, h('span', { class: 'name' }, t(labels[v])))));
  return wrap;
}

function preview() {
  return card({ class: 'preview', 'aria-label': t('settings.preview') },
    h('div', { class: 'card-head' }, h('h3', t('settings.preview')), chip(t('settings.preview.live'), 'info')),
    h('div', { class: 'col' },
      h('div', { class: 'row' }, h('span', { class: 'avatar' }, 'م'), h('div', h('b', t('preview.name')), h('div', { class: 'muted small' }, t('preview.role')))),
      h('div', { class: 'row wrap' }, chip(t('preview.paid'), 'ok'), chip(t('preview.due'), 'warn'), chip(t('preview.late'), 'bad'), chip(t('preview.new'), 'info')),
      h('div', { class: 'progress' }, h('i', { style: { width: '68%' } })),
      h('div', { class: 'row wrap' }, button(t('preview.primary'), { kind: 'primary', ico: 'plus' }), button(t('preview.secondary')), button('', { kind: 'ghost', ico: 'ellipsis', title: t('preview.more') })),
      h('p', { class: 'muted small' }, t('preview.text'))));
}

function appearance() {
  return h('div', { class: 'settings-grid' },
    card({},
      setting(t('settings.theme'), t('settings.theme.d'), themeCards()),
      setting(t('settings.font'), t('settings.font.d'), optionButtons('font', { plex: 'font.plex', system: 'font.system' }, (v) => h('div', { class: 'glyph', style: { fontFamily: v === 'plex' ? 'var(--font-plex)' : 'var(--font-system)' } }, t('font.sample')))),
      setting(t('settings.size'), t('settings.size.d'), optionButtons('size', { s: 'size.s', m: 'size.m', l: 'size.l', xl: 'size.xl' }, (v) => h('div', { class: 'glyph', style: { fontSize: { s: '1.1rem', m: '1.4rem', l: '1.75rem', xl: '2.1rem' }[v] } }, t('font.sample.short')))),
      setting(t('settings.density'), t('settings.density.d'), optionButtons('density', { comfortable: 'density.comfortable', compact: 'density.compact' })),
      setting(t('settings.motion'), t('settings.motion.d'), optionButtons('motion', { on: 'motion.on', off: 'motion.off' })),
      setting(t('settings.digits'), t('settings.digits.d'), optionButtons('digits', { latn: 'digits.latn', arab: 'digits.arab' }, (v) => h('div', { class: 'glyph num' }, v === 'latn' ? '0123456789' : '٠١٢٣٤٥٦٧٨٩'))),
      setting(t('settings.language'), t('settings.language.d'), segmented([['ar', 'العربية'], ['en', 'English']], getPrefs().lang, (v) => setPref('lang', v)))),
    preview());
}

function business() {
  if (!can('settings.edit')) return card({}, h('p', { class: 'muted' }, t('err.forbidden')));
  const name = input({ value: session.about['brand.name'] || '', maxlength: 80 });
  const short = input({ value: session.about['brand.short'] || '', maxlength: 3 });
  return card({}, h('form', { class: 'col', style: { maxInlineSize: '32rem' }, onSubmit: async (e) => {
    e.preventDefault();
    const btn = e.submitter; btn.classList.add('busy');
    try {
      await saveSettings('Business identity', { 'brand.name': name.value.trim(), 'brand.short': short.value.trim().slice(0, 3) });
      await refresh(); toast(t('toast.saved'));
    } catch (err) { toast(err.message, { kind: 'bad' }); } finally { btn.classList.remove('busy'); }
  } }, h('h3', t('settings.business')), h('p', { class: 'muted' }, t('settings.business.d')),
  field(t('setup.name'), name), field(t('setup.short'), short, { hint: t('setup.short.hint') }), button(t('action.save'), { kind: 'primary', type: 'submit', ico: 'save' })));
}

function account() {
  const old = input({ type: 'password', autocomplete: 'current-password' }), nw = input({ type: 'password', autocomplete: 'new-password' });
  const fo = field(t('account.old'), old), fn = field(t('account.new'), nw, { hint: t('setup.pw.hint', { n: 10 }) });
  return card({}, h('form', { class: 'col', style: { maxInlineSize: '32rem' }, onSubmit: async (e) => {
    e.preventDefault(); fo.setError(''); fn.setError('');
    const btn = e.submitter; btn.classList.add('busy');
    try { await post('/api/auth/password', { old: old.value, new: nw.value }); old.value = ''; nw.value = ''; toast(t('toast.saved')); }
    catch (err) { (err.status === 403 || /old|current/i.test(err.message) ? fo : fn).setError(err.message); } finally { btn.classList.remove('busy'); }
  } }, h('h3', t('settings.account')), h('p', { class: 'muted' }, `${session.me.full_name || ''} · ${session.me.username}`), fo, fn,
  button(t('account.change'), { kind: 'primary', type: 'submit', ico: 'lock' })));
}

function about() {
  const a = session.about;
  return card({}, h('h3', a.product || ''), h('p', { class: 'muted' }, `${t('about.version')} ${a.version || ''}`), h('p', { class: 'muted small' }, a.copyright || ''),
    h('p', { class: 'muted small' }, a.license || ''));
}

export function settingsView() {
  const r = here();
  let active = (r && r.query.tab) || 'look';
  const body = h('div', { style: { marginBlockStart: '1.2rem' } });
  const TABS = { look: appearance, business, account, about };
  const show = (id) => { active = id; body.replaceChildren(TABS[id]()); };
  const tb = tabs([{ id: 'look', label: t('settings.tab.look') }, { id: 'business', label: t('settings.tab.business') }, { id: 'account', label: t('settings.tab.account') }, { id: 'about', label: t('settings.tab.about') }], active, show);
  show(TABS[active] ? active : 'look');
  return h('div', pageHeader(t('nav.settings'), { sub: t('settings.sub') }), tb, body);
}

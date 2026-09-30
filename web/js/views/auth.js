// Login and first-run setup wizard. These two screens have no shell; they share the split "hero + form" frame.
import { h, icon } from '../core/dom.js';
import { t, tk } from '../i18n/index.js';
import { session, login, setup, brandName } from '../core/session.js';
import { saveSettings } from '../core/api.js';
import { getPrefs, setPref } from '../core/prefs.js';
import { button, field, input, select, segmented, chip } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';

function frame(...form) {
  const p = getPrefs();
  return h('div', { class: 'auth page-in' },
    h('div', { class: 'auth-tools' }, button(p.lang === 'ar' ? 'EN' : 'ع', { kind: 'ghost', title: t('lang.switch'), onClick: () => { setPref('lang', p.lang === 'ar' ? 'en' : 'ar'); location.reload(); } })),
    h('section', { class: 'auth-hero' },
      h('div', { class: 'row' }, h('div', { class: 'sb-mark' }, [...(brandName() || '?')][0]), h('b', { style: { fontSize: '1.15rem' } }, brandName())),
      h('div', h('h2', t('auth.hero.title')), h('p', t('auth.hero.text'))),
      h('ul', { class: 'auth-points' }, ...['auth.p1', 'auth.p2', 'auth.p3'].map((k, i) => h('li', icon(['shield-check', 'wifi-off', 'languages'][i]), t(k))))),
    h('section', { class: 'auth-panel' }, h('div', { class: 'auth-card' }, ...form)));
}

export function loginView(onDone) {
  const user = input({ autocomplete: 'username', autofocus: true, required: true });
  const pass = input({ type: 'password', autocomplete: 'current-password', required: true });
  const f1 = field(t('auth.username'), user), f2 = field(t('auth.password'), pass);
  const btn = button(t('auth.login'), { kind: 'primary', type: 'submit', ico: 'arrow-right' });
  const form = h('form', { onSubmit: async (e) => {
    e.preventDefault(); f2.setError('');
    btn.classList.add('busy');
    try { await login(user.value.trim(), pass.value); onDone(); }
    catch (err) { f2.setError(err.status === 401 || err.status === 403 || err.status === 429 ? err.message : t('state.error')); pass.select(); }
    finally { btn.classList.remove('busy'); }
  } }, f1, f2, btn);
  return frame(h('h1', t('auth.welcome')), h('p', { class: 'muted' }, t('auth.login.sub')), form,
    !session.local ? h('p', { class: 'muted small', style: { marginBlockStart: '1rem' } }, t('auth.remote.hint')) : null);
}

const KINDS = [
  ['trainer', 'presentation', tk('kind.trainer')], ['freelancer', 'laptop', tk('kind.freelancer')],
  ['software', 'server', tk('kind.software')], ['services', 'briefcase', tk('kind.services')],
];

export function setupView(onDone) {
  if (!session.local) {
    return frame(h('h1', t('setup.remote.title')), h('p', { class: 'muted' }, t('setup.remote.text')));
  }
  const data = { kinds: new Set(), lang: getPrefs().lang };
  let step = 0;
  const box = h('div');
  const name = input({ autofocus: true, required: true, maxlength: 80, placeholder: t('setup.name.ph') });
  const short = input({ maxlength: 3, placeholder: t('setup.short.ph') });
  const full = input({ autocomplete: 'name', required: true }), user = input({ autocomplete: 'username', required: true }), pw = input({ type: 'password', autocomplete: 'new-password', required: true }), pw2 = input({ type: 'password', autocomplete: 'new-password', required: true });
  const ff = { name: field(t('setup.name'), name), short: field(t('setup.short'), short, { hint: t('setup.short.hint') }), full: field(t('setup.fullname'), full), user: field(t('auth.username'), user), pw: field(t('auth.password'), pw, { hint: t('setup.pw.hint', { n: 10 }) }), pw2: field(t('setup.pw2'), pw2) };

  function steps() {
    return h('div', { class: 'wiz-steps', 'aria-label': `${step + 1}/3` }, ...[0, 1, 2].map((i) => h('i', { class: i <= step ? 'on' : '' })));
  }
  function paint() {
    box.replaceChildren();
    if (step === 0) {
      box.append(h('h1', t('setup.t1')), h('p', { class: 'muted' }, t('setup.s1')), steps(),
        h('div', { class: 'col', style: { marginBlockStart: '1.2rem' } }, ff.name, ff.short,
          h('div', { class: 'field' }, h('span', { class: 'label' }, t('setup.kinds')), h('div', { class: 'kind-grid' }, ...KINDS.map(([id, ico, k]) =>
            h('button', { type: 'button', class: 'kind-card', 'aria-pressed': String(data.kinds.has(id)), onClick: (e) => {
              data.kinds.has(id) ? data.kinds.delete(id) : data.kinds.add(id);
              e.currentTarget.setAttribute('aria-pressed', String(data.kinds.has(id)));
            } }, h('span', { class: 'ico' }, icon(ico)), h('b', t(k)))))),
          button(t('action.next'), { kind: 'primary', onClick: () => { if (!name.value.trim()) { ff.name.setError(t('err.required')); name.focus(); return; } ff.name.setError(''); step = 1; paint(); } })));
    } else if (step === 1) {
      box.append(h('h1', t('setup.t2')), h('p', { class: 'muted' }, t('setup.s2')), steps(),
        h('div', { class: 'col', style: { marginBlockStart: '1.2rem' } },
          h('div', { class: 'field' }, h('span', { class: 'label' }, t('settings.language')), segmented([['ar', 'العربية'], ['en', 'English']], data.lang, (v) => { data.lang = v; setPref('lang', v); })),
          h('div', { class: 'field' }, h('span', { class: 'label' }, t('settings.theme')),
            segmented([['auto', t('theme.auto')], ['morning', t('theme.morning')], ['evening', t('theme.evening')], ['navy', t('theme.navy')]], getPrefs().theme, (v) => setPref('theme', v))),
          h('div', { class: 'row' }, button(t('action.back'), { onClick: () => { step = 0; paint(); } }), button(t('action.next'), { kind: 'primary', onClick: () => { step = 2; paint(); } }))));
    } else {
      box.append(h('h1', t('setup.t3')), h('p', { class: 'muted' }, t('setup.s3')), steps(),
        h('form', { class: 'col', style: { marginBlockStart: '1.2rem' }, onSubmit: submit }, ff.full, ff.user, ff.pw, ff.pw2,
          h('div', { class: 'row' }, button(t('action.back'), { onClick: () => { step = 1; paint(); } }), button(t('setup.finish'), { kind: 'primary', type: 'submit', ico: 'check' }))));
    }
    const first = box.querySelector('input'); first && first.focus();
  }
  async function submit(e) {
    e.preventDefault();
    Object.values(ff).forEach((x) => x.setError && x.setError(''));
    if (pw.value.length < 10) { ff.pw.setError(t('setup.pw.hint', { n: 10 })); return; }
    if (pw.value !== pw2.value) { ff.pw2.setError(t('setup.pw.same')); return; }
    const btn = e.submitter; btn && btn.classList.add('busy');
    try {
      await setup({ username: user.value.trim(), full_name: full.value.trim(), password: pw.value });
      const short_ = (short.value.trim() || [...name.value.trim()][0] || '').slice(0, 3);
      try {
        await saveSettings('Business setup', { 'brand.name': name.value.trim(), 'brand.short': short_, 'business.kinds': [...data.kinds], 'business.lang': data.lang });
        await import('../core/session.js').then((m) => m.refresh());
      } catch (err) { toast(t('setup.saved.partial'), { kind: 'bad' }); }
      onDone();
    } catch (err) {
      ff.user.setError(err.message);
    } finally { btn && btn.classList.remove('busy'); }
  }
  paint();
  return frame(box);
}

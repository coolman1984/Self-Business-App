// Import people and companies from Excel or CSV in three calm steps: choose file and columns -> read the report -> import.
// Nothing is saved before the last button; a backup is made first; the whole import can be undone.
import { h, icon, mount } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { post, friendly } from '../core/api.js';
import { card, chip, button, emptyState, pageHeader, select, field, input, table, errorBox } from '../ui/kit.js';
import { confirmBox, toast } from '../ui/overlay.js';
import { href, go } from '../core/router.js';
import { date, num } from '../core/format.js';
import { queryAll, META, options, phoneShow } from '../core/domain.js';

const FIELDS = ['name', 'name_en', 'kind', 'company', 'phone', 'phone2', 'email', 'address', 'city', 'website', 'tags', 'source', 'tax_id', 'birthday', 'notes'];

export async function importView() {
  const root = h('div');
  const st = { step: 1, file: null, src: null, headerRow: 0, sheet: 0, preview: null, mapping: {}, role: 'lead', analysis: null, overrides: {}, report: null };
  const steps = () => h('div', { class: 'steps-line' }, ...[t('import.s1'), t('import.s2'), t('import.s3')].map((label, i) => h('span', { class: st.step === i + 1 ? 'on' : '' }, `${i + 1}. ${label}`)));
  const fail = (e) => toast(friendly(e), { kind: 'bad' });

  async function upload(file) {
    const res = await fetch('/api/upload?name=' + encodeURIComponent(file.name), { method: 'POST', body: file, credentials: 'same-origin' });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(j.error || 'upload');
    st.src = j.src; st.file = file.name;
  }
  async function loadPreview() {
    st.preview = await post('/api/import/preview', { src: st.src, sheet: st.sheet, headerRow: st.headerRow });
    st.mapping = { ...st.preview.mapping };
    paint();
  }

  function step1() {
    const drop = h('div', { class: 'card', style: { textAlign: 'center', padding: '2.5rem 1rem', borderStyle: 'dashed' } }, icon('file-spreadsheet'), h('h3', { style: { marginBlock: '.6rem' } }, st.file || t('import.choose')), h('p', { class: 'muted' }, t('import.hint')),
      h('input', { type: 'file', id: 'import-file', accept: '.xlsx,.csv,.txt', hidden: true, onChange: async (e) => { if (e.target.files[0]) { try { await upload(e.target.files[0]); st.headerRow = 0; st.sheet = 0; await loadPreview(); } catch (err) { fail(err); } } } }),
      button(st.file ? t('import.other') : t('import.pick'), { kind: 'primary', ico: 'upload', onClick: () => document.getElementById('import-file').click() }));
    drop.addEventListener('dragover', (e) => e.preventDefault());
    drop.addEventListener('drop', async (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) { try { await upload(f); await loadPreview(); } catch (err) { fail(err); } } });
    const pv = st.preview;
    if (!pv) return h('div', drop);
    const sels = pv.headers.map((hd, i) => {
      const s = select([['', t('import.ignore')], ...FIELDS.map((f) => [f, t('import.f.' + f)])], st.mapping[i] || '', { 'aria-label': hd || String(i + 1), onChange: (e) => { if (e.target.value) Object.keys(st.mapping).forEach((k) => { if (st.mapping[k] === e.target.value && Number(k) !== i) delete st.mapping[k]; }); st.mapping[i] = e.target.value; if (!e.target.value) delete st.mapping[i]; paint(); } });
      return s;
    });
    return h('div', { class: 'stack-lg' }, drop,
      card({}, h('div', { class: 'card-head' }, h('h2', t('import.columns')), pv.sheets.length > 1 ? select(pv.sheets.map((s, i) => [String(i), `${s.name} (${s.rows})`]), String(st.sheet), { 'aria-label': t('import.sheet'), onChange: async (e) => { st.sheet = Number(e.target.value); await loadPreview(); } }) : null),
        h('div', { class: 'row wrap', style: { marginBlockEnd: '.8rem' } }, h('label', { for: 'hdr-row' }, t('import.header.row')), input({ id: 'hdr-row', type: 'number', min: '1', max: '50', value: String(st.headerRow + 1), style: { inlineSize: '5rem' }, onChange: async (e) => { st.headerRow = Math.max(0, Number(e.target.value) - 1); await loadPreview(); } }), h('span', { class: 'muted small' }, t('import.rows.count', { n: num(pv.total) }))),
        h('div', { class: 'table-wrap' }, h('table', { class: 'table' }, h('thead', h('tr', ...pv.headers.map((hd, i) => h('th', { scope: 'col' }, hd || `#${i + 1}`))), h('tr', ...sels.map((s) => h('th', { scope: 'col' }, s)))),
          h('tbody', ...pv.sample.map((r) => h('tr', ...r.map((c) => h('td', String(c).slice(0, 60)))))))),
        !Object.values(st.mapping).includes('name') ? h('p', { class: 'error', role: 'alert', style: { marginBlockStart: '.6rem' } }, t('err.need_name_column')) : null,
        h('div', { class: 'row', style: { marginBlockStart: '1rem' } }, h('div', { class: 'field', style: { minInlineSize: '14rem' } }, h('label', { for: 'imp-role' }, t('import.role')), select(options('role', META.roles.slice(0, 4)), st.role, { id: 'imp-role', onChange: (e) => { st.role = e.target.value; } })),
          h('span', { class: 'grow' }), button(t('action.next'), { kind: 'primary', ico: 'arrow-right', disabled: !Object.values(st.mapping).includes('name'), onClick: analyze }))));
  }

  async function analyze() {
    try {
      st.analysis = await post('/api/import/analyze', { src: st.src, sheet: st.sheet, headerRow: st.headerRow, mapping: st.mapping, role: st.role, name: st.file });
      st.overrides = {}; st.step = 2; paint();
    } catch (e) { fail(e); }
  }

  function step2() {
    const a = st.analysis, s = a.summary;
    const tile = (label, n, kind, hint) => card({ class: 'stat' }, h('div', { class: 'label' }, label), h('div', { class: 'value num' }, num(n)), hint ? h('div', { class: 'muted small' }, hint) : null);
    const act = (r) => st.overrides[r.line] || r.action;
    const rows = a.rows.map((r) => ({ ...r, act: act(r) }));
    return h('div', { class: 'stack-lg' },
      h('div', { class: 'stats' }, tile(t('import.new'), s.create + s.maybe, 'ok', t('import.new.hint')), tile(t('import.match'), s.match, 'warn', t('import.match.hint')), tile(t('import.filedup'), s.file_dup, 'warn', t('import.filedup.hint')), tile(t('import.invalid'), s.invalid, 'bad', t('import.invalid.hint')), tile(t('import.warn'), s.warn, '', t('import.warn.hint'))),
      rows.length ? card({ class: 'flush' }, h('div', { class: 'card-head', style: { padding: '1rem 1rem 0' } }, h('h2', t('import.look')), h('span', { class: 'muted small' }, t('import.look.hint'))), table([
        { key: 'line', label: t('import.line'), render: (r) => h('span', { class: 'num' }, r.line) },
        { key: 'name', label: t('f.name'), render: (r) => h('div', h('b', r.name || '—'), r.phone ? h('div', { class: 'ltr num muted small' }, phoneShow(r.phone)) : null) },
        { key: 'status', label: t('import.status'), render: (r) => h('div', chip(t('import.st.' + r.status), r.status === 'invalid' ? 'bad' : r.status === 'create' ? 'ok' : 'warn'), r.matchName ? h('div', { class: 'small muted' }, t('import.same.as', { name: r.matchName })) : r.matchLine ? h('div', { class: 'small muted' }, t('import.same.line', { n: r.matchLine })) : null, r.warn.length ? h('div', { class: 'small' }, r.warn.map((w) => t('import.w.' + w)).join('، ')) : null) },
        { key: 'action', label: t('import.do'), render: (r) => (r.status === 'invalid' ? h('span', { class: 'muted' }, t('import.act.skip')) : select([...(r.status === 'match' ? [['fill', t('import.act.fill')]] : []), ['create', t('import.act.create')], ['skip', t('import.act.skip')]], r.act, { 'aria-label': r.name, onChange: (e) => { st.overrides[r.line] = e.target.value; } })) },
      ], rows)) : null,
      h('div', { class: 'row' }, button(t('action.back'), { onClick: () => { st.step = 1; paint(); } }), h('span', { class: 'grow' }), button(t('import.go', { n: num(s.create + s.maybe + s.match) }), { kind: 'primary', ico: 'check', onClick: run })));
  }

  async function run() {
    if (!(await confirmBox({ title: t('import.confirm.title'), text: t('import.confirm.text'), yes: t('import.confirm.yes') }))) return;
    try { st.report = await post('/api/import/commit', { token: st.analysis.token, overrides: st.overrides }); st.step = 3; paint(); } catch (e) { fail(e); }
  }

  function step3() {
    const r = st.report;
    return h('div', { class: 'stack-lg' }, card({}, emptyState({ ico: 'circle-check', title: t('import.done.title'), text: t('import.done.text', { created: num(r.created), filled: num(r.filled), skipped: num(r.skipped) }) }),
      r.failed.length ? h('div', { class: 'error-box', role: 'alert' }, icon('circle-alert'), h('div', h('b', t('import.failed', { n: r.failed.length })), h('ul', ...r.failed.slice(0, 10).map((f) => h('li', `${t('import.line')} ${f.line}: ${f.why}`))))) : null,
      h('div', { class: 'row', style: { justifyContent: 'center', marginBlockStart: '1rem' } },
        button(t('import.open'), { kind: 'primary', ico: 'users', href: href('/clients') }),
        button(t('import.undo'), { ico: 'undo-2', onClick: async () => { if (await confirmBox({ title: t('import.undo'), text: t('import.undo.text'), danger: true, yes: t('import.undo') })) { try { const u = await post('/api/import/undo', { batch: r.batch }); toast(t('import.undone', { n: u.removed })); go('/clients'); } catch (e) { fail(e); } } } }))));
  }

  function paint() { mount(root, steps(), st.step === 1 ? step1() : st.step === 2 ? step2() : step3()); }
  paint();
  return h('div', pageHeader(t('import.title'), { sub: t('import.sub'), crumbs: [h('a', { href: href('/clients') }, t('nav.clients'))] }), root);
}

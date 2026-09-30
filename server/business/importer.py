"""Import people and companies from Excel / CSV: preview, column mapping, duplicate report, backup first, undo.

Nothing is saved until the person presses "Import" (step 3). The analysis stays on the server (a 2,000-row file must not travel
back and forth), keyed by a random token that only its creator can use. Existing records are never overwritten: a match can only
have its EMPTY fields filled. Every imported record carries the batch id so the whole import can be undone in one step."""
import os
import re
import secrets
import time
from datetime import datetime

import tablefile
from store import BadRequest, now

from . import dedupe
from textnorm import norm_email, norm_phone, norm_text

FIELDS = ['name', 'name_en', 'kind', 'company', 'phone', 'phone2', 'email', 'address', 'city', 'website', 'tags', 'source', 'tax_id', 'birthday', 'notes']
SYNONYMS = {
    'name': ['name', 'full name', 'fullname', 'client', 'client name', 'customer', 'contact', 'الاسم', 'اسم', 'اسم العميل', 'العميل', 'اسم الشخص', 'الاسم بالكامل'],
    'name_en': ['english name', 'name en', 'الاسم بالانجليزي', 'الاسم بالانجليزية'],
    'kind': ['type', 'kind', 'النوع', 'نوع'],
    'company': ['company', 'organisation', 'organization', 'employer', 'الشركة', 'شركة', 'جهة العمل', 'المؤسسة', 'الجهة'],
    'phone': ['phone', 'mobile', 'tel', 'telephone', 'cell', 'موبايل', 'المحمول', 'الموبايل', 'تليفون', 'التليفون', 'هاتف', 'الهاتف', 'جوال', 'رقم', 'رقم الموبايل', 'رقم التليفون', 'رقم الهاتف'],
    'phone2': ['phone 2', 'mobile 2', 'second phone', 'other phone', 'تليفون 2', 'موبايل 2', 'رقم اخر', 'رقم تاني'],
    'email': ['email', 'e-mail', 'mail', 'ايميل', 'الايميل', 'بريد', 'البريد', 'البريد الالكتروني', 'الايميل الالكتروني'],
    'address': ['address', 'العنوان', 'عنوان'],
    'city': ['city', 'governorate', 'المدينه', 'المحافظه', 'مدينه', 'محافظه'],
    'website': ['website', 'site', 'url', 'الموقع', 'موقع'],
    'tags': ['tags', 'tag', 'labels', 'category', 'التصنيف', 'تصنيف', 'الوسوم', 'مجموعه'],
    'source': ['source', 'how found', 'المصدر', 'مصدر'],
    'tax_id': ['tax id', 'tax number', 'vat', 'الرقم الضريبي', 'رقم ضريبي', 'بطاقه ضريبيه'],
    'birthday': ['birthday', 'birth date', 'dob', 'تاريخ الميلاد', 'ميلاد'],
    'notes': ['notes', 'note', 'comments', 'remarks', 'ملاحظات', 'ملاحظه', 'تعليق'],
}
_SYN_NORM = {f: {norm_text(s) for s in v} for f, v in SYNONYMS.items()}
ORG_WORDS = re.compile(r'(^|\s)(شركه|مؤسسه|مكتب|مدرسه|مركز|اكاديميه|company|co|ltd|llc|inc|corp|center|centre|academy|school|group|مجموعه)(\s|$)', re.I)
KEEP_MIN = 1800
_DATE_FORMS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d', '%m/%d/%Y')


def suggest(headers):
    """Guess which column is which. A column is used once; the first good match wins."""
    out, used = {}, set()
    for i, h in enumerate(headers):
        n = norm_text(h)
        for f in FIELDS:
            if f not in used and n in _SYN_NORM[f]:
                out[i] = f
                used.add(f)
                break
    for i, h in enumerate(headers):      # weaker: the header contains the word
        n = norm_text(h)
        if i in out or not n:
            continue
        for f in FIELDS:
            if f not in used and any(s and s in n.split() for s in _SYN_NORM[f]):
                out[i] = f
                used.add(f)
                break
    return out


def parse_date(v):
    v = str(v or '').strip()
    if not v:
        return ''
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', v)
    if m:
        return m.group(1)
    v = norm_text(v).replace(' ', '/')
    for f in _DATE_FORMS:
        try:
            d = datetime.strptime(v.replace('.', '/').replace('-', '/'), f.replace('.', '/').replace('-', '/'))
            if d.year >= KEEP_MIN:
                return d.date().isoformat()
        except ValueError:
            continue
    return ''


def split_phones(v):
    parts = [p for p in re.split(r'[/\\,;،؛|\n]+|\s+(?:او|or)\s+', str(v or '')) if p.strip()]
    return parts[:2] if parts else []


def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def map_row(cells, mapping, default_country='20'):
    """One spreadsheet row -> ({field: value}, [warnings]). warnings are codes shown as plain sentences."""
    raw = {f: clean(cells[i]) if i < len(cells) else '' for i, f in mapping.items() if f in FIELDS}
    warn = []
    d = {k: v for k, v in raw.items() if v and k not in ('phone', 'phone2', 'email', 'birthday', 'kind')}
    phones = split_phones(raw.get('phone', '')) + split_phones(raw.get('phone2', ''))
    good = []
    for p in phones:
        n = norm_phone(p, default_country)
        if n and len(n) >= 9:
            if n not in good:
                good.append(n)
        else:
            warn.append('bad_phone')
    if good:
        d['phone'] = good[0]
    if len(good) > 1:
        d['phone2'] = good[1]
    if raw.get('email'):
        e = norm_email(raw['email'].split()[0] if raw['email'].split() else '')
        if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e):
            d['email'] = e
        else:
            warn.append('bad_email')
    if raw.get('birthday'):
        b = parse_date(raw['birthday'])
        if b:
            d['birthday'] = b
        else:
            warn.append('bad_date')
    kind = norm_text(raw.get('kind', ''))
    d['kind'] = 'org' if (kind in ('شركه', 'مؤسسه', 'جهه', 'org', 'company', 'organisation', 'organization', 'business') or (not kind and ORG_WORDS.search(norm_text(d.get('name', ''))))) else 'person'
    return d, sorted(set(warn))


class Analyses:
    """Analyses waiting for the person's decision (memory only, a few, expire after an hour)."""

    def __init__(self):
        self.items = {}

    def put(self, user_id, data):
        now_t = time.time()
        for k in [k for k, v in self.items.items() if now_t - v['t'] > 3600]:
            del self.items[k]
        while len(self.items) >= 4:
            del self.items[min(self.items, key=lambda k: self.items[k]['t'])]
        token = secrets.token_urlsafe(18)
        self.items[token] = {'t': now_t, 'user': user_id, **data}
        return token

    def get(self, token, user_id):
        a = self.items.get(token)
        if not a or a['user'] != user_id:
            raise BadRequest('E:import_expired|This import has expired. Start again.')
        a['t'] = time.time()
        return a


def open_upload(app, src):
    """The uploaded file the person just sent (only inside the uploads folder, only spreadsheet types)."""
    if not isinstance(src, str) or not src.startswith('/files/cas/') or '..' in src or '\\' in src:
        raise BadRequest('E:bad_file|Choose a file first.')
    path = os.path.realpath(os.path.join(app.uploads, src[len('/files/'):]))
    base = os.path.realpath(app.uploads)
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        raise BadRequest('E:bad_file|Choose a file first.')
    with open(path, 'rb') as f:
        data = f.read()
    try:
        return tablefile.read(path, data)
    except tablefile.BadFile as e:
        raise BadRequest(f'E:bad_file|{e}')


def preview(sheets, sheet_i=0, header_row=0):
    sheet = sheets[min(max(sheet_i, 0), len(sheets) - 1)]
    rows = sheet['rows']
    if header_row >= len(rows):
        header_row = 0
    headers = rows[header_row] if rows else []
    body = [r for r in rows[header_row + 1:] if any(clean(c) for c in r)]
    width = max([len(headers)] + [len(r) for r in body[:200]] or [0])
    headers = list(headers) + [''] * (width - len(headers))
    return {'sheets': [{'name': s['name'], 'rows': len(s['rows'])} for s in sheets], 'sheet': sheet_i, 'headerRow': header_row, 'headers': headers,
            'sample': [r + [''] * (width - len(r)) for r in body[:8]], 'total': len(body), 'mapping': {str(k): v for k, v in suggest(headers).items()}}


def analyze(app, access, sheets, sheet_i, header_row, mapping, role, country='20'):
    sheet = sheets[min(max(sheet_i, 0), len(sheets) - 1)]
    rows = sheet['rows'][header_row + 1:]
    mapping = {int(k): v for k, v in mapping.items() if v in FIELDS}
    if 'name' not in mapping.values():
        raise BadRequest('E:need_name_column|Choose which column holds the name.')
    idx = dedupe.Index.load(app, access, country)
    seen = dedupe.Index(country)
    out, summary = [], {'create': 0, 'match': 0, 'maybe': 0, 'file_dup': 0, 'invalid': 0, 'empty': 0, 'warn': 0}
    for n, cells in enumerate(rows):
        if not any(clean(c) for c in cells):
            summary['empty'] += 1
            continue
        line = header_row + 2 + n           # the row number the person sees in Excel
        d, warn = map_row(cells, mapping, country)
        item = {'line': line, 'data': d, 'warn': warn}
        if not d.get('name'):
            item.update(status='invalid', why='no_name', action='skip')
        else:
            hits = idx.find(d)
            dup = seen.find(d)
            if hits and hits[0][1] == 'same':
                item.update(status='match', match=hits[0][0], why=hits[0][2], action='fill')
            elif dup and dup[0][1] == 'same':
                item.update(status='file_dup', match_line=seen.rows[dup[0][0]]['_line'], why=dup[0][2], action='skip')
            elif hits or dup:
                item.update(status='maybe', match=hits[0][0] if hits else None, why='name', action='create')
            else:
                item.update(status='create', action='create')
            if item['status'] in ('create', 'maybe'):
                seen.add({**d, 'id': f'line{line}', '_line': line})
        summary[item['status']] += 1
        if warn:
            summary['warn'] += 1
        out.append(item)
    return {'items': out, 'summary': summary, 'role': role, 'mapping': mapping}


def public_items(items, statuses=None, offset=0, limit=100, existing=None):
    sel = [i for i in items if not statuses or i['status'] in statuses or ('warn' in statuses and i['warn'])]
    page = sel[offset:offset + limit]
    res = []
    for i in page:
        r = {'line': i['line'], 'status': i['status'], 'action': i['action'], 'name': i['data'].get('name', ''), 'phone': i['data'].get('phone', ''),
             'email': i['data'].get('email', ''), 'company': i['data'].get('company', ''), 'warn': i['warn'], 'why': i.get('why')}
        if i.get('match'):
            r['match'] = i['match']
            if existing and i['match'] in existing:
                r['matchName'] = existing[i['match']].get('name')
        if i.get('match_line'):
            r['matchLine'] = i['match_line']
        res.append(r)
    return {'rows': res, 'total': len(sel)}


FILL = ['name_en', 'phone', 'email', 'address', 'city', 'website', 'tax_id', 'birthday', 'source']
CHUNK = 60


def _strip(row):
    return {k: v for k, v in row.items() if not k.startswith('_') and k not in ('id', 'ver')}


def run_import(app, u, ip, analysis, overrides, filename, country='20'):
    """Saves the analysed rows. Backup first; one commit per 60 rows (each is all-or-nothing); returns the report."""
    from registry import META
    from .constants import ROLES
    guard = app.commit_guard(u)
    items = analysis['items']
    role = analysis['role'] if analysis['role'] in ROLES else 'lead'
    backup = app.backups.create('pre-import')
    batch = 'b' + secrets.token_hex(5)
    idx = dedupe.Index.load(app, dedupe_access(u), country)
    orgs = {dedupe.name_key(r.get('name')): i for i, r in idx.rows.items() if r.get('kind') == 'org'}
    report = {'created': 0, 'filled': 0, 'unchanged': 0, 'skipped': 0, 'failed': [], 'batch': batch, 'backup': backup}
    label = f'Import {filename}'[:100]
    ops, pending = [], 0

    def flush():
        nonlocal ops, pending
        if ops:
            app.store.commit(u['username'], ip, label, ops, guard=guard, user_id=u['id'])
        ops, pending = [], 0

    def org_for(name):
        k = dedupe.name_key(name)
        if k in orgs:
            return orgs[k]
        oid = f'impco-{batch}-{len(orgs)}'
        row = {'kind': 'org', 'name': name, 'status': 'active', 'import_batch': batch}
        ops.append({'e': 'parties', 'id': oid, 'op': 'put', 'row': row})
        ops.append({'e': 'party_roles', 'id': f'{oid}:{role}', 'op': 'put', 'row': {'party_id': oid, 'role': role}})
        orgs[k] = oid
        return oid

    for it in items:
        action = overrides.get(str(it['line']), it['action'])
        if action == 'skip' or it['status'] in ('invalid',):
            report['skipped'] += 1
            continue
        d = it['data']
        try:
            if action == 'fill' and it.get('match'):
                cur = app.store.get('parties', it['match'])
                if not cur:
                    report['skipped'] += 1
                    continue
                row, changed = _strip(cur), False
                for f in FILL:
                    if d.get(f) and not row.get(f):
                        row[f] = d[f]
                        changed = True
                if d.get('phone') and row.get('phone') and norm_phone(row['phone'], country) != d['phone'] and not row.get('phone2'):
                    row['phone2'], changed = d['phone'], True
                if changed:
                    META['parties'].validate(dict(row))
                    ops.append({'e': 'parties', 'id': it['match'], 'op': 'put', 'ver': cur['ver'], 'row': row})
                    report['filled'] += 1
                else:
                    report['unchanged'] += 1
                pid = it['match']
            else:
                pid = f'imp-{batch}-{it["line"]}'
                row = {k: v for k, v in d.items() if k in ('kind', 'name', 'name_en', 'phone', 'phone2', 'email', 'address', 'city', 'website', 'tags', 'source', 'tax_id', 'birthday')}
                row.update(status='active', import_batch=batch)
                META['parties'].validate(dict(row))
                ops.append({'e': 'parties', 'id': pid, 'op': 'put', 'row': row})
                ops.append({'e': 'party_roles', 'id': f'{pid}:{role}', 'op': 'put', 'row': {'party_id': pid, 'role': role, 'since': now()[:10]}})
                report['created'] += 1
            if d.get('company') and row.get('kind') != 'org':
                oid = org_for(d['company'])
                if oid != pid:
                    ops.append({'e': 'party_relations', 'id': f'{pid}:{oid}:works_at', 'op': 'put', 'row': {'from_party': pid, 'to_party': oid, 'kind': 'works_at'}})
            if d.get('notes'):
                ops.append({'e': 'notes', 'id': f'impn-{batch}-{it["line"]}', 'op': 'put', 'row': {'body': d['notes'], 'party_id': pid, 'subject_ref': f'parties:{pid}'}})
            pending += 1
            if pending >= CHUNK:
                flush()
        except BadRequest as e:
            report['failed'].append({'line': it['line'], 'why': str(e).split('|', 1)[-1]})
    flush()
    app.store.commit(u['username'], ip, label, [{'e': 'import_batches', 'id': batch, 'op': 'put', 'row': {
        'name': filename, 'at': now(), 'rows': len(items), 'created_n': report['created'], 'updated_n': report['filled'], 'skipped_n': report['skipped']}}],
        guard=guard, user_id=u['id'])
    return report


def dedupe_access(u):
    import query as query_mod
    return query_mod.access_for(u)


def undo_import(app, u, ip, batch):
    """Soft-deletes what the import created (records nobody edited since). Filled-in existing records are not reverted."""
    import query as query_mod
    access = query_mod.access_for(u)
    guard = app.commit_guard(u)
    parties = []
    cursor = None
    while True:
        page = query_mod.run(app.store, 'parties', access, [('import_batch', 'eq', batch)], limit=500, cursor=cursor)
        parties += page['rows']
        cursor = page['next']
        if not cursor:
            break
    keep = [p for p in parties if p['ver'] > 1 or not (p['id'].startswith('imp-') or p['id'].startswith('impco-'))]
    gone = [p for p in parties if p not in keep]
    ops = [{'e': 'parties', 'id': p['id'], 'op': 'del', 'ver': p['ver']} for p in gone]
    gone_ids = [p['id'] for p in gone]
    for entity, fk in (('party_roles', 'party_id'), ('notes', 'party_id')):
        for i in range(0, len(gone_ids), 200):
            for r in query_mod.run(app.store, entity, access, [(fk, 'in', gone_ids[i:i + 200])], limit=500)['rows']:
                if r['id'].startswith(('imp-', 'impco-', 'impn-')):
                    ops.append({'e': entity, 'id': r['id'], 'op': 'del', 'ver': r['ver']})
    for i in range(0, len(gone_ids), 200):
        for r in query_mod.run(app.store, 'party_relations', access, [('from_party', 'in', gone_ids[i:i + 200])], limit=500)['rows']:
            if r['id'].startswith('imp-'):
                ops.append({'e': 'party_relations', 'id': r['id'], 'op': 'del', 'ver': r['ver']})
    for i in range(0, len(ops), 300):
        app.store.commit(u['username'], ip, f'Undo import {batch}', ops[i:i + 300], guard=guard, user_id=u['id'])
    b = app.store.get('import_batches', batch)
    if b:
        row = _strip(b)
        row['undone'] = True
        app.store.commit(u['username'], ip, f'Undo import {batch}', [{'e': 'import_batches', 'id': batch, 'op': 'put', 'ver': b['ver'], 'row': row}], guard=guard, user_id=u['id'])
    return {'removed': len(gone), 'kept': len(keep)}

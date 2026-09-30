"""Import people and companies from Excel / CSV: preview, column mapping, duplicate report, backup first, undo.

Nothing is saved until the person presses "Import" (step 3). The analysis stays on the server (a 2,000-row file must not travel
back and forth), keyed by a random token that only its creator can use. Existing records are never overwritten: a match can only
have its EMPTY fields filled. Every imported record carries the batch id so the whole import can be undone in one step."""
import os
import re
import secrets
import threading
import time
from datetime import datetime

import tablefile
from store import BadRequest, now

from . import dedupe
from .util import rows, strip
from textnorm import norm_email, norm_phone, norm_text

FIELDS = ['name', 'name_en', 'kind', 'company', 'phone', 'phone2', 'email', 'address', 'city', 'website', 'tags', 'source', 'tax_id', 'birthday', 'notes']
SYNONYMS = {
    'name': ['name', 'full name', 'fullname', 'client', 'client name', 'customer', 'contact', 'الاسم', 'اسم', 'اسم العميل', 'العميل', 'اسم الشخص', 'الاسم بالكامل'],
    'name_en': ['english name', 'name en', 'الاسم بالانجليزي', 'الاسم بالانجليزية'],
    'kind': ['type', 'kind', 'النوع', 'نوع'],
    'company': ['company', 'company name', 'organisation', 'organization', 'employer', 'الشركة', 'شركة', 'اسم الشركة', 'اسم المؤسسة', 'اسم الجهة', 'جهة العمل', 'المؤسسة', 'الجهة'],
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
ORG_WORDS = re.compile(r'(^|\s)(' + '|'.join(norm_text(w) for w in ('شركة', 'مؤسسة', 'مكتب', 'مدرسة', 'مركز', 'أكاديمية', 'جمعية', 'مجموعة')) + r'|company|co|ltd|llc|inc|corp|center|centre|academy|school|group)(\s|$)', re.I)
ORG_KINDS = {norm_text(w) for w in ('شركة', 'مؤسسة', 'جهة', 'org', 'company', 'organisation', 'organization', 'business')}
NO_COMPANY = {'', '-', '--', 'لا يوجد', 'لايوجد', 'none', 'n/a', 'na', 'no', 'لا'}
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
    """Several numbers in one cell: separated by / , ; | new line, 'or', or simply by spaces between whole numbers."""
    v = str(v or '')
    parts = [p.strip() for p in re.split(r'[/\\,;،؛|\n]+|\s+(?:او|or)\s+', v) if p.strip()]
    out = []
    for p in parts:
        digits = re.sub(r'\D', '', norm_text(p))
        if len(digits) > 13 and ' ' in p:                       # two numbers typed with a space between them
            out += [x.strip() for x in re.findall(r'\+?\d[\d\-\(\)]{7,}', norm_text(p).replace(' ', '  ')) if x.strip()] or [p]
        else:
            out.append(p)
    return out[:2]


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
        n = '' if re.search(r'\dE[+-]?\d', p, re.I) else norm_phone(p, default_country)     # 1.01E+09 is a number Excel has already damaged
        if n and 9 <= len(n) - 1 <= 15:
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
    d['kind'] = 'org' if (kind in ORG_KINDS or (not kind and ORG_WORDS.search(norm_text(d.get('name', ''))))) else 'person'
    if norm_text(d.get('company', '')) in NO_COMPANY:
        d.pop('company', None)
    return d, sorted(set(warn))


class Analyses:
    """Analyses waiting for the person's decision (memory only, a few, expire after an hour)."""

    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def put(self, user_id, data):
        now_t = time.time()
        for k in [k for k, v in self.items.items() if now_t - v['t'] > 3600]:
            del self.items[k]
        while len(self.items) >= 4:
            del self.items[min(self.items, key=lambda k: self.items[k]['t'])]
        token = secrets.token_urlsafe(18)
        self.items[token] = {'t': now_t, 'user': user_id, **data}
        return token

    def take(self, token, user_id):
        """Uses the analysis once: a second press of the button (or a parallel request) finds nothing."""
        with self.lock:
            a = self.items.get(token)
            if not a or a['user'] != user_id:               # somebody else's token is not consumed by a wrong guess
                raise BadRequest('E:import_expired|This import has expired. Start again.')
            del self.items[token]
        return a

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
CREATE_FIELDS = ('kind', 'name', 'name_en', 'phone', 'phone2', 'email', 'address', 'city', 'website', 'tags', 'source', 'tax_id', 'birthday')
CHUNK = 60


def _code_of(e):
    text = str(e)
    if text.startswith('E:') and '|' in text:
        return text[2:].split('|', 1)[0], text.split('|', 1)[1]
    return ('conflict' if e.__class__.__name__ == 'Conflict' else 'failed'), text


def run_import(app, u, ip, analysis, overrides, filename, country='20'):
    """Saves the analysed rows: backup first, then the batch record (so even a half-finished import can be undone), then chunks of 60 rows.
    A chunk is all-or-nothing; a chunk that cannot be saved is reported line by line and the import goes on. Existing records only get empty fields filled."""
    import query as query_mod
    from registry import META
    from .constants import ROLES
    guard = app.commit_guard(u)
    access = query_mod.access_for(u)
    items = analysis['items']
    role = analysis['role'] if analysis['role'] in ROLES else 'lead'
    backup = app.backups.create('pre-import')
    batch = 'b' + secrets.token_hex(5)
    label = f'Import {filename}'[:100]
    report = {'created': 0, 'filled': 0, 'unchanged': 0, 'skipped': 0, 'failed': [], 'batch': batch, 'backup': backup}

    def commit(ops):
        return app.store.commit(u['username'], ip, label, ops, guard=guard, user_id=u['id'])

    commit([{'e': 'import_batches', 'id': batch, 'op': 'put', 'row': {'name': filename, 'at': now(), 'rows': len(items), 'state': 'running'}}])
    try:
        idx = dedupe.Index.load(app, access, country)
        orgs = {dedupe.name_key(r.get('name')): i for i, r in idx.rows.items() if r.get('kind') == 'org'}

        def build(it, action):
            """The changes for one spreadsheet row, or None (skipped). Companies it creates are remembered in `orgs` (and returned so a failed save can forget them)."""
            d, ops, count, made = it['data'], [], {'created': 0, 'filled': 0, 'unchanged': 0}, []
            if action == 'fill' and it.get('match'):
                cur = app.store.get('parties', it['match'])
                if not cur:
                    return None
                row, changed = strip(cur), False
                for f in FILL:
                    if d.get(f) and not row.get(f):
                        row[f] = d[f]
                        changed = True
                if d.get('phone') and row.get('phone') and norm_phone(row['phone'], country) != d['phone'] and not row.get('phone2'):
                    row['phone2'], changed = d['phone'], True
                if changed:
                    META['parties'].validate(dict(row))
                    ops.append({'e': 'parties', 'id': it['match'], 'op': 'put', 'ver': cur['ver'], 'row': row})
                    count['filled'] = 1
                else:
                    count['unchanged'] = 1
                pid, kind = it['match'], row.get('kind')
            else:
                pid = f'imp-{batch}-{it["line"]}'
                row = {k: v for k, v in d.items() if k in CREATE_FIELDS}
                row.update(status='active', import_batch=batch)
                META['parties'].validate(dict(row))
                ops.append({'e': 'parties', 'id': pid, 'op': 'put', 'row': row})
                ops.append({'e': 'party_roles', 'id': f'{pid}:{role}', 'op': 'put', 'row': {'party_id': pid, 'role': role}})
                count['created'] = 1
                kind = row.get('kind')
                if kind == 'org' and dedupe.name_key(row['name']) not in orgs:
                    orgs[dedupe.name_key(row['name'])] = pid                 # a company that is also a row must not be created twice
                    made.append(dedupe.name_key(row['name']))
            if d.get('company') and kind != 'org':
                k = dedupe.name_key(d['company'])
                if k in orgs:
                    oid = orgs[k]
                else:
                    oid = f'impco-{batch}-{len(orgs)}'
                    ops.append({'e': 'parties', 'id': oid, 'op': 'put', 'row': {'kind': 'org', 'name': d['company'], 'status': 'active', 'import_batch': batch}})
                    ops.append({'e': 'party_roles', 'id': f'{oid}:{role}', 'op': 'put', 'row': {'party_id': oid, 'role': role}})
                    orgs[k] = oid
                    made.append(k)
                rid = f'{pid}:{oid}:works_at'
                if oid != pid and not app.store.get('party_relations', rid):
                    ops.append({'e': 'party_relations', 'id': rid, 'op': 'put', 'row': {'from_party': pid, 'to_party': oid, 'kind': 'works_at'}})
            if d.get('notes'):
                same = query_mod.run(app.store, 'notes', access, [('party_id', 'eq', pid)], limit=500)['rows'] if action == 'fill' else []
                if not any(n.get('body') == d['notes'] for n in same):
                    ops.append({'e': 'notes', 'id': f'impn-{batch}-{it["line"]}', 'op': 'put', 'row': {'body': d['notes'], 'party_id': pid, 'subject_ref': f'parties:{pid}'}})
            return {'it': it, 'action': action, 'ops': ops, 'count': count, 'made': made}

        pending = []

        def save(built):
            """Saves built rows together; returns True/False. Never raises."""
            try:
                ops = [o for b in built for o in b['ops']]
                if ops:                                   # rows that change nothing (already complete) have nothing to save
                    commit(ops)
            except Exception as e:  # noqa: BLE001 - reported per row, the import goes on
                return _code_of(e)
            for b in built:
                for k, v in b['count'].items():
                    report[k] += v
            return None

        def flush():
            batch_rows, pending[:] = list(pending), []
            if not batch_rows:
                return
            if save(batch_rows) is None:
                return
            for b in batch_rows:                         # one bad row must not sink its 59 neighbours: forget the companies made here and save row by row
                for k in b['made']:
                    orgs.pop(k, None)
            for b in batch_rows:
                try:
                    again = build(b['it'], b['action'])
                except BadRequest as e:
                    code, why = _code_of(e)
                    report['failed'].append({'line': b['it']['line'], 'code': code, 'why': why})
                    continue
                if again is None:
                    report['skipped'] += 1
                    continue
                failure = save([again])
                if failure:
                    for k in again['made']:
                        orgs.pop(k, None)
                    report['failed'].append({'line': b['it']['line'], 'code': failure[0], 'why': failure[1]})

        for it in items:
            action = overrides.get(str(it['line']), it['action'])
            if action == 'skip' or it['status'] == 'invalid':
                report['skipped'] += 1
                continue
            try:
                built = build(it, action)
            except BadRequest as e:
                code, why = _code_of(e)
                report['failed'].append({'line': it['line'], 'code': code, 'why': why})
                continue
            if built is None:
                report['skipped'] += 1
                continue
            pending.append(built)
            if len(pending) >= CHUNK:
                flush()
        flush()
    finally:
        b = app.store.get('import_batches', batch)
        if b:
            row = strip(b)
            row.update(created_n=report['created'], updated_n=report['filled'], skipped_n=report['skipped'] + len(report['failed']), state='done' if not report['failed'] else 'partial')
            app.store.commit(u['username'], ip, label, [{'e': 'import_batches', 'id': batch, 'op': 'put', 'ver': b['ver'], 'row': row}], guard=guard, user_id=u['id'])
    return report


def dedupe_access(u):
    import query as query_mod
    return query_mod.access_for(u)


def undo_import(app, u, ip, batch):
    """Removes what the import ADDED and nobody touched since (people, their roles, notes and links). Anything other people have attached to an
    imported record since - tasks, opportunities, projects, files, notes - keeps that record alive. Details filled into existing records stay."""
    import query as query_mod
    access = query_mod.access_for(u)
    guard = app.commit_guard(u)
    parties = rows(app, access, 'parties', [('import_batch', 'eq', batch)])
    mine = f'impn-{batch}-'
    cand = {p['id']: p for p in parties if p['ver'] == 1 and (p['id'].startswith('imp-') or p['id'].startswith('impco-'))}
    keep = set()
    changed = True
    while changed:
        changed = False
        ids = sorted(set(cand) - keep)
        if not ids:
            break
        found = set()
        for i in range(0, len(ids), 150):
            part = ids[i:i + 150]
            for entity in ('opportunities', 'projects', 'tasks', 'appointments', 'activities', 'attachments'):
                found |= {r['party_id'] for r in rows(app, access, entity, [('party_id', 'in', part)])}
            found |= {n['party_id'] for n in rows(app, access, 'notes', [('party_id', 'in', part)]) if not n['id'].startswith(mine)}
            for r in rows(app, access, 'party_relations', [('to_party', 'in', part)]):
                if r['from_party'] not in cand or r['from_party'] in keep:      # somebody who stays works at this company
                    found.add(r['to_party'])
        new = (found & set(cand)) - keep
        if new:
            keep |= new
            changed = True
    gone = [i for i in cand if i not in keep]
    gone_set = set(gone)
    ops = [{'e': 'parties', 'id': i, 'op': 'del', 'ver': cand[i]['ver']} for i in gone]
    for i in range(0, len(gone), 150):
        part = gone[i:i + 150]
        for entity, key in (('party_roles', 'party_id'), ('party_relations', 'from_party'), ('party_relations', 'to_party')):
            for r in rows(app, access, entity, [(key, 'in', part)]):
                if not any(o['e'] == entity and o['id'] == r['id'] for o in ops):
                    ops.append({'e': entity, 'id': r['id'], 'op': 'del', 'ver': r['ver']})
    for n in rows(app, access, 'notes', [('id', 'like', mine)]):
        if n['id'].startswith(mine) and n['ver'] == 1:
            ops.append({'e': 'notes', 'id': n['id'], 'op': 'del', 'ver': n['ver']})
    for i in range(0, len(ops), 300):       # kind 'restore': a delete never beats a real change another PC made at the same time
        app.store.commit(u['username'], ip, f'Undo import {batch}', ops[i:i + 300], guard=guard, user_id=u['id'], kind='restore')
    b = app.store.get('import_batches', batch)
    if b:
        row = strip(b)
        row['undone'] = True
        app.store.commit(u['username'], ip, f'Undo import {batch}', [{'e': 'import_batches', 'id': batch, 'op': 'put', 'ver': b['ver'], 'row': row}], guard=guard, user_id=u['id'])
    return {'removed': len(gone_set), 'kept': len(parties) - len(gone_set)}

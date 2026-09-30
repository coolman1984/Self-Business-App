"""API routes of the business layer. Every route checks login, permission, data scope and money visibility here on the server."""
import query as query_mod
from auth import Forbidden
from store import BadRequest

from . import constants, dedupe, demo, importer, timeline, today


def add_routes(app):
    analyses = importer.Analyses()
    country = app.cfg.get('default_country_code', '20')

    def meta(h):
        h.send(200, constants.META)

    def today_(h):
        h.send(200, today.build(app, h.access()))

    def timeline_(h):
        qs = h.qs
        party = qs.get('party') or ''
        h.need('clients.view')
        row = app.store.get('parties', party)
        if not row or not query_mod.can_see('parties', row, h.access(), app.store):
            return h.send(404, {'error': 'Not found'})
        h.send(200, {'events': timeline.party_timeline(app, h.access(), party, int(qs.get('limit', 100)), qs.get('before') or None)})

    def duplicates(h):
        h.need('clients.view')
        access = h.access()
        idx = dedupe.Index.load(app, access, country)
        qs = h.qs
        if qs.get('name') or qs.get('phone') or qs.get('email'):
            cand = {'name': qs.get('name', ''), 'phone': qs.get('phone', ''), 'email': qs.get('email', '')}
            hits = idx.find(cand, exclude=qs.get('self') or None)[:5]
            return h.send(200, {'matches': [{'id': i, 'strength': s, 'why': w, 'name': idx.rows[i].get('name'), 'phone': idx.rows[i].get('phone'),
                                             'email': idx.rows[i].get('email'), 'kind': idx.rows[i].get('kind')} for i, s, w in hits]})
        groups = dedupe.groups(idx)
        h.send(200, {'groups': [{**g, 'rows': [{'id': i, 'name': idx.rows[i].get('name'), 'phone': idx.rows[i].get('phone'), 'email': idx.rows[i].get('email'),
                                                'kind': idx.rows[i].get('kind'), '_created': idx.rows[i].get('_created')} for i in g['ids']]} for g in groups[:100]]})

    # ---- import (administrator: it can change many records at once; a backup is always made first)
    def imp_preview(h):
        d = h.json_body()
        sheets = importer.open_upload(app, d.get('src'))
        h.send(200, importer.preview(sheets, int(d.get('sheet') or 0), int(d.get('headerRow') or 0)))

    def imp_analyze(h):
        h.need('clients.view')                # the report shows who already exists
        d = h.json_body()
        sheets = importer.open_upload(app, d.get('src'))
        a = importer.analyze(app, h.access(), sheets, int(d.get('sheet') or 0), int(d.get('headerRow') or 0), d.get('mapping') or {}, d.get('role') or 'lead', country)
        a['filename'] = str(d.get('name') or 'file')[:100]
        token = analyses.put(h.u['id'], a)
        existing = {i.get('match') for i in a['items'] if i.get('match')}
        names = {}
        if existing:
            for r in query_mod.run(app.store, 'parties', h.access(), [('id', 'in', sorted(existing)[:200])], limit=200)['rows']:
                names[r['id']] = r
        h.send(200, {'token': token, 'summary': a['summary'], **importer.public_items(a['items'], ['match', 'maybe', 'file_dup', 'invalid', 'warn'], 0, 100, names)})

    def imp_rows(h):
        d = h.json_body()
        a = analyses.get(d.get('token'), h.u['id'])
        h.send(200, importer.public_items(a['items'], d.get('statuses') or None, int(d.get('offset') or 0), min(int(d.get('limit') or 100), 200)))

    def imp_commit(h):
        d = h.json_body()
        a = analyses.take(d.get('token'), h.u['id'])          # used once: a double click or a second request finds nothing
        overrides = {str(k): v for k, v in (d.get('overrides') or {}).items() if v in ('create', 'fill', 'skip')}
        report = importer.run_import(app, h.u, h.ip, a, overrides, a.get('filename', 'file'), country)
        app.say(f'Import by {h.user}: {report["created"]} new, {report["filled"]} filled, {report["skipped"]} skipped, backup {report["backup"]}')
        h.send(200, report)

    def imp_undo(h):
        d = h.json_body()
        res = importer.undo_import(app, h.u, h.ip, str(d.get('batch') or ''))
        h.send(200, res)

    def demo_status(h):
        h.send(200, demo.status(app, h.u))

    def demo_load(h):
        d = h.json_body()
        h.send(200, demo.load(app, h.u, h.ip, 'en' if d.get('lang') == 'en' else 'ar', [k for k in (d.get('kinds') or []) if isinstance(k, str)][:4]))

    def demo_remove(h):
        h.send(200, demo.remove(app, h.u, h.ip))

    app.route('GET', '/api/business/meta', meta)
    app.route('GET', '/api/today', today_)
    app.route('GET', '/api/timeline', timeline_)
    app.route('GET', '/api/parties/duplicates', duplicates)
    app.route('POST', '/api/import/preview', imp_preview, perms=('data.import',))
    app.route('POST', '/api/import/analyze', imp_analyze, perms=('data.import',))
    app.route('POST', '/api/import/rows', imp_rows, perms=('data.import',))
    app.route('POST', '/api/import/commit', imp_commit, perms=('data.import',))
    app.route('POST', '/api/import/undo', imp_undo, perms=('data.import',))
    app.route('GET', '/api/demo/status', demo_status, perms=('data.import',))
    app.route('POST', '/api/demo/load', demo_load, perms=('data.import',))
    app.route('POST', '/api/demo/remove', demo_remove, perms=('data.import',))

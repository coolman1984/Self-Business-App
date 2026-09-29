"""HTTP server of the engine: one `App` object (no import-time side effects) and a request handler.

Harvested from BAMS `app.py` and made domain-free: entities, permissions and scopes come from the registries. The platform
and the modules add their own API routes with `app.route(method, path, fn, perms=...)`.

Security rules kept from BAMS: every route checks login, permission, data scope and money visibility on the SERVER;
Origin check on every POST (CSRF); 64 kB body limit and a failed-login limiter before login; first-run setup only from the
PC itself; secrets (personal link tokens) never in logs; static files only from a whitelist; security headers on
every answer.
"""
import hashlib
import html
import json
import logging
import logging.handlers
import mimetypes
import os
import socket
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

import backup as backup_mod
import query as query_mod
import xlsx
from auth import AuthError, Forbidden
from permissions import ADMIN_PERMS, PERMISSIONS
from registry import ENTITIES, META
from search import SearchIndex
from store import BadRequest, Conflict, now
from sync import SyncService
from system import System, lock_data
from version import COPYRIGHT, DEVELOPER, LICENSE_NOTE, PRODUCT, VERSION

DEFAULT_CONFIG = {
    'port': 8110,
    'host': '0.0.0.0',
    'data_dir': 'data',
    'backup_dir': 'backups',
    'extra_backup_dirs': [],
    'backup_interval_hours': 6,
    'keep_auto_backups': 200,
    'max_upload_mb': 50,
    'open_browser': True,
    'session_idle_minutes': 30,
    'session_max_hours': 12,
    'max_failed_logins': 5,
    'lockout_minutes': 15,
    'min_password_length': 10,
    'device_name': '',
    'sync_port': 8463,
    'sync_interval_seconds': 5,
    'peer_addresses': {},
    'default_country_code': '20',
}
STATIC = {'/': 'index.html', '/index.html': 'index.html'}
STATIC_DIRS = ('/css/', '/js/', '/lib/', '/fonts/')
STATIC_EXT = {'.html', '.js', '.mjs', '.css', '.svg', '.png', '.ico', '.woff', '.woff2', '.map', '.json', '.webmanifest'}
UPLOAD_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.zip'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
INLINE_EXT = IMAGE_EXT | {'.pdf'}
# a file is stored under the extension of its real content: (leading bytes) -> extensions that are allowed for it
MAGIC = {b'\xff\xd8\xff': {'.jpg', '.jpeg'}, b'\x89PNG\r\n\x1a\n': {'.png'}, b'GIF8': {'.gif'}, b'%PDF': {'.pdf'},
         b'PK\x03\x04': {'.docx', '.xlsx', '.pptx', '.zip'}, b'\xd0\xcf\x11\xe0': {'.doc', '.xls', '.ppt'}, b'BM': {'.bmp'}}
TYPES = {'.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.webp': 'image/webp',
         '.webmanifest': 'application/manifest+json',
         '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
LOCAL_IPS = ('127.0.0.1', '::1', '::ffff:127.0.0.1')
PLACEHOLDER = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200"><rect width="320" height="200" fill="#eef1f5"/>'
               b'<text x="160" y="96" font-family="Segoe UI,Arial" font-size="15" text-anchor="middle" fill="#6b7785">Picture is being copied</text>'
               b'<text x="160" y="118" font-family="Segoe UI,Arial" font-size="12" text-anchor="middle" fill="#8a95a3">from another PC...</text></svg>')
COOKIE = 'sbo_sid'
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; "
       "connect-src 'self' data: blob:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
PERM_LABEL = {}


def perm_label(p):
    if not PERM_LABEL or p not in PERM_LABEL:
        PERM_LABEL.update({k: label for _, ps in PERMISSIONS for k, label in ps})
    return PERM_LABEL.get(p, p)


def mask_audit_row(row, perms):
    """Removes hidden (money / sensitive) fields from the old and new values of one data-change log row."""
    hide = query_mod.hidden_fields(row.get('entity'), perms)
    if not hide:
        return
    for key in ('changes', 'before', 'after'):
        try:
            d = json.loads(row[key]) if row.get(key) else None
        except ValueError:
            continue
        if isinstance(d, dict):
            row[key] = json.dumps({k: v for k, v in d.items() if k not in hide}, ensure_ascii=False, sort_keys=True)


def attachment_header(filename):
    """Content-Disposition for a download whose name may contain Arabic letters: an ASCII fallback plus the RFC 5987 form."""
    ascii_name = ''.join(ch if ch.isascii() and (ch.isalnum() or ch in ' _-.') else '_' for ch in filename) or 'download'
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename, safe="")}'


def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            cfg.update(json.load(f))
    else:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    return cfg


class NotLoggedIn(Exception):
    pass


def is_admin(u):
    return bool(u) and 'users.manage' in u['perms']


def lan_urls(port):
    urls = [f'http://{socket.gethostname()}:{port}/']
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith('127.'):
                urls.append(f'http://{ip}:{port}/')
    except OSError:
        pass
    return urls


class App:
    """Everything one running program consists of. Tests and tools create their own instance."""

    def __init__(self, home, config_path=None, cfg=None, root=None, assets=None, say=None):
        self.home = home
        self.config_path = config_path or os.path.join(home, 'config.json')
        self.cfg = cfg or load_config(self.config_path)
        self.root = root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assets = assets
        self.data_dir = self.resolve(self.cfg['data_dir'])
        self.uploads = os.path.join(self.data_dir, 'uploads')
        os.makedirs(self.uploads, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, 'logs'), exist_ok=True)
        self.logger = logging.getLogger('sbo.' + hashlib.sha1(self.data_dir.encode()).hexdigest()[:8])
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh = logging.handlers.RotatingFileHandler(os.path.join(self.data_dir, 'logs', 'server.log'), maxBytes=5 * 1048576, backupCount=20, encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            self.logger.addHandler(fh)
        self._say = say
        self.routes = {'GET': {}, 'POST': {}}
        self.failed = {}
        self.failed_lock = threading.Lock()
        self.instance = lock_data(self.data_dir)  # taken before anything touches the data
        self.system = self.sync = self.index = None
        if self.instance:
            self.system = System(self.data_dir, self.cfg, self.uploads, self.resolve(self.cfg['backup_dir']),
                                 [self.resolve(d) for d in self.cfg['extra_backup_dirs']], log=self.say)
            self.sync = SyncService(self.system, self.cfg, self.uploads, log=self.say)
            self.index = SearchIndex(os.path.join(self.data_dir, 'index.db'), self.cfg.get('default_country_code', '20'))
            self.store.after_fold.append(self.index.apply)
            if self.index.needs_rebuild():
                self.index.rebuild(self.store)

    # shortcuts
    store = property(lambda s: s.system.store)
    auth = property(lambda s: s.system.auth)
    backups = property(lambda s: s.system.backups)
    journal = property(lambda s: s.system.journal)
    node = property(lambda s: s.system.node)

    def resolve(self, p):
        return p if os.path.isabs(p) else os.path.join(self.home, p)

    def say(self, msg):
        self.logger.info(msg)
        if self._say is None:
            print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)
        elif self._say:
            self._say(msg)

    def route(self, method, path, fn, perms=(), admin=False, prefix=False):
        """Adds an API route. fn(handler) returns nothing and calls handler.send(...). perms: any one is enough."""
        self.routes[method][path] = (fn, tuple(perms), admin, prefix)

    def about(self):
        out = {'product': PRODUCT, 'version': VERSION, 'developer': DEVELOPER, 'copyright': COPYRIGHT, 'license': LICENSE_NOTE,
               'installed': self.assets is not None}
        try:
            with self.store.lock:
                for k, v in self.store.conn.execute("SELECT id, value FROM settings WHERE id IN ('brand.name', 'brand.short')"):
                    try:
                        v = json.loads(v)
                    except (TypeError, ValueError):
                        pass
                    if isinstance(v, str) and v.strip():
                        out[k] = v.strip()[:80]
        except Exception:  # noqa: BLE001 - only cosmetics for the login screen
            pass
        return out

    def too_many_failures(self, ip, add=False):
        """More than 10 failed logins from one address within a minute: refuse quickly, without the slow password check."""
        t = time.time()
        with self.failed_lock:
            recent = [x for x in self.failed.get(ip, []) if t - x < 60]
            if add:
                recent.append(t)
            if recent:
                self.failed[ip] = recent[-50:]
            else:
                self.failed.pop(ip, None)
            if len(self.failed) > 5000:
                self.failed.clear()
            return len(recent) > 10

    # ------------------------------------------------------------ change permissions (used by /api/commit)
    def commit_guard(self, u):
        """Checks every change of a save against the user's permissions and data scope."""
        perms = set(u['perms'])
        mode = u.get('data_scope') or 'all'
        scopes = set(u.get('scopes') or [])

        def guard(changes, force):
            if force:  # replaces everything: import, demo data
                if 'data.import' not in perms or mode != 'all':
                    raise Forbidden('Only a user with the permission "' + perm_label('data.import') + '" and access to all data can replace all data.')
                return
            for c in changes:
                e, op = c['entity'], c['op']
                need = META[e].perms_for(op) if e in META else ()
                if not perms.intersection(need):
                    what = META[e].title if e in META else e
                    raise Forbidden(f'You are not allowed to {"add" if op == "insert" else "change" if op == "update" else "delete"} {what}. '
                                    + (f'Ask the administrator for the permission "{perm_label(need[0])}".' if need else 'This kind of record cannot be changed here.'))
                if mode == 'scopes' and e in META and (META[e].scope_self or META[e].scope_field or META[e].scope_via):
                    if op == 'insert' and c.get('scope') is None and not META[e].scope_self:
                        raise Forbidden('You can only work inside the areas assigned to you.')
                    if not {c.get('scope'), c.get('scope_before', c.get('scope'))} <= scopes:
                        raise Forbidden('You can only change the records assigned to you.')
                elif mode == 'own' and op != 'insert':
                    r = self.store.conn.execute(f'SELECT created_by FROM {ENTITIES[e][0]} WHERE id=?', (c['id'],)).fetchone()
                    if not r or r[0] != u['display']:
                        raise Forbidden('You can only change the records you created yourself.')
        return guard

    def keep_hidden_fields(self, u, ops):
        """A user who may not see money or sensitive fields can still edit the other fields of a record: the hidden values
        are taken from the stored record here, on the server, instead of being cleared because the page did not send them."""
        perms = set(u['perms'])
        for op in ops:
            if not isinstance(op, dict) or op.get('op') != 'put' or not isinstance(op.get('row'), dict) or op.get('e') not in META:
                continue
            m = META[op['e']]
            hidden = set()
            if 'money.view' not in perms:
                hidden |= set(m.money_fields)
            if 'data.sensitive' not in perms:
                hidden |= set(m.sensitive_fields)
            if not hidden:
                continue
            for f in hidden:
                op['row'].pop(f, None)
            cur = self.store.get(op['e'], op.get('id'))
            if cur:
                for f in hidden:
                    if cur.get(f) is not None:
                        op['row'][f] = cur[f]


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != 'nt'  # Windows: reuse would let a second copy share the port silently
    daemon_threads = True


def make_handler(app):
    log = app.logger

    class Handler(BaseHTTPRequestHandler):
        server_version = 'SBO/1.0'
        protocol_version = 'HTTP/1.1'
        timeout = 120
        u = None
        _read = False

        # ------------------------------------------------------------ plumbing
        def log_message(self, fmt, *args):
            pass

        app = property(lambda s: app)

        @property
        def user(self):
            return self.u['display'] if self.u else 'Not logged in'

        @property
        def log_path(self):
            return '/k/…' if self.path.startswith('/k/') else self.path

        @property
        def ip(self):
            return self.client_address[0]

        @property
        def token(self):
            for part in (self.headers.get('Cookie') or '').split(';'):
                k, _, v = part.strip().partition('=')
                if k == COOKIE:
                    return v
            return ''

        @property
        def qs(self):
            return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

        def login_required(self, touch=True):
            self.u = app.auth.session(self.token, self.ip, touch)
            if not self.u:
                raise NotLoggedIn()
            return self.u

        def can(self, *perms):
            return bool(self.u) and any(p in self.u['perms'] for p in perms)

        def need(self, *perms):
            if not perms:
                raise Forbidden('This is not allowed.')
            if not self.can(*perms):
                raise Forbidden('You do not have permission for this. Ask the administrator for: "' + perm_label(perms[0]) + '".')

        def need_admin(self):
            if not is_admin(self.u):
                raise Forbidden('Only an administrator can open this.')

        def need_all_data(self):
            if (self.u.get('data_scope') or 'all') != 'all':
                raise Forbidden('This is only for users who can see all the data.')

        def access(self):
            return query_mod.access_for(self.u)

        def send(self, code, body=b'', ctype='application/json', headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(code)
            unread = self.command == 'POST' and not self._read and int(self.headers.get('Content-Length') or 0)
            if code >= 400 or unread:
                self.close_connection = True
                self.send_header('Connection', 'close')
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', CSP)
            headers = dict(headers or {})
            if self.path.startswith('/api/'):
                headers.setdefault('Cache-Control', 'no-store')
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def set_session(self, token):
            return {'Set-Cookie': f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict'}

        def clear_session(self):
            return {'Set-Cookie': f'{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'}

        def body(self, limit=20 * 1048576):
            raw = self.headers.get('Content-Length') or '0'
            if not raw.isdigit():
                raise BadRequest('Invalid request length')
            n = int(raw)
            if n > limit:
                raise BadRequest(f'Request too large ({n // 1048576} MB)')
            self._read = True
            return self.rfile.read(n) if n else b''

        def json_body(self):
            raw = self.body(200 * 1048576 if self.u else 65536)  # before logging in only small requests
            try:
                d = json.loads(raw.decode('utf-8')) if raw else {}
            except ValueError:
                raise BadRequest('The request is not valid JSON')
            if not isinstance(d, dict):
                raise BadRequest('The request must be a JSON object')
            return d

        def denied(self, msg):
            app.auth.log(self.user, self.ip, 'access-denied', self.log_path.split('?')[0], msg)
            try:
                app.store.log_activity(self.user, self.ip, [{'type': 'denied', 'action': self.log_path.split('?')[0], 'detail': msg}])
            except Exception:  # noqa: BLE001
                pass

        def handle_safely(self, fn):
            try:
                fn()
            except NotLoggedIn:
                self.send(401, {'error': 'Please log in.', 'login': True}, headers=self.clear_session())
            except Forbidden as e:
                log.info('DENIED %s %s %s', self.user, self.log_path, e)
                self.denied(str(e))
                self.send(403, {'error': str(e)})
            except AuthError as e:
                self.send(400, {'error': str(e)})
            except Conflict as e:
                self.send(409, {'error': str(e)})
            except (BadRequest, ValueError, query_mod.QueryError) as e:
                log.info('BAD REQUEST %s %s %s', self.user, self.log_path, e)
                self.send(400, {'error': str(e)})
            except (ConnectionError, BrokenPipeError):
                pass
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc()
                log.error('ERROR %s %s\n%s', self.user, self.log_path, tb)
                try:
                    app.store.log_activity(self.user, self.ip, [{'type': 'server-error', 'action': self.log_path, 'detail': tb[-1900:]}])
                except Exception:  # noqa: BLE001
                    pass
                self.send(500, {'error': 'Server error. It has been recorded; please tell the administrator.'})

        # ------------------------------------------------------------ routing
        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            self.u = None
            self.handle_safely(self._get)

        def do_POST(self):
            self.u, self._read = None, False
            self.handle_safely(self._post)

        def me(self):
            u = self.u
            n = app.node
            return {**app.auth.public(u), 'display': u['display'], 'permissions': PERMISSIONS, 'adminPerms': sorted(ADMIN_PERMS),
                    'sessionIdleMinutes': app.cfg['session_idle_minutes'], 'minPasswordLength': app.auth.min_len, 'admin': is_admin(u),
                    'viaLink': bool(u.get('via_link')), 'node': {'id': n.id, 'name': n.name, 'role': n.role, 'authority': n.is_authority}}

        def node_status(self):
            n, j = app.node, app.journal.meta('join')
            return {'role': n.role, 'name': n.name, 'id': n.id, 'moved': n.moved,
                    'join': {'confirm': j['confirm'], 'authority': j.get('authority')} if j and n.role == 'unconfigured' else None}

        def extra_route(self, method, path):
            table = app.routes[method]
            hit = table.get(path)
            if hit is None:
                hit = next((v for k, v in table.items() if v[3] and path.startswith(k)), None)
            if hit is None:
                return False
            fn, perms, admin, _ = hit
            self.login_required()
            if perms:
                self.need(*perms)
            if admin:
                self.need_admin()
            fn(self)
            return True

        def _get(self):
            url = urlparse(self.path)
            p, qs = url.path, self.qs
            if p in STATIC:
                return self.serve_static(STATIC[p])
            if p.startswith(STATIC_DIRS):
                return self.serve_static(p.lstrip('/'))
            if p.startswith('/k/'):
                return self.link_page(p[3:])
            if p == '/api/auth/status':
                self.u = app.auth.session(self.token, self.ip, touch=False)
                return self.send(200, {'hasUsers': app.auth.has_users(), 'local': self.ip in LOCAL_IPS, 'me': self.me() if self.u else None,
                                       'node': self.node_status(), 'about': app.about()})
            if p == '/api/join/status':
                if self.ip not in LOCAL_IPS or app.auth.has_users() and app.node.role != 'member':
                    raise Forbidden('Only on this PC itself.')
                return self.send(200, {**app.sync.join_progress(), 'hasUsers': app.auth.has_users()})

            if p == '/api/version' and self.token:
                self.login_required(touch=False)
            else:
                self.login_required()
            if p == '/api/me':
                return self.send(200, self.me())
            if p == '/api/version':
                return self.send(200, {'version': app.store.version(), 'me': self.u['ver'], 'mustChange': bool(self.u['must_change']),
                                       'sync': app.sync.summary()})
            if p.startswith('/api/q/'):
                entity = p[len('/api/q/'):]
                if entity not in META:
                    return self.send(404, {'error': 'Not found'})
                self.need(*META[entity].perms_for('view'))
                filters = []
                for raw in parse_qs(url.query).get('f', []):  # f=field:op:value
                    field, _, rest = raw.partition(':')
                    op, _, value = rest.partition(':')
                    filters.append((field, op, value.split(',') if op == 'in' else value))
                res = query_mod.run(app.store, entity, self.access(), filters, qs.get('search'), qs.get('sort'), qs.get('desc') == '1',
                                    int(qs.get('limit', 50)), qs.get('cursor'), include_deleted=False)
                return self.send(200, res)
            if p.startswith('/api/get/'):
                entity, _, rid = p[len('/api/get/'):].partition('/')
                if entity not in META:
                    return self.send(404, {'error': 'Not found'})
                self.need(*META[entity].perms_for('view'))
                row = app.store.get(entity, unquote(rid))
                if not row or not query_mod.can_see(entity, row, self.access(), app.store):
                    return self.send(404, {'error': 'Not found'})
                return self.send(200, query_mod.mask(entity, row, set(self.u['perms'])))
            if p == '/api/search':
                allowed = [e for e, m in META.items() if m.search and set(m.perms_for('view')) & set(self.u['perms'])]
                hits = app.index.search(qs.get('q', ''), self.access(), int(qs.get('limit', 20)), allowed) if allowed else []
                return self.send(200, hits)
            if p == '/api/info':
                urls = lan_urls(app.cfg['port'])
                if not self.can('settings.view'):
                    return self.send(200, {'urls': urls})
                db_size = sum(os.path.getsize(os.path.join(app.data_dir, f)) for f in os.listdir(app.data_dir) if f.startswith('sbo.db'))
                up_size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(app.uploads) for f in fs)
                return self.send(200, {'urls': urls, 'dataDir': app.data_dir, 'backupDir': app.backups.dir, 'extraBackupDirs': app.backups.extra,
                                       'dbSize': db_size, 'uploadsSize': up_size, 'backupIntervalHours': app.cfg['backup_interval_hours'],
                                       'lastBackupError': app.backups.last_error, 'counts': app.store.counts(), 'serverTime': now()})
            if p == '/api/backups':
                self.need('backups.manage', 'backups.restore')
                return self.send(200, app.backups.list())
            if p == '/api/backups/folder':
                self.need('backups.manage')
                return self.send(200, {'dirs': app.backups.extra, 'error': app.backups.last_error, 'local': self.ip in LOCAL_IPS, 'admin': is_admin(self.u)})
            if p == '/api/trash':
                self.need('trash.restore')
                self.need_all_data()
                return self.send(200, app.store.trash())
            if p in ('/api/audit', '/api/activity'):
                self.need('logs.view' if p == '/api/audit' else 'logs.activity')
                if p == '/api/activity':
                    self.need_admin()
                node = qs.get('node', '') if is_admin(self.u) else ''
                scopes = (self.u.get('scopes') or []) if (self.u.get('data_scope') or 'all') == 'scopes' else None  # nothing assigned = nothing shown
                if (self.u.get('data_scope') or 'all') == 'own':
                    scopes = []
                perms = set(self.u['perms'])
                sees_values = {'money.view', 'data.sensitive'} <= perms  # otherwise the log must not reveal hidden fields
                res = app.store.query_log('audit' if p == '/api/audit' else 'activity', qs.get('q', ''), qs.get('user', ''),
                                          qs.get('type', ''), qs.get('scope', ''), qs.get('from', ''), qs.get('to', ''),
                                          max(1, min(1000, int(qs.get('limit', 200)))), max(0, int(qs.get('offset', 0))),
                                          scopes, node, admin=is_admin(self.u), search_values=sees_values)
                if p == '/api/audit' and not sees_values:
                    for row in res['rows']:
                        mask_audit_row(row, perms)
                return self.send(200, res)
            if p == '/api/security':
                self.need('logs.security')
                self.need_admin()
                return self.send(200, app.auth.query_log(qs.get('q', ''), qs.get('user', ''), qs.get('type', ''), qs.get('from', ''), qs.get('to', ''),
                                                         max(1, min(1000, int(qs.get('limit', 200)))), max(0, int(qs.get('offset', 0))), qs.get('node', '')))
            if p == '/api/devices':
                self.need_admin()
                return self.send(200, app.sync.overview())
            if p == '/api/quick-links':
                self.need_admin()
                return self.send(200, {'users': app.auth.link_list(), 'authority': app.node.is_authority,
                                       'authorityHint': '' if app.node.is_authority else app.auth.authority_hint(), 'urls': lan_urls(app.cfg['port'])})
            if p == '/api/devices/log':
                self.need_admin()
                with app.journal.lock:
                    rows = [dict(r) for r in app.journal.conn.execute('SELECT * FROM sync_log ORDER BY id DESC LIMIT ?', (min(1000, int(qs.get('limit', 300))),))]
                return self.send(200, rows)
            if p == '/api/conflicts':
                self.need_admin()
                return self.send(200, self.conflict_list())
            if p == '/api/users':
                self.need('users.manage')
                return self.send(200, {'users': app.auth.list_users(), 'permissions': PERMISSIONS, 'profiles': app.auth.profiles(),
                                       'adminPerms': sorted(ADMIN_PERMS), 'authority': app.node.is_authority,
                                       'authorityHint': '' if app.node.is_authority else app.auth.authority_hint()})
            if p == '/api/export.xlsx':
                self.need('users.manage', 'export.excel')
                self.need_all_data()
                if 'money.view' not in self.u['perms'] or 'data.sensitive' not in self.u['perms']:
                    raise Forbidden('The complete export contains amounts and sensitive information. You need the permissions to see them.')
                data = xlsx.build(app.store.export_sheets(admin=is_admin(self.u) and self.can('logs.activity')))
                log.info('EXPORT full workbook by %s (%s)', self.user, self.ip)
                app.store.log_activity(self.user, self.ip, [{'type': 'export', 'action': 'Full Excel export', 'target': 'All data'}])
                return self.send(200, data, TYPES['.xlsx'], {'Content-Disposition': attachment_header(f'Export_{datetime.now():%Y-%m-%d_%H%M}.xlsx')})
            if p.startswith('/files/'):
                self.need('files.download')
                return self.serve_file(app.uploads, p[len('/files/'):], src=p)
            if self.extra_route('GET', p):
                return
            self.send(404, {'error': 'Not found'})

        def _post(self):
            p = urlparse(self.path).path
            qs = self.qs
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                raise Forbidden('Request from another web site was blocked.')

            # ---------------- no login needed
            if p.startswith('/k/'):
                if app.too_many_failures(self.ip):
                    raise AuthError('Too many attempts. Wait a minute and try again.')
                try:
                    token, u = app.auth.link_login(p[3:], self.ip, self.headers.get('User-Agent', ''))
                except AuthError:
                    app.too_many_failures(self.ip, add=True)
                    time.sleep(0.6)
                    return self.link_page(p[3:])
                if self.token:
                    app.auth.logout(self.token, None, self.ip)
                app.say(f'Login with personal link: {u["display"]} ({self.ip})')
                return self.send(303, b'', 'text/plain', {'Location': '/', **self.set_session(token)})
            if p == '/api/auth/login':
                d = self.json_body()
                if app.too_many_failures(self.ip):
                    raise AuthError('Too many wrong attempts from this computer. Wait a minute and try again.')
                try:
                    token, u = app.auth.login(d.get('username'), d.get('password'), self.ip, self.headers.get('User-Agent', ''))
                except AuthError:
                    app.too_many_failures(self.ip, add=True)
                    time.sleep(0.6)
                    raise
                self.u = u
                app.say(f'Login: {u["display"]} ({self.ip})')
                return self.send(200, self.me(), headers=self.set_session(token))
            if p == '/api/join':
                if self.ip not in LOCAL_IPS or app.auth.has_users() or app.node.role != 'unconfigured':
                    raise Forbidden('Joining is only possible on a new, not yet set up PC, on the PC itself.')
                d = self.json_body()
                try:
                    return self.send(200, app.sync.join(d.get('address'), d.get('code'), d.get('name')))
                except ValueError as e:
                    raise BadRequest(str(e))
            if p == '/api/join/discover':
                if self.ip not in LOCAL_IPS or app.auth.has_users() or app.node.role != 'unconfigured':
                    raise Forbidden('Only on a new, not yet set up PC, on the PC itself.')
                return self.send(200, {'found': app.sync.discover()})
            if p == '/api/join/cancel':
                if self.ip not in LOCAL_IPS or app.node.role != 'unconfigured':
                    raise Forbidden('Not possible.')
                app.journal.set_meta('join', None)
                return self.send(200, {'ok': True})
            if p == '/api/node/moved':
                if self.ip not in LOCAL_IPS or not app.node.moved:
                    raise Forbidden('Only on this PC itself.')
                choice = self.json_body().get('choice')
                if choice == 'same':
                    app.node.confirm_same_machine()
                    app.auth.log('This PC', self.ip, 'node-confirmed', app.node.name, 'Confirmed on this PC: same computer as before')
                    app.sync.kick()
                    return self.send(200, {'ok': True})
                if choice == 'new':
                    with open(os.path.join(app.node.dir, 'RESET_REQUESTED'), 'w') as f:
                        f.write(now())
                    return self.send(200, {'ok': True, 'restart': True})
                raise BadRequest('Choose same or new')
            if p == '/api/auth/setup':
                if self.ip not in LOCAL_IPS:
                    raise Forbidden('The first administrator account can only be created on the PC with the program itself.')
                d = self.json_body()
                app.auth.setup(d.get('username'), d.get('full_name'), d.get('password'), self.ip)
                token, self.u = app.auth.login(d.get('username'), d.get('password'), self.ip, self.headers.get('User-Agent', ''))
                app.say(f'Administrator account created: {self.u["display"]}')
                return self.send(200, self.me(), headers=self.set_session(token))
            if p == '/api/auth/logout':
                u = app.auth.session(self.token, self.ip, touch=False)
                app.auth.logout(self.token, u, self.ip)
                return self.send(200, {'ok': True}, headers=self.clear_session())

            # ---------------- logged in
            self.login_required()
            if p == '/api/auth/password':
                d = self.json_body()
                app.auth.change_password(self.u, d.get('old'), d.get('new'), self.ip, self.token)
                self.u = app.auth.get(self.u['id'])
                return self.send(200, self.me())
            if p == '/api/log':
                d = self.json_body()
                events = [{**e, 'user': self.user} for e in (d.get('events') or []) if isinstance(e, dict)]
                app.store.log_activity(self.user, self.ip, events)
                return self.send(200, {'ok': True})
            if self.u['must_change']:
                raise Forbidden('Please change your temporary password first.')
            if app.node.moved:
                raise Forbidden('This PC needs a decision first: its data folder seems to come from another PC. Open the program on this PC itself.')
            if p == '/api/commit':
                d = self.json_body()
                label = str(d.get('label') or 'Change')[:200]
                force = bool(d.get('force'))
                ops = d.get('ops')
                if not isinstance(ops, list):
                    raise BadRequest('Nothing to save')
                if force:
                    self.need('data.import')
                    app.backups.create('pre-import')
                if any(isinstance(o, dict) and 'resolve' in o for o in ops):
                    raise Forbidden('Conflicts are decided only in Devices & Sync by an administrator.')
                app.keep_hidden_fields(self.u, ops)
                res = app.store.commit(self.user, self.ip, label, ops, force, guard=app.commit_guard(self.u), user_id=self.u['id'])
                log.info('COMMIT %s (%s) "%s" %s changes', self.user, self.ip, label, res['changes'])
                return self.send(200, res)
            if p == '/api/erase':  # legal erasure (privacy request); administrator PC only
                self.need('privacy.erase')
                self.need_all_data()
                d = self.json_body()
                if d.get('confirm') != 'ERASE':
                    raise BadRequest('Type ERASE to confirm.')
                if not app.auth.verify_current_password(self.u, d.get('password')):
                    app.auth.log(self.user, self.ip, 'erase-refused', str(d.get('entity')), 'Wrong password')
                    raise Forbidden('Enter your own password to confirm.')
                res = app.store.erase(self.user, self.ip, d.get('entity'), str(d.get('id') or ''), d.get('fields'), d.get('reason'),
                                      d.get('basis', ''), d.get('ref', ''), self.u['id'])
                app.auth.log(self.user, self.ip, 'erase-order', f'{d.get("entity")} {d.get("id")}',
                             f'fields: {", ".join(d.get("fields") or [])}; reason: {d.get("reason")}; ref: {d.get("ref", "")}')
                return self.send(200, res)
            if p == '/api/upload':
                self.need('files.upload', 'data.import', 'settings.edit')
                return self.upload(qs.get('name', 'file'))
            if p == '/api/xlsx':
                self.need('export.excel', 'users.manage')
                d = self.json_body()
                data = xlsx.build([(s.get('name', 'Sheet'), s.get('head', []), s.get('rows', [])) for s in d.get('sheets', [])])
                name = ''.join(ch for ch in str(d.get('filename') or 'export') if ch.isalnum() or ch in ' _-.')[:80] or 'export'
                return self.send(200, data, TYPES['.xlsx'], {'Content-Disposition': attachment_header(name + '.xlsx')})
            if p == '/api/backups':
                self.need('backups.manage')
                name = app.backups.create('manual')
                log.info('BACKUP manual by %s: %s', self.user, name)
                app.store.log_activity(self.user, self.ip, [{'type': 'backup', 'action': 'Backup created', 'target': name}])
                return self.send(200, {'name': name})
            if p == '/api/backups/folder':
                self.need('backups.manage')
                if not is_admin(self.u):
                    raise Forbidden('Only an administrator can choose the backup folder.')
                if self.ip not in LOCAL_IPS:
                    raise Forbidden('For safety, choose the backup folder on this PC itself.')
                folder = str(self.json_body().get('path') or '').strip().strip('"')
                self.set_backup_folder(folder)
                app.auth.log(self.u['display'], self.ip, 'backup-folder', folder or '-', 'Second backup folder set' if folder else 'Second backup folder removed')
                name = app.backups.create('manual') if folder else ''
                return self.send(200, {'ok': not app.backups.last_error, 'error': app.backups.last_error, 'name': name})
            if p == '/api/backups/restore':
                self.need('backups.restore')
                d = self.json_body()
                safety, res = app.backups.restore(d.get('name'), self.user, self.ip, self.u['id'])
                app.journal.reapply_erasures()
                app.store.log_activity(self.user, self.ip, [{'type': 'restore', 'action': 'Restored backup', 'target': d.get('name'),
                                                             'detail': f'{res["changes"]} records brought back; safety backup before restore: {safety}'}])
                app.auth.log(self.user, self.ip, 'backup-restored', d.get('name'), f'{res["changes"]} records changed back; safety backup: {safety}')
                app.say(f'Backup {d.get("name")} restored by {self.user} ({self.ip}); {res["changes"]} records; previous data saved as {safety}')
                return self.send(200, {'ok': True, 'safety': safety, 'changes': res['changes']})
            if p == '/api/trash/restore':
                self.need('trash.restore')
                self.need_all_data()
                return self.send(200, app.store.restore_txn(self.user, self.ip, str(self.json_body().get('txn'))))
            if p == '/api/quick-links/set':
                self.need_admin()
                d = self.json_body()
                app.auth.link_set(self.u, self.ip, str(d.get('id')), bool(d.get('on')))
                return self.send(200, {'ok': True})
            if p.startswith('/api/devices/'):
                return self.devices(p[len('/api/devices/'):])
            if p == '/api/conflicts/resolve':
                self.need_admin()
                return self.send(200, self.resolve_conflict(self.json_body()))
            if p in ('/api/profiles/save', '/api/profiles/delete'):
                self.need('users.manage')
                d = self.json_body()
                if p.endswith('save'):
                    return self.send(200, app.auth.save_profile(self.u, self.ip, d))
                app.auth.delete_profile(self.u, self.ip, str(d.get('id') or ''))
                return self.send(200, {'ok': True})
            if p.startswith('/api/users/'):
                self.need('users.manage')
                d = self.json_body()
                action = p[len('/api/users/'):]
                if action == 'save':
                    return self.send(200, app.auth.save_user(self.u, self.ip, d))
                uid = str(d.get('id') or '')
                if action == 'reset':
                    app.auth.reset_password(self.u, self.ip, uid, d.get('password'))
                elif action == 'unlock':
                    app.auth.unlock(self.u, self.ip, uid)
                elif action == 'logout':
                    app.auth.force_logout(self.u, self.ip, uid)
                elif action == 'delete':
                    app.auth.delete_user(self.u, self.ip, uid)
                else:
                    return self.send(404, {'error': 'Not found'})
                return self.send(200, {'ok': True})
            if self.extra_route('POST', p):
                return
            self.send(404, {'error': 'Not found'})

        # ------------------------------------------------------------ devices, conflicts
        def devices(self, action):
            self.need_admin()
            d = self.json_body()
            sync, node, journal = app.sync, app.node, app.journal
            try:
                if action == 'open-join':  # joining without a code is possible only while the administrator has opened it
                    if not node.is_authority:
                        raise Forbidden('Only the administrator PC can allow a new PC to join.')
                    minutes = max(1, min(60, int(d.get('minutes') or 10)))
                    until = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec='seconds')
                    journal.set_meta('open_join_until', until)
                    app.auth.log(self.u['display'], self.ip, 'join-opened', node.name, f'A new PC may join without a code until {until}')
                    return self.send(200, {'until': until})
                if action == 'close-join':
                    journal.set_meta('open_join_until', None)
                    app.auth.log(self.u['display'], self.ip, 'join-closed', node.name, 'Joining without a code was closed')
                    return self.send(200, {'ok': True})
                if action == 'export-key':
                    if not app.auth.verify_current_password(self.u, d.get('password')):
                        app.auth.log(self.user, self.ip, 'authority-export-refused', node.name, 'Wrong password')
                        raise Forbidden('Enter your own password to save the administrator key.')
                    if self.ip not in LOCAL_IPS:
                        raise Forbidden('For safety, save the administrator key on the administrator PC itself.')
                    if not node.is_authority or node.info.get('backup'):
                        raise Forbidden('Only the administrator PC can save the administrator key.')
                    pw = str(d.get('passphrase') or '')
                    if len(pw) < 12:
                        raise BadRequest('The passphrase must have at least 12 characters.')
                    import nodectl
                    box = nodectl.seal(node.authority_seed, pw, {'cluster': node.info.get('cluster_id'), 'authority_pub': node.info.get('authority_pub'),
                                                                 'exported': now(), 'from': node.name})
                    journal.set_meta('key_saved', now())
                    app.auth.log(self.u['display'], self.ip, 'authority-exported', node.name, 'Administrator key saved as a file (passphrase protected)')
                    return self.send(200, box, headers={'Content-Disposition': 'attachment; filename="administrator-key.json"'})
                if action == 'invite':
                    return self.send(200, sync.create_invite(self.user))
                if action == 'decide':
                    sync.decide(str(d.get('id')), bool(d.get('approve')), self.u)
                elif action == 'update':
                    sync.update_node(str(d.get('id')), self.u, name=d.get('name'), address=d.get('address'))
                elif action == 'revoke':
                    sync.update_node(str(d.get('id')), self.u, revoke=True)
                elif action == 'backup':
                    sync.set_backup(str(d.get('id')), self.u, bool(d.get('on')))
                elif action == 'sync-now':
                    for st in sync.status.values():
                        st['fails'] = 0
                    sync.kick()
                elif action == 'verify':
                    rep = journal.verify(all_signatures=bool(d.get('all')))
                    app.auth.log(self.user, self.ip, 'integrity-check', 'history', 'OK' if rep['ok'] else f'{rep["problemCount"]} problem(s)')
                    return self.send(200, rep)
                elif action == 'ack':
                    journal.ack_alert(str(d.get('key')))
                else:
                    return self.send(404, {'error': 'Not found'})
            except PermissionError as e:
                raise Forbidden(str(e))
            except ValueError as e:
                raise BadRequest(str(e))
            return self.send(200, {'ok': True})

        def conflict_list(self):
            out = app.store.conflicts()
            who = {}
            for c in out:
                if c['kind'] == 'conflict':
                    for fld, entries in c['detail'].items():
                        for e in entries:
                            k = (e['origin'], e['cseq'])
                            if k not in who:
                                who[k] = app.journal.describe(*k)
                            e['by'] = who[k]
                elif c['kind'] == 'deleted-edit':
                    c['delete_by'] = app.journal.describe(*c['detail']['delete'])
                    c['edits_by'] = [app.journal.describe(*x) for x in c['detail']['edits'][:10]]
            return out

        def resolve_conflict(self, d):
            entity, rid, action = d.get('entity'), str(d.get('id') or ''), d.get('action')
            if entity not in ENTITIES:
                raise BadRequest('Unknown record type')
            row = app.store.get(entity, rid, include_deleted=True)
            if not row:
                raise BadRequest('Record not found')
            ver = row.pop('ver')
            if action == 'value':
                field = d.get('field')
                if field not in {js for js, _, _, _ in ENTITIES[entity][2]}:
                    raise BadRequest('Unknown field')
                row[field] = d.get('value')
                op = {'e': entity, 'id': rid, 'op': 'put', 'row': row, 'ver': ver, 'resolve': [field]}
                label = f'Conflict resolved: {field}'
            elif action == 'keep-deleted':
                op = {'e': entity, 'id': rid, 'op': 'del', 'resolve': True}
                label = 'Conflict resolved: keep deleted'
            elif action == 'restore':
                op = {'e': entity, 'id': rid, 'op': 'put', 'row': row}
                label = 'Conflict resolved: record restored'
            else:
                raise BadRequest('Unknown action')
            res = app.store.commit(self.user, self.ip, label, [op], force=action != 'value', user_id=self.u['id'])
            app.auth.log(self.user, self.ip, 'conflict-resolved', f'{entity} {rid}', label)
            return res

        def set_backup_folder(self, folder):
            """Choose (or with '' remove) the second backup folder of this PC. Stored in config.json of this PC only."""
            if folder:
                folder = os.path.normpath(folder)
                if backup_mod.network_folder(folder):
                    raise BadRequest('Choose a USB drive or another disk of this PC, not a network folder (the backups contain personal data).')
                if not os.path.isabs(folder):
                    raise BadRequest('Type the full folder, for example E:\\Backups.')
                inside = [os.path.normcase(os.path.realpath(x)) for x in (app.home, app.data_dir, app.backups.dir)]
                f = os.path.normcase(os.path.realpath(folder))
                if any(f == x or f.startswith(x + os.sep) for x in inside):
                    raise BadRequest('Choose a folder on another disk or a USB drive, not inside the program data.')
                try:
                    os.makedirs(folder, exist_ok=True)
                    test = os.path.join(folder, '.write-test')
                    with open(test, 'w') as fh:
                        fh.write('ok')
                    os.remove(test)
                except OSError:
                    raise BadRequest('This folder cannot be used (not found or no permission to write). Check the drive and try again.')
            dirs = ([folder] if folder else []) + [x for x in app.cfg.get('extra_backup_dirs', [])[1:] if x]
            try:
                cfg = {}
                if os.path.exists(app.config_path):
                    with open(app.config_path, encoding='utf-8') as fh:
                        cfg = json.load(fh)
                cfg['extra_backup_dirs'] = dirs
                tmp = app.config_path + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as fh:
                    json.dump(cfg, fh, indent=2)
                os.replace(tmp, app.config_path)
            except (OSError, ValueError):
                raise BadRequest('The setting could not be saved (config.json is damaged or cannot be written).')
            app.cfg['extra_backup_dirs'] = dirs
            app.backups.extra = [app.resolve(x) for x in dirs]
            app.backups.last_error = ''

        # ------------------------------------------------------------ links, files, static
        def link_page(self, token):
            """Opening a personal link shows a tiny page that logs in by itself (js/quick.js). Logging in only happens with the
            POST from this page, so a program that merely looks at the link (a chat preview, a virus scanner) logs nobody in."""
            u = app.auth.link_user(token)
            ok = u and u['active'] and app.auth.link_allowed(u)
            title = app.about().get('brand.name') or PRODUCT
            now_in = app.auth.session(self.token, self.ip, touch=False) if ok and self.token else None
            if now_in and now_in['id'] == u['id']:
                return self.send(303, b'', 'text/plain', {'Location': '/'})
            if ok:
                form = (f'<form id="{"ask" if now_in else "go"}" method="post" action="/k/{html.escape(token)}">'
                        f'<button type="submit">{"Continue as " + html.escape(u["full_name"]) if now_in else "Open"}</button></form>')
                if now_in:
                    body = (f'<h1>Personal link of {html.escape(u["full_name"])}</h1><p>This browser is logged in as '
                            f'<b>{html.escape(now_in["full_name"])}</b>. Continuing logs {html.escape(now_in["full_name"])} out.</p>' + form)
                else:
                    body = (f'<h1>Welcome, {html.escape(u["full_name"])}</h1><p>Opening for you…</p>' + form +
                            '<p class="small">This is your personal link. Do not give it to anybody - whoever has it works under your name.</p>'
                            '<script src="/js/quick.js"></script>')
            else:
                body = ('<h1>This link does not work any more</h1><p>Please ask for your new link, '
                        'or <a href="/">log in with your user name and password</a>.</p>')
            page = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>{html.escape(title)}</title><style>body{{font-family:system-ui,Segoe UI,Arial,sans-serif;background:#f4f2ee;color:#1c1b19;'
                    'display:flex;min-height:90vh;align-items:center;justify-content:center;margin:0 16px}main{background:#fff;border-radius:12px;'
                    'padding:28px 32px;max-width:440px;box-shadow:0 4px 18px #0001;text-align:center}h1{font-size:1.35rem}'
                    'button{font-size:1.05rem;padding:10px 26px;border:0;border-radius:8px;background:#1f4e47;color:#fff;cursor:pointer}'
                    '.small{font-size:.85rem;color:#5e5b55;margin-top:18px}</style></head><body><main>' + body + '</main></body></html>')
            return self.send(200 if ok else 404, page, 'text/html; charset=utf-8', {'Cache-Control': 'no-store'})

        def upload(self, name):
            ext = os.path.splitext(name)[1].lower()
            if ext not in UPLOAD_EXT:
                raise BadRequest(f'File type {ext or "(none)"} is not allowed')
            data = self.body(int(app.cfg['max_upload_mb']) * 1048576)
            if not data:
                raise BadRequest('Empty file')
            for magic, exts in MAGIC.items():  # the content must match the extension (no script disguised as a picture)
                if data.startswith(magic) and ext not in exts:
                    raise BadRequest('The file content does not match its type')
            if ext in IMAGE_EXT and not any(data.startswith(m) for m, e in MAGIC.items() if e & IMAGE_EXT) and not data[:12].startswith(b'RIFF'):
                raise BadRequest('The file content does not match its type')
            sha = hashlib.sha256(data).hexdigest()
            os.makedirs(os.path.join(app.uploads, 'cas'), exist_ok=True)
            path = os.path.join(app.uploads, 'cas', sha + ext)
            if not os.path.exists(path):
                tmp = os.path.join(app.uploads, 'cas', f'.{sha}.{uuid.uuid4().hex[:8]}.tmp')
                with open(tmp, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            src = f'/files/cas/{sha}{ext}'
            app.store.record_file(src, sha, len(data), mimetypes.guess_type(path)[0] or '', self.user, self.ip, self.u['id'])
            log.info('UPLOAD %s (%s) %s -> %s %d bytes', self.user, self.ip, name, src, len(data))
            self.send(200, {'src': src, 'size': len(data)})

        def serve_static(self, rel):
            rel = unquote(rel).replace('\\', '/')
            parts = rel.split('/')
            ext = os.path.splitext(rel)[1].lower()
            if (any(x in ('', '.', '..') or ':' in x for x in parts) or ext not in STATIC_EXT
                    or not (rel == 'index.html' or len(parts) > 1 and parts[0] in ('css', 'js', 'lib', 'fonts'))):
                return self.send(404, {'error': 'File not found'})
            if app.assets is not None:
                data = app.assets.get(rel)
            else:
                path = os.path.join(app.root, 'web', *parts)
                data = None
                if os.path.isfile(path):
                    with open(path, 'rb') as f:
                        data = f.read()
            if data is None:
                return self.send(404, {'error': 'File not found'})
            return self.send(200, data, TYPES.get(ext) or mimetypes.guess_type(rel)[0] or 'application/octet-stream', {'Cache-Control': 'no-cache'})

        def serve_file(self, base, rel, src=None):
            base = os.path.realpath(base)
            path = os.path.realpath(os.path.join(base, unquote(rel)))
            if not path.startswith(base + os.sep) or not os.path.isfile(path):
                if src and app.store.file_info(unquote(src)):  # known file that has not been copied from another PC yet - never cached
                    if os.path.splitext(path)[1].lower() in IMAGE_EXT:
                        return self.send(200, PLACEHOLDER, 'image/svg+xml', {'Cache-Control': 'no-store'})
                    return self.send(404, {'error': 'This file is still being copied from another PC. Try again in a minute.'})
                return self.send(404, {'error': 'File not found'})
            ext = os.path.splitext(path)[1].lower()
            if ext not in UPLOAD_EXT:
                return self.send(404, {'error': 'File not found'})
            headers = {'Cache-Control': 'private, max-age=31536000, immutable'}
            if ext not in INLINE_EXT:
                headers['Content-Disposition'] = 'attachment'
            with open(path, 'rb') as f:
                self.send(200, f.read(), TYPES.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream', headers)

    return Handler


def run(app, background=False, open_browser=None):
    """Starts the servers and blocks until stopped. Returns immediately when another copy already runs on this data folder."""
    import webbrowser
    port = int(app.cfg['port'])
    if not app.instance:
        print('The program is already running on this PC. Opening it in the browser.')
        if not background:
            webbrowser.open(f'http://localhost:{port}/')
        return
    try:
        httpd = Server((app.cfg['host'], port), make_handler(app))
    except OSError:
        print(f'Port {port} is already in use - the program is probably already running. Opening it in the browser.')
        if not background:
            webbrowser.open(f'http://localhost:{port}/')
        return
    try:
        if app.auth.has_users():
            app.backups.create('startup')
    except Exception as e:  # noqa: BLE001
        app.say('Startup backup failed: ' + str(e))
    app.backups.start()
    app.sync.start()
    print('=' * 64)
    print(f' {PRODUCT} is running')
    print(f' This PC:        http://localhost:{port}/')
    for u in lan_urls(port):
        print(f' Other PCs:      {u}')
    print(f' This PC:        "{app.node.name}" ({app.node.role}, id {app.node.id}), sync port {app.sync.port}')
    print(f' Data folder:    {app.data_dir}')
    if not app.auth.has_users():
        print(f' FIRST START: open http://localhost:{port}/ on THIS PC to create the administrator account.')
    print(f' Version {VERSION} - {COPYRIGHT}')
    print(' Keep this window open. Close it to stop the program.')
    print('=' * 64, flush=True)
    app.say('Server started')
    if (app.cfg.get('open_browser', True) if open_browser is None else open_browser) and not background:
        threading.Timer(0.8, lambda: webbrowser.open(f'http://localhost:{port}/')).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.sync.shutdown()
        app.journal.flush_activity()
        app.say('Server stopped')

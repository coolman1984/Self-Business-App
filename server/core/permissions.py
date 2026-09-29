"""Permission registry. The core knows only the permissions that belong to the engine itself (users, backups, logs,
privacy, sensitive data, money visibility); the platform and every module register their own groups and the ready-made
profiles. Lists are mutated in place so `from permissions import ALL` always sees the registered permissions.
"""
ADMIN_GROUP = 'Administrator rights - only for administrators'
LOCKED_PROFILE = 'administrator'  # always has every right, so there is always a way to manage the system

PERMISSIONS = []      # [(group title, [(permission, label)])] in the order shown on the users screen
ALL = []              # every permission
ADMIN_PERMS = set()   # permissions that a personal link / portal link can never carry
WORK = []             # every permission that is not an administrator right
_PROFILES = []        # (id, name, perms list or callable returning a list)


def register_group(title, perms, admin=False):
    """perms: [(permission, label)]. admin=True puts them in the administrator group (never on a link)."""
    for group, ps in PERMISSIONS:
        if group == (ADMIN_GROUP if admin else title):
            ps.extend(x for x in perms if x[0] not in {p for p, _ in ps})
            break
    else:
        PERMISSIONS.append((ADMIN_GROUP if admin else title, list(perms)))
    _refresh()


def register_profile(pid, name, perms):
    """A ready-made profile. perms may be a callable (evaluated lazily) so it can refer to permissions registered later."""
    for i, (p, _, _) in enumerate(_PROFILES):
        if p == pid:
            _PROFILES[i] = (pid, name, perms)
            return
    _PROFILES.append((pid, name, perms))


def builtin_profiles():
    out = []
    for pid, name, perms in _PROFILES:
        out.append((pid, name, list(perms() if callable(perms) else perms)))
    return out


def _refresh():
    ALL[:] = [p for _, ps in PERMISSIONS for p, _ in ps]
    ADMIN_PERMS.clear()
    ADMIN_PERMS.update(p for g, ps in PERMISSIONS if g == ADMIN_GROUP for p, _ in ps)
    WORK[:] = [p for p in ALL if p not in ADMIN_PERMS]


# ---- engine permissions ----
register_group('Data', [
    ('data.sensitive', 'See sensitive information (national id, product keys, private notes)'),
    ('money.view', 'See amounts, prices and money reports'),
    ('export.excel', 'Export lists to Excel'),
    ('print', 'Print lists and reports / save as PDF'),
])
register_group('Settings & Backups', [
    ('logs.view', 'Data changes log (who changed what)'),
    ('settings.view', 'Settings page and server information'),
    ('settings.edit', 'Change general settings (name, logo, numbering, currency)'),
    ('backups.manage', 'See and create backups'),
    ('trash.restore', 'Recycle Bin: see and restore deleted records'),
])
register_group('', [
    ('users.manage', 'Manage people, links, profiles and permissions'),
    ('logs.activity', 'See what each person did and clicked (activity log)'),
    ('logs.security', 'See logins and the security log'),
    ('backups.restore', 'Restore a backup'),
    ('data.import', 'Import data, load or delete demo data'),
    ('privacy.erase', 'Legal erasure of personal data (privacy requests)'),
], admin=True)
register_profile('administrator', 'Administrator', lambda: list(ALL))

"""Finding people and companies that are probably the same one (never automatic: a person decides).

Keys: the normalised phone (E.164, Egypt by default), the lower-cased e-mail, and the Arabic-folded name (hamza, teh marbuta,
diacritics and digits ignored, word order ignored). A phone or e-mail match is strong; a name match alone is only "maybe"."""
import query as query_mod
from textnorm import norm_email, norm_phone, norm_text


def name_key(name):
    return ' '.join(sorted(norm_text(name).split()))


def keys_of(p, country='20'):
    phones = [x for x in (norm_phone(p.get('phone'), country), norm_phone(p.get('phone2'), country)) if x]
    mail = norm_email(p.get('email'))
    return phones, ([mail] if mail else []), name_key(p.get('name'))


class Index:
    """All live people/companies (not merged away), looked up by phone, e-mail and name."""

    def __init__(self, country='20'):
        self.country = country
        self.phone, self.email, self.name, self.rows = {}, {}, {}, {}

    @classmethod
    def load(cls, app, access, country='20'):
        idx = cls(country)
        cursor = None
        while True:
            page = query_mod.run(app.store, 'parties', access, [('status', 'ne', 'merged')], limit=500, cursor=cursor)
            for r in page['rows']:
                idx.add(r)
            cursor = page['next']
            if not cursor:
                return idx

    def add(self, p):
        phones, mails, nk = keys_of(p, self.country)
        self.rows[p['id']] = p
        for k in phones:
            self.phone.setdefault(k, []).append(p['id'])
        for k in mails:
            self.email.setdefault(k, []).append(p['id'])
        if nk:
            self.name.setdefault(nk, []).append(p['id'])

    def find(self, p, exclude=None):
        """[(id, strength, why)] strongest first. strength: 'same' (phone / e-mail) or 'maybe' (only the name)."""
        phones, mails, nk = keys_of(p, self.country)
        hits = {}
        for k in phones:
            for i in self.phone.get(k, []):
                hits.setdefault(i, ('same', 'phone'))
        for k in mails:
            for i in self.email.get(k, []):
                hits.setdefault(i, ('same', 'email'))
        for i in self.name.get(nk, []) if nk else []:
            hits.setdefault(i, ('maybe', 'name'))
        return [(i, s, w) for i, (s, w) in sorted(hits.items(), key=lambda kv: kv[1][0] != 'same') if i != exclude]


def groups(idx):
    """Every set of records that look like the same one (for the "possible duplicates" screen). Union of phone / e-mail / name matches."""
    parent = {i: i for i in idx.rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for table in (idx.phone, idx.email, idx.name):
        for ids in table.values():
            for other in ids[1:]:
                a, b = find(ids[0]), find(other)
                if a != b:
                    parent[a] = b
    members = {}
    for i in idx.rows:
        members.setdefault(find(i), []).append(i)
    res = []
    for ids in members.values():
        if len(ids) < 2:
            continue
        inside = set(ids)
        kinds = set()
        for kind, table in (('phone', idx.phone), ('email', idx.email), ('name', idx.name)):
            if any(len(inside & set(v)) > 1 for v in table.values()):
                kinds.add(kind)
        res.append({'ids': sorted(ids), 'why': sorted(kinds), 'strong': bool(kinds & {'phone', 'email'})})     # sorted: the same answer on every PC
    res.sort(key=lambda g: (not g['strong'], -len(g['ids']), g['ids'][0]))
    return res

"""Entity registry: the only place where the engine learns what kinds of records exist.

The core (store, replica, journal, sync) knows no business words. The platform and every activity module register their
entities here; the engine reads the registry to create tables, plan changes, fold changesets and export data.

An entity is: a table, a list of fields (js key, column, kind, label), merge rules for concurrent changes
(counters, resolvers), an optional data scope (which scope id a record belongs to, for per-scope permissions and the
change log), optional duplicate detection and the fields that hold uploaded-file references.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

T, I, R, B, J = 'text', 'int', 'real', 'bool', 'json'

# name -> (table, title, [(js key, column, kind, label)])   (same shape as BAMS, kept for the engine's loops)
ENTITIES = {}
COUNTERS = {}
RESOLVERS = {}
SPECS = {}      # name -> {'table', 'fields': [(js, col, kind)], 'counters', 'resolvers'}   (what the fold needs)
REPLICATED = set()
META = {}       # name -> Entity


@dataclass
class Entity:
    name: str
    table: str
    title: str
    fields: list                                  # [(js key, column, kind, label)]
    counters: set = field(default_factory=set)    # fields merged as deltas (quantities)
    resolvers: dict = field(default_factory=dict)  # field -> 'lww' | 'max' | 'min' | 'rank:a,b,c' | 'follow:<leader field>'
    scope_field: Optional[str] = None             # js key of a field holding the scope id of the record
    scope_self: bool = False                      # the record's own id is its scope (the scope "root" entity)
    scope_via: Optional[tuple] = None             # (fk js key, parent entity name): the scope of the parent record
    dup_keys: Optional[list] = None               # js keys; two live records with equal values are a possible duplicate
    file_fields: tuple = ()                       # js keys holding '/files/...' references
    search: tuple = ()                            # js keys whose text is searchable (global search, command palette)
    phone_fields: tuple = ()                      # searchable as phone numbers (normalised to +20...)
    email_fields: tuple = ()
    subtitle_fields: tuple = ()                   # shown under the title in search results
    money_fields: tuple = ()                      # hidden from users without the permission money.view
    sensitive_fields: tuple = ()                  # hidden from users without the permission data.sensitive
    immutable: bool = False                       # write-once record (issued documents): the earliest write wins, edits are refused
    validate: Optional[Callable] = None           # fn(row) raising store.BadRequest with a plain-words message
    perm_prefix: Optional[str] = None             # 'clients' -> clients.view / .create / .edit / .delete
    perms: dict = field(default_factory=dict)     # explicit {'view'|'insert'|'update'|'delete': (permission, ...)}; any one is enough
    index: tuple = ()                             # extra columns to index
    name_fields: tuple = ('name', 'title', 'caption')  # what to call a record in messages

    def perms_for(self, op):
        """The permissions (any one is enough) for 'view', 'insert', 'update' or 'delete'. Empty = nobody may."""
        if self.perms.get(op):
            return tuple(self.perms[op])
        if self.perm_prefix:
            return (self.perm_prefix + {'view': '.view', 'insert': '.create', 'update': '.edit', 'delete': '.delete'}[op],)
        return ()

    def columns(self):
        return [col for _, col, _, _ in self.fields]


def register(entity):
    """Adds (or replaces, when a module is upgraded in a test) an entity. Safe to call more than once."""
    ENTITIES[entity.name] = (entity.table, entity.title, list(entity.fields))
    COUNTERS[entity.name] = set(entity.counters)
    RESOLVERS[entity.name] = dict(entity.resolvers)
    SPECS[entity.name] = {'table': entity.table, 'fields': [(js, col, kind) for js, col, kind, _ in entity.fields],
                          'counters': COUNTERS[entity.name], 'resolvers': RESOLVERS[entity.name], 'immutable': entity.immutable}
    REPLICATED.add(entity.name)
    META[entity.name] = entity
    return entity


def scope_of(entity, row, lookup):
    """The scope id of a record (or None). lookup(entity, id) -> row dict of a parent record, for scope_via."""
    meta = META.get(entity)
    if meta is None:
        return None
    if meta.scope_self:
        return row.get('id')
    if meta.scope_field:
        return row.get(meta.scope_field)
    if meta.scope_via:
        fk, parent = meta.scope_via
        parent_row = lookup(parent, row.get(fk))
        return scope_of(parent, parent_row, lookup) if parent_row else None
    return None

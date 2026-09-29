---
name: self-business-dev
description: Project knowledge for Self Business OS (working name) - layers, BAMS engine harvest rules, money and sync invariants, i18n/RTL, how to test and verify the UI, and the pitfalls learned so far. Load it before changing anything in this repository, and update it whenever something new is learned.
---

# Self Business OS — how to change it safely

Read `CLAUDE.md` (rules) and `AGENT_HANDOFF.md` first. Designs live in `docs/`. Update this file whenever you learn
a new rule, pitfall, file or command.

## Layers (a test enforces them from Phase 1)
`core` (domain-free engine from BAMS) → `platform` (shared business kernel) → `modules/*` (activities) ;
`connectors/*` only through ports; `web/*` never decides permissions.

## Invariants
- Business state = deterministic fold of the journal; same on every PC. Record ids random.
- Journal envelope v2: signature covers `ops_hash`; ops can be redacted only by an admin-signed erase order.
- New replicated field/entity → additive migration + raise the schema number (older PCs wait instead of dropping).
- Money: integer minor units + currency; issued documents frozen (`lock-after`); payments/allocations append-only.
- Numbers assigned at issue from the PC's series; drafts have no number.
- Automations run only on the runner PC; created ids are deterministic; external effects via the outbox.
- Derived data (`index.db`: search, timeline, attention, report cache) is never replicated; always rebuildable.
- Every shareable record has `visibility`; internal notes are separate; one serializer decides what a client sees.
- Server checks permission + scope + money visibility on every route.
- Disabling a module never deletes its data.

## Commands
```
python3 -m unittest discover -s tests
# reference repos (read-only): see AGENT_HANDOFF.md §3
# Playwright: Chromium is pre-installed (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers); never run `playwright install`
```

## Where things are (Phase 1)
`server/core/` engine (see `PROVENANCE.md`) · `server/app.py` dev entry, `server/sbo_main.py` installed entry · `web/` pages ·
`tests/engine_domain.py` test-only domain (never shipped; sets a fast KDF for tests) · `tools/`, `installer/`, `.github/workflows/build.yml`.
Tests: `cd tests && python3 -m unittest test_unit test_convergence test_erase test_resolvers test_auth test_query test_search test_layers`
(fast, ~1 min) and `test_multinode` (real processes, ~2 min; do not edit `server/` while it runs).

## Pitfalls learned (add new ones here)
- After renaming a prefix, grep for numeric slices of the renamed strings (`name[4:]`); use a constant.
- Hand-built wire records in tests must use `journal.env_chash` / `signed_view` (envelope v2).
- Mutation-check security tests: disable the protection in a copy and confirm the tests fail.
- Register domains before opening the store: `bootstrap.register_domains()`; tests set `SBO_ENTITY_MODULES=engine_domain`.
- `hashlib.scrypt` N=2^17 needs ~135 MB: pass `maxmem`; tests lower `auth.KDF_N` only through `engine_domain`.
- FTS5 plain tables are cleared with `DELETE FROM fts` (`delete-all` is for external-content tables only).
- BAMS upgrade tests need full git history; in a shallow clone 2 tests fail for that reason only.
- `sqlite.org` is blocked by the session network policy — cite docs from memory/BAMS notes and say so.
- Arabic search needs normalisation (أ/إ/آ→ا, ة→ه, ى→ي, remove tashkeel and tatweel, Arabic-Indic digits → 0-9).
- FTS5 with `unicode61 remove_diacritics 2` works on Arabic in SQLite 3.45 (checked) but does not unify hamza forms.
- scrypt N=2^17 costs ~0.8 s here; measure on the reference old laptop before fixing parameters.
- From BAMS: `<a data-act>` needs `data-href` — use `<button>` for in-page actions; top-level names in classic
  scripts clash (we use ES modules); `pkill -f` matches your own shell; record ids never `length+1`.

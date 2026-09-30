---
name: self-business-dev
description: Project knowledge for Self Business OS (working name) - layers, BAMS engine harvest rules, money and sync invariants, i18n/RTL, how to test and verify the UI, and the pitfalls learned so far. Load it before changing anything in this repository, and update it whenever something new is learned.
---

# Self Business OS — how to change it safely

Read `CLAUDE.md` (rules) and `AGENT_HANDOFF.md` first. Designs live in `docs/`. Update this file whenever you learn
a new rule, pitfall, file or command.

## Layers (a test enforces them from Phase 1)
`core` (domain-free engine from BAMS) → `server/business/` (shared business kernel; NOT named `platform`) → `modules/*` (activities) ;
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

## Where things are (Phases 2-3)
`web/css/{tokens,base,components,shell}.css` design system · `web/js/core/` (api, dom, domain, format, prefs, router, session, textnorm) · `web/js/ui/` (kit, form, overlay,
palette, keys, quick, tour, timeline, icons) · `web/js/shell/shell.js` · `web/js/views/*` one file per screen (`dialogs.js` holds every create/edit form) · `web/js/i18n/{ar,en}.js`
(one key per line, single quotes — a test parses them) · `server/business/` (entities, perms, api, today, timeline, importer, dedupe, demo, constants) · `server/core/tablefile.py`
(xlsx/csv reader) · `server/core/launcher.py` (app window).
Tests: add `test_tokens test_i18n test_launcher test_business test_business_sync` to the fast list; browser tests need Playwright:
`SBO_PWLIB=/tmp/claude-0/pwlib python3 -m unittest test_js_units test_ui test_ui_business` (CI sets `SBO_REQUIRE_UI=1`).
Visual matrix: `SBO_PWLIB=... python3 tests/visual/matrix.py [--quick]` → `tests/visual/out/` (look at the pictures!).

## Rules learned in Phases 2-3
- A record is saved as a **whole** `put` with the `ver` you read; a missing field means "cleared". Screens build the row from the current record (`domain.updateRecord`).
- New user-visible word → `t('key')` in BOTH dictionaries; groups built dynamically (`t('stage.' + id)`) are checked against `server/business/constants.py`.
- New server rule → `bad('code', 'English')`; add `err.code` to both dictionaries (a test compares).
- Screens register themselves: `registerNav`, `route`, `registerQuickAdd`, `registerCommand`, `registerTodayBlock` (no central list to edit).
- Icons drawn for LTR; directional ones mirror by CSS. Use `arrow-right` / `chevron-right` for "forward".
- `[data-theme]` selectors (not `:root[...]`) so swatches can preview a theme.
- Playwright `wait_for_function` with an element-returning string trips the CSP (`unsafe-eval` refused): wait for a selector instead.
- Passwords must not contain the user name or the full name (server rule) — remember it in tests.
- Search: index both a word and its form without the article "ال" (`search._with_bare_words`), because people type both.
- Registry entities registered by one test file must be removed again (`test_business_sync.tearDownModule`) or later files in the same process see them.

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

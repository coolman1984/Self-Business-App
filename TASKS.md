# Tasks — where to continue

Legend: `[ ]` open · `[~]` in progress · `[x]` done · `(Q#)` waits for an owner answer (default used if unanswered).
Phases: `docs/ROADMAP.md`. Rules: `CLAUDE.md`. Handoff: `AGENT_HANDOFF.md`.

Owner decisions (2026-09-29): "agreed to my choices" → defaults of `docs/OWNER_BRIEF_AR.md` §ك apply (private repository
recommended — **the repository is still public: the owner must change its visibility in GitHub settings**; `cryptography`
allowed later; annual licence per activity; freelancer module first).

## Phase 0 — research & plan — DONE
- [x] BAMS + Trip Orders studied, market/licence/technology research, all design documents, rules, skill, handoff.

## Phase 1 — core engine (in progress)
- [x] 1.1 Harvest the BAMS engine into `server/core/` with `PROVENANCE.md`; prefixes renamed
- [x] 1.2 Port the engine tests on a test-only domain (`tests/engine_domain.py`): unit, convergence green
- [x] 1.3 Entity registry (`registry.py`); store/journal generic; scopes instead of areas; `state()` removed
- [x] 1.4 Journal envelope v2 (`ops_hash`, operations beside the signed body)
- [x] 1.5 Erase orders: rows, history, audit, registers, late changes, new PCs, restores, re-entry (`tests/test_erase.py`, mutation-checked)
- [x] 1.6 Resolver `min` and write-once entities (`tests/test_resolvers.py`) — replaces the planned `lock-after`
- [x] 1.7 Query API: filters, sort, cursor pagination, data scopes, money/sensitive masking (`query.py`, `tests/test_query.py`)
- [x] 1.8 Permission registry, data scopes on users, scrypt hashes + PBKDF2 compatibility (`tests/test_auth.py`)
- [x] 1.9 Derived search index, Arabic + phone normalisers (`search.py`, `textnorm.py`, `tests/test_search.py`)
- [x] 1.10 Backup: restore skips erased fields, erasures re-applied after restore (`test_erase`); multi-process backup scenarios green
- [x] 1.11 Router (`httpd.py`, `app.py`, `sbo_main.py`): multi-process suite 35/35 scenarios green (the BAMS v1-upgrade scenario was removed)
- [x] 1.12 Layer test (`test_layers.py`) and secrets-in-logs + upload-content tests (`test_secrets_in_logs.py`)
- [x] 1.13 CI + Windows walking skeleton: **first GitHub run green** — Linux tests, then on Windows Nuitka build + Inno Setup installer + the built SBO.exe started and served its pages (run 36617210947). Still to check by hand on a real PC: installing over an existing install, the data-folder permissions (icacls, see 1.17)
- [x] 1.14 Reviews: (a) author's adversarial pass — 6 findings fixed (signed per-value commitments against relay tampering, exact erase matching, KDF limits, probing through hidden fields, restore of issued documents, installer language file); (b) external review of PR #1 — 15 findings + 8 minor, all fixed with regression tests in `tests/test_review_fixes.py`, `test_erase.py`, `test_multinode.py` (open join closed unless the administrator opens a window; erase also scrubs backups, journal copies and audit files and no longer makes a pre-erase backup; blanks need an erase order; audit log masked; key export asks for the password; fail-closed scopes; DESC paging with NULLs; Arabic download names; numeric `max`; bad addresses; attachment type conflicts; password policy without composition rules; exact whole-number money; BMP uploads)
- [ ] 1.15 Remove remaining dead BAMS code (legacy `pw_pub` publish path in `auth.login`)
- [ ] 1.16 Benchmark scrypt on an old laptop; decide the final parameters (ADR-020)
- [ ] 1.17 Installer data-folder permissions: `icacls` grants Administrators, SYSTEM and `{username}` (the account that runs Setup). If Setup is elevated with a different administrator account, the everyday user would lose access — verify on a real PC and switch to granting the original user
- [ ] 1.18 Minor review notes not yet done: `reapply_erasures` scans the journal once per erased record at every start (add a marker); `Store.fingerprint()` holds the store lock while hashing; `web/index.html` has a hard-coded English placeholder (Phase 2 i18n); dead constants `journal.ADMIN_ENTITIES`, duplicate schema numbers in `sync`/`journal`

## Phase 2 — design system and shell — DONE (review fixes pending in the PR)
- [x] 2.1 Tokens, themes (morning, evening, navy, navy night, high contrast), fonts (IBM Plex Sans, OFL, bundled), Lucide icons; **contrast test** (`test_tokens.py`)
- [x] 2.2 i18n Arabic + English, RTL through logical CSS; test for missing/unused keys, matching placeholders, no English words in Arabic (`test_i18n.py`)
- [x] 2.3 UI kit (buttons, forms, tables, tabs, chips, cards, modal, side panel, toast + undo, menu, skeleton/empty/error states, picker, command palette, shortcuts sheet, offline banner, guided tour)
- [x] 2.4 Shell: grouped sidebar (collapsible, drawer on phones), top bar (search, sync light, theme, language), module-registered navigation, quick-add registry
- [x] 2.5 Login, first-run wizard (business name, activity, look, owner account), settings (look with live preview, business, account, about), help
- [x] 2.6 Edge/Chrome app-window launch (`launcher.py`, `test_launcher.py`)
- [x] 2.7 Real-browser tests (`test_ui.py`, 25) and visual matrix (`tests/visual/matrix.py`, uploaded by CI) — keyboard-only walkthrough, reduced motion, phone drawer, XSS check, offline banner
- [ ] 2.8 Devices/sync screen and joining a second PC from the UI (wizard offers only "new business" for now) — Phase 11 (API exists)
- [ ] 2.9 Team screen (add people, permissions, profiles) — API exists (`/api/users/*`), screen not built yet

## Phase 3 — people, work, timeline, search, Today v1, import (in progress: review + PR)
- [x] 3.1 Entities + permissions + profiles (`server/business/`): parties, roles, relations, opportunities, projects, tasks, appointments, notes, activities, inbox, attachments, services, custom fields, import batches
- [x] 3.2 Clients: list with live Arabic-aware filter, client file (overview, timeline, work, notes, files), duplicate warning while typing, duplicates screen, merge by redirect (and un-merge)
- [x] 3.3 Sales board (drag, or the Move menu for keyboard users), projects with progress, tasks (tick + undo, quick add), calendar (Saturday first), services, inbox
- [x] 3.4 Today v1 (late, follow-ups due, today's schedule, coming days, pipeline, inbox) — server-side, scope and money aware
- [x] 3.5 Timeline from the change log (complete, masked for money/sensitive, includes deleted records and merged duplicates)
- [x] 3.6 Excel/CSV import: preview, column guess (Arabic + English headers), duplicate report (new / same / similar / repeated in file / invalid), fills only empty fields, backup first, undo (`tablefile.py`, `importer.py`)
- [x] 3.7 Demo data (removable in one step, keeps what was edited), extra fields per client/project/opportunity
- [x] 3.8 Multi-PC tests for the business entities (`test_business_sync.py`)
- [ ] 3.9 Independent review (correctness, distributed, security) and fixes
- [ ] 3.10 Quotes/agreements/invoices → Phase 4; contact-point table and price lists are not built (phone/e-mail are fields of the party for now, see DATA_MODEL §3)

## Test map
| Area | File | Status |
|---|---|---|
| engine unit / convergence (ported) | `tests/test_unit.py`, `test_convergence.py` | green (32) |
| legal erasure | `tests/test_erase.py` | green (8) |
| resolvers, write-once | `tests/test_resolvers.py` | green (4) |
| passwords, permission registry | `tests/test_auth.py` | green (6) |
| query API | `tests/test_query.py` | green (10) |
| search, normalisers | `tests/test_search.py` | green (11) |
| layers, secrets, uploads | `tests/test_layers.py`, `test_secrets_in_logs.py` | green (6) |
| several PCs, real processes | `tests/test_multinode.py` | 35 scenarios, green (last full run after the review fixes) |
| design tokens (contrast AA) | `tests/test_tokens.py` | green (2) |
| translations | `tests/test_i18n.py` | green (9) |
| pure browser code under Node | `tests/test_js_units.py` | green (7) |
| app-window launcher | `tests/test_launcher.py` | green (6) |
| interface shell in a real browser | `tests/test_ui.py` | green (25) |
| business layer API (validation, search, scope, money, Today, timeline, duplicates, demo, 2,000-row import) | `tests/test_business.py` | green (24) |
| business screens in a real browser | `tests/test_ui_business.py` | green (24) |
| business entities on several PCs | `tests/test_business_sync.py` | green (8) |
| visual matrix (screenshots, reviewed by eye) | `tests/visual/matrix.py` | run by CI, artefact `visual-matrix` |

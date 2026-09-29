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
- [~] 1.10 Backup: erase replay on restore (done in the router: `reapply_erasures`; restore skips erased fields) — needs a multi-process test
- [~] 1.11 Router rewrite (`httpd.py`, `app.py`): written; multi-process suite ported (27/36 passed on the first run, fixes applied, **re-run pending**)
- [~] 1.12 Layer test + log secret scanner: `tests/test_layers.py` written, **not yet run**; secret scanner test still to write
- [~] 1.13 CI + Windows walking skeleton: `sbo_main.py`, `tools/*`, `installer/sbo.iss`, workflow written, **never built** — first CI run will tell; `T34_InstalledMode` must be rewritten for the new entry point
- [ ] 1.14 Independent review (distributed + security) → fix → regression tests → history
- [ ] 1.15 Remove dead BAMS code (legacy user-key publish path, `T02_Upgrade` scenario, `make_legacy` references)
- [ ] 1.16 Benchmark scrypt on an old laptop; decide the final parameters (ADR-020)

## Test map
| Area | File | Status |
|---|---|---|
| engine unit / convergence (ported) | `tests/test_unit.py`, `test_convergence.py` | green (32) |
| legal erasure | `tests/test_erase.py` | green (8) |
| resolvers, write-once | `tests/test_resolvers.py` | green (4) |
| passwords, permission registry | `tests/test_auth.py` | green (6) |
| query API | `tests/test_query.py` | green (10) |
| search, normalisers | `tests/test_search.py` | green (11) |
| layers | `tests/test_layers.py` | written, not run |
| several PCs, real processes | `tests/test_multinode.py` | 36 scenarios; fixes applied, re-run pending |
| visual matrix | `tests/visual/` | Phase 2 |

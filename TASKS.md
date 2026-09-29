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
- [~] 1.13 CI + Windows walking skeleton: the program compiles with Nuitka on Linux (module layout OK), the compiled binary starts, serves the packed pages, writes its data to SBO_HOME and contains no .py file. **The Windows step (Inno Setup installer) has never run** — the first CI run will tell. A pull request needs a `main` branch, which does not exist yet (see below)
- [x] 1.14 Review pass by the author as adversarial reviewer: 6 findings fixed with regression tests (signed per-value commitments against relay tampering, exact erase matching, KDF limits, probing through hidden fields, restore of issued documents, installer language file). An external independent review (code-review on the pull request) is still to run
- [ ] 1.15 Remove remaining dead BAMS code (legacy `pw_pub` publish path in `auth.login`)
- [ ] 1.16 Benchmark scrypt on an old laptop; decide the final parameters (ADR-020)

**Blocked (2026-09-29):** the remote repository has no `main` branch. Creating it by pushing the first commit was refused by the safety check ("merge without review"); the owner must create `main` (or allow the push), then: open the pull request, let CI run (Windows build included), run the external review, fix, merge.

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
| visual matrix | `tests/visual/` | Phase 2 |

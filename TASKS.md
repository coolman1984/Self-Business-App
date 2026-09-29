# Tasks — where to continue

Legend: `[ ]` open · `[~]` in progress · `[x]` done · `(Q#)` waits for an owner answer (default used if unanswered).
Phases: `docs/ROADMAP.md`. Rules: `CLAUDE.md`. Handoff: `AGENT_HANDOFF.md`.

## Phase 0 — research & plan
- [x] Read BAMS (Mr.Ayman-HR @ 5f5b3ce) fully; run its fast tests (31/33; 2 need full git history)
- [x] Read Trip Orders (Yousef-Transportation @ 1ecc471) docs; note its UI is not built yet
- [x] Market + open-source + technology research (`docs/RESEARCH.md`)
- [x] Product, architecture, data model, design, security, sync, modules, automation, roadmap docs
- [x] Rules (`CLAUDE.md`), project skill, history, ideas, handoff, Arabic owner brief
- [ ] Owner answers the open questions (`docs/OWNER_BRIEF_AR.md` §ك) — defaults below apply meanwhile
- [ ] Owner sends the Yousef UI screenshots (Q3)

## Phase 1 — core engine (next)
- [ ] 1.1 Copy BAMS engine files into `server/core/` with `core/PROVENANCE.md` (source commit, per-file changes); rename prefixes (`BAMS-` → product-neutral `SBO-`), env var `SBO_HOME`
- [ ] 1.2 Port engine tests with a test-only domain (`tests/engine_domain.py`, Trip Orders pattern); make them green before any change
- [ ] 1.3 Registry: `Entity`, `Field`, `Module` manifests; `store` reads specs from the registry; remove `AREA_CHILDREN`/`state()`
- [ ] 1.4 Journal envelope v2 (ops beside envelope, `ops_hash`), verification, receive rules; tests
- [ ] 1.5 Erase orders (admin-signed), redaction in rows/journal/audit/CAS, rebuild index; 3-PC test
- [ ] 1.6 Resolvers `min` and `lock-after`; tests
- [ ] 1.7 Query API (filter, sort, cursor pagination), scopes, money mask serializer; permission matrix tests
- [ ] 1.8 Auth generalisation: permission registry, profiles Owner/Manager/Assistant/Accountant/Support/Viewer, scopes; KDF per ADR-011 (Q2) with PBKDF2 upgrade path + benchmark gate
- [ ] 1.9 Derived `index.db`: FTS5 + Arabic/phone normalisers; rebuild tool; tests (hamza, ta marbuta, alef maqsura, tashkeel, Arabic-Indic digits, +20 phones)
- [ ] 1.10 Backup: erase-order replay on restore; prefix rename; tests
- [ ] 1.11 Router rewrite (small router + route modules), security headers (CSP), BAMS protections kept; tests
- [ ] 1.12 Layer-boundary test (`tests/test_layers.py`), log secret scanner test
- [ ] 1.13 CI: Linux tests; Windows walking-skeleton build (Nuitka + Inno Setup) that starts and serves a page
- [ ] 1.14 Independent review (distributed + security) → fix → regression tests → history

## Test map (grows per phase)
| Area | File | Status |
|---|---|---|
| engine unit/convergence/multi-PC (ported) | `tests/test_unit.py`, `test_convergence.py`, `test_multinode.py` | Phase 1 |
| layers | `tests/test_layers.py` | Phase 1 |
| search normaliser | `tests/test_search.py` | Phase 1 |
| permissions matrix | `tests/test_permissions.py` | Phase 1 |
| erasure | `tests/test_erase.py` | Phase 1 |
| visual matrix | `tests/visual/` | Phase 2 |

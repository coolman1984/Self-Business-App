# Architecture

Status: proposed in Phase 0 (2026-09-29), to be confirmed by the owner. Decisions are ADRs (§6); a changed decision
gets a new ADR that names the old one — never silently edited.

## 1. Shape of the system

```
 ┌──────────────────────────── one PC (every PC of the team runs the same program) ─────────────────────────────┐
 │                                                                                                               │
 │  Window: Edge/Chrome in app mode → http://127.0.0.1:<port>      (other PCs/phones on the LAN: http://<pc>)    │
 │     web/  ES modules, no build step: ui-kit · shell · platform views · module views · i18n (ar/en)            │
 │                                   │ JSON over HTTP (session cookie, CSRF origin check)                        │
 │  server/ (Python 3.12, standard library)                                                                      │
 │   ├─ http        router, auth per request, permission + scope + money-visibility filters                     │
 │   ├─ platform    business kernel: parties · work · money · timeline · today · automation · import · reports  │
 │   ├─ modules     lecturer · freelancer · software  (register entities, pages, perms, reports, templates …)    │
 │   ├─ connectors  ports: messaging · calendar · storage · payments · tax · signature · AI  (adapters later)     │
 │   └─ core        domain-free engine harvested from BAMS:                                                      │
 │        registry · store(commit/plan) · journal (signed, chained) · replica (deterministic fold) · query       │
 │        sync (TLS, pinned) · node (keys) · auth (users, sessions, permissions, profiles) · backup · files(CAS) │
 │        search (FTS5 derived index) · system (start, upgrade, lock) · erase (legal erasure)                   │
 │                                                                                                               │
 │  data/  business.db (rows = fold of journal) · journal.db (source of truth, never restored backwards)         │
 │         auth.db · index.db (derived: search, timeline, attention — rebuildable) · files/cas · logs · node/    │
 └───────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
         ▲ changesets over TLS 1.3 with pinned certificates (LAN, or later via the relay)            ▼
   other PCs of the same business                                   optional internet gateway (later phases):
                                                                    client portal · relay for remote team · messages
```

## 2. Layers and the one rule between them

| Layer | May depend on | Must never |
|---|---|---|
| `core` | stdlib only | know any business word (client, invoice, course…) |
| `platform` | core | know any activity (centre, licence, revision round…) |
| `modules/*` | platform, core | depend on another module (share through platform only) |
| `connectors/*` | core (ports defined in platform) | be called directly by modules — only through a port |
| `web/*` | server API | decide permissions (the server decides; the UI only hides) |

A test (`tests/test_layers.py`) fails when an import crosses these lines.

## 3. What we take from BAMS (Mr.Ayman-HR @ 5f5b3ce, v2.4.0)

The golden rule: **do not rewrite an engine that is proven** (33 fast tests, 36 multi-PC tests, two independent reviews).
We harvest, generalise the few coupled places, and keep a provenance note per file (`core/PROVENANCE.md`).

| BAMS file | Coupling found | Plan |
|---|---|---|
| `ed25519.py`, `tlscert.py` | none | **reuse as-is** (prefix constants renamed) |
| `node.py` (identity, keys, epochs, clone detection, authority key) | none | reuse as-is |
| `replica.py` (multi-value registers, resolvers `max`/`rank`/`follow`, counters, tombstones, flags) | none — spec-driven | reuse; add resolver `min`, and `lock-after:<field>=<value>` flag for issued documents (§5.4) |
| `journal.py` (changesets, HLC, version vectors, receive rules, audit/activity/security views, roster) | `area_id` column in audit; admin entity list | reuse; `area_id` → generic `scope`; **envelope v2**: ops stored beside the envelope, the hash covers `ops_hash` → allows legal erasure (ADR-008) |
| `sync.py` (TLS server, sessions, pull/push, peers, attachments, discovery, open join) | none | reuse; later add relay transport (ADR-013) |
| `store.py` (commit → plan → changeset, optimistic `ver`, trash, restore, conflicts, export) | `ENTITIES` dict, `AREA_CHILDREN`, `state()` sends *everything* to the browser, survey duplicate rule | **generalise**: entities come from the registry; `state()` replaced by the query API (ADR-004); duplicate rules become per-entity specs |
| `auth.py` (PBKDF2, sessions, lockout, profiles, personal links, admin-signed account changes, password proof) | break-area permission list and area restriction | reuse; permissions registered by platform/modules; area restriction → generic **scopes**; hashing per ADR-011 |
| `backup.py` (online backup API, integrity check, second folder, no network folders, compensating restore) | file prefix `bams_` | reuse; add erase-order replay on restore (ADR-008) |
| `system.py`, `nodectl.py`, `bams_main.py` | names | reuse, renamed |
| `app.py` (router + all routes) | heavily domain-coupled | **rewrite** as a small router + route modules; keep its patterns (Origin check, 64 kB pre-auth limit, failed-login limiter, local-only admin actions, static whitelist) |
| `xlsx.py` (writer) | none | reuse; add reader (import) |
| `js/app.js` (2,500 lines, one file, English only, light only) | domain | **not reused** — new UI; keep patterns (`esc` everywhere, idle logout not while typing, activity log) |
| tests `harness.py`, `cluster.py`, `test_convergence.py`, multi-PC tests | partly domain | reuse with a test-only engine domain (as Trip Orders did in `tests/engine_domain.py`) |
| installer (Inno Setup), Nuitka build, release workflow | names | reuse, renamed, in Phase 1 as a *walking skeleton* |
| method: `CLAUDE.md`, skill, history with lessons, `IDEAS.md`, review → fix → regression test | — | reuse |

From **Trip Orders** (Yousef) we reuse *ideas*: the design-token table, light theme with depth, motion table, command
palette + shortcut map, stackable side panels, settings with live preview, slides/tours, the internet "mailbox"
gateway (office PC never reachable from the internet), brand only in config, i18n keys with test for missing keys.

## 4. Runtime and delivery

- Python 3.12 portable runtime, standard library only (one possible exception: ADR-011), SQLite 3.45+.
- Installed program compiled with Nuitka + Inno Setup (BAMS pipeline). Data in `%ProgramData%\<Brand>`; program in
  `Program Files`. Updates never touch data. Code-signing certificate recommended before selling (SmartScreen).
- The window: the program starts its local server and opens Edge (or Chrome) with `--app=http://127.0.0.1:<port>`;
  fallback: the default browser. LAN access stays available for team members and phones (permissions apply).
- Background jobs in the same process: backups, sync workers, automation runner, scheduled attention refresh.

## 5. Key mechanisms

### 5.1 Module registry
Every module (and the platform itself) registers a manifest: entities, fields, permissions, pages, navigation,
reports, attention providers, automation triggers/actions/templates, document templates, settings, tour, help,
demo data, search providers. Disabled module = hidden UI and stopped jobs; **its data and journal stay** and come back
when it is enabled again. Details: `MODULES.md`.

### 5.2 Store and journal (from BAMS)
Save = one SQLite transaction: validate → permission guard → diff to ops → signed changeset → fold → append → commit.
Business state = deterministic fold of the journal, identical on every PC. Soft delete, recycle bin, compensating
restore, audit of every field change (who, when, PC, old, new). Details: `SYNC.md`.

### 5.3 Query API instead of "send everything"
BAMS loads all data into the browser. A business OS accumulates years of invoices and activities, so the server
exposes paginated, filtered, permission-scoped queries (`/api/q/<entity>?filter…&sort…&cursor…`), record views with
related lists, and aggregate endpoints. Target: 50,000 parties / 200,000 documents, any list < 150 ms on an old PC.

### 5.4 Money correctness in a replicated system
- Amounts are integers in minor units (piastres/cents) + currency code; no floats anywhere in money.
- **Issued documents are snapshots**: issuing a quote/invoice writes an immutable snapshot (lines, totals, parties,
  terms, hash). A concurrent draft edit made on another PC before it saw the issue is kept as a flagged conflict,
  never merged into the legal document. Changes after issue = credit note / new version.
- **Payments and allocations are append-only events** (like BAMS "transactions"); balances are computed, never stored
  as editable numbers. Reversal = a new negative event. Possible duplicate payments (same party, amount, day, method)
  are flagged, never auto-deleted.
- **Numbering without conflicts offline**: drafts have no number; a number is assigned at issue from the issuing PC's
  series (`INV-A-0001`, `INV-B-0001` …; series letter per PC). Optional strict single series: only the "numbering PC"
  may issue (others queue "ready to issue"). Owner question Q9.

### 5.5 Derived local index (`index.db`)
Search (FTS5 + Arabic normalisation), timelines, attention items and report caches are **derived** from the business
data, per PC, never replicated, always rebuildable ("Rebuild index" tool + automatic on schema change).

### 5.6 Visibility (portal-ready from day one)
Every shareable record has `visibility` (`internal` | `client`); internal notes are a separate entity. The portal
serializer only emits `client` fields of `client` records of that client. Enforced in one server function, tested.

## 6. Decisions (ADRs)

| # | Decision | Why | Cost / risk |
|---|---|---|---|
| ADR-001 | Keep Python 3.12 stdlib + SQLite + plain JS (ES modules, no build step) | proven by BAMS; zero-install; small; the owner's team knows it; easy support for years | we build our own UI kit (~2–3k lines); escape hatch: vendor Preact+htm (MIT, ~10 kB, no build) only if a screen's state gets unmanageable — needs a new ADR |
| ADR-002 | **Extract a domain-free core** from BAMS instead of a third fork | 3 copies of one engine = 3× bug fixes; the core boundary already exists (0 domain words in sync/replica/node) | extraction effort in Phase 1; keep provenance + tests |
| ADR-003 | Strong relational model for core entities; custom fields only as an extension table with typed values | reports, integrity, performance; per brief §4 | migrations are additive only for replicated tables |
| ADR-004 | Server-side query API, pagination, derived index | data volume over years | more endpoints than BAMS |
| ADR-005 | Search = SQLite FTS5 over normalised Arabic/English text + phone/email normalisers | fast, offline, no dependency | own normaliser to maintain |
| ADR-006 | Party model (person / organisation + roles + relations) | "one object, many roles" (brief §20) | merge/dedupe must be sync-safe → merge by redirect (DATA_MODEL §3) |
| ADR-007 | Money: minor units, issued snapshots, append-only payments, per-PC number series | correctness under offline concurrency | per-PC series look unusual → explained in UI; strict mode available |
| ADR-008 | Journal envelope v2 with separated ops (hash covers ops hash) → **legal erasure** without breaking signatures | PDPL (Law 151/2020 + 2025 regulations); "never delete" is not legal in every case | engine change at extraction time (no legacy data yet — cheapest moment) |
| ADR-009 | Client portal through an internet gateway that receives client-scoped, minimal snapshots pushed by the office; client actions return as submissions the office pulls. Office PC never reachable from the internet. | local-first + security (Trip Orders idea) | a small cloud service to run (cost, ops) — Phase 10; before that: "share pack" (PDF/HTML) |
| ADR-010 | Desktop window = browser app mode on localhost | no dependency, native feel | depends on Edge being present (it is on Windows 10/11) |
| ADR-011 | Passwords: new hashes scrypt N=2^17,r=8,p=1 (stdlib, OWASP); PBKDF2 verified and upgraded at next login; **Argon2id + AES-GCM** if the owner allows `cryptography` as the single runtime dependency | OWASP 2026; memory-hard | scrypt ≈ 0.8 s/login on this machine — to benchmark on an old office PC; BAMS password-proof keys must follow the same KDF |
| ADR-012 | Module registry with manifests; disable ≠ delete | brief §33 | registry tests |
| ADR-013 | Remote team sync via a relay (same gateway), changesets signed end-to-end; encrypted end-to-end if ADR-011 dependency accepted | 2–4 person teams are often not in one office; LAN-only BAMS sync would fail them | later phase; relay sees only ciphertext only with AES |
| ADR-014 | Automations: one runner PC executes (default: owner PC, failover by role); created records use deterministic ids (rule + trigger event) so a double run merges instead of duplicating; external effects go through an outbox with idempotency keys and optional human approval | offline multi-PC would otherwise run every rule on every PC | runner role management |
| ADR-015 | Tax, messaging, payments, calendar, signature, AI = ports + adapters (connectors) | laws and providers change; core stays stable | adapter per provider |
| ADR-016 | i18n: Arabic + English, every string by key, logical CSS properties, `dir` switch, Western digits by default (setting) | brief §11 | test for missing keys and RTL snapshots |

## 7. Performance and reliability budgets

| Budget | Target |
|---|---|
| Cold start to Today screen | < 3 s on a 5-year-old laptop (SSD) |
| Save (one form) | < 100 ms p95 local |
| List / search | < 150 ms p95 at 50k parties, 200k documents |
| Sync of 1,000 changesets between two PCs on LAN | < 10 s |
| Backup of a 500 MB database | online, no pause of the UI |
| Memory | < 300 MB server process |
| Installer | < 60 MB |

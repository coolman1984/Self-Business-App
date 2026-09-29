# Development History and Lessons Learned

Newest first. Every change adds an entry: what changed, why, mistakes, lessons. Kept in the same pull request as the
change (rule in `CLAUDE.md`).

---

## Phase 1 — core engine (2026-09-29, in progress)

**What:** the BAMS engine (5f5b3ce) was harvested into `server/core/` and made domain-free; new pieces written on top
(registry, permissions registry, query API, Arabic search, router). Details per file: `server/core/PROVENANCE.md`.

**Built and tested (in-process suites, 71 tests green at the last run):**
- Entity registry + scopes: the engine no longer knows any business word (a test enforces it).
- **Journal envelope v2 and legal erase orders**: personal values can be blanked in rows, stored history, audit rows and fold
  registers on every PC while hash chains and signatures still verify; late changes, new PCs, restores and re-entry cannot
  bring them back. The tests were mutation-checked (disabling the redaction makes them fail).
- **Write-once entities** for issued documents (earliest write wins in any arrival order) and a `min` resolver — permutation tests.
- Query API with cursor pagination, data scopes (`all`/`scopes`/`own`) and money/sensitive masking on the server.
- scrypt password hashes; BAMS-style PBKDF2 hashes still verify and are upgraded at login on the administrator PC.
- Arabic-aware FTS5 search (hamza, teh marbuta, alef maqsura, diacritics, Arabic-Indic digits) and Egyptian phone numbers.
- Router `httpd.py` (no import-time side effects), entry points `server/app.py` and `server/sbo_main.py`, first multi-process
  run: 27 of 36 scenarios passed before any fix.

**Mistakes / lessons**
- A hard-coded slice (`name[4:]`) in the backup code and in two tests broke after the prefix rename (BAMS `bams_` 5 chars → `sbo_`
  4 chars) — the same trap Trip Orders documented. Fixed with a `PREFIX` constant; tests use the constant.
- The planned `lock-after` resolver cannot be deterministic (needs the dominated history of every field). Replaced by write-once
  snapshot entities (ADR-017). Lesson: prove a merge rule under all arrival orders *before* writing it into the design.
- A first version of the "late change" erase test passed even with the incoming-redaction code disabled, because the change
  reached the administrator PC only after the order had reached its author. A mutation check found it; the test now delivers the
  late change first. Lesson: mutation-check security tests.
- Wire format change (envelope v2) broke the fork test, which built its own forged record — tests that hand-build wire records
  must use the shared helpers (`env_chash`, `signed_view`).
- The auto-mode command classifier was unavailable for a long stretch in this session; file edits still worked, commands did not.
  Lesson: keep work committed in small steps so a tooling outage never strands a large uncommitted change.

## Phase 0 — research and plan (2026-09-29)

**What:** studied the two reference repositories (read-only), researched the market (HoneyBook, Dubsado, Bonsai,
Moxie, Plutio, Twenty, Dolibarr, ERPNext, Invoice Ninja), open-source licences, sync engines, password hashing, Egypt
ETA e-invoicing and the PDPL; wrote the documentation set (`docs/*`, `CLAUDE.md`, skill, `TASKS.md`, `IDEAS.md`,
`AGENT_HANDOFF.md`, `docs/OWNER_BRIEF_AR.md`). No code yet — by design (brief §39).

**Findings that changed the plan (details in `docs/OWNER_BRIEF_AR.md` §ج):**
1. The BAMS engine is already domain-free in its sync/replica/node/crypto parts, and the owner has forked it twice
   (BAMS, Trip Orders). → Extract a shared core instead of a third fork (ADR-002).
2. BAMS sends all data to the browser (`/api/state`) — fine for break areas, not for years of invoices. → Query API.
3. The signed, replicated, never-rolled-back journal stores old and new values of every field on every PC — this
   conflicts with legal erasure under Egypt's PDPL (regulations issued Nov 2025). → Journal envelope v2 + erase orders.
4. Offline multi-PC + sequential invoice numbers = duplicate numbers. → Per-PC series, optional strict numbering PC.
5. Automations evaluated on every PC would run N times. → Runner PC + deterministic ids + outbox.
6. The client portal needs the internet; the office PC must never be reachable from it. → Gateway (Trip Orders idea).
7. BAMS sync is LAN-only; small teams are often remote. → Relay transport later.
8. The stdlib has no Argon2id and no AES. → scrypt now; one vetted dependency (`cryptography`) proposed to the owner.
9. The new repository is **public** and the product is commercial. → Owner question Q1.

**Mistakes / lessons**
- Two BAMS tests failed in the shallow clone because they read an old commit from git history; not a code bug.
  Lesson (already known in BAMS): upgrade tests need full history (`fetch-depth: 0`).
- `sqlite.org` is blocked by the session's network policy; the WAL/network-filesystem rule was taken from known
  SQLite documentation and BAMS research notes. Lesson: record which sources could not be fetched.
- The UI screenshots referenced in the brief were not attached; Trip Orders' written design system was used instead.

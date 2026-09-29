# Development History and Lessons Learned

Newest first. Every change adds an entry: what changed, why, mistakes, lessons. Kept in the same pull request as the
change (rule in `CLAUDE.md`).

---

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

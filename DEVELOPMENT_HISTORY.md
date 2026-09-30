# Development History and Lessons Learned

Newest first. Every change adds an entry: what changed, why, mistakes, lessons. Kept in the same pull request as the
change (rule in `CLAUDE.md`).

---

## Review fixes and design pass for Phases 2-3 (2026-09-30)

**What:** three independent reviews (security, correctness, several PCs) found ~45 real problems; every one reproduced by the reviewer is fixed with a
regression test (`tests/test_business_review.py`, `test_ui_review.py`, new cases in `test_business_sync.py`). Then a design pass on the owner's request
("improve the look and feeling drastically"): `web/css/polish.css` (depth, colour per stat and per sales stage, glowing sidebar, floating search, Today hero
with a day ring, cover band on the client file, calmer empty states, softer inputs and dialogs), checked in Arabic/English, light/dark/navy and on a phone.

**Most important fixes**
- A spreadsheet could freeze the program (`1E999999`), pad millions of empty rows or smuggle entity declarations past a prefix check → size, row, cell and
  number limits; declarations refused anywhere in the file.
- "Undo" after a delete blanked amounts and national IDs for people who cannot see them; "remove sample data" did the same → hidden fields are taken from
  the stored record even when it is deleted; demo removal reads unmasked rows.
- A user limited to areas saw and changed every business record (entities without areas were open) → fail closed in queries and in the save guard.
- Import: a second import of the same file failed and left a half import without a batch; a double click imported twice; notes and company links doubled;
  undo deleted clients others had attached work to and shared companies → batch record first, row-by-row retry, one-time token, idempotent links and notes,
  undo keeps anything with attached work; undo and demo removal save as `restore` so they never beat a real edit made on another PC.
- Merge: cycles and chains were accepted, merged records were offered as targets, the survivor's file did not show the duplicate's work, no un-merge →
  server rule (`check_party`), merged records out of search, family ids in every tab, a banner with un-merge, Undo on the toast.
- Several PCs: a restored/undone record overwrote other PCs' edits (now only the fields that differ travel); `done_at`, `closed_at`, `lost_reason` follow
  their status; party status has a rank (merged wins over archived); Today and duplicate groups are now the same on every PC.
- Screens: Undo toast was off-screen in Arabic on phones; the record menu was cut off; Enter in a client picker saved the form without the client; tasks
  screen crashed without client rights; refreshes lost filters, focus and scroll and grew the history; the sync poll stole keyboard focus; listeners doubled
  after each new sign-in; shortcuts failed on the Arabic keyboard layout; Settings was hidden from team members (their own password and text size).
- Text is no longer cut silently (refused with a message); wrong types become plain messages instead of server errors.

**Lessons**
- Independent reviewers with the right to run code found in an hour what 225 green tests missed: ask them to *prove* each finding with a script.
- A Python heredoc with `\'` inside single quotes breaks the whole script (nothing runs) — write such edit scripts to a file with double quotes.
- Tests that pin a CSS class (`.page-head`) break with a redesign: prefer roles and ids for what matters.

## Phases 2 and 3 — design system, shell, people, work, Today, import (2026-09-30, in review)

**What:** the whole interface (no build step, plain ES modules): tokens/themes/fonts/icons, i18n Arabic + English with a test that reads the dictionaries, UI kit, shell,
login + first-run wizard + settings, command palette, tour, Edge app window; then the business kernel (`server/business/`) and its screens: clients and the client file,
timeline, sales board, projects, tasks, calendar, services, inbox, Today v1, Excel/CSV import, sample data, extra fields. Details: `TASKS.md`, `docs/DESIGN.md` §11-12,
`docs/DATA_MODEL.md` §8, ADR-021..026.

**Numbers:** 9 new test files; UI journeys run in a real Chromium (49 browser tests), backend API tests (24), several-PC tests (8), the 2,000-row messy Excel test.

**Mistakes / lessons**
- I deleted `web/js/quick.js` and `web/css/app.css` while replacing the placeholder page; the personal-link page still loads them (an existing test caught it in review of my own diff).
  Lesson: grep for a file name in `server/` before deleting anything under `web/`.
- The first version of the palette compared raw text, so "اعدادات" did not find "الإعدادات". Fixed by folding text the same way the server does (`textnorm.js`), and the server index
  now also stores each word without the article "ال". Lesson: every place that compares Arabic text needs the same folding, on both sides.
- A record edit is a **whole** `put`. My first settings save sent only the changed key and the server (correctly) answered *conflict*, because the row existed with a version. Lesson:
  one helper (`domain.updateRecord`, `api.saveSettings`) reads the current version and sends everything; screens never build ops by hand.
- Loading the sample data twice after keeping one edited demo record crashed with *conflict* (same id). The loader now skips records that already exist. Found by a test that removes and
  reloads.
- A test helper (`wait_for_function` with an element-returning string) was refused by our own CSP (`unsafe-eval`). The CSP is right; the test waits for a selector.
- The drawer's backdrop had a higher z-index than the drawer on phones, so nothing in the menu was clickable. Found by the phone test, not by looking.
- The tour card covered the menu it explains; chevrons pointed the wrong way in English; the top bar was crowded on a phone; month names ignored the digit setting. All found by looking at the
  screenshots of the visual matrix (as the brief demands), none by the functional tests.
- `Intl.NumberFormat` with `currencyDisplay: 'name'` printed "جنيه مصري" on every card; the symbol (ج.م) is shorter and clearer.
- Registering business entities inside one test module leaked into the next ones in the same process; the module now restores the registry in `tearDownModule`.
- Search hit lists must open the *record*, not `/parties/<id>`: a small `openRecord()` maps entities to pages or edit forms.

**Not done on purpose (see TASKS):** team screen, devices/sync screen, contact-points table, quotes and invoices (Phase 4).

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
- **External review of PR #1 found 15 real issues that 83 green tests and a self-review had missed.** Worth remembering: (1) my own
  erase design left the erased values in backups made *before* the erase, in the monthly audit files, and even created a new
  unredacted backup on purpose; (2) "accept and check later" for blanked values let a relay silently destroy data; (3) an
  "easy join" inherited from BAMS was open to any device by default — a security feature that is optional in a document must be
  closed in code; (4) new code paths for one route (`/api/audit`) skipped the masking that other routes had — mask in one shared
  place next time. Lessons: always run an independent review before merging; write the regression test first for each finding.
- CI (slower, shared runners) exposed a race in `test_g_revoke`: the removed PC could hand its change to a PC that had not yet heard of the
  removal. That is the documented limit (changes made before the removal is known are accepted); the test now waits until the other PC
  knows before it checks the property. Lesson: a test of "after X" must wait for X to be visible on every PC involved, not only on one.
- The main branch did not exist; the owner allowed pushing the first commit as `main` so a pull request could be opened.
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

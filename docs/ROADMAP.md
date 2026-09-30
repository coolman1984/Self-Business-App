# Roadmap

Every phase = code + tests + real run + visual check + docs + independent review + fixes, on a branch, merged only
after review. Order changed from the brief where research showed a better order (reasons in §2).

## 1. Phases and success criteria

| # | Phase | Delivers | Done when (success criteria) |
|---|---|---|---|
| 0 | Research & plan | this documentation set | owner has read the brief and answered the open questions (or accepted defaults) |
| 1 | **Core engine** (harvest from BAMS) | `server/core/*`: registry, store/plan, journal v2 (ops beside envelope), replica (+`min`, `lock-after`), query API, auth (generic permissions, scopes, money mask, scrypt/Argon2id), backup (+erase replay), files CAS, FTS5 search with Arabic normaliser, system/lock/upgrade, sync (LAN), erase orders; layer test; CI (Linux tests) + **walking-skeleton Windows build** | all ported BAMS engine tests green (unit, convergence, multi-process) on a test domain; new tests: envelope v2 verify after erasure on 3 PCs, lock-after, scope/money filters, Arabic search; Windows build produces an installer that starts and serves a page; provenance file lists every harvested file and change |
| 2 | **Design system & shell** | tokens, fonts, themes, i18n (ar/en) + RTL, UI kit (button, field, table, card, side panel, modal, toast+undo, empty/loading/error states, skeleton, tabs, chips, palette), shell (sidebar, top bar, command palette, shortcuts, offline banner), login, first-run wizard skeleton, settings shell, Edge app-mode launch | Playwright visual matrix (DESIGN §10) captured and reviewed; zero missing i18n keys; contrast test passes; keyboard-only walkthrough of shell; reduced-motion honoured |
| 3 | **People, work, timeline, search, Today v1, import** | parties + roles + relations + contact points (dedupe, merge by redirect), services, opportunities (pipeline board), projects, tasks, calendar, notes, activities, files, tags, custom fields; living client file; timeline; global search; Today v1 (tasks, appointments, follow-ups); **Excel/CSV import** of people (preview, mapping, duplicates, backup first); demo-data framework | a non-technical tester creates a client, a project and 3 tasks in < 5 min; importing a 2,000-row messy Excel produces no silent change and a correct duplicate report; search finds Arabic names with/without hamza/ta-marbuta; timeline shows every change |
| 4 | **Money** | services pricing, quotes (offer pack), agreements, invoices + lines, installments, payments + allocations, credit notes, expenses, recurring plans, per-PC number series, print/PDF (print CSS), receivables view, cash-flow (simple), tax profile + tax connector port (no ETA yet); Today v1 money sections | money property tests (sum of allocations = paid, no floats, issued snapshot immutable under concurrency on 2 PCs, duplicate payment flagged); a quote → accepted → deposit → final invoice → payment journey works end-to-end in Arabic and English |
| 5 | **Freelancer module** (thinnest module → validates the module system cheaply) | platforms & fees, scope items, revision rounds, time tracking, profitability, freelancer demo data, templates | module can be disabled/enabled without data loss (test); profitability numbers match a hand-calculated fixture |
| 6 | **Lecturer module** | centres, courses, groups, enrolments, sessions, attendance, share agreements & settlements, certificates, evaluations, demo data | the 3,000 / 30% / 70% example and a month of mixed collections reconcile exactly; attendance sheet printable; Today shows tomorrow's sessions with amounts |
| 7 | **Software company module** | products, releases, installations, licences, devices, contracts & SLA, tickets, visits, change requests, updates, renewals, demo data | "clients on version < X", SLA timers, renewal pipeline correct on fixtures; client file shows installations + tickets + money on one timeline |
| 8 | **Automation** | engine (runner role, deterministic ids, outbox, run log, dry run), 13 templates, approvals in Today, `wa.me`/`mailto:` messaging connector | double-runner test yields one result; every template has a test; a failing action is visible in Today within one minute |
| 9 | **Reports** | the ~15 decision reports (receivables, overdue, monthly income, profit by project/client/service, new clients, lead conversion, open/late projects, recurring, renewals, time spent, support load) + module reports; export Excel | each report matches its fixture; money-hidden users cannot reach money reports (server test) |
| 10 | **Client portal** | gateway (hosting per owner answer), client-scoped snapshots, portal UI (projects, progress, files, quotes approve, contracts, invoices, payments, deliveries approve, tickets), expiring links, submissions pulled by office | security review passes; a client can never see another client's or internal data (property test over random data); office PC not reachable from the internet |
| 11 | **Multi-device & hardening** | devices screen, relay transport for remote teams, backup admin PC, conflict "To decide" UX, performance budgets, independent security + distributed review | multi-process suite green incl. relay; performance budgets met on the reference old laptop; all review findings fixed with regression tests |
| 12 | **Installer & commercial release** | signed installer, auto-update channel, licence/activation (per owner decision), user guides ar/en, help centre, release notes | clean install/upgrade/uninstall on Windows 10 and 11 keeps data; SmartScreen-clean with code signing; pilot users sign off |

**Status:** Phase 0, 1 done and merged; Phases 2 and 3 implemented on branch `ccr-b21effdb-07jb83` (see `TASKS.md`), waiting for review and merge.

## 2. Why the order differs from the brief

1. **Import moved into Phase 3** (brief: implicit/late): customers arrive with Excel; without import the first pilot fails.
2. **Today v1 in Phases 3–4** instead of after everything: it is the hero screen; it grows with each phase.
3. **Freelancer before lecturer**: it is almost entirely platform, so it proves the module system with the least code;
   lecturer then adds the richest module-specific model.
4. **Reports before portal**: reports are local and cheap; the portal needs internet hosting decisions and a security
   review.
5. **Windows build as a walking skeleton in Phase 1**: installer problems found at the end are expensive (BAMS lesson).
6. **Sync engine exists from Phase 1** (it *is* the storage engine); Phase 11 adds the relay, devices UX and hardening.

## 3. Pilot plan (recommended)

After Phase 4: 2–3 real users per chosen module use it for 2 weeks with their real data (on their PCs, backups on),
weekly 20-minute feedback, issues triaged into the next phase. A module is "done" only after its pilot.

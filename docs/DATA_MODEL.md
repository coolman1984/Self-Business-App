# Data Model (high level)

Status: Phase 0 proposal. Tables are grouped by layer. Every replicated table carries the BAMS common columns:
`id` (random, never `length+1`), `ver`, `created_at/by`, `updated_at/by`, `deleted`, `deleted_at/by/txn`, plus
`scope` (for data scopes) and — for demo data — `sample` (1 = demo; "Delete demo data" removes exactly these).
Money: `*_minor INTEGER` + `currency TEXT` (ISO 4217). Dates: ISO text; times with time zone of the business.

## 1. Principles

1. Relational tables for everything the business reasons about; **custom fields** only as an extension
   (`custom_field_defs` + `custom_values` typed columns), never instead of a real column.
2. **One object, many roles**: a person/company exists once; roles and relations are rows, not copies.
3. **Events are immutable** (payments, allocations, attendance marks, time entries once approved, stock of licences):
   corrections are new events.
4. **Issued documents are snapshots** (see ARCHITECTURE §5.4).
5. Every link between records is an explicit foreign key where the relation is known; a generic `links` table only
   for "related to" associations the user makes by hand.
6. Replication rules (resolvers, counters, duplicate detectors) are declared next to the entity (SYNC.md §4).

## 2. Entity map

```
Party (person | organisation) ─┬─ PartyRole (lead, client, student, centre, vendor, partner, platform …)
    │                          ├─ ContactPoint (phone, email, whatsapp, address, social) — normalised, searchable
    │                          ├─ PartyRelation (person ↔ organisation: works at, owner of, contact for, parent of…)
    │                          └─ Consent (marketing / data processing, date, source)
    │
Opportunity (lead journey) ── stage, source, value estimate, expected close, owner
    │
Offer/Quote ── lines ── issued snapshot ── accepted/declined (portal or manual)
    │
Agreement/Contract ── terms, start/end, renewal rule, revenue share rules, SLA, attachments
    │
Engagement: Project (freelancer/agency) · CourseGroup (lecturer) · ServiceContract/Installation (software)
    ├─ Milestone / Phase ── Deliverable (revision rounds) 
    ├─ Task (assignee, due, checklist) · Appointment/Session (calendar)
    ├─ TimeEntry · Expense (billable?)
    └─ Ticket (software) · Visit
Money: Invoice ── lines ── installments (schedule) ── snapshot │ Payment ── Allocation (payment → invoice/installment)
       CreditNote · Expense · RecurringPlan (subscription / retainer / maintenance) · Settlement (shares)
Everywhere: Note (internal) · Message (sent/received log) · File (CAS) · Tag · CustomValue · Activity (call, meeting…)
Derived (index.db): SearchIndex · TimelineEvent · AttentionItem · ReportCache
System: Settings · Brand · NumberSeries · Template (document, message, automation) · AutomationRule · AutomationRun ·
        Outbox · ModuleState · Users/Profiles/Permissions (auth.db) · EraseOrder · RetentionPolicy
```

## 3. Platform tables (core business kernel)

| Table | Key columns | Notes |
|---|---|---|
| `parties` | kind (`person`/`org`), display_name, name_ar, name_en, legal_name, tax_id, national_id (optional, sensitive), birthday, notes_summary, owner_user, merged_into | `merged_into` = merge by **redirect**: references to B keep working offline and are resolved to A at read time; no mass rewrite. Unmerge possible. |
| `party_roles` | party_id, role, status, since, source, module | role values registered by modules (`student`, `centre`, `licensee` …) |
| `contact_points` | party_id, kind, value, value_norm, label, is_primary, verified | `value_norm`: E.164 phone (Egypt default `+20`), lower-case email; drives duplicate suggestions |
| `party_relations` | from_party, to_party, kind, title, primary, since, until | e.g. Mohamed *is IT manager at* Company X, *contact for* Branch Y |
| `addresses` | party_id, label, line1, city, governorate, country, geo (optional) | branches of a company are org parties with relation `branch_of` |
| `consents` | party_id, purpose, granted, at, source, evidence_file | PDPL: direct marketing requires consent |
| `services` | name, description, unit (hour, session, project, month, licence, visit), price_minor, currency, tax_code, module, active | catalogue for quotes and invoices |
| `packages` | name, items (service ids + qty), price_minor | bundles |
| `price_lists` | name, currency, valid_from/to; `price_list_items` | optional |
| `opportunities` | party_id, title, stage (registered pipeline), source, value_minor, probability, expected_close, lost_reason, owner_user | pipelines per module; stage `rank` resolver |
| `activities` | kind (call, meeting, message, email, visit, note), at, duration, party_id, subject_ref, summary, outcome, next_step_at | manual timeline entries |
| `notes` | subject_ref, body (markdown), internal (always 1), pinned | never visible to the client |
| `tasks` | title, subject_ref, assignee, due_at, priority, status (rank), checklist JSON, recurrence, visibility | `status`: `rank:todo,doing,waiting,done` with `cancelled` separate |
| `appointments` | title, starts_at, ends_at, tz, location, party_ids, subject_ref, reminder_rules, kind | lecturer sessions are appointments + session row |
| `projects` | party_id, title, kind (module), status (rank), start, due, budget_minor, billing_mode (fixed, hourly, milestone, retainer), visibility | generic engagement container |
| `milestones` | project_id, title, due, amount_minor, status, invoice_id | |
| `deliverables` | project_id, milestone_id, title, due, delivered_at, revisions_allowed, revisions_used (counter), approval_status, visibility | client approval via portal later |
| `time_entries` | user, project_id, task_id, started_at, minutes, billable, rate_minor, invoiced_invoice_id | immutable after invoiced |
| `files` | sha256, size, mime, name, subject_ref, visibility, version_of | content-addressed (BAMS CAS) |
| `tags`, `taggings` | name, colour · tag_id, subject_ref | |
| `links` | from_ref, to_ref, kind | user-made "related to" only |
| `custom_field_defs` | entity, key, label_ar, label_en, type (text, number, date, choice, party, money), options, required, module | extension layer |
| `custom_values` | entity, record_id, key, text_v, num_v, date_v, ref_v | typed columns, indexed |

`subject_ref` = `"<entity>:<id>"` — used only for *attachable* things (notes, tasks, files, activities) that can hang
on many kinds of records; business relations use real foreign keys.

## 4. Money tables

| Table | Key columns | Notes |
|---|---|---|
| `number_series` | doc_type, pc_letter, prefix, next, year_reset, strict_pc | per-PC series (ADR-007) |
| `quotes` | party_id, opportunity_id, project_id, status (`rank:draft,sent,viewed,accepted,declined,expired`), valid_until, currency, totals, terms, issued_snapshot, number, visibility | acceptance creates agreement/project/deposit via automation template |
| `quote_lines` | quote_id, service_id, description, qty (milli-units), unit_price_minor, discount, tax_code | |
| `agreements` | party_id, kind (contract, maintenance, retainer, revenue_share, licence, NDA), start, end, auto_renew, renewal_notice_days, terms, signed_at, signed_by, files, share_rules JSON | revenue share: e.g. `{"centre": 30, "lecturer": 70, "collector": "centre"}` |
| `invoices` | party_id, project_id, agreement_id, kind (deposit, milestone, final, recurring, credit), status (`rank:draft,issued,partially_paid,paid` + `void`), issue_date, due_date, currency, fx_rate_to_base, totals, number, issued_snapshot, snapshot_hash, tax_profile, eta_state | `paid` is **derived** from allocations, stored only as a cache flag |
| `invoice_lines` | invoice_id, service_id, description, qty, unit_price_minor, discount, tax_code, project_id, time_entry_ids | |
| `installments` | invoice_id or agreement_id, due_date, amount_minor, label | schedule; "overdue" derived |
| `payments` | party_id, received_at, amount_minor, currency, method (cash, bank, InstaPay, wallet, card, cheque, platform), reference, fee_minor (platform/bank fees), account, received_by | **append-only** |
| `allocations` | payment_id, invoice_id, installment_id, amount_minor | append-only; reversal = negative row |
| `expenses` | date, amount_minor, currency, category, vendor_party_id, project_id, billable, receipt_file, paid_by | |
| `recurring_plans` | party_id, kind (subscription, retainer, maintenance), amount_minor, interval, next_run, end, invoice_template | generates draft invoices (automation) |
| `settlements` | agreement_id, period, parties_shares JSON, collected_minor, due_each JSON, status, payment_ids | lecturer/centre and partner shares |
| `accounts` | name, kind (cash, bank, wallet), currency | simple cash position, not a ledger |
| `tax_profiles` | name, country, regime (none, vat, eta_einvoice, eta_ereceipt), registration_no, rates JSON, connector | the core never hard-codes a tax law |

Balances, receivables, overdue, expected collections, profit per project/client/service are **queries** (views),
never editable numbers.

## 5. Module tables

### 5.1 Lecturer / trainer (`lect_*`)
| Table | Notes |
|---|---|
| `lect_centres` | 1:1 extension of an org party with role `centre`: branches (org parties), default share rules, payment terms, rating, last contact (derived) |
| `lect_courses` | title, description, level, hours, sessions_count, price_minor, outline, requirements, materials (files) |
| `lect_groups` | course_id, centre_id, branch_id, room, start, end, schedule rule, capacity, price_minor, share agreement_id, status |
| `lect_enrolments` | group_id, student party_id, price_minor, discount_minor, status, certificate_issued_at |
| `lect_sessions` | group_id, appointment_id, n, topic_planned, topic_done, notes, files |
| `lect_attendance` | session_id, enrolment_id, mark (present, absent, late, excused) — event per mark, last wins per (session, enrolment) with `max`-safe resolver |
| `lect_evaluations` | enrolment_id or group_id, score, comment, anonymous |
| `lect_certificates` | enrolment_id, number (series), issued_at, template, file |

Money: student payments are normal `payments` with allocations to enrolment invoices; `settlements` compute
"collected / centre due / lecturer due / not collected" from share rules and who collected.

### 5.2 Freelancer (`free_*`) — thin on purpose; most is platform
| Table | Notes |
|---|---|
| `free_platforms` | Upwork, Mostaql, Khamsat, Fiverr, direct …; fee rule (percent/fixed/tiered), currency, withdrawal fee |
| `free_platform_fees` | computed per payment received through a platform (event) |
| `free_scope_items` | project_id, in/out of scope, text — protects against scope creep; change requests become quotes |
| `free_revision_rounds` | deliverable_id, n, requested_at, notes, billable_extra |

### 5.3 Small software company (`soft_*`)
| Table | Notes |
|---|---|
| `soft_products` | name, edition list, current version |
| `soft_releases` | product_id, version, released_at, notes, fixes (ticket ids) |
| `soft_installations` | client party_id, branch party_id, product_id, version_installed, installed_at, installed_by, location, seats, devices JSON, environment notes, acceptance_at, warranty_end |
| `soft_licences` | installation_id, key (hashed + last 4 shown), seats, expires, status |
| `soft_devices` | installation_id, name, kind, serial, os, notes |
| `soft_contracts` | agreement extension: SLA (response/resolve hours per priority), maintenance visits included, renewal price |
| `soft_tickets` | party_id, installation_id, title, description, priority (rank), status (rank:new,triaged,in_progress,waiting_client,resolved,closed), channel, sla_due (derived), assignee, resolution, fixed_in_release_id, minutes_spent, billable, visibility |
| `soft_ticket_events` | ticket_id, kind (comment internal/public, status, assignment), text — append-only |
| `soft_visits` | party_id, installation_id, date, purpose, minutes, cost_minor, billable, report |
| `soft_change_requests` | party_id, product_id, title, estimate, quote_id, status, release_id |
| `soft_updates` | installation_id, from_version, to_version, at, by, notes |

## 6. Derived tables (`index.db`, per PC, rebuildable, never synced)

| Table | Built from | Used by |
|---|---|---|
| `search_fts` (FTS5) + `search_docs` | names, contact points (normalised), numbers, titles, tags, module search providers | global search, command palette |
| `timeline` | journal audit rows mapped to business events + `activities` + messages + files; fan-out to every related party/project | client file, project page |
| `attention` | attention providers (queries) | Today Command Center |
| `report_cache` | report queries per period | reports |

## 7. Duplicates, merge and the one-object rule

1. On create, suggestions: same normalised phone/email → "Is this the same person?" (never automatic).
2. Import: fuzzy match (normalised Arabic name + phone) → preview groups "new / update / possible duplicate".
3. Merge B into A: `B.merged_into = A` (replicated change), UI and queries follow the redirect; contact points and
   roles are copied to A as *new rows* (so offline PCs that edit B still converge); unmerge clears the redirect.
4. Concurrent creation of the same person on two PCs offline → two rows + a "possible duplicate" flag (same rule as
   BAMS survey duplicates), shown in "To decide".

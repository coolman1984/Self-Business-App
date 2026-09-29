# Modules — core, platform and activity modules

## 1. Three rings

1. **Core** (domain-free engine): storage, journal, sync, auth, backup, files, search, registry, query, erase.
2. **Platform** (shared business kernel, always on): parties, opportunities, services, quotes, agreements,
   projects, tasks, calendar, notes, activities, files, tags, custom fields, invoices, payments, expenses, recurring,
   settlements, timeline, Today, automation, templates, import/export, reports, portal (later), connectors.
3. **Activity modules** (switchable): add entities, pages, permissions, reports, attention providers, automation
   templates, document templates, settings, wizard questions, tour, help, demo data.

## 2. Manifest (what a module registers)

```python
# server/modules/lecturer/manifest.py  (illustrative)
MODULE = Module(
    id='lecturer', version=1, name={'ar': 'المحاضر والمدرب', 'en': 'Lecturer & Trainer'}, icon='presentation',
    requires=['platform>=1'],
    roles=['student', 'centre'],                                  # party roles it introduces
    entities=[Entity('lect_courses', fields=[...], search=['title'], timeline=True), ...],
    resolvers={'lect_groups': {'status': 'rank:planned,running,finished'}},
    permissions=[('lecturer.view', ...), ('lecturer.attendance', ...), ('lecturer.settlements', ...)],
    pages=[Page('centres', nav_group='training'), Page('courses'), Page('groups'), Page('sessions')],
    record_tabs={'parties': [Tab('courses', when_role='student'), Tab('centre', when_role='centre')]},
    attention=[sessions_tomorrow, unpaid_students, centre_settlement_due, centre_no_contact],
    triggers=['lect.session.upcoming', 'lect.enrolment.created', 'lect.group.finished'],
    actions=['lect.issue_certificates'],
    automation_templates=['session_reminder', 'certificate_on_finish', 'unpaid_student_followup'],
    document_templates=['certificate', 'centre_statement', 'attendance_sheet'],
    reports=['centre_profitability', 'group_collection', 'attendance_rate'],
    wizard=[Question('centres_count'), Question('default_share', default={'centre': 30, 'lecturer': 70})],
    settings=[...], tour=[...], help=[...], demo=demo_data, search=[...],
)
```
The web side mirrors it: `web/modules/lecturer/index.js` registers views, record tabs, palette actions, icons.

## 3. Enable / disable

- Enabling: run additive migrations of its tables (idempotent), register everything, show the wizard questions.
- Disabling: hide pages/nav/actions/attention/automations; **no data is deleted**; the journal still folds its
  changesets (so other PCs with the module on stay consistent); re-enabling restores everything.
- A PC that does not have a module's *code* version yet keeps its changesets aside (schema rule) until updated.

## 4. Version 1 modules

### Lecturer & trainer
Journey: centre found → agreement (share %) → course → group (schedule) → enrolments → sessions (attendance, topic,
files) → collections → settlement with the centre → certificates → evaluation → next group / new centre.
Today: sessions today/tomorrow (centre, place, time, amount to collect there), unpaid students, centre settlements due,
centres not contacted for 60 days, groups finishing (certificates).
Money example: student pays 3,000; share centre 30% / lecturer 70% → collected 3,000; centre due 900; lecturer due
2,100; who holds the cash decides the settlement direction; uncollected enrolments listed.

### Freelancer
Journey: lead → call (activity) → needs → offer pack (quote + scope + terms + deposit) → acceptance → agreement →
deposit invoice → project + milestones + tasks → deliveries → revision rounds → final invoice → payment → follow-up →
new work / retainer.
Specials: scope items in/out, revision round counter with extra-billable rounds, time tracking, platform fee rules
(Upwork, Mostaql, Khamsat, Fiverr, direct), profitability per project/client/service (income − expenses − fees −
time cost optional).

### Small software company
Journey: lead → offer → agreement → sale → installation (branch, devices, version, licence) → training → acceptance →
warranty → support tickets / visits → maintenance contract → updates (release → installation) → change requests →
renewal.
Specials: installation register per branch, licence keys (hashed), SLA per priority with due times, ticket timeline
(internal vs client-visible), visits with cost, "which clients run version < X", renewal pipeline, support load per
client, client profitability.

## 5. Future modules (the core already supports them)

Consultant (engagements, hourly, reports) · marketing agency (retainers, content calendar, approvals) · designer
(proofs, revision rounds) · photographer (bookings, shoots, galleries links, deposits) · independent accountant
(clients, periodic filings calendar) · engineer / engineering office (sites, visits, drawings approvals) · maintenance
services (visits, spare parts as expenses) · small clinic (appointments, patients — **needs extra privacy review**) ·
fitness coach (packages, sessions, check-ins) · private tutor (students, parents, sessions, monthly fees) ·
home services (jobs, locations, technicians).
Each future module must fit in the manifest; if it needs a core change, that change goes to platform/core first.

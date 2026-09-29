# Product — Self Business OS (working name)

> Status: Phase 0 (study and plan), 2026-09-29. Owner: Mohamed Fawzy.
> The final brand is not decided: every visible name, logo and colour comes from settings (`brand.*`), never from code.

## 1. One sentence

**"My whole office inside one program"** — one local-first business core for people who work for themselves or in
teams of 1–4, with activity modules (lecturer, freelancer, small software company, …) that plug into the same data.

Design motto: **very strong inside, very simple outside.**

## 2. Who it is for

| Segment | Typical person | What hurts today |
|---|---|---|
| Solo lecturer / trainer | teaches at 3–6 training centres, groups of students, percentage deals | who paid, what each centre owes, which session is tomorrow, where the material is |
| Freelancer / consultant | 5–30 clients a year, projects with deposits and revision rounds | proposals in Word, deals in WhatsApp, money in a notebook, deadlines in the head |
| Micro software company (1–4 people) | sells a desktop/web program, installs it, supports it for years | who has which version, which contract expires, open tickets, unpaid visits |
| Person with several activities | lecturer + consultant + freelancer | three spreadsheets and three habits for one life |
| Small agency / service office | 2–4 people, clients, projects, retainers | shared follow-up, who does what, recurring invoices |

Not for: companies with departments, accountants who need a full general ledger, e-commerce shops with stock.

## 3. The problem (validated by research, see `RESEARCH.md`)

1. **Scattered work**: Excel + WhatsApp + email + folders + calendar + separate invoices. Nobody sees the whole client.
2. **Forgotten money**: overdue invoices, unpaid remainders, centre shares nobody reconciled, renewals that lapsed.
3. **Tools built for others**: CRMs designed for sales teams; ERPs that take months; freelancer SaaS that is US-centric
   (payments need a US/Canada bank, US tax layer) and online-only.
4. **Setup fatigue**: flexible tools (Dubsado) take days to configure; rigid ones (HoneyBook) fight the user.
5. **No after-sale memory**: small software companies lose the history of installations, versions, tickets and visits.

## 4. Promise (what the user feels)

- Opens the program in the morning and in 10 seconds knows: **who needs a reply, who owes money, what is due today,
  what is at risk.** (Today Command Center — the hero screen.)
- Enters a client once; the same person can be a lead, a client, a student and a contact of a company.
- Opens any client and sees **one living file**: every call, project, invoice, payment, program, ticket, file, decision
  on one timeline.
- Never loses data: every delete goes to the recycle bin, every change is recorded, backups are automatic and checked.
- Works without internet; a small team works on several PCs that share changes when they meet.
- Starts useful on day one: a guided setup, ready-made templates per activity, realistic demo data, Excel import.

## 5. Product principles (the tie-breakers)

1. **"Does this make the owner's life easier?"** — if not, it is not built.
2. **Attention over dashboards**: show what needs action and why, not twenty charts.
3. **One object, many roles**: never duplicate a person or company to give it another role.
4. **Templates before editors**: ready-made automations, documents and pipelines; advanced editors later and hidden.
5. **Progressive disclosure**: modules the user did not choose are invisible; advanced fields are folded away.
6. **Local-first, cloud-optional**: the core never needs the internet; the internet adds reach (portal, messages).
7. **Money is sacred**: amounts in integer minor units, issued documents are immutable snapshots, payments are events.
8. **History is sacred, privacy is law**: nothing silently erased — except by the separate, audited legal-erasure path.
9. **Arabic first-class**: Arabic and English, RTL and LTR, Egyptian realities (WhatsApp, InstaPay, wallets, ETA).
10. **AI is optional**: everything works without it; AI suggests, humans approve money, deletes and outgoing messages.

## 6. What we will NOT build (version 1)

| Not in V1 | Why | Instead |
|---|---|---|
| Full double-entry accounting, payroll, stock/inventory | ERP creep; the audience does not need it | clean money layer + export/connector for accountants |
| Full ETA e-invoice / e-receipt submission | needs USB-token signing, OAuth per taxpayer, most target users are not in scope yet | tax connector interface + tax profile; Egypt connector as a later module |
| Online payment processing | licences, fees, per-country providers | record payments (cash, bank, InstaPay, wallet, card); payment links later via connector |
| Built-in email client / WhatsApp Business API | heavy, costly, fragile | `mailto:` and `wa.me` pre-filled messages (zero cost, works now); API connectors later |
| Cloud SaaS multi-tenant version | contradicts local-first V1; hosting/ops cost | local program + optional small gateway for portal |
| Native mobile apps | cost | responsive web UI on the LAN; portal on phones |
| Drag-and-drop automation designer | frightens small users | templates with a few switches; a form-based editor later |
| LMS (video hosting, quizzes platform) | different product | course material files + links |
| Marketing campaigns, ads, social scheduling | out of scope | lead source tracking only |
| Hundreds of reports | noise | ~15 decision reports + module reports |

## 7. Product map

```
                         ┌──────────────── Today Command Center ────────────────┐
                         │ needs you · money waiting · today · due soon · risk  │
                         └───────────────────────────────────────────────────────┘
   People & Companies ── Opportunities ── Quotes ── Agreements/Contracts ── Projects ── Deliveries
          │                                                   │                 │
          └── Timeline (one per client/person/project) ── Invoices ── Payments ── Expenses ── Profit
                                                              │
   Core services: search · command palette · files · notes · tasks · calendar · templates · tags · custom fields
                  automation · import/export · reports · users & permissions · backups · recycle bin · audit · sync

   Modules:  Lecturer (centres, courses, groups, sessions, attendance, shares, certificates)
             Freelancer (services, packages, milestones, revisions, time, platform fees, retainers)
             Software company (products, releases, installations, licences, SLA, maintenance, tickets, visits, renewals)
             later: consultant, agency, designer, photographer, clinic, tutor, trainer, engineering office, home services …
```

## 8. First-run journey (summary; screens in `DESIGN.md` §8)

1. Welcome → language (Arabic/English) → **"What do you run?"** (pick one or more activities).
2. Business basics: name, logo, colours, country, currency, time zone, (tax status: "not registered / VAT registered /
   e-invoice obliged" — only sets the tax profile, no law in the core).
3. Activity questions (only for the chosen modules): services and prices, centres and percentages, products and
   versions, numbering style of documents.
4. Team: "just me" or invite people (roles: owner, manager, assistant, accountant, support, viewer).
5. Start: **Try with demo data** · **Import from Excel** · **Start empty**. Demo data is removable in one step.
6. Guided tour of the Today screen (3–5 steps), then the user is working.

## 9. Success measures (product level)

- Time to first value < 10 minutes (setup + first client + first invoice) for a non-technical user.
- Daily return: the Today screen is opened ≥ 5 days/week by pilot users after 4 weeks.
- Money recovered: pilot users report overdue items they would have missed (qualitative, collected in pilot notes).
- Zero data-loss incidents; every restore test passes; every release passes the full test suite and the RTL/theme
  visual checks.

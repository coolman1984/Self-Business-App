# Automation Engine

Goal: a general engine (not tied to one activity), **templates first**, observable, safe offline with several PCs.

## 1. Anatomy of a rule

```
Rule = trigger + conditions + actions (+ optional delay per action) (+ optional human approval) + limits
```

| Part | Details |
|---|---|
| Trigger | a domain event (derived from folded changesets) or a schedule: `party.created`, `party.role_changed`, `opportunity.stage_changed`, `quote.accepted`, `agreement.signed`, `payment.received`, `invoice.overdue(days)`, `appointment.upcoming(hours)`, `agreement.ending(days)`, `project.created/finished`, `ticket.created/status_changed/sla_near`, `date(at)`, `recurring(daily/weekly/monthly)`, plus module triggers (`lect.session.upcoming`, …) |
| Conditions | field comparisons on the trigger record and related records (all/any), tags, amounts, module, owner user |
| Actions | create task / project / invoice (draft) / appointment / document (draft from template) / note / follow-up; change status; add tag; create notification; **prepare message** (draft in outbox); send message (only if the rule allows auto-send); run another rule (depth ≤ 3); module actions |
| Delay | "after 2 days", "3 days before due date", "at 9:00 next working day" |
| Approval | per action: none / owner / role; approval queue shown in Today ("محتاج منك") |
| Limits | max runs per record, quiet hours, working days, no loops (same rule + record + trigger once) |

## 2. Execution model (safe with several PCs, offline)

1. **Event source**: every PC derives the same domain events from the same folded changesets (deterministic).
2. **Runner PC**: only the PC with the `automation-runner` role executes (default: owner PC; a backup runner can take
   over after N hours of silence). Other PCs show "automations run on <PC>".
3. **Deterministic ids**: records created by an action get `id = hash(rule_id, trigger_event_id, action_index)`. If
   two PCs ever run the same rule for the same event (failover, split network), the inserts carry the same id and
   merge — no duplicates.
4. **Scheduled triggers** are evaluated by the runner at start and every minute; missed windows while off are
   caught up once (with a "late" note), never multiplied.
5. **External effects** (messages, portal publish, webhooks) go to the **outbox** with an idempotency key; the
   connector sends; result recorded; retry with backoff; failures visible in Today and in the run log.
6. **Dry run / test**: "Test this rule on <record>" shows what would happen, changes nothing.
7. **Run log** per run: trigger, why it matched (conditions evaluated), actions and results, errors, duration,
   retry button, pause rule, "turn off after errors" (after 3 consecutive failures the rule pauses and says so).

## 3. Templates (V1 ships these; each is a rule with 1–3 switches)

| Template | Module | What it does |
|---|---|---|
| Offer accepted → start work | freelancer/platform | create project from quote, deposit invoice (draft), kickoff checklist tasks, follow-up in 3 days |
| Invoice overdue 7 days → follow-up | platform | follow-up task + WhatsApp/email reminder **draft** (auto-send only if switched on) |
| Installment due in 3 days | platform | reminder draft to client, notification to owner |
| New lead → first contact | platform | task "call within 24 h", tag source |
| Contract ending in 30 days → renewal | platform/software | renewal task, call task, renewal quote draft |
| Session tomorrow → reminder | lecturer | notification with centre, place, time, amount to collect; optional message draft to the group |
| Group finished → certificates | lecturer | issue certificate drafts for students with attendance ≥ X% and paid |
| Student unpaid after 2 sessions | lecturer | follow-up task + message draft |
| Ticket high priority created | software | notify assignee, SLA timer, client acknowledgement draft |
| Ticket resolved → confirm | software | ask the client to confirm (message draft), close after 5 days silence |
| Delivery sent → approval reminder | freelancer | remind client after 3 days (draft) |
| Monthly retainer | platform | draft invoice on the 1st, notify owner |
| Client inactive 90 days | platform | "check in" task |

## 4. Editor (later, hidden behind "Advanced")

Form-based ("When … If … Then …"), with plain-language preview ("لما عرض يتقبل، اعمل مشروع، واعمل فاتورة عربون مسودة،
وفكرني بعد ٣ أيام"). No canvas designer in V1.

## 5. Tables

`automation_rules` (replicated, admin-changeable) · `automation_runs` (replicated from the runner, append-only) ·
`automation_approvals` · `outbox` (replicated; state machine `draft → approved → sending → sent/failed`) ·
`notifications` (per user).

## 6. AI hooks (optional, later)

Actions `ai.summarise`, `ai.draft_message`, `ai.suggest_next_step` produce **drafts only**; never money, delete or
send without approval. Provider through the AI connector port; off by default; nothing leaves the PC without the
owner enabling it.

# Design System and UX

Status: Phase 0 direction. Built and visually verified in Phase 2 (build → run → screenshot → critique → improve).
Visual reference: the owner's Yousef-Transportation direction (`docs/DESIGN.md` there — tokens, depth, motion,
palette, panels). The screenshots mentioned in the brief were not attached yet (open question Q3); when they arrive,
this file gets a "Reference screens" section. We keep the *spirit*, not a copy: a new identity for this product.

## 1. Personality

Calm, warm, confident — "a tidy personal office", not a control room and not a marketing site.
- **Calm**: generous spacing, few colours, one accent, quiet motion.
- **Warm**: rounded shapes, friendly empty states, Egyptian-Arabic microcopy option ("مين محتاج منك رد؟").
- **Confident**: strong typography, clear hierarchy, numbers that line up.

## 2. Tokens (CSS custom properties; brand colours overridable in settings with contrast check)

| Token | Light "Morning" | Dark "Evening" | Use |
|---|---|---|---|
| `--canvas` | `#F4F2EE` (warm paper, never pure white) | `#101214` | page background |
| `--surface` | `#FFFFFF` | `#171A1D` | cards, tables |
| `--surface-2` | `#FAF8F5` | `#1D2125` | stripes, inputs |
| `--raised` | `#FFFFFF` + shadow-2 | `#22272B` | side panels, menus |
| `--ink` | `#1C1B19` | `#ECEAE6` | main text |
| `--ink-2` | `#5E5B55` | `#A7A39C` | secondary |
| `--line` | `#E4E0D9` | `#2C3136` | borders |
| `--brand` | `#1F4E47` (deep teal) | `#7CC2B6` | structure, selected nav, headings |
| `--accent` | `#E07A3F` (warm copper) | `#F29A61` | the single accent: primary button, focus ring, "today" marker |
| `--ok` / `--warn` / `--bad` / `--info` | `#2E8B57` / `#C98A12` / `#C8453B` / `#2F6FB3` | `#5BD18F` / `#F2B84B` / `#FF7A6E` / `#6FA8E8` | **meaning only** (paid / due soon / overdue / info) |
| radius | 8 / 12 / 18 px | | inputs / cards / sheets |
| shadow-1 | `0 1px 2px rgb(28 27 25/.06), 0 2px 8px rgb(28 27 25/.05)` | inset hairline | cards |
| shadow-2 | `0 10px 30px rgb(28 27 25/.14)` | `0 10px 30px rgb(0 0 0/.5)` | panels |
| spacing | 4-pt scale: 4 8 12 16 20 24 32 40 56 | | |

Extra themes: **High contrast** (AA+), **Brand** (from the user's logo colours, auto-checked for contrast).
All themes pass WCAG 2.2 AA — a unit test checks token pairs.

## 3. Typography

- Bundled (offline): **IBM Plex Sans Arabic** + **IBM Plex Sans** (OFL) default; options Cairo, Tajawal, Noto Kufi
  Arabic (OFL). Subset to Arabic + Latin + digits.
- Size setting S/M/L/XL (13/14/15/17 px base), ratio 1.2; density Comfortable/Compact.
- Money and times: `tabular-nums`; digits Western by default, Arabic-Indic optional per user.
- Money display: `12,500.00 ج.م` / `EGP 12,500.00` according to locale; negative in `--bad` with a minus, never only red.

## 4. Layout and navigation

- **Shell**: sidebar (collapsible to icons) · top bar (global search, quick add `+`, sync/offline dot, notifications,
  user menu) · content · **side panel** (inline-end; stackable; `Esc` closes one level).
- **Sidebar groups** (only enabled modules appear):
  1. اليوم Today · صندوق الوارد Inbox (quick captures)
  2. العملاء والناس Clients & People · الفرص Opportunities
  3. الشغل Work: Projects · Tasks · Calendar
  4. الفلوس Money: Quotes · Invoices · Payments · Expenses · Receivables
  5. module group(s): e.g. التدريب Training (Centres, Courses, Groups, Sessions) · الدعم Support (Tickets,
     Installations, Contracts, Renewals)
  6. التقارير Reports · الأتمتة Automations
  7. (bottom) Settings · Help
- **Record pattern** ("living file"): header (name, roles as chips, key money figures, primary action) → tabs:
  Overview · Timeline · Work · Money · Files · module tabs (Courses / Installations …) · Notes (internal).
  Every name anywhere is a link that opens the record in the side panel without losing the page.
- **Command palette** `Ctrl K`: search everything + actions ("عميل جديد", "فاتورة جديدة", "ابدأ مشروع",
  "روح للمستحقات", "افتح الإعدادات", "غيّر الثيم").
- **Shortcuts**: `N` new (context) · `G` then `T/C/P/I/R/S` go to page · `/` search · `J/K` rows · `Enter` open ·
  `E` edit · `Esc` close · `?` shortcut sheet. Shown in tooltips.
- **Quick capture** `Ctrl Space`: one line ("كلم أحمد بكرة بخصوص العرض") lands in Inbox → convert to task/note/lead.
- Filters live in the URL (bookmarkable). Tables: sticky header, column chooser, saved views, bulk actions, keyboard.

## 5. The Today Command Center (hero screen)

Sections are *attention items* with a reason and a one-click next action — not charts.

| Section | Examples | One-click action |
|---|---|---|
| محتاج منك النهارده | replies owed, approvals waiting, tasks due today | open / reply on WhatsApp / done |
| فلوس منتظرة | overdue invoices (days, amount), installments due this week, centre settlements | send reminder (drafted) / record payment |
| مواعيد النهارده | sessions, meetings, visits — with place, centre, amount due there | open / navigate / mark attended |
| تسليمات قريبة | deliverables in ≤ 3 days, revision rounds waiting | open project |
| عملاء محتاجين متابعة | no contact for N days while an opportunity/ticket is open | log call / snooze |
| تجديدات قريبة | contracts/licences/maintenance ending in ≤ 30 days | prepare renewal quote |
| مشاكل مفتوحة | tickets near/over SLA | open ticket |
| مشروعات معرضة للتأخير | due soon with open tasks, no activity | open |
| اتعمل مؤخرًا | last 10 things (mine / team) | — |
| اقتراحات | rule-based (and later AI): "3 clients haven't paid since…" | — |

Ordering = money at risk × urgency; each item can be snoozed or dismissed (per user, replicated). Per module the
providers differ (lecturer sees sessions, centres, students, dues; software company sees tickets, SLA, renewals).
Top strip: three numbers only — *due today*, *money expected this week*, *overdue total*.

## 6. Motion (explains, never decorates)

| Pattern | Spec |
|---|---|
| Page change | fade + rise 6 px, 160 ms, `cubic-bezier(.2,.8,.2,1)` |
| Side panel | slide from inline-end, 220 ms; backdrop fade |
| Save | button morphs to ✓ 600 ms; toast from bottom with **Undo** (soft delete makes undo cheap) |
| Move between stages (board) | card travels to the new column 200 ms |
| Number change | short count 300 ms |
| Status change | 800 ms soft glow in the new status colour |
| Loading | skeletons, never a blank page; spinner only inside buttons |
`prefers-reduced-motion` and a setting turn motion off (instant state changes).

## 7. States every screen must have

Empty (says what this is + the next step + "load demo data" when relevant) · loading (skeleton) · error (what
happened, what to do, retry; technical details folded for admins) · offline (banner: "شغال من غير نت — كل حاجة
بتتحفظ وهتتبعت لما النت يرجع") · permission denied (what and whom to ask) · large data (pagination/virtual list).

## 8. First-run wizard (screens)

1. Language + theme (live preview) → 2. "إنت بتدير إيه؟" cards (lecturer, freelancer, software company; "more soon")
→ 3. Business basics (name, logo, colours with contrast check, country, currency, time zone, tax status)
→ 4. Activity questions (only chosen modules; each ≤ 5 fields, all skippable, sensible defaults)
→ 5. Team (just me / invite) → 6. Start: demo data · import from Excel · empty → 7. Tour of Today (3–5 steps).
Progress dots, back always possible, everything editable later in Settings.

## 9. Settings (grouped cards with live preview)

Appearance (per user) · Business & brand · Activities (enable/disable modules) · Documents & numbering · Money & tax
profile · Templates (documents, messages) · Automations · Users & permissions · Devices & sync · Backups ·
Recycle bin · Activity & security logs · Data (import/export, demo data, privacy & retention) · Help.

## 10. Visual QA matrix (every new screen, Phase 2 onward)

Arabic/RTL · English/LTR · light · dark · font XL · 1440 px · 1280 px · 390 px phone · empty · 1,000+ rows · error ·
loading · offline. Playwright screenshots per state in `tests/visual/` (stored as artefacts, reviewed each phase).
Checklist: crowding, bad spacing, clipped text (Arabic is ~20–30% longer), mirrored icons, unclear buttons,
inconsistent sizes, anything that looks "admin-panel".

## 11. As built (Phase 2)

- **Tokens** live in `web/css/tokens.css` (CSS custom properties). Themes are `[data-theme]` on `<html>`: `morning` (default, warm off-white with a deep green
  sidebar and a copper accent), `evening` (dark), `navy` (light with a navy sidebar and an amber accent), `navynight`, `contrast` (black on white, yellow accent).
  "Automatic" follows the system setting. `data-font` (`plex` or `system`), `data-size` (`s m l xl` = 13/14/15/17 px root size), `data-density`, `data-motion`.
  `tests/test_tokens.py` computes WCAG contrast for every text/background pair of every theme (AA 4.5:1 text, 3:1 for icons, dots and the focus ring).
- **Selectors are `[data-theme=...]`, not `:root[...]`**, so a swatch inside Settings can show another theme by carrying the attribute itself.
- **Logical properties only** (`margin-inline-start`, `inset-inline-end` ...). Icons that point somewhere (arrows, chevrons, log-out, panel) are drawn for
  left-to-right and mirrored by CSS in Arabic: write `arrow-right` for "forward" everywhere.
- **Digits**: Western by default, Arabic-Indic per user (Settings → Look). Money is formatted from whole piastres; Arabic shows the symbol (ج.م).
- **Shell** (`web/js/shell/shell.js`): the sidebar is built from `registerNav()` calls made by each screen/module; the top bar has search (Ctrl+K), the sync light,
  theme and language switches, the quick-add button (built from `registerQuickAdd()`), shortcuts and help. On phones the sidebar becomes a drawer.
- **Forms** are described as data (`ui/form.js`): the same look, validation and error placement for every record; dialogs open as a side panel (records) or a
  centered box (questions). Errors from the server arrive as `E:<code>|English` and are shown through `err.<code>` in the user's language.
- **Undo instead of "are you sure" wherever possible**: ticking a task and deleting a record show an *Undo* toast; the undo is a new change (nothing is rolled back).
- **Guided tour**: 4 steps, once, restartable from Help; the spotlight is drawn with a giant box-shadow, the card is placed beside tall targets.
- **Visual QA**: `tests/visual/matrix.py` produces ~70 screenshots (ar/en × themes × widths × text size × states); CI keeps them as an artefact. Findings of the
  first review pass that were fixed: hard-coded server name under the brand, redundant quick-add buttons, comma style in English greetings, direction of chevrons
  and forward arrows, tour card covering the menu it explains, crowded phone top bar, month names not following the digit setting.

## 12. As built (Phase 3 screens)

Client file = header (avatar, roles, call / WhatsApp / e-mail buttons) + tabs *Overview · Timeline · Work · Notes · Files*. Sales = board (drag or *Move* menu).
Tasks = a table with a quick-add line. Calendar = month grid, Saturday first, dots on phones. Today = numbers, "needs your attention", today's schedule, coming days,
pipeline; a new business sees a start card and an offer to load sample data. Import = three steps (file and columns → report → done) with per-row decisions.

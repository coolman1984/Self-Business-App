# Ideas Book — reusable ideas (بالعربي والإنجليزي)

Same shape as the BAMS ideas book: **Problem → Idea → How → Where → Reuse when / watch out.** New idea → new card.
Ideas harvested from BAMS are listed in BAMS' own `IDEAS.md`; here only new ideas or new twists.

## 1. Merge by redirect, not rewrite
- **Problem:** merging two duplicate clients rewrites hundreds of references; an offline PC still editing the old
  client would diverge.
- **Idea:** the duplicate gets `merged_into = <kept id>`; reads follow the redirect; nothing else is rewritten.
- **Reuse:** any replicated system with dedupe. **Watch out:** unmerge must be possible; search shows the kept record.
- 🇪🇬 بدل ما نغيّر كل الروابط لما ندمج عميلين، بنحط "سهم" من المكرر للأصلي. أي جهاز لسه بيشتغل على القديم يفضل سليم.

## 2. Per-PC document number series
- **Problem:** two PCs offline both issue "INV-0042".
- **Idea:** each PC has a series letter (`INV-A-…`, `INV-B-…`); drafts have no number; the number is given at issue.
- **Watch out:** if the law needs one gapless series, use a single "numbering PC".
- 🇪🇬 كل جهاز له حرف في رقم الفاتورة، فمستحيل جهازين يطلعوا نفس الرقم وهما مفصولين.

## 3. Issued documents are snapshots, payments are events
- **Problem:** "last writer wins" on an invoice total is a financial bug.
- **Idea:** issuing freezes a snapshot; payments/allocations are append-only; balances are computed.
- 🇪🇬 الفاتورة بعد ما تطلع بتتجمّد زي الورق، والدفعات بتتسجل كأحداث، والرصيد بيتحسب مش بيتكتب.

## 4. Deterministic ids for automation results
- **Problem:** the same rule may run on two PCs and create two tasks.
- **Idea:** `id = hash(rule, trigger event, action index)` → the second insert merges into the first.
- 🇪🇬 الأتمتة لو اشتغلت مرتين بتطلع نفس الرقم، فالنتيجة واحدة مش اتنين.

## 5. Envelope hash covers the ops hash (erasable history)
- **Problem:** a signed hash-chained history cannot forget personal data, but the law may require it.
- **Idea:** sign the envelope that contains `ops_hash`; keep ops beside it; an authorised erase replaces ops with a
  redaction marker — chains and signatures still verify.
- 🇪🇬 السجل يفضل مختوم ومتسلسل، ومع ذلك نقدر نمسح بيانات شخص بشكل قانوني من غير ما نكسر الختم.

## 6. Attention items instead of dashboards
- **Problem:** dashboards full of charts don't say what to do.
- **Idea:** providers return items with *reason, amount at risk, urgency, next action*; ranked; snooze/done.
- 🇪🇬 الشاشة الرئيسية بتقولك "اعمل إيه دلوقتي ولي" مش بترسم رسومات.

## 7. `wa.me` / `mailto:` as the first messaging connector
- **Problem:** WhatsApp Business API is costly and slow to set up; in Egypt WhatsApp is the main channel.
- **Idea:** open a pre-filled WhatsApp/email message from a template; the user presses send; the program logs it.
- 🇪🇬 رسالة واتساب جاهزة بضغطة، من غير أي اشتراك.

## 8. Visibility flag from day one (portal-ready)
- **Idea:** every shareable record has `internal|client`; internal notes are a separate table; one serializer decides.
- 🇪🇬 من أول يوم كل حاجة معلّمة "داخلي" ولا "للعميل"، فبوابة العميل بعدين تبقى آمنة.

## 9. Derived local index
- **Idea:** search, timeline, attention and report caches live in a per-PC `index.db` rebuilt from the data; never
  synced, never backed up as truth.
- 🇪🇬 الفهارس بتتبني من البيانات على كل جهاز، ولو باظت بنبنيها تاني في ثواني.

## 10. Browser app mode as a desktop window
- **Idea:** `msedge --app=http://127.0.0.1:<port>` gives a native-looking window with zero dependencies.
- 🇪🇬 البرنامج يفتح في شباك لوحده كأنه برنامج ويندوز، من غير ما نزود أي مكتبة.

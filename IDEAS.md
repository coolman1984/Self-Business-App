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

## 11. Write-once records: "earliest write wins", whatever arrives first
- **Problem:** an issued invoice must never change, but two offline PCs may both "issue" the same document, and a rule like
  "lock after issue" depends on which change arrived first.
- **Idea:** keep only the earliest write per field by (clock, PC, number); remember the others as dropped and flag the row.
- **Where:** `replica.Registers.write(once=True)`, entities with `immutable=True`. **Proof:** `tests/test_resolvers.py` (all arrival orders).
- 🇪🇬 الفاتورة اللي اتصدرت أول واحدة هي اللي بتفضل في كل الأجهزة، ومهما كان ترتيب وصول التغييرات النتيجة واحدة.

## 12. Sign the hash of the operations, not the operations
- **Problem:** a signed history cannot forget; the law sometimes requires forgetting.
- **Idea:** the signature covers `ops_hash`; the operations live beside it; erasing replaces them, the chain still verifies.
- 🇪🇬 الختم بيتحط على بصمة التفاصيل مش على التفاصيل نفسها، فنقدر نمسح بيانات شخص من غير ما نكسر السجل.

## 13. Mutation-check the tests that guard security
- **Idea:** switch the protection off in a copy of the code and confirm that the tests fail; if they still pass, they prove nothing.
- 🇪🇬 قبل ما تصدّق اختبار أمان، اقفل الحماية بإيدك وشوف الاختبار بيفشل ولا لأ.

## 10. Browser app mode as a desktop window
- **Idea:** `msedge --app=http://127.0.0.1:<port>` gives a native-looking window with zero dependencies.
- 🇪🇬 البرنامج يفتح في شباك لوحده كأنه برنامج ويندوز، من غير ما نزود أي مكتبة.

## 14. Screens register themselves
- **Idea:** navigation, routes, quick-add items, palette commands and Today blocks are registered by each screen/module with one call each; no central file lists them.
- 🇪🇬 أي شاشة أو نشاط جديد بيسجّل نفسه في القايمة والبحث والإضافة السريعة بسطر واحد، من غير ما نعدّل في ملفات مركزية.

## 15. Errors as codes, texts by language
- **Idea:** the server says `E:name_required|A name is required`; each language file has `err.name_required`; a test compares the codes in Python with the dictionaries.
- 🇪🇬 السيرفر بيقول كود المشكلة، والشاشة بتقولها بلغة المستخدم. ومفيش رسالة إنجليزي بتظهر في وسط الكلام العربي.

## 16. Import = read → report → decide → backup → save → undo
- **Idea:** the analysis never saves; the report groups rows (new / same / similar / repeated / invalid); existing records only get their EMPTY fields filled; a backup is made first; every imported record carries the batch id so one click undoes it.
- 🇪🇬 الاستيراد بيوريك التقرير الأول، وميكتبش فوق حاجة موجودة، وبيعمل نسخة احتياطية، وتقدر ترجّعه كله بضغطة.

## 17. A theme preview is the theme
- **Idea:** because tokens hang on `[data-theme]` (not only on `<html>`), a swatch simply carries the attribute and shows the real theme, with no duplicated colours.
- 🇪🇬 مربع المعاينة بياخد نفس ألوان الشكل الحقيقي لأنه بيلبس نفس الخاصية، فمفيش ألوان مكررة.

## 18. Undo instead of "are you sure"
- **Idea:** finishing a task or deleting a record acts at once and offers *Undo* for 8 seconds; the undo is a new change, so history stays honest.
- 🇪🇬 بدل ما نسألك «متأكد؟» كل مرة، بنعمل الحاجة وندّيك زرار «تراجع».

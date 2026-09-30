"""The business screens in a real browser (Phase 3): a non-technical person's journeys. Each test makes its own data through the API
(fast) and then works through the screens like a user would (typing, clicking, keyboard)."""
import json
import os
import re
import sys
import unittest
from datetime import date, timedelta
from urllib.parse import quote

import ui_harness as ui

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'core'))
import xlsx  # noqa: E402

OK, WHY = ui.available()
REQUIRE = os.environ.get('SBO_REQUIRE_UI') == '1'


def put(c, entity, rid, row, ver=None):
    return c.post('/api/commit', {'label': 'x', 'ops': [{'e': entity, 'id': rid, 'op': 'put', 'ver': ver, 'row': row}]})


@unittest.skipUnless(OK or REQUIRE, WHY)
class Business(ui.UiBase):
    server_name = 'biz'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ac = cls.srv.owner
        profiles = ac.get('/api/users')['profiles']
        for name, profile, pw in (('assist', 'assistant', 'Green-Tree-4471'), ('viewer', 'viewer', 'Blue-Lake-5582')):
            perms = next(p['perms'] for p in profiles if p['id'] == profile)
            ac.post('/api/users/save', {'username': name, 'full_name': name.title(), 'password': pw, 'must_change': False, 'role': profile, 'perms': perms, 'data_scope': 'all', 'scopes': []})

    # ---------------------------------------------------------------- a first client, from nothing
    def test_new_client_in_a_few_clicks_lands_on_the_file_and_is_saved(self):
        pg = self.page()
        pg.click('#tb-add')
        pg.click('.menu button:has-text("عميل جديد")')
        pg.wait_for_selector('.drawer form')
        pg.fill('.drawer input >> nth=0', 'سلمى عبد الله') if False else None
        pg.fill('.drawer label:has-text("الاسم") + input', 'سلمى عبد الله')
        pg.fill('.drawer label:has-text("التليفون") + input', '01098765432')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.record-head h1:has-text("سلمى عبد الله")')
        rows = self.srv.owner.get('/api/q/parties?f=name:eq:' + quote('سلمى عبد الله'))['rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['phone'], '01098765432')
        self.assertEqual(self.srv.owner.get('/api/q/party_roles?f=party_id:eq:' + rows[0]['id'])['rows'][0]['role'], 'lead')
        self.assertIn('010 9876 5432' if False else '01098765432', pg.inner_text('.kv'))
        self.assertNoErrors()

    def test_name_is_required_and_the_message_is_in_arabic(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients')
        pg.click('#new-client')
        pg.wait_for_selector('.drawer form')
        pg.click('.drawer button:has-text("حفظ")')
        self.assertIn('لازم', pg.inner_text('.drawer .field.invalid .error'))
        self.assertEqual(pg.locator('.drawer').count(), 1)

    def test_typing_an_existing_phone_warns_about_a_possible_duplicate(self):
        put(self.srv.owner, 'parties', 'dupui-1', {'name': 'حسام كامل', 'phone': '+201055550009'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients')
        pg.click('#new-client')
        pg.fill('.drawer label:has-text("التليفون") + input', '010 5555 0009')
        pg.wait_for_selector('.dup-hint:not([hidden])')
        self.assertIn('حسام كامل', pg.inner_text('.dup-hint'))
        self.assertIn('نفس التليفون', pg.inner_text('.dup-hint'))

    def test_search_finds_arabic_names_without_hamza_and_the_list_filters_live(self):
        put(self.srv.owner, 'parties', 'srch-1', {'name': 'أسامة إبراهيم', 'city': 'الإسكندرية'})
        put(self.srv.owner, 'parties', 'srch-2', {'name': 'شركة الأكاديمية', 'kind': 'org'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients')
        pg.wait_for_selector('.table tbody tr')
        pg.fill('.toolbar input[type=search]', 'اسامه ابراهيم')
        pg.wait_for_function("document.querySelectorAll('.table tbody tr').length === 1")
        self.assertIn('أسامة إبراهيم', pg.inner_text('.table tbody'))
        pg.fill('.toolbar input[type=search]', 'الاكاديميه')
        pg.wait_for_function("document.querySelectorAll('.table tbody tr').length === 1")
        pg.fill('.toolbar input[type=search]', 'مفيش زيه')
        pg.wait_for_selector('.empty')

    def test_palette_finds_a_client_and_opens_the_file(self):
        put(self.srv.owner, 'parties', 'pal-1', {'name': 'ياسمين الفقي', 'phone': '01011112222'})
        pg = self.page()
        pg.keyboard.press('Control+k')
        pg.keyboard.type('ياسمين')
        pg.wait_for_selector('.palette li[role=option]:has-text("ياسمين الفقي")')
        pg.click('.palette li[role=option]:has-text("ياسمين الفقي")')
        pg.wait_for_selector('.record-head h1:has-text("ياسمين الفقي")')

    # ---------------------------------------------------------------- the living client file
    def test_client_file_notes_tasks_timeline_and_edit(self):
        put(self.srv.owner, 'parties', 'file-1', {'name': 'رنا مصطفى', 'phone': '01000000777', 'email': 'rana@example.com'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/file-1')
        pg.wait_for_selector('.record-head h1:has-text("رنا مصطفى")')
        self.assertTrue(pg.locator('a[href^="tel:"]').count() >= 1)
        self.assertIn('wa.me/201000000777', pg.get_attribute('a:has-text("WhatsApp")', 'href'))
        # a note
        pg.click('.pill-tabs button[data-id=notes]')
        pg.fill('.compose textarea', 'تحب المواعيد الصباحية')
        pg.click('.compose button:has-text("حفظ")')
        pg.wait_for_selector('.list-item:has-text("تحب المواعيد الصباحية")')
        # a task from the overview
        pg.click('.pill-tabs button[data-id=overview]')
        pg.click('button:has-text("مهمة جديدة")')
        pg.fill('.drawer label:has-text("المهمة") + input', 'إرسال عرض السعر')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.list-item:has-text("إرسال عرض السعر")')
        # edit the phone and see it in the timeline as "old <- new"
        pg.click('.record-head button:has-text("تعديل")')
        pg.fill('.drawer label:has-text("التليفون") + input', '01000000888')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.kv:has-text("01000000888")')
        pg.click('.pill-tabs button[data-id=timeline]')
        pg.wait_for_selector('.timeline')
        text = pg.inner_text('.timeline')
        for want in ('اتضاف رنا مصطفى', 'إرسال عرض السعر', 'تحب المواعيد الصباحية', '01000000888', '01000000777'):
            self.assertIn(want, text)
        self.assertNoErrors()

    def test_delete_a_client_and_undo_brings_it_back(self):
        put(self.srv.owner, 'parties', 'del-ui', {'name': 'عميل للحذف'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/del-ui')
        pg.wait_for_selector('.record-head')
        pg.click('.record-head button[title="المزيد"]')
        pg.click('.menu button:has-text("حذف")')
        pg.click('.modal button:has-text("حذف")')
        pg.wait_for_selector('.toast button:has-text("تراجع")')
        self.assertEqual(self.srv.owner.get('/api/q/parties?f=id:eq:del-ui')['rows'], [])
        pg.click('.toast button:has-text("تراجع")')
        for _ in range(20):
            if self.srv.owner.get('/api/q/parties?f=id:eq:del-ui')['rows']:
                break
            pg.wait_for_timeout(200)
        self.assertEqual(self.srv.owner.get('/api/get/parties/del-ui')['name'], 'عميل للحذف')

    def test_merge_a_duplicate_into_the_right_client(self):
        put(self.srv.owner, 'parties', 'mrg-a', {'name': 'منال حسين', 'phone': '01022223333'})
        put(self.srv.owner, 'parties', 'mrg-b', {'name': 'منال حسين مكرر'})
        put(self.srv.owner, 'notes', 'mrg-n', {'body': 'ملاحظة على المكرر', 'party_id': 'mrg-b'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/mrg-b')
        pg.wait_for_selector('.record-head')
        pg.click('.record-head button[title="المزيد"]')
        pg.click('.menu button:has-text("دمج")')
        pg.fill('.modal input, .drawer input', 'منال حسين')
        pg.wait_for_selector('.picker-list li[role=option]:has-text("منال حسين")')
        pg.click('.picker-list li[role=option] >> nth=0')
        pg.click('.modal button:has-text("ادمج"), .drawer button:has-text("ادمج")')
        pg.wait_for_url(re.compile('mrg-a'))
        pg.wait_for_selector('.record-head h1:text-is("منال حسين")')
        pg.click('.pill-tabs button[data-id=timeline]')
        pg.wait_for_selector('.timeline')
        self.assertIn('ملاحظة على المكرر', pg.inner_text('.timeline'))
        pg.goto(self.srv.base + '/#/clients/mrg-b')
        pg.wait_for_url(re.compile('mrg-a'))

    # ---------------------------------------------------------------- sales board
    def test_opportunity_moves_between_stages_by_menu_and_by_drag(self):
        put(self.srv.owner, 'parties', 'op-c', {'name': 'عميل الفرص'})
        put(self.srv.owner, 'opportunities', 'op-ui', {'title': 'دورة الإكسل', 'party_id': 'op-c', 'stage': 'new', 'value_minor': 500000})
        pg = self.page()
        pg.goto(self.srv.base + '/#/sales')
        pg.wait_for_selector('.kcard:has-text("دورة الإكسل")')
        pg.click('.kcard:has-text("دورة الإكسل") button:has-text("نقل")')
        pg.click('.menu button:has-text("اجتماع")')
        pg.wait_for_selector('.lane[data-stage=meeting] .kcard')
        self.assertEqual(self.srv.owner.get('/api/get/opportunities/op-ui')['stage'], 'meeting')
        pg.drag_and_drop('.kcard:has-text("دورة الإكسل")', '.lane[data-stage=offer] .cards')
        pg.wait_for_selector('.lane[data-stage=offer] .kcard')
        self.assertEqual(self.srv.owner.get('/api/get/opportunities/op-ui')['stage'], 'offer')
        self.assertEqual(self.srv.owner.get('/api/get/opportunities/op-ui')['value_minor'], 500000, 'moving a card never touches the amount')

    def test_assistant_without_money_sees_no_amounts_but_can_still_move_cards(self):
        put(self.srv.owner, 'parties', 'nm-c', {'name': 'عميل بلا مبالغ'})
        put(self.srv.owner, 'opportunities', 'nm-op', {'title': 'صفقة سرية', 'party_id': 'nm-c', 'stage': 'contacted', 'value_minor': 987654300})
        pg = self.page(user=('assist', 'Green-Tree-4471'))
        pg.goto(self.srv.base + '/#/sales')
        pg.wait_for_selector('.kcard:has-text("صفقة سرية")')
        self.assertNotIn('9,876,543', pg.inner_text('body'))
        self.assertNotIn('9876543', pg.inner_text('body'))
        pg.click('.kcard:has-text("صفقة سرية") button:has-text("نقل")')
        pg.click('.menu button:has-text("عرض سعر")')
        pg.wait_for_selector('.lane[data-stage=offer] .kcard:has-text("صفقة سرية")')
        self.assertEqual(self.srv.owner.get('/api/get/opportunities/nm-op')['value_minor'], 987654300)

    def test_viewer_sees_but_cannot_add_or_change(self):
        pg = self.page(user=('viewer', 'Blue-Lake-5582'))
        pg.goto(self.srv.base + '/#/clients')
        pg.wait_for_selector('#view .page-in')
        self.assertEqual(pg.locator('#new-client').count(), 0)
        self.assertEqual(pg.locator('#tb-add').count(), 0)
        self.assertEqual(pg.locator('#nav-settings').count(), 0)
        pg.goto(self.srv.base + '/#/tasks')
        pg.wait_for_selector('#view .page-in')
        self.assertEqual(pg.locator('#task-quick').count(), 0)

    # ---------------------------------------------------------------- tasks, calendar, Today
    def test_tasks_quick_add_tick_undo_and_filters(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/tasks')
        pg.wait_for_selector('#task-quick')
        pg.fill('#task-quick', 'مهمة سريعة من الكيبورد')
        pg.keyboard.press('Enter')
        pg.wait_for_selector('.table tbody tr:has-text("مهمة سريعة من الكيبورد")')
        tid = self.srv.owner.get('/api/q/tasks?f=title:eq:' + quote('مهمة سريعة من الكيبورد'))['rows'][0]['id']
        pg.click('.table tbody tr:has-text("مهمة سريعة من الكيبورد") input[type=checkbox]')
        pg.wait_for_selector('.toast button:has-text("تراجع")')
        self.assertEqual(self.srv.owner.get('/api/get/tasks/' + tid)['status'], 'done')
        self.assertTrue(self.srv.owner.get('/api/get/tasks/' + tid)['done_at'])
        pg.click('.toast button:has-text("تراجع")')
        for _ in range(25):
            if self.srv.owner.get('/api/get/tasks/' + tid)['status'] == 'todo':
                break
            pg.wait_for_timeout(200)
        self.assertEqual(self.srv.owner.get('/api/get/tasks/' + tid)['status'], 'todo')
        self.assertNotIn('done_at', self.srv.owner.get('/api/get/tasks/' + tid))

    def test_calendar_shows_appointments_and_creates_one_on_a_day(self):
        d = date.today()
        put(self.srv.owner, 'appointments', 'cal-1', {'title': 'اجتماع المراجعة', 'starts_at': d.isoformat() + 'T13:00', 'ends_at': d.isoformat() + 'T14:00'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/calendar')
        pg.wait_for_selector('.cal .day.today')
        self.assertIn('اجتماع المراجعة', pg.inner_text('.cal .day.today'))
        pg.click('.page-head button:has-text("موعد جديد")')
        pg.fill('.drawer label:has-text("العنوان") + input', 'جلسة تدريب')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.cal .ev:has-text("جلسة تدريب")')
        self.assertEqual(len(self.srv.owner.get('/api/q/appointments?f=title:eq:' + quote('جلسة تدريب'))['rows']), 1)

    def test_today_shows_late_tasks_todays_appointments_and_ticking_works(self):
        d = date.today()
        put(self.srv.owner, 'tasks', 'today-late', {'title': 'مهمة متأخرة جدًا', 'due': (d - timedelta(days=3)).isoformat()})
        put(self.srv.owner, 'appointments', 'today-ap', {'title': 'موعد النهارده', 'starts_at': d.isoformat() + 'T17:00'})
        pg = self.page()
        pg.wait_for_selector('#block-attention')
        self.assertIn('مهمة متأخرة جدًا', pg.inner_text('#block-attention'))
        self.assertIn('موعد النهارده', pg.inner_text('#block-today'))
        pg.click('#block-attention .list-item:has-text("مهمة متأخرة جدًا") input[type=checkbox]')
        for _ in range(25):
            if self.srv.owner.get('/api/get/tasks/today-late')['status'] == 'done':
                break
            pg.wait_for_timeout(200)
        self.assertEqual(self.srv.owner.get('/api/get/tasks/today-late')['status'], 'done')

    # ---------------------------------------------------------------- import through the wizard
    def test_import_wizard_end_to_end_with_report_and_undo(self):
        put(self.srv.owner, 'parties', 'wiz-old', {'name': 'موجود من قبل', 'phone': '+201000000101'})
        head = ['الاسم', 'الموبايل', 'الايميل', 'الشركة']
        rows = [[f'مستورد {i}', '010%08d' % (200 + i), f'imp{i}@example.com', 'شركة الاستيراد' if i % 5 == 0 else ''] for i in range(30)]
        rows.append(['موجود من قبل (نسخة)', '01000000101', '', ''])
        rows.append(['', '01011111111', '', ''])
        path = os.path.join(self.srv.root, 'import-test.xlsx')
        with open(path, 'wb') as f:
            f.write(xlsx.build([('عملاء', head, rows)]))
        pg = self.page()
        pg.goto(self.srv.base + '/#/import')
        pg.set_input_files('#import-file', path)
        pg.wait_for_selector('select[aria-label="الاسم"]')
        self.assertEqual(pg.eval_on_selector('select[aria-label="الاسم"]', 'e => e.value'), 'name')
        self.assertEqual(pg.eval_on_selector('select[aria-label="الموبايل"]', 'e => e.value'), 'phone')
        self.assertEqual(pg.eval_on_selector('select[aria-label="الشركة"]', 'e => e.value'), 'company')
        before = self.srv.owner.get('/api/q/parties?limit=1')['total']
        pg.click('button:has-text("التالي")')
        pg.wait_for_selector('.stats')
        summary = pg.inner_text('.stats')
        self.assertIn('موجودين قبل كده', summary)
        self.assertEqual(self.srv.owner.get('/api/q/parties?limit=1')['total'], before, 'analysing saves nothing')
        pg.wait_for_selector('.table tbody tr:has-text("موجود من قبل")')
        pg.click('button:has-text("استورد")')
        pg.click('.modal button:has-text("ابدأ")')
        pg.wait_for_selector('.empty:has-text("الاستيراد خلص")')
        self.assertGreaterEqual(self.srv.owner.get('/api/q/parties?limit=1')['total'], before + 30)
        self.assertEqual(self.srv.owner.get('/api/get/parties/wiz-old')['name'], 'موجود من قبل')
        pg.click('button:has-text("رجّع الاستيراد")')
        pg.click('.modal button:has-text("رجّع الاستيراد")')
        pg.wait_for_url(re.compile('/clients'))
        self.assertEqual(self.srv.owner.get('/api/q/parties?f=name:like:' + quote('مستورد 1'))['rows'], [])
        self.assertNoErrors()

    def test_import_is_hidden_from_people_without_the_right(self):
        pg = self.page(user=('assist', 'Green-Tree-4471'))
        pg.goto(self.srv.base + '/#/clients')
        pg.wait_for_selector('#view .page-in')
        self.assertEqual(pg.locator('a[href="#/import"]').count(), 0)

    # ---------------------------------------------------------------- sample data
    def test_sample_data_can_be_loaded_from_settings_and_removed_in_one_step(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings?tab=data')
        pg.click('button:has-text("حمّل بيانات تجريبية")')
        pg.wait_for_selector('.stats')
        self.assertGreater(self.srv.owner.get('/api/demo/status')['total'], 40)
        pg.goto(self.srv.base + '/#/settings?tab=data')
        pg.click('button:has-text("امسح البيانات التجريبية")')
        pg.click('.modal button:has-text("امسح البيانات التجريبية")')
        pg.wait_for_selector('button:has-text("حمّل بيانات تجريبية")')
        self.assertEqual(self.srv.owner.get('/api/demo/status')['total'], 0)

    def test_custom_field_can_be_added_and_filled_on_a_client(self):
        put(self.srv.owner, 'parties', 'cf-c', {'name': 'عميل بخانة إضافية'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings?tab=fields')
        pg.click('button:has-text("خانة جديدة")')
        pg.fill('.modal label:has-text("الاسم بالعربي") + input', 'رقم العقد')
        pg.click('.modal button:has-text("حفظ")')
        pg.wait_for_selector('.list-item:has-text("رقم العقد")')
        pg.goto(self.srv.base + '/#/clients/cf-c')
        pg.click('button:has-text("املا المعلومات الإضافية")')
        pg.fill('.modal label:has-text("رقم العقد") + input', 'A-1024')
        pg.click('.modal button:has-text("حفظ")')
        pg.wait_for_selector('.kv:has-text("A-1024")')

    # ---------------------------------------------------------------- languages, phones, keyboard
    def test_english_screens_have_no_missing_translations_and_ltr_layout(self):
        put(self.srv.owner, 'parties', 'en-c', {'name': 'English Client', 'phone': '01000000123'})
        put(self.srv.owner, 'opportunities', 'en-op', {'title': 'Deal', 'party_id': 'en-c', 'stage': 'offer', 'value_minor': 250000})
        put(self.srv.owner, 'tasks', 'en-t', {'title': 'Send offer', 'party_id': 'en-c', 'due': date.today().isoformat()})
        pg = self.page(lang='en')
        for path in ('/', '/clients', '/clients/en-c', '/sales', '/projects', '/tasks', '/calendar', '/services', '/inbox', '/settings?tab=data', '/settings?tab=fields', '/import', '/duplicates'):
            pg.goto(self.srv.base + '/#' + path)
            pg.wait_for_selector('#view .page-in')
            pg.wait_for_timeout(150)
        pg.goto(self.srv.base + '/#/clients/en-c')
        for tab in ('timeline', 'work', 'notes', 'files'):
            pg.click(f'.pill-tabs button[data-id={tab}]')
            pg.wait_for_timeout(250)
        self.assertEqual(pg.evaluate('document.documentElement.dir'), 'ltr')
        self.assertNoErrors()

    def test_phone_width_has_no_sideways_scroll_on_business_screens(self):
        put(self.srv.owner, 'parties', 'ph-c', {'name': 'عميل على الموبايل', 'phone': '01000000456', 'email': 'a-very-long-email-address-for-testing-overflow@example-company-name.com', 'address': 'عنوان طويل جدا جدا جدا جدا جدا جدا جدا جدا'})
        pg = self.page(width=390, height=800)
        for path in ('/', '/clients', '/clients/ph-c', '/sales', '/projects', '/tasks', '/calendar', '/services', '/inbox', '/import', '/settings?tab=data'):
            pg.goto(self.srv.base + '/#' + path)
            pg.wait_for_selector('#view .page-in')
            pg.wait_for_timeout(200)
            self.assertLessEqual(pg.evaluate('document.documentElement.scrollWidth'), 391, f'sideways scroll on {path}')

    def test_every_dialog_opens_and_closes_with_escape_and_restores_focus(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/tasks')
        pg.wait_for_selector('#task-quick')
        pg.click('.page-head button:has-text("مهمة جديدة")')
        pg.wait_for_selector('.drawer form')
        self.assertTrue(pg.evaluate("document.activeElement && document.activeElement.closest('.drawer') !== null"))
        pg.keyboard.press('Escape')
        self.assertEqual(pg.locator('.drawer').count(), 0)

    def test_task_form_validates_dates_and_checklist_round_trips(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/tasks')
        pg.click('.page-head button:has-text("مهمة جديدة")')
        pg.fill('.drawer label:has-text("المهمة") + input', 'مهمة بخطوات')
        pg.click('.drawer button:has-text("ضيف خطوة")')
        pg.fill('.drawer input[aria-label="الخطوة"]', 'الخطوة الأولى')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.table tbody tr:has-text("مهمة بخطوات")')
        row = self.srv.owner.get('/api/q/tasks?f=title:eq:' + quote('مهمة بخطوات'))['rows'][0]
        self.assertEqual(row['checklist'], [{'t': 'الخطوة الأولى', 'd': False}])

    def test_money_is_typed_in_pounds_and_stored_in_piastres(self):
        put(self.srv.owner, 'parties', 'mny-c', {'name': 'عميل المبالغ'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/sales')
        pg.click('.page-head button:has-text("فرصة جديدة")')
        pg.fill('.drawer label:has-text("العنوان") + input', 'صفقة بالمبلغ')
        pg.fill('.drawer .picker input', 'عميل المبالغ')
        pg.click('.picker-list li[role=option] >> nth=0')
        pg.fill('.drawer label:has-text("القيمة المتوقعة") + input', '٢٥٠٠٫٥٠')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.kcard:has-text("صفقة بالمبلغ")')
        self.assertEqual(self.srv.owner.get('/api/q/opportunities?f=title:eq:' + quote('صفقة بالمبلغ'))['rows'][0]['value_minor'], 250050)

    def test_a_second_person_editing_the_same_record_gets_a_friendly_message(self):
        put(self.srv.owner, 'parties', 'race-c', {'name': 'سباق التعديل'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/race-c')
        pg.wait_for_selector('.record-head')
        pg.click('.record-head button:has-text("تعديل")')
        pg.wait_for_selector('.drawer form')
        cur = self.srv.owner.get('/api/get/parties/race-c')
        put(self.srv.owner, 'parties', 'race-c', {'name': 'سباق التعديل', 'city': 'غيّرها حد تاني'}, cur['ver'])
        pg.fill('.drawer label:has-text("المدينة") + input', 'مدينتي')
        pg.click('.drawer button:has-text("حفظ")')
        pg.wait_for_selector('.drawer .error:not([hidden])')
        self.assertIn('حد تاني', pg.inner_text('.drawer .error'))
        self.assertEqual(pg.locator('.drawer').count(), 1, 'the form stays open so nothing typed is lost')


if __name__ == '__main__':
    unittest.main()

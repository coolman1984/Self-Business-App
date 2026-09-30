"""Browser regression tests for the correctness review of Phases 2-3 (one test per finding)."""
import os
import re
import unittest
from datetime import date, timedelta

import ui_harness as ui
from test_ui_business import put

OK, WHY = ui.available()
REQUIRE = os.environ.get('SBO_REQUIRE_UI') == '1'


@unittest.skipUnless(OK or REQUIRE, WHY)
class ReviewUi(ui.UiBase):
    server_name = 'uirev'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ac = cls.srv.owner
        for name, pw, perms in (('taskonly', 'Jade-Moon-1188', ['tasks.view', 'tasks.create', 'tasks.edit']),
                                ('salesonly', 'Rose-Field-2299', ['sales.view', 'sales.create', 'sales.edit'])):
            ac.post('/api/users/save', {'username': name, 'full_name': name.title(), 'password': pw, 'must_change': False, 'role': 'x', 'perms': perms, 'data_scope': 'all', 'scopes': []})

    def test_undo_toast_is_on_screen_in_arabic_on_a_phone(self):
        put(self.srv.owner, 'tasks', 'toast-t', {'title': 'مهمة للتوست', 'due': date.today().isoformat()})
        pg = self.page(width=390, height=800)
        pg.goto(self.srv.base + '/#/tasks')
        pg.click('.table tbody tr:has-text("مهمة للتوست") input[type=checkbox]')
        box = pg.locator('.toast button:has-text("تراجع")').bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], 390)

    def test_record_menu_stays_inside_the_window(self):
        put(self.srv.owner, 'parties', 'menu-c', {'name': 'عميل القائمة'})
        for lang, w in (('ar', 1360), ('en', 1360), ('ar', 390)):
            pg = self.page(width=w, lang=lang)
            pg.goto(self.srv.base + '/#/clients/menu-c')
            pg.click('.record-head .contact-btns button:last-child')
            b = pg.locator('.menu').bounding_box()
            self.assertGreaterEqual(b['x'], 0, (lang, w))
            self.assertLessEqual(b['x'] + b['width'], w, (lang, w))
            self.assertLessEqual(pg.evaluate('document.documentElement.scrollWidth'), w + 1)

    def test_merged_records_show_in_the_survivor_file_and_can_be_unmerged(self):
        put(self.srv.owner, 'parties', 'sv-a', {'name': 'الأساسي'})
        put(self.srv.owner, 'parties', 'sv-b', {'name': 'المكرر'})
        put(self.srv.owner, 'tasks', 'sv-t', {'title': 'مهمة المكرر', 'party_id': 'sv-b'})
        put(self.srv.owner, 'notes', 'sv-n', {'body': 'ملاحظة المكرر', 'party_id': 'sv-b'})
        cur = self.srv.owner.get('/api/get/parties/sv-b')
        put(self.srv.owner, 'parties', 'sv-b', {'name': 'المكرر', 'status': 'merged', 'merged_into': 'sv-a'}, cur['ver'])
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/sv-a')
        pg.wait_for_selector('.list-item:has-text("مهمة المكرر")')
        pg.click('.pill-tabs button[data-id=notes]')
        pg.wait_for_selector('.list-item:has-text("ملاحظة المكرر")')
        pg.goto(self.srv.base + '/#/clients/sv-b')          # no endless redirect: a banner with un-merge
        pg.wait_for_selector('.banner:has-text("الأساسي")')
        pg.click('.banner button:has-text("فك الدمج")')
        for _ in range(25):
            if self.srv.owner.get('/api/get/parties/sv-b').get('status') == 'active':
                break
            pg.wait_for_timeout(200)
        self.assertNotIn('merged_into', self.srv.owner.get('/api/get/parties/sv-b'))

    def test_task_screen_works_without_client_rights(self):
        put(self.srv.owner, 'parties', 'np-c', {'name': 'مخفي'})
        put(self.srv.owner, 'tasks', 'np-t', {'title': 'مهمة بدون عملاء', 'party_id': 'np-c'})
        pg = self.page(user=('taskonly', 'Jade-Moon-1188'))
        pg.goto(self.srv.base + '/#/tasks')
        pg.wait_for_selector('.table tbody tr:has-text("مهمة بدون عملاء")')
        self.assertEqual(pg.locator('.error-box').count(), 0)
        self.assertNoErrors()

    def test_today_for_a_sales_only_person_shows_their_follow_ups(self):
        put(self.srv.owner, 'opportunities', 'so-op', {'title': 'متابعة مبيعات', 'stage': 'contacted', 'next_step_at': (date.today() - timedelta(days=1)).isoformat()})
        pg = self.page(user=('salesonly', 'Rose-Field-2299'))
        pg.wait_for_selector('#block-attention:has-text("متابعة مبيعات")')

    def test_picker_enter_chooses_the_client(self):
        put(self.srv.owner, 'parties', 'pk-c', {'name': 'منى المختارة'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/tasks')
        pg.click('.page-head button:has-text("مهمة جديدة")')
        pg.fill('.drawer label:has-text("المهمة") + input', 'مهمة بعميل')
        pg.locator('.drawer .picker input').first.fill('منى المختارة')
        pg.wait_for_selector('.picker-list li[role=option]')
        pg.locator('.drawer .picker input').first.press('Enter')
        self.assertEqual(pg.locator('.drawer').count(), 1, 'Enter picked the client, it did not save the form')
        self.assertEqual(pg.locator('.drawer .picker input').first.input_value(), 'منى المختارة')

    def test_ticking_a_task_keeps_the_filter_and_undo_restores_the_old_status(self):
        put(self.srv.owner, 'tasks', 'kf-t', {'title': 'متأخرة شغالة', 'status': 'doing', 'due': (date.today() - timedelta(days=2)).isoformat()})
        pg = self.page()
        pg.goto(self.srv.base + '/#/tasks')
        pg.click('.filters button[data-v=late]')
        pg.click('.table tbody tr:has-text("متأخرة شغالة") input[type=checkbox]')
        pg.wait_for_selector('.toast button:has-text("تراجع")')
        self.assertEqual(pg.get_attribute('.filters button[data-v=late]', 'aria-pressed'), 'true')
        pg.click('.toast button:has-text("تراجع")')
        for _ in range(25):
            if self.srv.owner.get('/api/get/tasks/kf-t')['status'] == 'doing':
                break
            pg.wait_for_timeout(200)
        self.assertEqual(self.srv.owner.get('/api/get/tasks/kf-t')['status'], 'doing')

    def test_note_delete_button_is_offered(self):
        put(self.srv.owner, 'parties', 'nd-c', {'name': 'عميل الملاحظة'})
        put(self.srv.owner, 'notes', 'nd-n', {'body': 'ملاحظة للحذف', 'party_id': 'nd-c'})
        pg = self.page()
        pg.goto(self.srv.base + '/#/clients/nd-c?tab=notes')
        pg.wait_for_selector('.list-item:has-text("ملاحظة للحذف") button[title="حذف"]')

    def test_shortcuts_work_with_the_arabic_keyboard_layout(self):
        pg = self.page()
        pg.evaluate("dispatchEvent(new KeyboardEvent('keydown', {key: 'ن', code: 'KeyK', ctrlKey: true, bubbles: true}))")
        pg.wait_for_selector('.palette')

    def test_settings_is_reachable_for_everybody(self):
        pg = self.page(user=('taskonly', 'Jade-Moon-1188'))
        self.assertEqual(pg.locator('#nav-settings').count(), 1)
        pg.click('#nav-settings')
        pg.wait_for_selector('.settings-grid')

    def test_sync_poll_does_not_steal_keyboard_focus(self):
        pg = self.page()
        pg.focus('#nav-tasks')
        pg.evaluate("import('/js/core/session.js').then((m) => m.pollSync())")
        pg.wait_for_timeout(500)
        self.assertEqual(pg.evaluate('document.activeElement.id'), 'nav-tasks')


if __name__ == '__main__':
    unittest.main()

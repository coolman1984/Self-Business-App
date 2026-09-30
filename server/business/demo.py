"""Demo data: a small, believable business so a new user can try every screen, removable in one step.

Every demo record has sample = 1 and a fixed id (demo-...). Removing demo data deletes exactly the records that are still
untouched; anything the person edited is kept and simply stops being "demo"."""
from datetime import date, datetime, timedelta

import query as query_mod
from store import BadRequest

ENTITIES = ['party_roles', 'party_relations', 'notes', 'activities', 'tasks', 'appointments', 'inbox', 'opportunities', 'projects', 'services', 'parties']

PEOPLE = {
    'ar': [('منى إبراهيم', 'client', 'القاهرة'), ('أحمد سمير', 'lead', 'الجيزة'), ('سارة عادل', 'client', 'الإسكندرية'), ('كريم حسن', 'lead', 'القاهرة'),
           ('هدى فؤاد', 'client', 'المنصورة'), ('طارق منصور', 'partner', 'القاهرة')],
    'en': [('Mona Ibrahim', 'client', 'Cairo'), ('Ahmed Samir', 'lead', 'Giza'), ('Sara Adel', 'client', 'Alexandria'), ('Karim Hassan', 'lead', 'Cairo'),
           ('Hoda Fouad', 'client', 'Mansoura'), ('Tarek Mansour', 'partner', 'Cairo')],
}
ORGS = {'ar': [('أكاديمية النور', 'client'), ('شركة الأفق للحلول', 'client')], 'en': [('Nour Academy', 'client'), ('Horizon Solutions', 'client')]}
SERVICES = {
    'trainer': {'ar': [('ساعة تدريب', 'hour', 400), ('ورشة عمل يوم كامل', 'session', 3000), ('برنامج تدريبي كامل', 'project', 18000)],
                'en': [('Training hour', 'hour', 400), ('Full-day workshop', 'session', 3000), ('Complete training programme', 'project', 18000)]},
    'freelancer': {'ar': [('تصميم شعار', 'project', 2500), ('ساعة عمل', 'hour', 300), ('صيانة شهرية', 'month', 1500)],
                   'en': [('Logo design', 'project', 2500), ('Working hour', 'hour', 300), ('Monthly upkeep', 'month', 1500)]},
    'software': {'ar': [('تركيب وتشغيل النظام', 'project', 12000), ('زيارة دعم', 'item', 800), ('اشتراك صيانة شهري', 'month', 2000)],
                 'en': [('System installation', 'project', 12000), ('Support visit', 'item', 800), ('Monthly maintenance', 'month', 2000)]},
}
GENERAL = {'ar': [('استشارة', 'hour', 500), ('خدمة أساسية', 'item', 1000), ('اشتراك شهري', 'month', 1500)],
           'en': [('Consultation', 'hour', 500), ('Standard service', 'item', 1000), ('Monthly plan', 'month', 1500)]}
TEXT = {
    'ar': {'opp': ['برنامج تدريب للفريق', 'موقع تعريفي للشركة', 'عقد صيانة سنوي', 'ورشة يوم واحد', 'استشارة تسويقية'],
           'proj': ['تدريب مبيعات — الدفعة الأولى', 'تجديد الهوية البصرية', 'تركيب النظام الجديد'],
           'task': ['الاتصال بـ{0} لتأكيد الموعد', 'تجهيز العرض المبدئي', 'مراجعة المحتوى النهائي', 'إرسال متابعة بعد الاجتماع', 'تحديث الجدول الشهري', 'تسليم النسخة الأولى', 'الرد على استفسار الأسعار'],
           'appt': ['اجتماع تعارف مع {0}', 'جلسة عمل — مراجعة التقدم', 'مكالمة متابعة', 'زيارة موقع العميل'],
           'note': ['يفضّل التواصل بعد الساعة الرابعة عصرًا.', 'طلبت خصمًا على الباقة السنوية، ننتظر ردها.', 'العميل مهتم بخدمة التدريب عن بُعد.', 'شخص مهذب ودقيق في المواعيد.'],
           'act': ['اتصال هاتفي — ناقشنا الاحتياجات', 'اجتماع سريع — عرض الأسعار', 'رسالة واتساب — أرسلنا التفاصيل'],
           'inbox': ['أتصل بالأستاذ ماجد بخصوص عرض الأسعار', 'فكرة: باقة تدريب للشركات الصغيرة'], 'tag': 'تجريبي'},
    'en': {'opp': ['Team training programme', 'Company website', 'Yearly maintenance contract', 'One-day workshop', 'Marketing consultation'],
           'proj': ['Sales training - first group', 'Brand refresh', 'New system installation'],
           'task': ['Call {0} to confirm the appointment', 'Prepare the first offer', 'Review the final content', 'Send a follow-up after the meeting', 'Update the monthly schedule', 'Deliver the first version', 'Answer the price question'],
           'appt': ['Intro meeting with {0}', 'Working session - progress review', 'Follow-up call', 'Visit the client site'],
           'note': ['Prefers to be contacted after 4 pm.', 'Asked for a discount on the yearly plan, waiting for a reply.', 'Interested in remote training.', 'Polite and punctual.'],
           'act': ['Phone call - discussed the needs', 'Quick meeting - presented prices', 'WhatsApp message - sent the details'],
           'inbox': ['Call Mr Maged about the price offer', 'Idea: training bundle for small companies'], 'tag': 'demo'},
}


def _d(days, hour=None, minute=0):
    d = date.today() + timedelta(days=days)
    return d.isoformat() if hour is None else f'{d.isoformat()}T{hour:02d}:{minute:02d}'


def status(app, u):
    access = query_mod.access_for(u)
    counts = {}
    for e in ENTITIES:
        counts[e] = query_mod.run(app.store, e, access, [('sample', 'eq', 1)], limit=1)['total']
    return {'counts': counts, 'total': sum(counts.values())}


def build(lang='ar', kinds=()):
    T = TEXT['en' if lang == 'en' else 'ar']
    lg = 'en' if lang == 'en' else 'ar'
    P = []
    ops = []

    def put(entity, rid, row):
        ops.append({'e': entity, 'id': rid, 'op': 'put', 'row': {**row, 'sample': True}})
    people = PEOPLE[lg]
    for n, (name, role, city) in enumerate(people, 1):
        pid = f'demo-p{n}'
        P.append(pid)
        put('parties', pid, {'kind': 'person', 'name': name, 'phone': f'+2010000000{n:02d}', 'email': f'demo{n}@example.com', 'city': city, 'status': 'active', 'tags': T['tag']})
        put('party_roles', f'{pid}:{role}', {'party_id': pid, 'role': role, 'since': _d(-30 * n)})
    orgs = ORGS[lg]
    for n, (name, role) in enumerate(orgs, 1):
        oid = f'demo-o{n}'
        put('parties', oid, {'kind': 'org', 'name': name, 'phone': f'+2022222220{n}', 'email': f'info{n}@example.com', 'city': people[0][2], 'status': 'active', 'tags': T['tag']})
        put('party_roles', f'{oid}:{role}', {'party_id': oid, 'role': role, 'since': _d(-90)})
    put('party_relations', 'demo-p1:demo-o1:works_at', {'from_party': 'demo-p1', 'to_party': 'demo-o1', 'kind': 'works_at', 'title': 'Training manager' if lg == 'en' else 'مديرة التدريب'})
    put('party_relations', 'demo-p6:demo-o2:contact_for', {'from_party': 'demo-p6', 'to_party': 'demo-o2', 'kind': 'contact_for'})
    for n, (name, unit, price) in enumerate(SERVICES.get(next((k for k in kinds if k in SERVICES), ''), GENERAL)[lg], 1):
        put('services', f'demo-s{n}', {'name': name, 'unit': unit, 'price_minor': price * 100, 'currency': 'EGP', 'active': True})
    stages = ['new', 'contacted', 'meeting', 'offer', 'won']
    values = [4500, 12000, 30000, 18000, 9000]
    for n, title in enumerate(T['opp']):
        row = {'party_id': f'demo-p{n + 2 if n < 4 else 1}', 'title': title, 'stage': stages[n], 'value_minor': values[n] * 100, 'currency': 'EGP', 'source': ['referral', 'social', 'website', 'event', 'referral'][n],
               'expected_close': _d(7 * (n + 1)), 'probability': [10, 30, 50, 70, 100][n]}
        if n in (1, 2):
            row.update(next_step='اتصال متابعة' if lg == 'ar' else 'Follow-up call', next_step_at=_d(-n + 1))
        put('opportunities', f'demo-op{n + 1}', row)
    projs = [('active', -20, 25, 'demo-p1', 25000), ('planned', 5, 40, 'demo-o2', 60000), ('done', -60, -10, 'demo-p3', 8000)]
    for n, title in enumerate(T['proj']):
        st, a, b, party, budget = projs[n]
        put('projects', f'demo-pr{n + 1}', {'party_id': party, 'title': title, 'status': st, 'start': _d(a), 'due': _d(b), 'budget_minor': budget * 100, 'currency': 'EGP', 'billing_mode': 'fixed'})
    due = [-3, -1, 0, 0, 1, 3, 5]
    for n, title in enumerate(T['task']):
        party = f'demo-p{(n % 5) + 1}'
        put('tasks', f'demo-t{n + 1}', {'title': title.format(people[n % 5][0]), 'party_id': party, 'project_id': 'demo-pr1' if n % 3 == 0 else None, 'due': _d(due[n]),
                                       'priority': ['high', 'normal', 'urgent', 'normal', 'low', 'normal', 'high'][n], 'status': ['todo', 'doing', 'todo', 'waiting', 'todo', 'todo', 'todo'][n],
                                       'kind': 'follow_up' if n in (0, 3) else 'task'})
    slots = [(0, 15, 0), (0, 18, 30), (1, 11, 0), (3, 10, 0)]
    for n, title in enumerate(T['appt']):
        dd, h, m = slots[n]
        put('appointments', f'demo-a{n + 1}', {'title': title.format(people[1][0]), 'starts_at': _d(dd, h, m), 'ends_at': _d(dd, h + 1, m), 'kind': ['meeting', 'session', 'call', 'visit'][n],
                                              'party_id': f'demo-p{n + 1}', 'status': 'scheduled', 'location': 'Zoom' if n == 2 else ('مكتب العميل' if lg == 'ar' else 'Client office')})
    for n, body in enumerate(T['note']):
        put('notes', f'demo-n{n + 1}', {'body': body, 'party_id': f'demo-p{n + 1}', 'subject_ref': f'parties:demo-p{n + 1}', 'pinned': n == 0})
    for n, summary in enumerate(T['act']):
        put('activities', f'demo-ac{n + 1}', {'kind': ['call', 'meeting', 'message'][n], 'at': _d(-n - 1, 12, 0), 'party_id': f'demo-p{n + 1}', 'summary': summary, 'duration_min': [12, 30, None][n]})
    for n, text in enumerate(T['inbox']):
        put('inbox', f'demo-i{n + 1}', {'text': text, 'status': 'new'})
    return ops


def load(app, u, ip, lang='ar', kinds=()):
    if status(app, u)['total']:
        raise BadRequest('E:demo_exists|Demo data is already loaded.')
    ops = [o for o in build(lang, kinds) if not app.store.get(o['e'], o['id'])]      # a record kept from an earlier demo stays as it is
    guard = app.commit_guard(u)
    for i in range(0, len(ops), 150):
        app.store.commit(u['username'], ip, 'Load demo data', ops[i:i + 150], guard=guard, user_id=u['id'])
    return status(app, u)


def remove(app, u, ip):
    """Deletes the untouched demo records; edited ones stay and lose the demo mark."""
    access = query_mod.access_for(u)
    guard = app.commit_guard(u)
    removed = kept = 0
    for e in ENTITIES:
        rows = query_mod.run(app.store, e, access, [('sample', 'eq', 1)], limit=500)['rows']
        ops = []
        for r in rows:
            if r['ver'] == 1:
                ops.append({'e': e, 'id': r['id'], 'op': 'del', 'ver': r['ver']})
                removed += 1
            else:
                row = {k: v for k, v in r.items() if not k.startswith('_') and k not in ('id', 'ver', 'sample')}
                ops.append({'e': e, 'id': r['id'], 'op': 'put', 'ver': r['ver'], 'row': row})
                kept += 1
        for i in range(0, len(ops), 150):
            app.store.commit(u['username'], ip, 'Remove demo data', ops[i:i + 150], guard=guard, user_id=u['id'])
    return {'removed': removed, 'kept': kept}

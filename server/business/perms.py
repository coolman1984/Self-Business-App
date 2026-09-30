"""Permission groups and ready-made profiles of the business layer (labels are English; the screens translate `perm.<name>`)."""
from permissions import register_group, register_profile, ALL


def register_all():
    register_group('People and companies', [('clients.view', 'See people and companies'), ('clients.create', 'Add people and companies'),
                                            ('clients.edit', 'Change people and companies'), ('clients.delete', 'Delete people and companies')])
    register_group('Sales', [('sales.view', 'See opportunities'), ('sales.create', 'Add opportunities'), ('sales.edit', 'Change opportunities'),
                             ('sales.delete', 'Delete opportunities')])
    register_group('Projects', [('projects.view', 'See projects'), ('projects.create', 'Add projects'), ('projects.edit', 'Change projects'),
                                ('projects.delete', 'Delete projects')])
    register_group('Tasks and inbox', [('tasks.view', 'See tasks and the inbox'), ('tasks.create', 'Add tasks'), ('tasks.edit', 'Change tasks'),
                                       ('tasks.delete', 'Delete tasks')])
    register_group('Calendar', [('calendar.view', 'See appointments'), ('calendar.create', 'Add appointments'), ('calendar.edit', 'Change appointments'),
                                ('calendar.delete', 'Delete appointments')])
    register_group('Notes and follow-ups', [('notes.view', 'See notes and follow-ups'), ('notes.create', 'Write notes and follow-ups'),
                                            ('notes.edit', 'Change notes'), ('notes.delete', 'Delete notes')])
    register_group('Services', [('services.view', 'See services'), ('services.create', 'Add services'), ('services.edit', 'Change services'),
                                ('services.delete', 'Delete services')])
    register_group('Files', [('files.upload', 'Attach files'), ('files.download', 'Open and download files')])

    def work(edit=True, delete=False, sensitive=False, money=False):
        ps = [p for p in ALL if p.split('.')[0] in ('clients', 'sales', 'projects', 'tasks', 'calendar', 'notes', 'services', 'files')]
        if not edit:
            ps = [p for p in ps if p.endswith('.view') or p == 'files.download']
        if not delete:
            ps = [p for p in ps if not p.endswith('.delete')]
        extra = (['data.sensitive'] if sensitive else []) + (['money.view'] if money else []) + ['print', 'export.excel'] * bool(edit)
        return ps + extra

    register_profile('team', 'Team member (sees money)', lambda: work(True, False, False, True))
    register_profile('assistant', 'Assistant (no money)', lambda: work(True, False, False, False))
    register_profile('viewer', 'View only', lambda: work(False, False, False, False))

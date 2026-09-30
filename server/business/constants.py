"""Words of the business layer that both the server (validation, Today, demo) and the screens share.
The screens receive them from /api/business/meta and translate every id with the keys `<group>.<id>` (a test checks that
every id has an Arabic and an English text)."""

PARTY_KINDS = ['person', 'org']
PARTY_STATUS = ['active', 'archived', 'merged']
ROLES = ['lead', 'client', 'vendor', 'partner', 'student', 'other']          # modules add more (student, centre ...)
RELATION_KINDS = ['works_at', 'contact_for', 'owner_of', 'family_of']
STAGES = ['new', 'contacted', 'meeting', 'offer', 'won', 'lost']             # sales pipeline, in order
OPEN_STAGES = ['new', 'contacted', 'meeting', 'offer']
PROJECT_STATUS = ['planned', 'active', 'paused', 'done', 'cancelled']
BILLING_MODES = ['fixed', 'hourly', 'milestone', 'retainer']
TASK_STATUS = ['todo', 'doing', 'waiting', 'done', 'cancelled']
OPEN_TASK = ['todo', 'doing', 'waiting']
TASK_PRIORITY = ['low', 'normal', 'high', 'urgent']
TASK_KINDS = ['task', 'follow_up', 'call']
APPOINTMENT_KINDS = ['meeting', 'call', 'session', 'visit', 'other']
APPOINTMENT_STATUS = ['scheduled', 'done', 'cancelled']
ACTIVITY_KINDS = ['call', 'meeting', 'message', 'email', 'visit']
SOURCES = ['referral', 'social', 'website', 'walk_in', 'event', 'other']
SERVICE_UNITS = ['hour', 'session', 'project', 'month', 'item']
FIELD_TYPES = ['text', 'number', 'date', 'choice']
CUSTOMIZABLE = ['parties', 'projects', 'opportunities']

META = {
    'partyKinds': PARTY_KINDS, 'roles': ROLES, 'relationKinds': RELATION_KINDS, 'stages': STAGES, 'openStages': OPEN_STAGES,
    'projectStatus': PROJECT_STATUS, 'billingModes': BILLING_MODES, 'taskStatus': TASK_STATUS, 'taskPriority': TASK_PRIORITY,
    'taskKinds': TASK_KINDS, 'appointmentKinds': APPOINTMENT_KINDS, 'appointmentStatus': APPOINTMENT_STATUS,
    'activityKinds': ACTIVITY_KINDS, 'sources': SOURCES, 'serviceUnits': SERVICE_UNITS, 'fieldTypes': FIELD_TYPES, 'customizable': CUSTOMIZABLE,
}

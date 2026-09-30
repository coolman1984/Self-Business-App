// Inbox: quick thoughts captured in a second, turned into a task, a client or a note when there is time.
import { h } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { card, button, emptyState, pageHeader } from '../ui/kit.js';
import { toast } from '../ui/overlay.js';
import { ago } from '../core/format.js';
import { queryAll, updateRecord } from '../core/domain.js';
import { go } from '../core/router.js';
import { captureDialog, taskDialog, partyDialog } from './dialogs.js';

export async function inboxView() {
  const rows = await queryAll('inbox', { filters: [['status', 'eq', 'new']], sort: 'rowid', desc: true });
  const reload = () => go('/inbox?r=' + Date.now());
  const finish = async (x) => { await updateRecord(t('inbox.done'), 'inbox', x, { status: 'done' }); reload(); };
  return h('div', pageHeader(t('nav.inbox'), { sub: t('inbox.sub'), actions: [can('tasks.create') ? button(t('inbox.capture'), { kind: 'primary', ico: 'plus', onClick: () => captureDialog(reload) }) : null] }),
    rows.length ? card({}, ...rows.map((x) => h('div', { class: 'list-item', style: { alignItems: 'flex-start' } }, h('div', { class: 'grow' }, h('p', { style: { whiteSpace: 'pre-wrap' } }, x.text), h('div', { class: 'muted small' }, ago(x._created))),
      h('div', { class: 'row wrap' },
        can('tasks.create') ? button(t('inbox.to.task'), { small: true, ico: 'square-check-big', onClick: () => taskDialog(null, async () => { await finish(x); }, { title: x.text.split('\n')[0].slice(0, 120), notes: x.text.length > 120 ? x.text : undefined }) }) : null,
        can('clients.create') ? button(t('inbox.to.client'), { small: true, ico: 'user-plus', onClick: () => partyDialog(null, async () => { await finish(x); }, { name: x.text.split('\n')[0].slice(0, 100) }) }) : null,
        can('tasks.edit') ? button(t('inbox.done'), { small: true, kind: 'ghost', ico: 'check', onClick: () => finish(x) }) : null)))) :
      emptyState({ ico: 'inbox', title: t('inbox.empty.title'), text: t('inbox.empty.text') }));
}

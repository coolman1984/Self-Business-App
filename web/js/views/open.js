// Opens any record from a search hit: people and projects have pages, the rest open their edit form.
import { go, refresh } from '../core/router.js';
import { getRecord, recordPath } from '../core/domain.js';

export async function openRecord(entity, id) {
  const d = await import('./dialogs.js');
  if (entity === 'parties' || entity === 'projects') return go(recordPath(entity, id));
  const row = await getRecord(entity, id);
  const table = { tasks: d.taskDialog, opportunities: d.opportunityDialog, appointments: d.appointmentDialog, services: d.serviceDialog, activities: d.activityDialog };
  if (table[entity]) return table[entity](row, () => refresh());
  if (row.party_id) return go(recordPath('parties', row.party_id));
  return go(recordPath(entity, id));
}

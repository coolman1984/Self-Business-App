import { h } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { can } from '../core/session.js';
import { card, chip, button, emptyState, pageHeader, table } from '../ui/kit.js';
import { money } from '../core/format.js';
import { queryAll, enumText } from '../core/domain.js';
import { refresh } from '../core/router.js';
import { serviceDialog } from './dialogs.js';

export async function servicesView() {
  const rows = await queryAll('services', { sort: 'name' });
  const reload = () => refresh();
  return h('div', pageHeader(t('nav.services'), { sub: t('services.sub'), actions: [can('services.create') ? button(t('service.new'), { kind: 'primary', ico: 'plus', onClick: () => serviceDialog(null, reload) }) : null] }),
    rows.length ? card({ class: 'flush' }, table([
      { key: 'name', label: t('f.service'), render: (s) => h('div', h('b', s.name), s.description ? h('div', { class: 'muted small' }, s.description) : null) },
      { key: 'unit', label: t('f.unit'), render: (s) => enumText('services', 'unit', s.unit) || '' },
      ...(can('money.view') ? [{ key: 'price', label: t('f.price'), num: true, render: (s) => (s.price_minor != null ? money(s.price_minor) : '') }] : []),
      { key: 'active', label: t('f.offered'), render: (s) => (s.active === false ? chip(t('services.off')) : chip(t('services.on'), 'ok')) },
    ], rows, { onOpen: can('services.edit') ? (s) => serviceDialog(s, reload) : null }))
      : emptyState({ ico: 'tag', title: t('services.empty.title'), text: t('services.empty.text'), action: can('services.create') ? button(t('service.new'), { kind: 'primary', ico: 'plus', onClick: () => serviceDialog(null, reload) }) : null }));
}

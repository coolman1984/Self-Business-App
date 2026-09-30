// "Add something" registry. Each module registers what can be created (new client, new task, new note ...); the top bar button,
// the Today page, the "n" shortcut and the command palette all list the same items, so a module needs one line to appear everywhere.
import { icon } from '../core/dom.js';
import { t } from '../i18n/index.js';
import { menu } from './overlay.js';
import { registerCommand } from './palette.js';
import { can } from '../core/session.js';

const items = [];   // {k, ico, run, perm}
export function registerQuickAdd(item) {
  items.push(item);
  registerCommand({ k: item.k, ico: item.ico, run: item.run, words: 'new add create', perm: item.perm });
}
export const quickAddItems = () => items.filter((i) => !i.perm || can(...[].concat(i.perm)));
export function openQuickAdd(anchor) {
  const list = quickAddItems();
  if (list.length && anchor) menu(anchor, list.map((i) => ({ label: t(i.k), ico: i.ico, onClick: i.run })));
}

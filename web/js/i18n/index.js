// Translations. Every visible word goes through t('key') (or a `k:` field that is passed to t later); a test checks that every
// key used in the code exists in BOTH languages and that both have the same placeholders.
import { AR } from './ar.js';
import { EN } from './en.js';

const DICT = { ar: AR, en: EN };
let current = 'ar';
const subs = [];

export const lang = () => current;
export const dir = () => (current === 'ar' ? 'rtl' : 'ltr');
export const onLang = (fn) => subs.push(fn);

export function setLang(l, root = document.documentElement) {
  if (!DICT[l]) l = 'ar';
  const changed = l !== current;
  current = l;
  root.lang = l;
  root.dir = dir();
  if (changed) subs.forEach((f) => f(l));
}

export const hasKey = (key) => DICT[current][key] !== undefined || DICT.en[key] !== undefined;

export function t(key, params) {
  let s = DICT[current][key];
  if (s === undefined) s = DICT.en[key];
  if (s === undefined) { console.warn('missing translation', key); return key; }
  if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined ? m : String(params[k])));
  return s;
}
// marks a key that is translated later (e.g. in a navigation table); the test also checks these
export const tk = (key) => key;

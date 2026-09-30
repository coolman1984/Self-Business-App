// Personal display choices (theme, font, size, density, motion, language). They live in this browser only and are applied
// as data-* attributes on <html>; the design tokens do the rest. Nothing here is business data.
import { setLang } from '../i18n/index.js';
import { setDigits } from './format.js';

const KEY = 'sbo.prefs.v1';
export const DEFAULTS = { theme: 'auto', font: 'plex', size: 'm', density: 'comfortable', motion: 'on', digits: 'latn', lang: 'ar', sidebar: 'open', tour: 'todo' };
export const CHOICES = {
  theme: ['auto', 'morning', 'evening', 'navy', 'navynight', 'contrast'],
  font: ['plex', 'system'],
  size: ['s', 'm', 'l', 'xl'],
  density: ['comfortable', 'compact'],
  motion: ['on', 'off'],
  digits: ['latn', 'arab'],
  lang: ['ar', 'en'],
};

let prefs = { ...DEFAULTS };
try { prefs = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch (e) { /* private window: defaults */ }
for (const k of Object.keys(CHOICES)) if (!CHOICES[k].includes(prefs[k])) prefs[k] = DEFAULTS[k];

const mq = matchMedia('(prefers-color-scheme: dark)');
export const resolvedTheme = () => (prefs.theme === 'auto' ? (mq.matches ? 'evening' : 'morning') : prefs.theme);

export function apply(root = document.documentElement) {
  root.dataset.theme = resolvedTheme();
  root.dataset.font = prefs.font;
  root.dataset.size = prefs.size;
  root.dataset.density = prefs.density;
  root.dataset.motion = prefs.motion;
  setDigits(prefs.digits);
  setLang(prefs.lang, root);
}
mq.addEventListener && mq.addEventListener('change', () => { if (prefs.theme === 'auto') apply(); });

export const getPrefs = () => ({ ...prefs });
export function setPref(key, value) {
  prefs[key] = value;
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* not saved, still applied for this visit */ }
  apply();
}

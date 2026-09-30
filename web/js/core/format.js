// Dates, numbers and money in the language of the screen. Money is whole numbers in the smallest unit (piastres), never floats.
import { lang } from '../i18n/index.js';

// digits: Western (0-9) by default, Arabic-Indic on request; set by core/prefs.js
let digits = 'latn';
export const setDigits = (d) => { digits = d === 'arab' ? 'arab' : 'latn'; };
const loc = () => (lang() === 'ar' ? `ar-EG-u-nu-${digits}` : 'en-GB');
const locNum = () => loc();

export function num(n) { return n == null || n === '' ? '' : new Intl.NumberFormat(locNum()).format(n); }

export function money(minor, cur = 'EGP') {
  if (minor == null || minor === '') return '';
  const major = Number(minor) / 100;
  try { return new Intl.NumberFormat(locNum(), { style: 'currency', currency: cur, currencyDisplay: lang() === 'ar' ? 'symbol' : 'code', maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(major); }
  catch (e) { return `${major} ${cur}`; }
}

// dates are stored as ISO text (YYYY-MM-DD or full ISO timestamps)
export function date(v, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!v) return '';
  const d = new Date(String(v).length <= 10 ? v + 'T00:00:00' : v);
  return isNaN(d) ? String(v) : new Intl.DateTimeFormat(loc(), opts).format(d);
}
export const time = (v) => (v ? new Intl.DateTimeFormat(loc(), { hour: '2-digit', minute: '2-digit' }).format(new Date(v)) : '');
export const dateTime = (v) => (v ? `${date(v)} ${time(v)}` : '');
export const weekday = (v) => date(v, { weekday: 'long' });

const UNITS = [['year', 31536000], ['month', 2592000], ['day', 86400], ['hour', 3600], ['minute', 60]];
export function ago(v) {
  if (!v) return '';
  const secs = (new Date(v).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang() === 'ar' ? 'ar-EG' : 'en', { numeric: 'auto' });
  for (const [u, s] of UNITS) if (Math.abs(secs) >= s) return rtf.format(Math.round(secs / s), u);
  return rtf.format(0, 'second');
}

export const listSep = () => (lang() === 'ar' ? '، ' : ', ');
export const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
export const initials = (name) => (String(name || '?').trim().split(/\s+/).slice(0, 2).map((w) => [...w][0]).join('') || '?').toUpperCase();
export function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'greet.morning' : h < 18 ? 'greet.afternoon' : 'greet.evening';
}

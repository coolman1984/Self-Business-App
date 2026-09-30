// Same idea as the server's Arabic search normaliser (server/core/textnorm.py): people type without hamza, teh marbuta or
// diacritics, and with Arabic-Indic or Western digits. Both sides are folded to one plain form before comparing.
const DIAC = /[ً-ٰٟـ]/g;
const MAP = { 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه' };

export function norm(text) {
  return String(text || '').toLowerCase()
    .replace(DIAC, '')
    .replace(/[أإآٱىة]/g, (c) => MAP[c])
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x660))
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x6F0))
    .trim();
}

// every word typed must be found inside the text (order does not matter)
export function matches(text, query) {
  const t = norm(text);
  return norm(query).split(/\s+/).filter(Boolean).every((w) => t.includes(w));
}

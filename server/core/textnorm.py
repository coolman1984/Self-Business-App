"""Text normalisation for search and duplicate detection (Arabic and English, Egyptian phone numbers).

Light Arabic normalisation, the usual choice for search: remove diacritics (tashkeel) and tatweel, unify the alef forms,
alef maqsura -> yeh, teh marbuta -> heh, hamza-on-waw/yeh -> waw/yeh; Arabic-Indic and Persian digits -> 0-9; lower case;
punctuation -> spaces. The original text is never changed - only the search copy.
"""
import re
import unicodedata

_TRANSLATE = {}
_TRANSLATE.update({ord(c): 'ا' for c in 'أإآٱ'})
_TRANSLATE.update({ord('ى'): 'ي', ord('ة'): 'ه', ord('ؤ'): 'و', ord('ئ'): 'ي'})
_TRANSLATE.update({ord(c): str(i) for i, c in enumerate('٠١٢٣٤٥٦٧٨٩')})
_TRANSLATE.update({ord(c): str(i) for i, c in enumerate('۰۱۲۳۴۵۶۷۸۹')})
_DROP = re.compile('[ً-ٰٟـ​-‏‪-‮﻿]')
_NOT_WORD = re.compile(r'[^\w]+', re.UNICODE)


def norm_text(s):
    if s is None:
        return ''
    s = unicodedata.normalize('NFKC', str(s))
    s = _DROP.sub('', s).translate(_TRANSLATE).lower()
    return _NOT_WORD.sub(' ', s).replace('_', ' ').strip()


def norm_phone(s, country='20'):
    """E.164 form (+201012345678) or '' when the text does not look like a phone number."""
    digits = re.sub(r'\D', '', norm_text(s).replace(' ', '')) if s else ''
    raw = str(s or '').strip()
    if len(digits) < 7:
        return ''
    if raw.startswith('+'):
        return '+' + digits
    if digits.startswith('00'):
        return '+' + digits[2:]
    if digits.startswith('0'):
        return '+' + country + digits[1:]
    if digits.startswith(country) and len(digits) >= len(country) + 8:
        return '+' + digits
    return '+' + country + digits


def phone_tokens(s, country='20'):
    """Search tokens of a phone number: the international digits and the national form with the leading 0."""
    e164 = norm_phone(s, country)
    if not e164:
        return []
    intl = e164[1:]
    national = '0' + intl[len(country):] if intl.startswith(country) else intl
    return [intl, national]


def norm_email(s):
    return str(s or '').strip().lower()

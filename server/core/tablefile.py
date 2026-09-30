"""Reads spreadsheets and CSV files into plain rows of text, safely (written for this product, standard library only).

  * .xlsx (Office Open XML): shared strings, inline strings, numbers, dates (by cell format), booleans; several sheets.
  * .csv: UTF-8 (with or without BOM) or Windows-1256 (Arabic Excel's "CSV"), delimiter comma / semicolon / tab detected.

A file is untrusted input: size limits on the archive and on every part, no XML with DOCTYPE/ENTITY (blocks entity-expansion
attacks), a row and column cap. Nothing is executed; formulas are read as their last calculated value.
"""
import csv
import io
import re
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

MAX_ROWS = 50000
MAX_COLS = 200
MAX_PART = 60 * 1048576
MAX_TOTAL = 200 * 1048576
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}


class BadFile(Exception):
    pass


def _xml(z, name):
    info = z.getinfo(name)
    if info.file_size > MAX_PART:
        raise BadFile('The file is too large')
    data = z.read(name)
    if b'<!DOCTYPE' in data[:2000] or b'<!ENTITY' in data[:20000]:
        raise BadFile('The file has unsafe content')
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise BadFile('The file is damaged') from e


def _col_index(ref):
    n = 0
    for ch in re.match(r'[A-Z]+', ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _text(el):
    return ''.join(t.text or '' for t in el.iter('{%s}t' % NS['m']))


DATE_BUILTIN = set(range(14, 23)) | {27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58}
_DATE_CODE = re.compile(r'[dmyhs]', re.I)


def _date_styles(z):
    """Indexes of cell formats (cellXfs) that show a date."""
    if 'xl/styles.xml' not in z.namelist():
        return set()
    root = _xml(z, 'xl/styles.xml')
    custom = {}
    for nf in root.iterfind('m:numFmts/m:numFmt', NS):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '', nf.get('formatCode', ''))
        custom[int(nf.get('numFmtId'))] = bool(_DATE_CODE.search(code))
    out = set()
    for i, xf in enumerate(root.iterfind('m:cellXfs/m:xf', NS)):
        fid = int(xf.get('numFmtId', 0))
        if fid in DATE_BUILTIN or custom.get(fid):
            out.add(i)
    return out


def _number(v):
    try:
        d = Decimal(v)
    except InvalidOperation:
        return v
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), 'f')


def _serial_to_iso(v):
    try:
        d = Decimal(v)
    except InvalidOperation:
        return v
    base = datetime(1899, 12, 30)
    dt = base + timedelta(days=float(d))
    return dt.date().isoformat() if d == d.to_integral_value() or dt.hour == dt.minute == 0 else dt.isoformat(timespec='minutes')


def read_xlsx(data):
    """Returns [{'name': sheet name, 'rows': [[text, ...], ...]}]. Empty trailing cells are trimmed; empty rows kept as [] (row numbers stay true)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise BadFile('This is not an .xlsx file') from e
    with z:
        if sum(i.file_size for i in z.infolist()) > MAX_TOTAL:
            raise BadFile('The file is too large')
        names = set(z.namelist())
        if 'xl/workbook.xml' not in names:
            raise BadFile('This is not an .xlsx file')
        shared = []
        if 'xl/sharedStrings.xml' in names:
            for si in _xml(z, 'xl/sharedStrings.xml').iterfind('m:si', NS):
                shared.append(_text(si))
        dates = _date_styles(z)
        wb = _xml(z, 'xl/workbook.xml')
        rels = {r.get('Id'): r.get('Target') for r in _xml(z, 'xl/_rels/workbook.xml.rels').iterfind('rel:Relationship', NS)}
        sheets = []
        for s in wb.iterfind('m:sheets/m:sheet', NS):
            target = rels.get(s.get('{%s}id' % NS['r']), '')
            path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            if path not in names:
                continue
            rows = []
            root = _xml(z, path)
            for row in root.iterfind('m:sheetData/m:row', NS):
                if len(rows) >= MAX_ROWS:
                    raise BadFile('The sheet has more than %d rows' % MAX_ROWS)
                idx = int(row.get('r', len(rows) + 1)) - 1
                while len(rows) < idx:
                    rows.append([])
                cells = []
                for c in row.iterfind('m:c', NS):
                    col = _col_index(c.get('r', 'A1'))
                    if col >= MAX_COLS:
                        continue
                    while len(cells) < col:
                        cells.append('')
                    t, style = c.get('t'), int(c.get('s', 0) or 0)
                    v = c.find('m:v', NS)
                    if t == 'inlineStr':
                        val = _text(c.find('m:is', NS)) if c.find('m:is', NS) is not None else ''
                    elif v is None or v.text is None:
                        val = ''
                    elif t == 's':
                        val = shared[int(v.text)] if int(v.text) < len(shared) else ''
                    elif t == 'b':
                        val = 'TRUE' if v.text == '1' else 'FALSE'
                    elif t in ('str', 'e'):
                        val = v.text
                    else:
                        val = _serial_to_iso(v.text) if style in dates else _number(v.text)
                    cells.append(val.strip() if isinstance(val, str) else val)
                while cells and cells[-1] == '':
                    cells.pop()
                rows.append(cells)
            sheets.append({'name': s.get('name', 'Sheet'), 'rows': rows})
        return sheets


def read_csv(data):
    for enc in ('utf-8-sig', 'cp1256'):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise BadFile('The text file has an unknown encoding')
    head = text[:4096]
    delim = max((',', ';', '\t'), key=lambda d: head.count(d))
    rows = []
    for r in csv.reader(io.StringIO(text), delimiter=delim):
        if len(rows) >= MAX_ROWS:
            raise BadFile('The file has more than %d rows' % MAX_ROWS)
        r = [c.strip() for c in r[:MAX_COLS]]
        while r and r[-1] == '':
            r.pop()
        rows.append(r)
    return [{'name': 'CSV', 'rows': rows}]


def read(name, data):
    ext = name.lower().rsplit('.', 1)[-1] if '.' in name else ''
    if ext == 'xlsx':
        return read_xlsx(data)
    if ext in ('csv', 'txt'):
        return read_csv(data)
    if ext == 'xls':
        raise BadFile('Old .xls files are not supported - save the file as .xlsx or .csv in Excel first')
    raise BadFile('Use an .xlsx or .csv file')

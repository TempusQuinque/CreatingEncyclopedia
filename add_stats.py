#!/usr/bin/env python3
"""Add a statistical table to the supplement from a CSV file, or replace one (same table number and year).

    python3 add_stats.py encyclopaedia.html stats/sample_table.csv --num I --year 1970 \\
        --title "SAMPLE TABLE: LOREM IPSUM, 1970" --category "Sample Statistics" \\
        [--sub "(Lorem ipsum dolor sit amet.)"] [--note "NOTES.—Lorem ipsum."] [--page 2] [--order 10]

The CSV file (any spreadsheet can save one: File > Save as > CSV):
  - The first row holds the headings. The first column is the name column ("Country"); the others hold numbers.
    If the first column is headed "No." or "Rank", it gives the ranks; otherwise the rows are numbered 1, 2, 3...
  - Then one row per line, in the order they are to be printed. Numbers may have thousands commas. Leave a cell
    empty (or write -) where there is no figure: it is printed as a dash. At most one decimal place is shown.

Each table belongs to a category and a year (--category, --year). The contents lists each category with a button
for each of its years; a category-and-year page shows its tables in the order they were added.
The previous version of the page is kept as encyclopaedia.html.bak. Run check.py afterwards.
"""
import argparse, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enc_common import Page, fail, resolve_group, slug, human, fold, ROMAN

ap = argparse.ArgumentParser(description='Add a statistical table from a CSV file.')
ap.add_argument('html', metavar='encyclopaedia.html'); ap.add_argument('csv')
ap.add_argument('--num', required=True, help='table number, e.g. I or 12')
ap.add_argument('--year', required=True, type=int, help='the year of the figures, e.g. 1970')
ap.add_argument('--title', required=True, help='the title, in capitals, e.g. "PRODUCTION OF STEEL, 1970"')
ap.add_argument('--category', required=True, help='the contents heading it is listed under, e.g. "Industry"')
ap.add_argument('--sub', default=None, help='a line under the title, e.g. "(Countries are ranked by production.)"')
ap.add_argument('--note', default=None, help='notes printed under the table, e.g. "NOTES.—In million metric tons."')
ap.add_argument('--page', dest='first_page', type=int, default=None, help='first page number of this category-and-year (new ones only)')
ap.add_argument('--order', type=int, default=None, help='position in the contents among the statistics')
ap.add_argument('--group', default=None, help='contents group (default: the group of the other statistics)')
a = ap.parse_args()

num = a.num.strip().upper().rstrip('.')
if not (ROMAN.fullmatch(num) or num.isdigit()):
    fail(f'--num "{a.num}" must be a Roman numeral or a number')
if not os.path.isfile(a.csv):
    fail(f'{a.csv} not found')
with open(a.csv, newline='', encoding='utf-8-sig') as f:
    sample = f.read(4096); f.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in r] for r in csv.reader(f, dialect) if any(c.strip() for c in r)]
if len(rows) < 2:
    fail(f'{a.csv} needs a heading row and at least one row of figures')
head = rows[0]
has_rank = fold(head[0]).rstrip('.') in ('no', 'rank', '#', 'number')
if has_rank:
    head = head[1:]
if len(head) < 2:
    fail(f'{a.csv}: the heading row needs a name column and at least one number column; found {rows[0]}')
lab, cols = head[0], head[1:]


def number(c, r, h):
    s = c.replace(',', '').replace('−', '-').replace(' ', '').replace(' ', '')
    if s in ('', '-', '—', '–', '..', 'n.a.', 'na'):
        return None
    try:
        v = float(s)
    except ValueError:
        fail(f'{a.csv}, row {r}: "{c}" in the column "{h}" is not a number')
    return int(v) if v == int(v) else v


out = []
for i, r in enumerate(rows[1:], start=2):
    if len(r) != len(rows[0]):
        fail(f'{a.csv}, row {i} has {len(r)} cells but the heading row has {len(rows[0])}: {r}')
    rk = (r[0] or '–') if has_rank else len(out) + 1
    if has_rank and str(rk).isdigit():
        rk = int(rk)
    cells = r[1:] if has_rank else r
    out.append({'rk': rk, 'n': cells[0], 'c': [number(c, i, h) for c, h in zip(cells[1:], cols)]})
decs = [2 if any(isinstance(row['c'][k], float) for row in out) else 0 for k in range(len(cols))]
table = {'num': num, 'year': a.year, 'type': 'navy', 'lab': lab, 'title': a.title.strip(), 'cols': cols,
         'rows': out, 'decs': decs}
if a.sub:
    table['sub'] = a.sub.strip()
if a.note:
    table['note'] = a.note.strip()

page = Page(a.html)
D = page.DATA
cats = [k for k, v in D.items() if v['meta'].get('kind') == 'stats' and not v['meta'].get('store')]
group = resolve_group(page, a.group, 'Atlas and Statistics') if a.group else \
    (D[cats[0]]['meta'].get('group') if cats else resolve_group(page, None, 'Atlas and Statistics'))
if 'stats' not in D:
    D['stats'] = {'meta': {'guide': 'STATISTICAL TABLES', 'title': 'Statistical Tables', 'kind': 'stats', 'start': 2,
                           'sig': 'STAT. SUPP.—1*', 'group': group, 'store': True}, 'blocks': [], 'tables': []}
elif D['stats']['meta'].get('kind') != 'stats':
    fail('the key "stats" is used by an entry that is not the statistical supplement')
tables = D['stats'].setdefault('tables', [])
idx = next((i for i, t in enumerate(tables) if str(t.get('num')) == num and t.get('year') == a.year), None)
replaced = idx is not None
if replaced:
    tables[idx] = table
else:
    tables.append(table); idx = len(tables) - 1

key = next((k for k in cats if D[k]['meta'].get('cat') == a.category and D[k]['meta'].get('yr') == a.year), None)
if key is None:
    key = f'st-{slug(a.category)}-{a.year}'
    if key in D:
        fail(f'the key {key} is already used by another entry')
    start = a.first_page or (max([D[k]['meta'].get('start', 2) for k in cats], default=0) + 2)
    D[key] = {'meta': {'guide': 'STATISTICAL TABLES', 'title': f'{a.category}, {a.year}', 'kind': 'stats',
                       'cat': a.category, 'yr': a.year, 'tables': [idx], 'start': start, 'group': group,
                       'sig': 'STAT. SUPP.—1*'}, 'blocks': []}
    made = True
else:
    m = D[key]['meta']
    if idx not in m['tables']:
        m['tables'].append(idx)
    if a.first_page:
        m['start'] = a.first_page
    made = False
if a.order is not None:
    D[key]['meta']['ord'] = a.order
size = page.save()
print(f'{"replaced" if replaced else "added"} TABLE {num} ({a.year}), {len(out)} rows x {len(cols)} columns, '
      f'in "{D[key]["meta"]["title"]}" ({"new entry " if made else ""}{key}, from page {D[key]["meta"]["start"]})')
print(f'page saved: {human(size)}. Now run: python3 check.py {a.html}')

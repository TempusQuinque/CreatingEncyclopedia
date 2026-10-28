"""Shared helpers for the encyclopaedia scripts (add_article.py, add_atlas.py, add_stats.py, remove_entry.py, check.py).
Not meant to be run on its own. Keep it in the same folder as the scripts."""
import json, os, re, sys, shutil, unicodedata

NAMES = ('DATA', 'IMGS', 'TILES')
ROMAN = re.compile(r'(?=[IVXLCDM]+$)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})')


def fail(msg):
    print('ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


class Page:
    """The encyclopaedia page: its text and the three data objects DATA, IMGS and TILES."""

    def __init__(self, path):
        self.path = path
        if not os.path.isfile(path):
            fail(f'{path} not found. Give the path of the encyclopaedia page (encyclopaedia.html or index.html) first.')
        self.text = open(path, encoding='utf-8').read()
        self.obj = {}
        for n in NAMES:
            marker = f'const {n}='
            c = self.text.count(marker)
            if c != 1:
                fail(f'{path}: expected one "{marker}" in the page but found {c}. The file may be damaged: '
                     f'restore {os.path.basename(path)}.bak or start again from the template.')
            i = self.text.find(marker) + len(marker)
            try:
                self.obj[n], _ = json.JSONDecoder().raw_decode(self.text, i)
            except json.JSONDecodeError as e:
                fail(f'{path}: the {n} data cannot be read ({e}). The file may be damaged: restore {os.path.basename(path)}.bak.')

    DATA = property(lambda self: self.obj['DATA'])
    IMGS = property(lambda self: self.obj['IMGS'])
    TILES = property(lambda self: self.obj['TILES'])

    def groups(self):
        """The contents groups set in the EDIT THIS block, plus 'Other Articles' (always present)."""
        m = re.search(r'const BOOK\s*=\s*\{.*?groups\s*:\s*\[(.*?)\]', self.text, re.S)
        if not m:
            return None
        g = [a or b for a, b in re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", m.group(1))]
        return g if 'Other Articles' in g else g + ['Other Articles']

    def book_value(self, name):
        m = re.search(r'const BOOK\s*=\s*\{.*?\b' + name + r"\s*:\s*'((?:[^'\\]|\\.)*)'", self.text, re.S)
        return m.group(1) if m else None

    def save(self):
        s = self.text
        title = self.book_value('title')                     # keep the <title> tag in step with BOOK.title
        if title:
            s = re.sub(r'<title>.*?</title>', lambda m: '<title>' + title.replace('&', '&amp;').replace('<', '&lt;') + '</title>', s, count=1)
        for n in NAMES:
            marker = f'const {n}='
            i = s.find(marker) + len(marker)
            _, e = json.JSONDecoder().raw_decode(s, i)
            s = s[:i] + json.dumps(self.obj[n], ensure_ascii=False) + s[e:]
        shutil.copy2(self.path, self.path + '.bak')          # the previous version, in case something goes wrong
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(s)
        os.replace(tmp, self.path)
        self.text = s
        return len(s.encode('utf-8'))


def match_group(page, wanted):
    """The group name exactly as set in the page (forgiving case and '&'), or None if there is no such group."""
    groups = page.groups()
    if groups is None:
        return wanted
    for g in groups:
        if g == wanted:
            return g
    for g in groups:
        if fold(g) == fold(wanted) or fold(g).replace(' and ', ' & ') == fold(wanted).replace(' and ', ' & '):
            return g
    return None


def resolve_group(page, wanted, default=None):
    """Return the group name as set in the page, or stop with the list of valid groups."""
    groups = page.groups()
    if groups is None:
        return wanted or default or 'Other Articles'
    if not wanted:
        return default if default in groups else 'Other Articles'
    g = match_group(page, wanted)
    if g:
        return g
    fail(f'group "{wanted}" is not one of the contents groups set in the EDIT THIS block of the page: '
         + '; '.join(f'"{g}"' for g in groups) + '. Use one of these, or add the new group to BOOK.groups first.')


def fold(t):
    t = unicodedata.normalize('NFKD', str(t))
    return ''.join(c for c in t if not unicodedata.combining(c)).lower().strip()


def norm_ref(t):
    """As the page does it: how a cross-reference is matched with an entry's title or guide word."""
    t = fold(t).upper()
    t = re.sub(r'[–—-]', '-', t)
    t = re.sub(r'\s+', ' ', t)
    return re.sub(r'[\s.,;:]+$', '', t).strip()


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', fold(t)).strip('-') or 'entry'


def human(n):
    return f'{n / 1048576:.1f} MB' if n >= 1048576 else f'{n / 1024:.0f} KB'


# ---- rough page estimate for a written article, from measurements with Libre Caslon Text ----
COL_H, PAGE_PX = 926, 2 * 926          # two columns of 926 px make a page


def estimate_pages(entry, imgs_size=None):
    """(text pages, plates) for an article; about +/- 1 page. Plates are extra, unnumbered leaves."""
    px, plates = 0.0, 0
    words = lambda h: len(re.sub(r'<[^>]+>', ' ', h).split())
    for b in entry.get('blocks', []):
        t = b.get('t')
        if t == 'p':
            px += 2.45 * words(b.get('html', '')) + 9
        elif t == 'h':
            px += 36
        elif t == 'ol':
            px += sum(2.45 * words(i) + 14 for i in b.get('items', []))
        elif t == 'fig':
            px += 320 * b.get('h', 400) / max(1, b.get('w', 640)) + 36
        elif t == 'wfig':
            px += 2 * (668 * b.get('h', 400) / max(1, b.get('w', 1280)) + 40)
        elif t == 'table':
            px += (35 + 18 * b.get('html', '').count('<tr>')) * (2 if b.get('span') else 1)
        elif t == 'plate':
            plates += 1
    return max(1, -(-int(px * 1.04) // PAGE_PX)), plates

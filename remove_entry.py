#!/usr/bin/env python3
"""Remove entries (articles, atlas plates, statistics pages) and their images from the encyclopaedia page.

    python3 remove_entry.py encyclopaedia.html sample-article sample-country world st-sample-1970 stats

Statistical tables no longer shown by any statistics page are removed too. The key "stats" (the store that holds
all the tables) can only be removed together with every statistics page.
The previous version of the page is kept as encyclopaedia.html.bak.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enc_common import Page, fail, human

if len(sys.argv) < 3:
    print(__doc__); sys.exit(1)
page = Page(sys.argv[1]); keys = list(dict.fromkeys(sys.argv[2:]))
D, I, T = page.DATA, page.IMGS, page.TILES
missing = [k for k in keys if k not in D]
if missing:
    fail('no entry with the key ' + ', '.join(missing) + '. Nothing was removed. The keys are: ' + ', '.join(D))
cats = [k for k, v in D.items() if v['meta'].get('kind') == 'stats' and not v['meta'].get('store')]
if 'stats' in keys and any(k not in keys for k in cats):
    fail('"stats" holds the tables used by ' + ', '.join(k for k in cats if k not in keys) +
         '. Remove those too, or keep "stats". Nothing was removed.')
for k in keys:
    del D[k]
    for i in [i for i in I if re.fullmatch(re.escape(k) + r'(\.p?\d+|_page)', i)]:
        del I[i]
    T.pop(k, None)
    print('removed ' + k)
if 'stats' in D:                                   # drop tables no page shows any more, and renumber the rest
    tabs = D['stats'].get('tables', [])
    used = sorted({i for v in D.values() if v['meta'].get('kind') == 'stats' for i in v['meta'].get('tables', [])})
    if len(used) < len(tabs):
        new = {old: n for n, old in enumerate(used)}
        D['stats']['tables'] = [tabs[i] for i in used]
        for v in D.values():
            if v['meta'].get('kind') == 'stats' and 'tables' in v['meta'] and not v['meta'].get('store'):
                v['meta']['tables'] = [new[i] for i in v['meta']['tables']]
        print(f'removed {len(tabs) - len(used)} statistical table(s) no longer shown')
size = page.save()
print(f'page saved: {human(size)}')

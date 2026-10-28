#!/usr/bin/env python3
"""Add an atlas plate (a large map opened in the zoomable viewer), or replace one with the same key.

    python3 add_atlas.py encyclopaedia.html world images/world_map.png --title "The World, 1970" \\
        --guide "THE WORLD, POLITICAL, 1970" --plate "PLATE I" --cap "The world: political divisions, 1 Jan. 1970." \\
        [--alt "Political map of the world"] [--order 1] [--group "Atlas and Statistics"] [--quality 70]

The map image can be large (8,000-16,000 px wide is typical for a world map); export it as PNG from Inkscape or
any drawing program. The script stores a page-sized image and a pyramid of 1,024-px WebP tiles, so the viewer
loads only what is on screen. Big maps make big pages: roughly 1 MB of tiles for every 4 million pixels of map.
The previous version of the page is kept as encyclopaedia.html.bak. Run check.py afterwards.
"""
import sys, os, io, re, math, base64, argparse
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enc_common import Page, fail, resolve_group, ROMAN, human

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser(description='Add an atlas plate with a zoomable viewer.')
ap.add_argument('html', metavar='encyclopaedia.html'); ap.add_argument('key'); ap.add_argument('image')
ap.add_argument('--title', required=True, help='as listed in the contents')
ap.add_argument('--guide', required=True, help='the running head, in capitals')
ap.add_argument('--plate', default='PLATE I', help='the plate number, e.g. "PLATE II" (or just II)')
ap.add_argument('--cap', default='', help='the caption under the map')
ap.add_argument('--alt', default='', help='a short description of the map, for screen readers')
ap.add_argument('--group', default=None, help='contents group (default: Atlas and Statistics)')
ap.add_argument('--order', type=int, default=None, help='position among the plates (1 = first)')
ap.add_argument('--quality', type=int, default=70, help='WebP quality of the tiles (default 70; lower makes the page smaller)')
a = ap.parse_args()

if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', a.key):
    fail(f'key "{a.key}" must be lower-case letters, digits and hyphens only')
pn = re.sub(r'^plate\s*', '', a.plate.strip(), flags=re.I).rstrip('.').upper()
if not (ROMAN.fullmatch(pn) or pn.isdigit()):
    fail(f'--plate "{a.plate}" must be like "PLATE II"')
if not os.path.isfile(a.image):
    fail(f'image not found: {a.image}')
page = Page(a.html)
D = page.DATA
old = D.get(a.key)
if old and old['meta'].get('kind') != 'atlas':
    fail(f'key "{a.key}" is already used by the article "{old["meta"]["title"]}": choose another key')
group = resolve_group(page, a.group, 'Atlas and Statistics')

im = Image.open(a.image).convert('RGB'); W, H = im.size


def uri(img, q):
    b = io.BytesIO(); img.save(b, 'WEBP', quality=q, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()


pw = min(2250, W); pageimg = im.resize((pw, round(H * pw / W)), Image.LANCZOS)
levels = []; f = 1.0
while True:
    levels.insert(0, f)
    if W * f / 2 < 1200:
        break
    f /= 2
T = {'W0': W, 'H0': H, 'size': 1024, 'levels': []}
for f in levels:
    w, h = max(1, round(W * f)), max(1, round(H * f))
    L = im if f == 1.0 else im.resize((w, h), Image.LANCZOS)
    cols, rows = math.ceil(w / 1024), math.ceil(h / 1024); tiles = {}
    for cy in range(rows):
        for cx in range(cols):
            tiles[f'{cx}_{cy}'] = uri(L.crop((cx * 1024, cy * 1024, min(w, (cx + 1) * 1024), min(h, (cy + 1) * 1024))), a.quality)
    T['levels'].append({'f': f, 'w': w, 'h': h, 'cols': cols, 'rows': rows, 'tiles': tiles})
    print(f'  level {f}: {w} x {h}, {cols * rows} tiles')

meta = {'guide': a.guide, 'title': a.title, 'kind': 'atlas', 'w': W, 'h': H, 'plate': f'PLATE {pn}',
        'platecap': f'Plate {pn}', 'cap': a.cap, 'alt': a.alt or a.title, 'group': group}
if a.order is not None:
    meta['ord'] = a.order
D[a.key] = {'meta': meta, 'blocks': []}
page.IMGS[a.key + '_page'] = uri(pageimg, 78)
page.TILES[a.key] = T
size = page.save()
print(f'{"replaced" if old else "added"} {a.key}: atlas plate {pn}, {W} x {H} px')
print(f'page saved: {human(size)}. Now run: python3 check.py {a.html}')

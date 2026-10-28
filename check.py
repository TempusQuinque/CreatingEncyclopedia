#!/usr/bin/env python3
"""Check the encyclopaedia page for problems. Run it after every change.

    python3 check.py encyclopaedia.html             quick checks (a few seconds)
    python3 check.py encyclopaedia.html --pages     also sets every entry in a browser and counts its real pages
    python3 check.py encyclopaedia.html --remove-unused   also deletes stored images that no entry uses

--pages needs Playwright (pip install playwright, then: playwright install chromium) and an internet connection,
because the page breaks depend on the font, which comes from Google Fonts. Without --pages, page counts are
estimates (about +/- 1 page).

It lists every entry, then ERRORS (must be fixed), WARNINGS (probably wrong) and NOTES (for information).
It exits with status 1 if there are errors.
"""
import sys, os, re, glob, shutil, subprocess, tempfile, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enc_common import Page, norm_ref, fold, human, estimate_pages

CLOUDFLARE, GITHUB = 25 * 1048576, 100 * 1000 * 1000
SAMPLES = {'sample-article', 'sample-country', 'world', 'st-sample-1970'}


def order_keys(D, groups):
    gl = groups or ['Other Articles']
    gi = lambda m: gl.index(m.get('group') or 'Other Articles') if (m.get('group') or 'Other Articles') in gl else -1
    sk = lambda t: re.sub(r'[^a-z0-9]', '', re.sub(r'^the ', '', fold(t)))
    keys = [k for k in D if not D[k]['meta'].get('store')]
    return sorted(keys, key=lambda k: (gi(D[k]['meta']), D[k]['meta'].get('ord', 999), sk(D[k]['meta'].get('title', ''))))


def block_texts(entry):
    for b in entry.get('blocks', []):
        for f in ('html', 'cap'):
            if b.get(f):
                yield b[f]
        for it in b.get('items', []):
            yield it


def measure(path, keys, prepare=None):
    """Open the page in Chromium and set each entry: {key: (folios, plates, overflowing folios)}, font ok, errors."""
    from playwright.sync_api import sync_playwright
    out, errors = {}, []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1640, 'height': 1200})
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: m.type == 'error' and not m.text.startswith('Failed to load resource') and errors.append(m.text))
        pg.on('requestfailed', lambda r: 'fonts.g' not in r.url and errors.append(f'could not load {r.url[:120]}'))   # the font is reported separately
        if prepare:
            prepare(pg)
        pg.goto('file://' + os.path.abspath(path))
        pg.wait_for_timeout(500)
        pg.evaluate('document.fonts.ready.then(()=>1)')
        for k in keys:
            ok = pg.evaluate(f"(()=>{{const b=document.querySelector('#toc [data-art=\"{k}\"]'); if(!b) return false; b.click(); return true}})()")
            if not ok:
                errors.append(f'{k}: no button for it in the contents'); continue
            last, stable = None, 0
            for _ in range(40):
                pg.wait_for_timeout(150)
                sig = pg.evaluate("[...document.querySelectorAll('#stack .page')].map(p=>(p.dataset.folio||'P')+[...p.querySelectorAll('.col')].map(c=>c.scrollHeight).join(',')).join('|')")
                stable = stable + 1 if sig == last and sig else 0
                last = sig
                if stable >= 3:
                    break
            r = pg.evaluate("""[...document.querySelectorAll('#stack .page')].map(p=>({f:p.dataset.folio||null,
                 over:[...p.querySelectorAll('.col')].some(c=>c.scrollHeight>c.clientHeight+2)}))""")
            out[k] = ([int(x['f']) for x in r if x['f'] and x['f'].isdigit()], sum(1 for x in r if not x['f']),
                      [x['f'] for x in r if x['over']])
        font = pg.evaluate("[...document.fonts].filter(f=>f.family.includes('Caslon')&&f.status==='loaded').length")
        b.close()
    return out, font > 0, errors


def main(argv=None, prepare=None):
    ap = argparse.ArgumentParser(description='Check the encyclopaedia page for problems.')
    ap.add_argument('page', help='encyclopaedia.html (or index.html)')
    ap.add_argument('--pages', action='store_true', help='set every entry in a browser and count its real pages')
    ap.add_argument('--remove-unused', action='store_true', help='delete stored images that no entry uses')
    ap.add_argument('--articles', default=None, help='folder of article Markdown files (default: articles/ beside the page)')
    a = ap.parse_args(argv)
    page = Page(a.page)
    D, I, TL, text = page.DATA, page.IMGS, page.TILES, page.text
    E, W, N = [], [], []
    size = len(text.encode('utf-8'))

    # ---- the file itself ----
    if not text.rstrip().endswith('</html>'):
        E.append('the page does not end with </html>: it may have been cut short. Restore encyclopaedia.html.bak')
    groups = page.groups()
    if groups is None:
        E.append('the EDIT THIS block (const BOOK = {...}) with its groups list was not found in the page script')
    tm = re.search(r'<title>(.*?)</title>', text)
    bt = page.book_value('title')
    if tm and bt and tm.group(1).replace('&amp;', '&') != bt:
        N.append(f'the <title> tag ("{tm.group(1)}") differs from BOOK.title ("{bt}"); any of the add_ or remove_ scripts brings it into step')
    if bt == 'The Example Encyclopaedia':
        N.append('the book is still called "The Example Encyclopaedia": set the title and the rest of the EDIT THIS block')
    node = shutil.which('node')
    if node:
        scripts = re.findall(r'<script>(.*?)</script>', text, re.S)
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write('\n;\n'.join(scripts)); js = f.name
        r = subprocess.run([node, '--check', js], capture_output=True, text=True)
        os.unlink(js)
        if r.returncode:
            msg = [l for l in r.stderr.splitlines() if l.strip()][:5]
            E.append('the page script has a syntax error, probably in the EDIT THIS block: ' + ' | '.join(m[:160] for m in msg))
    else:
        N.append('Node.js was not found, so the page script was not checked for syntax errors (--pages also catches them)')
    if size > GITHUB:
        E.append(f'the page is {human(size)}: GitHub refuses files over 100 MB')
    elif size > CLOUDFLARE:
        E.append(f'the page is {human(size)}: Cloudflare Pages refuses files over 25 MiB (GitHub Pages allows 100 MB). '
                 'Make map plates smaller or lower add_atlas.py --quality')
    elif size > 20 * 1048576:
        W.append(f'the page is {human(size)}, close to the 25 MiB limit of Cloudflare Pages')

    order = order_keys(D, groups)
    # cross-reference targets, as the page builds them
    REF = {}
    for k in order:
        m = D[k]['meta']
        for n in (m.get('title'), m.get('guide')):
            if n:
                REF[norm_ref(n)] = k; REF[norm_ref(re.sub(r',\s*\d{4}.*$', '', n))] = k
    tabs = D.get('stats', {}).get('tables', [])
    for k in order:
        for i in D[k]['meta'].get('tables', []) if D[k]['meta'].get('kind') == 'stats' else []:
            if 0 <= i < len(tabs):
                REF['TABLE ' + str(tabs[i].get('num'))] = k
    if any(D[k]['meta'].get('kind') == 'stats' for k in order):
        REF['STATISTICAL TABLES'] = REF['STATISTICAL SUPPLEMENT'] = 'stats'

    # ---- measurement in a browser ----
    measured, font_ok = {}, None
    if a.pages:
        try:
            keys = [k for k in order if D[k]['meta'].get('kind') != 'atlas'
                    and (not groups or (D[k]['meta'].get('group') or 'Other Articles') in groups)]
            measured, font_ok, errs = measure(a.page, keys, prepare)
            for e in errs:
                E.append('in the browser: ' + e[:300])
            if not font_ok:
                W.append('Libre Caslon Text did not load in the browser (no internet connection?), so the page counts '
                         'below were set in another font and may be wrong')
        except ImportError:
            E.append('--pages needs Playwright: pip install playwright, then: playwright install chromium')
        except Exception as e:
            E.append(f'--pages could not run the browser: {str(e).splitlines()[0][:200]}')

    # ---- every entry ----
    rows, spans, used_imgs, used_tabs, unresolved = [], {}, set(), set(), {}
    titles, guides = {}, {}
    for k in order:
        m = D[k]['meta']; kind = m.get('kind') or 'article'
        g = m.get('group') or 'Other Articles'
        if groups and g not in groups:
            E.append(f'{k}: its group "{g}" is not one of BOOK.groups, so it does not appear in the contents. '
                     'Change the group (add_article.py) or add it to BOOK.groups')
        titles.setdefault(fold(m.get('title', '')), []).append(k)
        for b in D[k].get('blocks', []):
            if b.get('img'):
                used_imgs.add(b['img'])
                if b['img'] not in I:
                    E.append(f'{k}: the image {b["img"]} is missing from the page: run add_article.py for it again')
        for t in block_texts(D[k]):
            for sc in re.findall(r'<span class="sc">(.*?)</span>', t):
                for part in re.split(r';\s*', re.sub(r'<[^>]+>', '', sc)):
                    if part.strip() and norm_ref(part) not in REF:
                        unresolved.setdefault(part.strip(), set()).add(k)
        if kind == 'atlas':
            used_imgs.add(k + '_page')
            if k + '_page' not in I:
                E.append(f'{k}: the map image is missing: run add_atlas.py for it again')
            if k not in TL:
                N.append(f'{k}: the map has no tiles, so the viewer only enlarges the page-sized image')
            where = f'{m.get("plate", "PLATE ?").title()}, {m.get("w", "?")} x {m.get("h", "?")} px'
        elif kind == 'stats':
            ts = m.get('tables', [])
            for i in ts:
                used_tabs.add(i)
                if not 0 <= i < len(tabs):
                    E.append(f'{k}: it shows table number {i}, which does not exist in DATA.stats.tables'); continue
                t = tabs[i]
                if t.get('type') != 'navy':
                    W.append(f'{k}: TABLE {t.get("num")} has "type": "{t.get("type")}", a fixed layout from the original '
                             'project; use "navy" (as add_stats.py does)')
                for r in t.get('rows', []):
                    if t.get('type') == 'navy' and len(r.get('c', [])) != len(t.get('cols', [])):
                        E.append(f'{k}: TABLE {t.get("num")}, row "{r.get("n")}" has {len(r.get("c", []))} figures '
                                 f'for {len(t.get("cols", []))} columns')
            est = max(1, -(-sum(160 + 15 * len(tabs[i].get('rows', [])) for i in ts if 0 <= i < len(tabs)) // 1000))
            first = m.get('start', 2)
            if k in measured and measured[k][0]:
                f = measured[k][0]; spans.setdefault('Stat. Supp.', []).append((f[0], f[-1], k, True))
                where = f'Stat. Supp., pp. {f[0]}–{f[-1]}' if len(f) > 1 else f'Stat. Supp., p. {f[0]}'
            else:
                spans.setdefault('Stat. Supp.', []).append((first, first + est - 1, k, False))
                where = f'Stat. Supp., from p. {first}, {len(ts)} table{"s" if len(ts) != 1 else ""}'
        else:
            vol, start = m.get('vol', '?'), m.get('start', 0)
            guides.setdefault(norm_ref(m.get('guide', '')), []).append(k)
            if k in measured and measured[k][0]:
                f, plates, over = measured[k]
                end, how = f[-1], ''
                if f[0] != start:
                    E.append(f'{k}: its first page is set as {f[0]} but its page: is {start}')
                for o in over:
                    E.append(f'{k}: text runs past the foot of a column on page {o}')
                spans.setdefault(vol, []).append((start, end, k, True))
            else:
                n, plates = estimate_pages(D[k])
                end, how = start + n - 1, ' (est.)'
                spans.setdefault(vol, []).append((start, end, k, False))
            if start % 2:
                N.append(f'{k}: starts on an odd (right-hand) page, {start}; articles usually start on an even page')
            where = f'{vol}, {start}' + (f'–{end}' if end > start else '') + how + (f' + {plates} plate{"s" if plates > 1 else ""}' if plates else '')
        rows.append((g, k, kind, m.get('title', ''), where))

    # ---- pages that collide ----
    for vol, lst in spans.items():
        lst.sort()
        for (s1, e1, k1, m1), (s2, e2, k2, m2) in zip(lst, lst[1:]):
            label = 'the statistical supplement' if vol == 'Stat. Supp.' else f'Vol. {vol}'
            if s1 == s2:
                E.append(f'{k1} and {k2} both start on page {s1} of {label}')
            elif e1 >= s2:
                if m1:
                    E.append(f'{k1} runs to page {e1} of {label}, but {k2} starts on page {s2}: move {k2} to page '
                             f'{e1 + 1 + (e1 + 1) % 2} or later')
                else:
                    W.append(f'{k1} probably runs to about page {e1} of {label}, but {k2} starts on page {s2}. '
                             'Move one of them (check with --pages)')
    for t, ks in titles.items():
        if len(ks) > 1:
            W.append('several entries have the title "' + D[ks[0]]['meta']['title'] + '": ' + ', '.join(ks))
    for t, ks in guides.items():
        if len(ks) > 1 and t:
            W.append(f'several articles have the guide word "{t}", so cross-references to it are ambiguous: ' + ', '.join(ks))
    orphans = [i for i in I if i not in used_imgs]
    if orphans:
        if a.remove_unused:
            for i in orphans:
                del I[i]
            page.save()
            N.append(f'removed {len(orphans)} unused image(s): ' + ', '.join(orphans[:8]) + ('…' if len(orphans) > 8 else ''))
        else:
            W.append(f'{len(orphans)} image(s) are stored but not used ({human(sum(len(I[i]) for i in orphans))}): '
                     + ', '.join(orphans[:8]) + ('…' if len(orphans) > 8 else '')
                     + f'. To delete them: python3 check.py {a.page} --remove-unused')
    spare = [str(i) for i in range(len(tabs)) if i not in used_tabs]
    if spare:
        N.append('statistical tables not shown on any statistics page: number(s) ' + ', '.join(spare))
    if unresolved:
        items = sorted(unresolved)
        N.append(f'{len(items)} cross-reference(s) have no entry yet and are printed as plain small capitals: '
                 + '; '.join(items[:15]) + ('…' if len(items) > 15 else ''))
    present = [k for k in SAMPLES if k in D and 'sample' in fold(D[k]['meta'].get('title', '') + k)]
    if present and len(order) > len(present) + 0:
        N.append('the sample entries are still in the page: remove them with python3 remove_entry.py '
                 f'{os.path.basename(a.page)} ' + ' '.join(k for k in ('sample-article', 'sample-country', 'world', 'st-sample-1970') if k in present)
                 )

    # ---- the Markdown sources ----
    adir = a.articles or os.path.join(os.path.dirname(os.path.abspath(a.page)), 'articles')
    if os.path.isdir(adir):
        mt = os.path.getmtime(a.page); keys_md = {}
        for md in sorted(glob.glob(os.path.join(adir, '*.md'))):
            head = open(md, encoding='utf-8').read(3000)
            km = re.search(r'^\s*key\s*:\s*([^\s#]+)', head, re.M)
            if not km:
                W.append(f'{os.path.relpath(md)} has no "key:" line'); continue
            key = km.group(1).strip('"\'')
            if key in keys_md:
                E.append(f'{os.path.relpath(md)} and {os.path.relpath(keys_md[key])} have the same key "{key}"')
            keys_md[key] = md
            if key not in D:
                W.append(f'{os.path.relpath(md)} (key {key}) is not in the page. Add it (python3 add_article.py {a.page} {os.path.relpath(md)}) or delete the file')
            elif os.path.getmtime(md) > mt + 1:
                W.append(f'{os.path.relpath(md)} has changed since the page was last saved: python3 add_article.py {a.page} {os.path.relpath(md)}')
        for k in order:
            if (D[k]['meta'].get('kind') or 'article') == 'article' and k not in keys_md:
                N.append(f'{k} has no Markdown file in {os.path.relpath(adir)}/, so it cannot be rebuilt from source')

    # ---- report ----
    print(f'{a.page}: {human(size)}, {len(order)} entries' + (' (pages counted in the browser)' if measured else ''))
    last = None
    for g, k, kind, title, where in rows:
        if g != last:
            print(f'  {g}'); last = g
        print(f'    {k:<22} {kind:<8} {title[:38]:<38} {where}')
    for name, lst in (('ERRORS', E), ('WARNINGS', W), ('NOTES', N)):
        if lst:
            print(f'\n{name} ({len(lst)})')
            for x in lst:
                print('  - ' + x)
    print(f'\n{len(E)} error(s), {len(W)} warning(s).' + ('' if a.pages else ' Page counts are estimates: run with --pages to count them in a browser.'))
    return 1 if E else 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Add articles to the encyclopaedia page from Markdown files. An article with the same key is replaced.

    python3 add_article.py encyclopaedia.html articles/my_article.md [more.md ...]
    python3 add_article.py encyclopaedia.html articles/*.md          (rebuild every article)

The format is described in README.md; articles/sample_article.md and articles/sample_country.md show every feature.
If any file has a problem, nothing is saved and every problem is listed. The previous version of the page is kept
as encyclopaedia.html.bak. Run check.py afterwards.
"""
import sys, os, re, io, math, base64, html
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enc_common import Page, match_group, ROMAN, slug, human

Image.MAX_IMAGE_PIXELS = None
FIELDS = {'key', 'title', 'guide', 'volume', 'page', 'group', 'order'}
FLAGS = {'wide', 'plate', 'line', 'colour', 'color', 'span'}
DASH = r'(?:—|–|--|-)'


class Problem(Exception):
    pass


def inline(t):
    """Markdown inline marks to the page's HTML: [[CROSS-REFERENCE]], **bold**, *italic*."""
    t = re.sub(r'(?<!-)\s*--\s*(?!-)', '—', t)                       # -- is an em dash, set close
    t = re.sub(r'(?<![\w_])__(\S.*?\S|\S)__(?![\w_])', r'**\1**', t)  # __bold__ and _italic_ as well
    t = re.sub(r'(?<![\w_])_(\S.*?\S|\S)_(?![\w_])', r'*\1*', t)
    t = t.replace('\\*', '\x00')                                      # \* is a plain asterisk
    t = html.escape(t, quote=False)
    t = re.sub(r'\[\[(.+?)\]\]', r'<span class="sc">\1</span>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', t)
    return t.replace('\x00', '*')


def read_front(md, path, warns):
    md = md.lstrip('﻿').lstrip()
    m = re.match(r'---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)', md, re.S)
    if not m:
        raise Problem('the file must start with a block between two --- lines giving key, title, guide, volume, page '
                      'and group. Copy the top of articles/sample_country.md.')
    meta = {}
    for ln in m.group(1).splitlines():
        if not ln.strip() or ln.lstrip().startswith('#'):
            continue
        if ':' not in ln:
            raise Problem(f'cannot read this line of the --- block: "{ln.strip()}". Each line is "name: value".')
        k, v = ln.split(':', 1)
        k, v = k.strip().lower(), v.strip()
        parts = re.split(r'\s{2,}|\s+#\s', v, maxsplit=1)
        if len(parts) == 2:
            warns.append(f'{k}: ignored the text after the value ("{parts[1].strip()}")')
            v = parts[0].strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
            v = v[1:-1]
        if k not in FIELDS:
            warns.append(f'"{k}:" is not a field this script uses; ignored')
        meta[k] = v
    for need in ('key', 'title', 'guide', 'volume', 'page'):
        if not meta.get(need):
            raise Problem(f'the --- block has no "{need}:" line')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', meta['key']):
        raise Problem(f'key "{meta["key"]}" must be lower-case letters, digits and hyphens only, e.g. "{slug(meta["key"])}"')
    if not re.fullmatch(r'\d+', meta['page']):
        raise Problem(f'page "{meta["page"]}" must be a whole number: the article\'s first page')
    meta['volume'] = meta['volume'].upper()
    if not (ROMAN.fullmatch(meta['volume']) or meta['volume'].isdigit()):
        raise Problem(f'volume "{meta["volume"]}" must be a Roman numeral such as XIX')
    if 'order' in meta and not re.fullmatch(r'-?\d+', meta['order']):
        raise Problem(f'order "{meta["order"]}" must be a whole number')
    return meta, md[m.end():]


def caption(line, kind_hint):
    """'*Fig. 1.—Caption.*' and its common variants -> ('Fig. 1.', '1', 'Caption.')."""
    c = line.strip()
    if c.startswith('*') and c.endswith('*') and not c.startswith('**'):
        c = c[1:-1].strip()
    m = re.match(r'(fig\.?|figure|plate)\s*([\dIVXLivxl]+)\b\s*\.?\s*' + DASH + r'?\s*[:.]?\s*(.*)$', c, re.I)
    if not m or not m.group(3):
        raise Problem(f'the line after an image must be its caption, starting "*{kind_hint} 1.—": found "{line.strip()}"')
    word = 'Plate' if m.group(1).lower().startswith('plate') else 'Fig.'
    return f'{word} {m.group(2).upper()}.', m.group(2).upper(), m.group(3).strip()


def table_html(lines):
    rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in lines]
    rows = [r for r in rows if not all(re.fullmatch(r':?-{2,}:?', c) or not c for c in r)]   # drop | --- | rows
    if not rows:
        raise Problem('a table has no rows')
    n = len(rows[0])
    for r in rows[1:]:
        if len(r) != n:
            raise Problem(f'a table row has {len(r)} cells but the heading row has {n}: | {" | ".join(r)} |')
    num = lambda c: bool(re.fullmatch(r'[−–\-+]?[\d,.]+%?|—|–|-', c))
    head = '<thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in rows[0]) + '</tr></thead>'
    body = ''.join('<tr>' + ''.join(f'<td class="num">{inline(c)}</td>' if num(c) else f'<td>{inline(c)}</td>'
                                    for c in r) + '</tr>' for r in rows[1:])
    return f'<table>{head}<tbody>{body}</tbody></table>', n


def tokenize(body):
    """Split the text into raw blocks: heading, image (+ caption), table (+ notes), list, paragraph."""
    lines = body.replace('\r\n', '\n').split('\n')
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append(('p', ' '.join(l.strip() for l in para)))
            para.clear()

    while i < len(lines):
        ln = lines[i]; s = ln.strip()
        if not s:
            flush(); i += 1; continue
        if re.match(r'#{3,}\s', s):
            raise Problem(f'"{s}": only ## headings are used. For a sub-heading write a run-in heading at the start of '
                          'the paragraph: *1. Title.*—Text…')
        if re.match(r'#\s', s):
            if not out and not para:
                i += 1; continue                                   # a title line: the title comes from the --- block
            raise Problem(f'"{s}": use ## for a section heading')
        if s.startswith('## '):
            flush(); out.append(('h', s[3:].strip())); i += 1; continue
        if re.fullmatch(r'(-{3,}|\*{3,}|_{3,})', s):
            flush(); i += 1; continue                              # a horizontal rule: ignored
        if s.startswith('!['):
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                raise Problem(f'the image "{s}" has no caption line after it')
            out.append(('img', s, lines[j].strip())); i = j + 1; continue
        if re.match(r'\*\*\s*table\b', s, re.I):
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            rows = []
            while j < len(lines) and lines[j].strip().startswith('|'):
                rows.append(lines[j]); j += 1
            if not rows:
                raise Problem(f'"{s}" is not followed by a table (lines starting with |)')
            notes = []
            k = j
            while True:                                            # notes: lines starting with ^, with or without blank lines before
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and lines[k].strip().startswith('^'):
                    notes.append(lines[k].strip()[1:].strip()); k += 1; j = k
                else:
                    break
            out.append(('table', s, rows, notes)); i = j; continue
        if s.startswith('|'):
            raise Problem(f'a table needs a caption line above it, such as **TABLE I.—Population, 1970**: found "{s}"')
        if s.startswith('^'):
            raise Problem(f'a note (a line starting ^) must come straight after a table: "{s}"')
        if re.match(r'[-+]\s|\*\s', s):
            raise Problem(f'bulleted lists are not used: number the items instead (1. 2. 3.): "{s}"')
        nxt = next((l.strip() for l in lines[i + 1:] if l.strip()), '')
        if re.match(r'\d{1,3}[.)]\s', s) and (not para or para[-1].rstrip().endswith(':')
                                                or (re.match(r'1[.)]\s', s) and re.match(r'2[.)]\s', nxt))):
            flush()
            items = []
            while i < len(lines) and re.match(r'\s*\d{1,3}[.)]\s', lines[i]):
                items.append(lines[i].strip()); i += 1
            out.append(('ol', items)); continue
        para.append(ln); i += 1
    flush()
    return out


def build(meta, body, base_dirs, warns):
    key = meta['key']
    blocks, imgs, after_head = [], {}, True
    fig_n = []

    def image(path, flags, n, kind):
        tried = []
        for d in ([] if os.path.isabs(path) else base_dirs) + ([''] if os.path.isabs(path) else []):
            p = os.path.join(d, path); tried.append(p)
            if os.path.isfile(p):
                break
        else:
            raise Problem(f'image not found: "{path}" (looked for ' + ', '.join(tried) + ')')
        im = ImageOps.exif_transpose(Image.open(p))
        if flags & {'colour', 'color'}:
            im = im.convert('RGB')
        else:
            im = ImageOps.autocontrast(im.convert('L'), cutoff=0.3)
        maxw = {'fig': 640, 'wfig': 1280, 'plate': 2400}[kind]
        if im.width > maxw:
            im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, 'WEBP', quality=80, method=6)
        ik = f'{key}.{"p" if kind == "plate" else ""}{n}'          # e.g. war.3 (Fig. 3), war.p1 (Plate I)
        if ik in imgs:
            raise Problem(f'two {"plates" if kind == "plate" else "figures"} are numbered {n}')
        imgs[ik] = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
        return ik, im.width, im.height

    for tok in tokenize(body):
        kind = tok[0]
        if kind == 'h':
            blocks.append({'t': 'h', 'html': inline(tok[1])}); after_head = True
        elif kind == 'img':
            _, line, capline = tok
            m = re.match(r'!\[(.*?)\]\((.+?)\)\s*((?:\{\s*\w+\s*\}\s*)*)$', line)
            if not m:
                raise Problem(f'cannot read the image line "{line}". Write ![Alt text](images/file.jpg) then any of '
                              '{wide} {plate} {line} {colour}')
            alt, path, fl = m.groups()
            flags = {f.lower() for f in re.findall(r'\{\s*(\w+)\s*\}', fl)}
            bad = flags - FLAGS
            if bad:
                raise Problem(f'unknown image option {{{bad.pop()}}}: use {{wide}}, {{plate}}, {{line}} or {{colour}}')
            bk = 'plate' if 'plate' in flags else 'wfig' if 'wide' in flags else 'fig'
            label, nstr, cap = caption(capline, 'Plate' if bk == 'plate' else 'Fig.')
            if (bk == 'plate') != label.startswith('Plate'):
                warns.append(f'"{label}": an image marked {{plate}} is captioned "Plate N.", other images "Fig. N."')
            n = int(nstr) if nstr.isdigit() else len([b for b in blocks if b['t'] == 'plate']) + 1
            if bk != 'plate':
                fig_n.append(n)
            ik, w, h = image(path, flags, n, bk)
            b = {'t': bk, 'n': n, 'img': ik, 'w': w, 'h': h, 'alt': alt or cap,
                 'cap': f'<span class="fign">{label}</span>—{inline(cap)}'}
            if 'line' in flags:
                b['line'] = True
            blocks.append(b)
        elif kind == 'table':
            _, capline, rows, notes = tok
            m = re.match(r'\*\*\s*table\s+([\dIVXLCivxlc]+)\b\s*\.?\s*' + DASH + r'?\s*[:.]?\s*(.*?)\s*\*\*\s*((?:\{\s*\w+\s*\}\s*)*)$',
                         capline, re.I)
            if not m or not m.group(2):
                raise Problem(f'cannot read the table caption "{capline}". Write **TABLE I.—Caption** on the line above the table')
            num, cap, fl = m.groups()
            h, ncol = table_html(rows)
            b = {'t': 'table', 'cap': inline(f'TABLE {num.upper()}.—{cap}'), 'cols': ncol, 'html': h}
            if 'span' in fl.lower():
                b['span'] = True
            blocks.append(b)
            for note in notes:
                blocks.append({'t': 'p', 'html': inline(note), 'cls': '', 'tnote': True})
        elif kind == 'ol':
            items = tok[1]
            first = int(re.match(r'(\d+)', items[0]).group(1))
            b = {'t': 'ol', 'items': [inline(re.sub(r'^\d+[.)]\s*', '', it)) for it in items]}
            if first != 1:
                b['start'] = first
            blocks.append(b)
        else:
            text = re.sub(r'(?<!-)\s*--\s*(?!-)', '—', tok[1].strip())
            if not blocks:
                cls = 'lead'
                if not text.startswith('**'):
                    warns.append('the first paragraph (the lead) usually starts with the headword in bold: **HEADWORD**, …')
            elif re.match(r'\*?\s*see also\b', text, re.I):
                cls = 'seealso'
                text = re.sub(r'^\*?\s*see also\s*\*?\s*[:.]?\s*\*?\s*', '*See also* ', text, flags=re.I)
            elif re.match(r'(\*\*)?\s*bibliography\b', text, re.I):
                cls = 'biblio'
                text = re.sub(r'^(\*\*)?\s*bibliography\s*[.:]?\s*(\*\*)?\s*[.:]?\s*' + DASH + r'?\s*', '%%BIB%%', text,
                              flags=re.I)
            elif re.fullmatch(r'\(\s*(?:[A-Z]\.\s*){1,6}\)', text):
                cls = 'sig'
                text = '(' + ' '.join(re.findall(r'[A-Z]\.', text)) + ')'
            elif re.match(r'\*[^*]+?\*\s*\.?\s*(?:—|–|-)', text):
                cls = 'sub'
                m = re.match(r'\*([^*]+?)\*\s*\.?\s*(?:—|–|-)+\s*', text)
                head = m.group(1).strip()
                text = f'*{head if head.endswith((".", "?", "!")) else head + "."}*—' + text[m.end():]
            else:
                cls = 'first' if after_head else ''
            if re.search(r'(?<!!)\[[^\]]+\]\([^)]+\)', text):
                warns.append('links like [text](url) are not supported: only the text is kept. Use [[HEADWORD]] for a '
                             'cross-reference')
                text = re.sub(r'(?<!!)\[([^\]]+)\]\([^)]+\)', r'\1', text)
            h = inline(text)
            if cls == 'sub':
                h = re.sub(r'^<em>(.+?)</em>—', r'<em class="runin">\1</em>—', h)
            if cls == 'biblio':
                h = h.replace('%%BIB%%', '<span class="bib">Bibliography.</span>—', 1)
            blocks.append({'t': 'p', 'html': h, 'cls': cls}); after_head = False
    if fig_n and fig_n != list(range(fig_n[0], fig_n[0] + len(fig_n))):
        warns.append('the figures are not numbered in order: ' + ', '.join(map(str, fig_n)))
    if not blocks:
        raise Problem('the article has no text')
    return blocks, imgs


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    page = Page(sys.argv[1])
    D, I = page.DATA, page.IMGS
    page_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
    results, problems, seen = [], [], {}
    for md_path in sys.argv[2:]:
        warns = []
        try:
            if not os.path.isfile(md_path):
                raise Problem('file not found')
            meta, body = read_front(open(md_path, encoding='utf-8').read(), md_path, warns)
            key = meta['key']
            if key in seen:
                raise Problem(f'key "{key}" is also used by {seen[key]}')
            seen[key] = md_path
            old = D.get(key)
            if old and old['meta'].get('kind') in ('atlas', 'stats'):
                raise Problem(f'key "{key}" is already used by the {old["meta"]["kind"]} entry "{old["meta"]["title"]}": '
                              'choose another key')
            group = 'Other Articles'
            if not meta.get('group'):
                warns.append('no "group:" given, so it is listed under Other Articles')
            else:
                group = match_group(page, meta['group'])
                if group is None:
                    raise Problem(f'group "{meta["group"]}" is not one of the contents groups set in the EDIT THIS block: '
                                  + '; '.join(f'"{g}"' for g in page.groups()) + '. Use one of these or add it to BOOK.groups.')
            if meta['guide'] != meta['guide'].upper():
                warns.append(f'the guide word "{meta["guide"]}" (the running head) is usually in capitals')
            dirs = list(dict.fromkeys([os.path.dirname(os.path.abspath(md_path)), page_dir]))
            blocks, imgs = build(meta, body, dirs, warns)
            start = int(meta['page'])
            m = {'guide': meta['guide'], 'title': meta['title'], 'start': start, 'vol': meta['volume'],
                 'sig': f"VOL. {meta['volume']}—{math.ceil(start / 32)}*", 'range': '', 'group': group}
            if 'order' in meta:
                m['ord'] = int(meta['order'])
            results.append((md_path, key, {'meta': m, 'blocks': blocks}, imgs, warns, bool(old)))
        except Problem as e:
            problems.append(f'{md_path}: {e}')
            for w in warns:
                problems.append(f'{md_path}: (warning) {w}')
    if problems:
        print('Nothing was saved. Fix these and run the command again:', file=sys.stderr)
        for p in problems:
            print('  - ' + p, file=sys.stderr)
        sys.exit(1)
    for md_path, key, entry, imgs, warns, replaced in results:
        D[key] = entry
        for k in [k for k in I if re.fullmatch(re.escape(key) + r'\.p?\d+', k)]:
            del I[k]
        I.update(imgs)
    size = page.save()
    for md_path, key, entry, imgs, warns, replaced in results:
        m = entry['meta']
        print(f'{"replaced" if replaced else "added"} {key}: "{m["title"]}", Vol. {m["vol"]}, from page {m["start"]} '
              f'({len(entry["blocks"])} blocks, {len(imgs)} images)')
        for w in warns:
            print(f'  warning: {w}')
    print(f'page saved: {human(size)}. Now run: python3 check.py {sys.argv[1]}')


if __name__ == '__main__':
    main()

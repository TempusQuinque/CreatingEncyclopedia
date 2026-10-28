# Instructions for AI assistants

This folder is a template for an in-universe encyclopaedia. The whole site is one file, `encyclopaedia.html`. Read this file and `README.md` before changing anything.

## The most important rule

`encyclopaedia.html` is large: under 1 MB now, up to 25 MB once maps and photographs are added. Almost all of it is image data on a few very long lines.

- **Never read, print or paste the whole file, and never rewrite or regenerate it.** Reading it floods your context. Writing it back from memory destroys it.
- The README's "open it in a text editor" is for people. You edit it as described here.
- To look at the code, search for a specific string (`grep -n "EDIT THIS" encyclopaedia.html`) and read only the lines around the match.
- Change the content only through the scripts below. Never edit `DATA`, `IMGS` or `TILES` by hand, and never reformat them.
- The only parts to edit by hand are:
  - the `EDIT THIS` block (`const BOOK = {…}`) near the top of the script;
  - the CSS, if the user asks for a different look.

  Edit them by replacing one exact string, never by writing out the whole file.
- Every script keeps the previous version as `encyclopaedia.html.bak`. If something goes wrong, copy it back.

## How to make each kind of change

| Task | What to do |
|---|---|
| Add or change an article | Write or edit `articles/<key>.md`, then run `python3 add_article.py encyclopaedia.html articles/<key>.md`. An article with the same key is replaced. |
| Rebuild every article | `python3 add_article.py encyclopaedia.html articles/*.md` |
| Add or replace a map plate | `python3 add_atlas.py encyclopaedia.html <key> <image.png> --title … --guide … --plate "PLATE II" --cap …` |
| Add or replace a statistical table | Save the figures as a CSV file in `stats/`, then run `python3 add_stats.py encyclopaedia.html stats/<file>.csv --num … --year … --title … --category …` |
| Remove entries | `python3 remove_entry.py encyclopaedia.html <key> [<key> …]` |
| Rename the book, change the cover or the contents groups | Edit the `EDIT THIS` block, then run `check.py`. The `<title>` tag on line 6 is updated from `BOOK.title` whenever a script saves the page. |
| Check the work | Run `python3 check.py encyclopaedia.html` after every change. Fix every ERROR, read the WARNINGS and report them. |

The Markdown files in `articles/` are the source of the articles. Never change an article's text inside the HTML: edit its `.md` file and run `add_article.py` again. If an article in the page has no `.md` file, `check.py` says so.

Every script prints `ERROR:` (or "Nothing was saved") and exits with status 1 when it refuses to do something. In that case the page has not changed. Read the message, fix the input and run the command again.

## Writing an article

Copy `articles/sample_country.md`, or `articles/sample_article.md` for figures and longer text. The full format is in README.md. The script depends on these rules:

- **The `---` block at the top has these fields:**

  | Field | Rule |
  |---|---|
  | `key` | Lower-case letters, digits and hyphens |
  | `title` | As listed in the contents |
  | `guide` | The running head, in capitals |
  | `volume` | A Roman numeral |
  | `page` | A whole number |
  | `group` | Must be one of the groups in `BOOK.groups` |
  | `order` | Optional: its position within its group |

  Put nothing else on these lines.
- **Blocks:** leave a blank line between them.
- **The lead:** the first paragraph starts with the headword in bold: `**HEADWORD**, …`
- **Headings:**
  - `## I. SECTION` for a section heading.
  - Below that, use run-in headings at the start of a paragraph: `*1. Title.*—Text…`. Never use `###`.
- **Dashes:** use em dashes, as the samples do. The script also accepts `--`.
- **Figures:** put the image line, then the caption on the next line: `*Fig. 1.—Caption, 1965.*`.
  - Number figures 1, 2, 3 in order.
  - A full-page image takes `{plate}` and the caption `*Plate I.—…*`.
  - Image paths are relative to the `.md` file or to this folder. Keep images in `images/`.
- **Tables:** put `**TABLE I.—Caption**`, then a pipe table on the next line, then any `^ Note` lines.
- **Lists:** numbered only (`1.`, `2.`). There are no bulleted lists and no web links.
- **Cross-references:** `[[HEADWORD]]` links to an entry whose title or guide word matches.
- **Endings, in this order:**
  - `*See also* [[A]]; [[B]].`
  - `**Bibliography.**—…`
  - the author's initials alone on the last line: `(A. B. C.)`

Write in the voice and conventions the user has chosen. If they haven't said, follow the samples: the dispassionate, factual voice of a printed reference work.

## Page numbers

Each article states its volume and first page, and articles in the same volume must not overlap.

- Start written articles on even, left-hand pages.
- Leave room between articles: in a real encyclopaedia, unwritten articles fill the gaps.
- `check.py` estimates each article's length (to about ±1 page) and warns of overlaps. `check.py --pages` counts the pages exactly in a browser.

## Checking the layout

The page breaks depend on the font, Libre Caslon Text, which loads from Google Fonts.

- If Playwright and an internet connection are available, run `python3 check.py encyclopaedia.html --pages`.
  - It sets every entry, counts its pages and reports script errors and text running past a column.
  - If it warns that the font did not load, its page counts are not reliable.
- Otherwise, tell the user that the layout hasn't been checked and ask them to open the file in a browser and look.
- Never claim that the pages are right without one of these checks.

## Do not

- Change the engine code (the script after the `EDIT THIS` block) unless the user asks.
  - If they do, make small, targeted edits.
  - Then run `check.py`, which checks the script's syntax if Node.js is installed, and `check.py --pages`.
- Use statistical table types other than `"navy"`, which is what `add_stats.py` writes. The others are fixed layouts from the original project.
- Let the page grow past 25 MiB, the Cloudflare Pages limit for one file. Large map plates are usually the cause: lower `add_atlas.py --quality` or use a smaller image.

## When you finish

Tell the user three things:
- what you changed;
- what `check.py` reported;
- whether the layout was checked in a browser.

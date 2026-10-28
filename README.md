# Encyclopaedia template

A blank template for an in-universe encyclopaedia. Articles are set as the two-column pages of a printed book, map plates open in a zoomable viewer, and there is a supplement of statistical tables. It is the engine behind *The Imperial Encyclopaedia*, with all of that project's content removed.

The whole site is **one HTML file**. There's no server, no framework and no build step: open `encyclopaedia.html` in a browser, or upload it to any static host (GitHub Pages, Cloudflare Pages, Netlify), and it works.

## What's in the folder

| File | What it is |
|---|---|
| `encyclopaedia.html` | The encyclopaedia, with four sample entries. Open it to see how everything looks. |
| `add_article.py` | Adds articles from Markdown files, or replaces those with the same key. |
| `add_atlas.py` | Adds a large map as an atlas plate with a zoomable viewer. |
| `add_stats.py` | Adds a statistical table from a CSV file. |
| `remove_entry.py` | Removes entries, for example the samples. |
| `check.py` | Checks the page for problems. Run it after every change. |
| `enc_common.py` | Shared code for the scripts. Keep it beside them. |
| `articles/` | The articles as Markdown: the two samples (placeholder text). Copy one to start your own. |
| `stats/` | The sample table as a CSV file. |
| `images/` | The sample images. |
| `AGENTS.md` | Instructions for an AI assistant working on the encyclopaedia. |

The scripts need Python 3 and Pillow (`pip install pillow`). `check.py --pages` also needs Playwright (`pip install playwright`, then `playwright install chromium`).

## Quick start

1. **Name your book.** Open `encyclopaedia.html` in a text editor and find the block marked `EDIT THIS` near the top of the script. Set the title, the edition line, the cover lettering, the atlas volume and the contents groups. (The `<title>` tag at the very top is brought into step with the title whenever a script runs.)
2. **Write an article** in Markdown (copy `articles/sample_country.md`), then add it:
   `python3 add_article.py encyclopaedia.html articles/my_article.md`
3. **Add a map plate:**
   `python3 add_atlas.py encyclopaedia.html world images/my_world_map.png --title "The World, 1970" --guide "THE WORLD, POLITICAL, 1970" --plate "PLATE I" --cap "The world: political divisions as at 1 Jan. 1970." --order 1`
4. **Add a statistical table** (see below):
   `python3 add_stats.py encyclopaedia.html stats/steel.csv --num I --year 1970 --title "PRODUCTION OF STEEL, 1970" --category "Industry"`
5. **Remove the samples** once you have your own entries:
   `python3 remove_entry.py encyclopaedia.html sample-article sample-country world st-sample-1970`
   and delete the sample files in `articles/`, `stats/` and `images/`.
6. **Check:** `python3 check.py encyclopaedia.html`. Then open the file in a browser to look at the pages, and upload it.

Every script saves the previous version of the page as `encyclopaedia.html.bak`. If a script finds a problem in what you gave it, it says what's wrong and changes nothing.

## Writing articles

Each article is a Markdown file in `articles/`. It starts with a short block of facts, exactly like this:

```
---
key: sample-country
title: Sample Country
guide: SAMPLE COUNTRY
volume: XIX
page: 412
group: Countries and Territories
---
```

| Field | What it is |
|---|---|
| `key` | A short code in lower-case letters, digits and hyphens. A link ending `#sample-country` opens the entry. |
| `title` | The name in the contents. |
| `guide` | The running head at the top of each page, in capitals. |
| `volume`, `page` | The volume (a Roman numeral) and the first page. Articles look best starting on an even, left-hand page. |
| `group` | The contents group: one of the groups set in the `EDIT THIS` block. |
| `order` | Optional. A number that sets the article's place within its group. Otherwise the group is in alphabetical order. |

Then the text. Leave a blank line between paragraphs and other blocks.

| Write | To get |
|---|---|
| The first paragraph, starting `**HEADWORD**,` | The lead, with the headword in bold |
| `## I. HISTORY` | A section heading |
| `*1. Early History.*—The kingdom…` | A paragraph with a run-in heading. Use these for subsections; `###` is not used. |
| `![Alt text](images/photo.jpg)` and the caption on the next line, `*Fig. 1.—Caption.*` | A numbered figure. After the image, add `{wide}` for a figure across both columns, `{plate}` for a full page (caption `*Plate I.—…*`), `{line}` for a drawing (no halftone screen) or `{colour}` to keep a photograph in colour. |
| `**TABLE I.—Caption**` and a pipe table on the next line | A ruled table. Numbers are set to the right. Add `{span}` after the caption for a table across the whole page. |
| `^ Note text.` after a table | A note printed under the table |
| `1. First item` lines | A numbered list. There are no bulleted lists. |
| `[[GREAT BRITAIN]]` | A cross-reference in small capitals. It becomes a link when an entry has that title or guide word. |
| `*See also* [[ZENDA]]; [[ELPHBERG DYNASTY]].` | The see-also line |
| `**Bibliography.**—…` | The bibliography |
| `(A. H. H.)` | The author's initials, alone on the last line |

- `*italic*` and `**bold**` work anywhere. Write `\*` for a plain asterisk.
- Use em dashes (—) as shown; `--` is turned into one.
- Image paths are relative to the Markdown file or to the encyclopaedia's folder.
- Photographs are made greyscale (unless `{colour}`) and resized: 640 px wide for a figure, 1,280 for a wide figure and 2,400 for a plate. They're stored inside the page as WebP.

You can add several articles at once (`python3 add_article.py encyclopaedia.html articles/*.md`). Keep the Markdown files: they're the source. To change an article, edit its file and add it again.

## How the pages are set

The page is laid out in the reader's browser each time an entry opens:
- Blocks are placed one after another into fixed-size columns.
- A paragraph that doesn't fit is split word by word. The column is filled without leaving a single line stranded at the head or foot of a column.
- A figure that doesn't fit waits for the next place it does.
- A plate gets a page of its own.
- On a narrow screen (under 840 px), the article flows as a single column instead.

The text is set in Libre Caslon Text, loaded from Google Fonts. The page breaks depend on the font, so always check new articles in a browser that can load it.

Each article's first page is fixed by its `page:` line, and articles in the same volume mustn't run into each other. `check.py` estimates every article's length and warns if one probably overlaps the next; `check.py --pages` counts the pages exactly.

## Atlas plates

`add_atlas.py` takes a large map image: 8,000–16,000 px wide is typical for a world map, exported as PNG from Inkscape or any drawing program. It stores a page-sized image and a pyramid of 1,024-px WebP tiles. The viewer loads only the tiles on screen, so the reader can zoom right in to small lettering.

Big maps make big pages: allow roughly 1 MB of tiles for every 4 million pixels of map. Lower `--quality` (default 70) if the file grows too large. Running the command again with the same key replaces the plate.

## Statistical tables

The statistical supplement is a set of ranked tables. Each table belongs to a **category** and a **year**. The contents lists each category, with a button for each of its years.

Make a table in any spreadsheet and save it as CSV:

```
Country,Steel (million tons),Share of world (%)
Ruritania,"1,250",12.5
Borduria,980,9.8
```

- **The first row** holds the headings: the name column first, then the number columns.
- **Ranks:** the rows are numbered 1, 2, 3… in order. For ranks of your own, add a first column headed `No.`.
- **Missing figures:** leave a cell empty for no figure, and it's printed as a dash.

Then:

```
python3 add_stats.py encyclopaedia.html stats/steel.csv --num I --year 1970 \
    --title "PRODUCTION OF STEEL, 1970" --category "Industry" \
    --sub "(Countries are ranked by production.)" --note "NOTES.—In million metric tons."
```

The same number and year replaces a table. `--sub` and `--note` are optional. Each category-and-year has its own first page in the supplement: set it with `--page`, or a new one starts two pages after the last. `stats/sample_table.csv` makes the sample table.

## Checking your work

`python3 check.py encyclopaedia.html` lists every entry and its pages. It reports:
- errors (things that must be fixed);
- warnings (probably wrong);
- notes.

It catches:
- a damaged or cut-short file, and syntax errors in the `EDIT THIS` block (when Node.js is installed);
- entries that won't appear in the contents because their group isn't in `BOOK.groups`;
- articles whose pages overlap;
- missing or unused images (`--remove-unused` deletes the unused ones);
- Markdown files that haven't been added, or have changed since;
- cross-references to entries that don't exist yet;
- a page too large for the host.

With `--pages`, it also sets every entry in a browser (Playwright, with an internet connection for the font). It counts the real pages and reports script errors and text running past the foot of a column.

## Working with an AI assistant

Give the assistant this folder and point it to `AGENTS.md`. Coding assistants that can run commands, such as Claude Code, Codex or Cursor, can follow it to write articles, add plates and tables, and check the result.

The main thing an assistant must not do is read or rewrite `encyclopaedia.html` itself: the file is mostly image data and will soon be many megabytes. All changes go through the scripts.

A chat assistant that can't run commands can still write articles in the Markdown format; you then run the scripts yourself.

## Publishing

Upload `encyclopaedia.html`, renamed `index.html` if it's the site's home page. Photographs and map tiles take nearly all the space, and hosts limit the size of one file:
- Cloudflare Pages allows 25 MiB.
- GitHub allows 100 MB.

A link to `index.html#key` opens that entry directly.

## Notes

- The cover, masthead and contents come from the `EDIT THIS` block. Everything else about the look is in the CSS at the top of the file.
- The sample text (lorem ipsum) and images are placeholders. Replace them.
- Don't upload `encyclopaedia.html.bak`: it's only a safety copy.

You're free to use and adapt this template.

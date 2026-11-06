#!/usr/bin/env python3
"""Check the rebuilt tables in figure-notes/<book>/chNN.json against the PDF.

Every word and number in a rebuilt table must appear in the text of the PDF page(s)
holding that figure. This catches typos and invented values. It does not check
position: a value put in the wrong row or column, or a cell left out, is not caught,
so every table is also checked by eye against a render of the page.

    python3 scripts/check_tables.py handbooks/faa-h-8083-30b/ch06-aircraft-weight-and-balance.md
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# Some FAA tables use a font whose "fi" and "ff" ligatures come out of the PDF text
# layer as stray characters ("short \u00ffeld takeo\u02dbs"). Map them back.
LIGATURES = {"\u00ff": "fi", "\u02db": "ff"}


def tokens(s):
    for k, v in LIGATURES.items():
        s = s.replace(k, v)
    s = s.replace("\u2013", "-").replace("\u2212", "-").replace("\u00ad", "-")
    return re.findall(r"[A-Za-z]+|[-+]?\d[\d,]*\.?\d*|[-+]", s)


def main():
    md_path = Path(sys.argv[1])
    m = re.match(r"ch(\d+)-", md_path.name)
    notes_path = ROOT / "figure-notes" / md_path.parent.name / f"ch{m.group(1)}.json"
    notes = json.loads(notes_path.read_text())
    md = md_path.read_text()
    pdf = md_path.with_suffix(".pdf")
    bad = 0
    for num, note in notes.items():
        if not note.get("table"):
            continue
        # page(s) of the figure: around the page marker before its caption (the app sometimes
        # puts a figure one page early)
        pos = md.index(f"**Figure {num}.**")
        page = re.findall(r"\[Page \d+-(\d+)\]", md[:pos])[-1]
        first = int(page) - 1 if int(page) > 1 else 1
        text = subprocess.check_output(["pdftotext", "-f", str(first), "-l", str(int(page) + 2),
                                        str(pdf), "-"], text=True, stderr=subprocess.DEVNULL)
        page_tokens = tokens(text)
        cells = [c.strip() for row in note["table"].splitlines()[2:]
                 for c in row.strip("|").split("|")]
        missing = []
        for cell in cells:
            for t in tokens(cell):
                if t in "+-" or t.isalpha() and len(t) < 3:
                    continue
                if t not in page_tokens:
                    missing.append(t)
        status = "ok" if not missing else f"NOT IN PDF: {missing}"
        bad += bool(missing)
        print(f"Figure {num}: {len(cells)} cells, {status}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export one FAA-H-8083 handbook chapter to Markdown from Cam's AMT Handbooks app data.

Usage:
    python3 scripts/export_handbook.py --atk ../atk-amt-handbooks FAA-H-8083-31B 13

Reads   <atk>/public/content/<BOOK>/chapters/ch-NN.json   (text, headings, printed
        pages, figure captions; extracted from the FAA PDF by the app's pipeline)
        figure-notes/<book-id>/chNN.json                   (figure descriptions and
        rebuilt tables, written by hand and checked against the PDF)
Writes  handbooks/<book-id>/chNN-<slug>.md

The handbook text is copied as extracted, not edited. The app repo commit is
recorded in the output. This and build_acs.py are the only places source data
enters the repo; when a separate system provides it, replace them.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_URL = "https://amt-handbooks.aviatorstoolkit.com/#/{book}/{chapter}/{section}"
PENDING = "(Description not yet written.)"


def slugify(title: str) -> str:
    title = title.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                       text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def load_notes(book_id: str, chapter: int) -> dict:
    path = ROOT / "figure-notes" / book_id / f"ch{chapter:02d}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_figure(b, notes, warnings):
    note = notes.get(b["number"], {})
    out = [f"**Figure {b['number']}.** {b['caption']}", ""]
    if note.get("table"):
        out += [note["table"].rstrip(), ""]
    desc = note.get("description")
    if not desc:
        warnings.append(f"Figure {b['number']}: no description")
    out += [f"*Figure description:* {desc or PENDING}", ""]
    return out


def export(atk: Path, book: str, chapter: int):
    book_id = book.lower()
    meta = json.loads((atk / "public/content" / book / "meta.json").read_text(encoding="utf-8"))
    ch = json.loads((atk / "public/content" / book / "chapters" / f"ch-{chapter:02d}.json")
                    .read_text(encoding="utf-8"))
    notes = load_notes(book_id, chapter)
    warnings = []

    title = ch["title"]
    lines = [
        f"# {book} {meta['title']}",
        "",
        f"## Chapter {chapter}: {title}",
        "",
        f"Source: {book}, {meta['title']} ({meta['editionYear']}), "
        f"Chapter {chapter}, pages {ch['printedPageStart']} to {ch['printedPageEnd']}. "
        f"Published by the {meta['publisher']}. {meta['license']}.",
        "",
        "This is a faithful Markdown conversion of the FAA text. Page markers like "
        "[Page 13-8] show where each printed page starts. Figures are given as their "
        "caption plus a written description; the images are not included.",
        "",
        f"Converted by `scripts/export_handbook.py` from the AMT Handbooks app data "
        f"(campeterson/atk-amt-handbooks at commit `{git_commit(atk)}`). "
        f"Original PDF of this chapter: `{slug_name(chapter, title)}.pdf`.",
        "",
    ]
    level_prefix = {2: "###", 3: "####", 4: "#####"}
    page = None

    def mark(p):
        nonlocal page
        if p and p != page:
            page = p
            lines.extend([f"[Page {p}]", ""])

    for s in ch["sections"]:
        if s["title"] and s["id"] != "intro":
            mark(s["printedPage"])
            lines += [f"{level_prefix.get(s['level'], '#####')} {s['title']}", ""]
        for b in s["blocks"]:
            mark(b.get("printedPage"))
            kind = b["kind"]
            if kind == "paragraph":
                lines += [b["md"], ""]
            elif kind == "list":
                for i, item in enumerate(b["items"], 1):
                    lines.append(f"{i}. {item}" if b.get("ordered") else f"- {item}")
                lines.append("")
            elif kind == "figure":
                lines += render_figure(b, notes, warnings)
            elif kind == "equation":
                # In this data these are in-text figure references kept as images;
                # the alt text holds the exact printed text.
                lines += [b["alt"], ""]
            else:
                warnings.append(f"{b['id']}: unknown block kind {kind!r}, skipped")

    out = ROOT / "handbooks" / book_id / f"{slug_name(chapter, title)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    figs = sum(1 for s in ch["sections"] for b in s["blocks"] if b["kind"] == "figure")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes, "
          f"{len(ch['sections'])} sections, {figs} figures)")
    pending = [w for w in warnings if w.endswith("no description")]
    if pending:
        print(f"  {len(pending)} of {figs} figures still need a description")
    for w in warnings:
        if not w.endswith("no description"):
            print("  WARNING", w)


def slug_name(chapter: int, title: str) -> str:
    return f"ch{chapter:02d}-{slugify(title)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atk", required=True, type=Path,
                    help="path to a checkout of campeterson/atk-amt-handbooks")
    ap.add_argument("book", help="handbook code, e.g. FAA-H-8083-31B")
    ap.add_argument("chapters", nargs="+", type=int, help="chapter numbers")
    args = ap.parse_args()
    if not (args.atk / "public/content" / args.book).is_dir():
        sys.exit(f"No data for {args.book} under {args.atk}/public/content")
    for n in args.chapters:
        export(args.atk, args.book, n)


if __name__ == "__main__":
    main()

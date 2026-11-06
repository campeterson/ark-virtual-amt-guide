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


def load_corrections(book_id: str, chapter: int) -> dict:
    path = ROOT / "corrections" / book_id / f"ch{chapter:02d}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fix_hyphens(text: str, corr: dict) -> str:
    """Restore hyphens the app dropped where the PDF breaks a compound at a line end."""
    for word in corr.get("hyphen_fixes", []):
        joined = word.replace("-", "")
        text = re.sub(rf"\b{re.escape(joined)}\b", word, text)
        text = re.sub(rf"\b{re.escape(joined.capitalize())}\b", word[0].upper() + word[1:], text)
    return text


def render_figure(b, notes, warnings, corr=None):
    note = notes.get(b["number"], {})
    caption = (corr or {}).get("captions", {}).get(b["number"], b["caption"])
    out = [f"**Figure {b['number']}.** {fix_hyphens(caption, corr or {})}", ""]
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
    level_prefix = {2: "###", 3: "####", 4: "#####", 5: "######"}
    corr = load_corrections(book_id, chapter)
    if corr:
        lines[-2] += f" Text fixes from `corrections/{book_id}/ch{chapter:02d}.json` are applied."
    used = set()
    page = None

    def mark(p):
        nonlocal page
        if p and p != page:
            page = p
            lines.extend([f"[Page {p}]", ""])

    def heading(title, level, printed_page):
        mark(printed_page)
        lines.extend([f"{level_prefix.get(level, '######')} {title}", ""])

    def text_block(b):
        mark(b.get("printedPage"))
        if b["kind"] == "paragraph":
            lines.extend([fix_hyphens(b["md"], corr), ""])
        else:
            start = b.get("start") or corr.get("list_start", {}).get(b.get("id"), 1)
            for i, item in enumerate(b["items"], start):
                item = fix_hyphens(item, corr)
                lines.append(f"{i}. {item}" if b.get("ordered") else f"- {item}")
            lines.append("")

    for s in ch["sections"]:
        if s["title"] and s["id"] != "intro":
            level = corr.get("section_levels", {}).get(s["id"], s["level"])
            heading(s["title"], level, s["printedPage"])
        for b in s["blocks"]:
            bid = b.get("id")
            if bid in corr.get("insert_heading_before", {}):
                h = corr["insert_heading_before"][bid]
                heading(h["title"], h["level"], h["printedPage"])
                used.add(("insert_heading_before", bid))
            for nb in corr.get("insert_before", {}).get(bid, []):
                text_block(nb)
                used.add(("insert_before", bid))
            if bid in corr.get("replace", {}):
                for nb in corr["replace"][bid]:
                    text_block(nb)
                used.add(("replace", bid))
                kind = None
            else:
                kind = b["kind"]
            if kind in ("paragraph", "list"):
                text_block(b)
            elif kind == "figure":
                lines += render_figure(b, notes, warnings, corr)
            elif kind == "equation":
                # In this data these are in-text figure references kept as images;
                # the alt text holds the exact printed text.
                lines += [b["alt"], ""]
            elif kind is not None:
                warnings.append(f"{b['id']}: unknown block kind {kind!r}, skipped")
            for nb in corr.get("insert_after", {}).get(bid, []):
                text_block(nb)
                used.add(("insert_after", bid))
        for nb in corr.get("append_to_section", {}).get(s["id"], []):
            text_block(nb)
            used.add(("append_to_section", s["id"]))

    # every correction must have found its target, or the app data has changed
    for key in ("insert_heading_before", "insert_before", "replace", "insert_after",
                "append_to_section"):
        for target in corr.get(key, {}):
            if (key, target) not in used:
                warnings.append(f"correction {key} -> {target} matched nothing")

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

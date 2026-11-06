#!/usr/bin/env python3
"""Check a converted handbook chapter against its FAA PDF.

Usage:
    python3 scripts/check_chapter.py handbooks/faa-h-8083-31b/ch13-aircraft-landing-gear-systems.md

The PDF is the file with the same name and a .pdf extension.

Checks 1-3 compare text reduced to lowercase letters and digits (so
hyphenation, quotes and spacing don't matter):

1. Nothing missing: every line of body text in the PDF must appear in the
   Markdown. Body text is picked out by line height, which drops figure
   labels, headings and page numbers.
2. Nothing scrambled: every sentence of handbook text in the Markdown must
   appear in the PDF body text, read one column at a time. This catches
   paragraphs whose two columns were merged line by line.
   Also: no sentence duplicated, and paragraphs in the PDF's order.
3. Captions exact: each figure caption must match the PDF's caption in full.
4. Hyphens kept: compounds hyphenated at a PDF line end ("single-engine")
   must not come out joined ("singleengine").
5. Formulas: flags debris left by flattened fractions ("= D – ( ) W", a lone "W").

Lines or sentences that are known to be fine (e.g. a figure label that
happens to be set at body-text height) can be listed in the chapter's
corrections file under "check_ignore", with the reason.

Exits 1 if anything is reported.
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Body text and captions are picked out by line height, measured from each PDF:
# the same handbook comes out at different heights depending on how the PDF was
# produced (the FAA original vs. a re-saved copy).
MIN_CHARS = 25                    # ignore shorter fragments

LINE_RE = re.compile(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">'
                     r'(.*?)</line>', re.S)
WORD_RE = re.compile(r'>([^<]*)</word>')


def norm(s: str) -> str:
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def is_label(t: str) -> bool:
    """A figure callout that happens to be set at body or caption height ("Inl",
    "B A", "m b er D"): short, no ordinary word, or no sentence ending."""
    t = t.strip()
    if re.search(r"[.:;\])]$", t):       # ends like a sentence, list number or caption
        return False
    return len(t) < 12 or not re.search(r"[a-z]{3,}", t)


def _all_lines(pdf: Path):
    xml = subprocess.check_output(["pdftotext", "-bbox-layout", str(pdf), "-"], text=True,
                                  stderr=subprocess.DEVNULL)
    for page_no, page in enumerate(xml.split("<page ")[1:], 1):
        width = float(re.search(r'width="([\d.]+)"', page).group(1))
        for m in LINE_RE.finditer(page):
            x0, y0, x1, y1 = map(float, m.groups()[:4])
            text = html.unescape(" ".join(WORD_RE.findall(m.group(5))))
            yield page_no, width, x0, y0, round(y1 - y0, 1), text


def line_heights(lines):
    """(body_min, body_max, caption_min, caption_max) for this PDF. Body height is the
    most common height of full lines; caption height the most common height of lines
    that start "Figure N-N."."""
    from collections import Counter
    body = Counter(h for *_, h, t in lines if len(t.split()) >= 6)
    cap = Counter(h for *_, h, t in lines if re.match(r"Figure \d+[-\u00ad]\d+\.", t))
    hb = body.most_common(1)[0][0]
    hc = cap.most_common(1)[0][0] if cap else hb
    if hc >= hb - 0.3:          # captions not distinguishable by height
        return hb - 0.4, hb + 0.6, None, None
    return hb - 0.4, hb + 0.6, hc - 0.3, hc + 0.3


def pdf_body_lines(pdf: Path, captions=True):
    """Body-text (and caption) lines in reading order: page by page, left column then
    right. Returns (page, text, kind) with kind "body" or "caption"."""
    lines = list(_all_lines(pdf))
    bmin, bmax, cmin, cmax = line_heights(lines)
    out, cur, buf = [], None, []
    for page_no, width, x0, y0, h, text in lines + [(None, 1, 0, 0, 0, "")]:
        if page_no != cur:
            buf.sort()
            out += [(cur, t, k) for _, _, _, t, k in buf]
            cur, buf = page_no, []
        if page_no is None:
            break
        if re.fullmatch(r"\d+-\d+", text.strip()):          # page number
            continue
        if bmin <= h <= bmax:
            kind = "body"
        elif captions and cmin is not None and cmin <= h <= cmax:
            kind = "caption"
        else:
            continue
        buf.append((0 if x0 < width / 2 else 1, y0, x0, text, kind))
    return out


def md_handbook_text(md: str) -> str:
    """The Markdown minus everything the converter added (header, page markers,
    figure descriptions, rebuilt tables)."""
    body = md.split("\n[Page ", 1)
    md = "[Page " + body[1] if len(body) == 2 else md
    md = re.sub(r"^\[Page [^\]]+\]$", "", md, flags=re.M)
    # rebuilt tables sit between a caption and its description: converter material
    md = re.sub(r"(^\*\*Figure [^\n]*\n)(.*?)(^\*Figure description:\*)", r"\1\3", md,
                flags=re.M | re.S)
    # a description runs from its marker to the next blank line
    md = re.sub(r"^\*Figure description:\*.*?(?=\n\s*\n|\Z)", "", md, flags=re.M | re.S)
    md = re.sub(r"^\|.*\|$", "", md, flags=re.M)
    md = re.sub(r"\*\*(Figure [^*]+)\*\*", r"\1", md)
    return md


def splits_once(n: str, ref: str, min_piece: int = 15) -> bool:
    """True if n is two pieces of ref (a sentence cut by one column or page break,
    with a caption or figure in between). A scrambled sentence needs three or more."""
    lo, hi = 0, len(n)            # longest prefix of n found in ref
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if n[:mid] in ref:
            lo = mid
        else:
            hi = mid - 1
    return lo >= min_piece and len(n) - lo >= min_piece and n[lo:] in ref


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    md_path = Path(sys.argv[1])
    pdf_path = md_path.with_suffix(".pdf")
    m = re.match(r"ch(\d+)-", md_path.name)
    corr = ROOT / "corrections" / md_path.parent.name / f"ch{m.group(1)}.json" if m else None
    ignore = []
    if corr and corr.exists():
        ignore = [norm(x["text"]) for x in json.loads(corr.read_text())
                  .get("check_ignore", [])]

    md = md_handbook_text(md_path.read_text(encoding="utf-8"))
    md_n = norm(re.sub(r"^#+ ", "", md, flags=re.M))
    md = re.sub(r"^#+ .*$", "", md, flags=re.M)   # headings aren't body-height text in the PDF
    lines = pdf_body_lines(pdf_path)
    # body text and captions are read as separate streams, so a caption set between
    # two halves of a sentence doesn't break it
    ref_n = (norm(" ".join(t for _, t, k in lines if k == "body")) + "|"
             + norm(" ".join(t for _, t, k in lines if k == "caption")))

    def ignored(n):
        return any(n in i or i in n for i in ignore)

    missing = []
    for page, text, _ in lines:
        n = norm(text)
        if len(n) >= MIN_CHARS and n not in md_n and not ignored(n):
            missing.append((page, text))

    scrambled = []
    for para in md.split("\n"):             # list items and formula lines one at a time
        for sent in re.split(r"(?<=[.?!:;])\s+", para.strip()):
            n = norm(sent)
            if len(n) < MIN_CHARS or n in ref_n or ignored(n):
                continue
            if splits_once(n, ref_n):
                continue
            scrambled.append(sent)

    # 2b. nothing duplicated: a sentence must not appear in the Markdown more often
    # than in the PDF (catches a fix that re-adds text the app already had elsewhere)
    duplicated = []
    seen = {}
    for para in re.split(r"\n\s*\n", md):
        for sent in re.split(r"(?<=[.?!])\s+", para.strip()):
            n = norm(sent)
            if len(n) >= 40:
                seen[n] = seen.get(n, 0) + 1
    for n, count in seen.items():
        if count > 1 and count > ref_n.count(n):
            duplicated.append(n[:120])

    # 2c. paragraphs in the PDF's order
    body_ref = norm(" ".join(t for _, t, k in lines if k == "body"))
    out_of_order, prev = [], -1
    for para in re.split(r"\n\s*\n", md):
        p = para.strip()
        if p.startswith(("Figure ", "[Figure")):
            continue
        n = norm(p)[:60]
        if len(n) < 30:
            continue
        i = body_ref.find(n, max(prev, 0))     # text the FAA repeats: take the next one
        if i < 0:
            i = body_ref.find(n)
        if i < 0:
            continue
        if i < prev:
            out_of_order.append(p[:120])
        prev = i

    # 3. every figure caption complete and exact. PDF captions are rebuilt line by line:
    # a line starting "Figure N." opens a caption; short fragments without a full stop
    # (figure labels that happen to be set at caption height) are skipped.
    pdf_caps, cur = {}, None
    for _, t, k in lines:
        if k != "caption":
            continue
        m = re.match(r"Figure (\d+)[\u00ad-](\d+)\.", t)
        if m:
            cur = f"{m.group(1)}-{m.group(2)}"
            pdf_caps[cur] = t
        elif cur and not is_label(t):
            pdf_caps[cur] += " " + t
    bad_captions = []
    for m in re.finditer(r"^Figure (\d+-\d+)\. (.*)$", md, flags=re.M):
        n = norm(f"Figure {m.group(1)}. {m.group(2)}")
        if norm(pdf_caps.get(m.group(1), "")) != n and not ignored(n):
            bad_captions.append((m.group(1), m.group(2)))

    # 4. hyphens kept: this handbook doesn't split words across lines, so a hyphen at a
    # line end is a real compound hyphen ("single-engine"). The joined form must not
    # appear in the Markdown more often than the PDF prints it mid-line.
    raw = subprocess.check_output(["pdftotext", "-raw", str(pdf_path), "-"], text=True)
    flat = re.sub(r"\s+", " ", raw.replace("\u00ad", "-"))
    lost_hyphens = set()
    for (_, a, _), (_, b, _) in zip(lines, lines[1:]):
        m1 = re.search(r"(\w+)[\u00ad-]$", a.rstrip())
        m2 = re.match(r"(\w+)", b.lstrip())
        if not (m1 and m2):
            continue
        joined = m1.group(1) + m2.group(1)
        pat = rf"\b{re.escape(joined)}\b"
        if len(re.findall(pat, md, re.I)) > len(re.findall(pat, flat, re.I)):
            lost_hyphens.add(f"{m1.group(1)}-{m2.group(1)}")

    # 5. formulas: stacked fractions flattened by extraction leave tell-tale debris,
    # e.g. "F × L CG = D – ( ) W" or a lone "W" paragraph. Formulas that were rewritten
    # by hand (see the corrections file) don't have these.
    garbled = []
    for para in re.split(r"\n\s*\n", md):
        p = para.strip()
        if not p or p.startswith(("Figure ", "[Figure", "|", "-", "*")):
            continue
        if re.search(r"\(\s*\)", p) or re.fullmatch(r"[A-Z]{1,2}", p) or \
                (len(p) < 60 and "=" in p and re.search(r"[A-Za-z]\s+[A-Za-z]+\s*=", p)
                 and not re.search(r"[÷/]|\(.*\)", p)):
            if not ignored(norm(p)):
                garbled.append(p[:120])

    print(f"{md_path.name}: {len(lines)} PDF body lines checked")
    print(f"  missing from Markdown: {len(missing)}")
    for page, text in missing:
        print(f"    PDF p{page}: {text}")
    print(f"  not found in PDF (scrambled or altered): {len(scrambled)}")
    for s in scrambled:
        print(f"    {s[:200]}")
    print(f"  duplicated sentences: {len(duplicated)}")
    for d in duplicated:
        print(f"    {d}")
    print(f"  paragraphs out of order: {len(out_of_order)}")
    for o in out_of_order:
        print(f"    {o}")
    print(f"  captions not matching the PDF: {len(bad_captions)}")
    for num, cap in bad_captions:
        print(f"    Figure {num}: {cap[:200]}")
    print(f"  possible garbled formulas: {len(garbled)}")
    for x in garbled:
        print(f"    {x}")
    print(f"  hyphens lost at PDF line ends: {len(lost_hyphens)}")
    for h in sorted(lost_hyphens):
        print(f"    {h}")
    sys.exit(1 if missing or scrambled or duplicated or out_of_order or bad_captions
             or lost_hyphens or garbled else 0)


if __name__ == "__main__":
    main()

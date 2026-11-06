"""Shared helpers for corrections/<book>/build_chNN.py.

A chapter's build script lists the hand-checked text fixes (block replacements and
insertions, each pulled from the PDF with pdf_grab), then calls write_corrections().
That adds the fixes that can be worked out mechanically from the PDF:

- section_levels: heading level of every app section, from the PDF's heading style
  (A-head red Arial 17 -> 2, B-head Helvetica 15 -> 3, C-head Times 17 -> 4,
  D-head italic Times 15 -> 5)
- captions: any caption that differs from the PDF's caption is replaced by the PDF's
- hyphen_fixes: compounds hyphenated at a PDF line end that the app joined

The result is checked with scripts/check_chapter.py, never trusted on its own.
"""
import html
import json
import re
import subprocess
from pathlib import Path

from check_chapter import is_label, norm, pdf_body_lines

ROOT = Path(__file__).resolve().parent.parent


def _clean(t):
    return (t.replace("­", "-").replace("’", "'").replace("‘", "'")
            .replace("“", '"').replace("”", '"'))


def _key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))


def heading_levels(pdf: Path, app: dict):
    xml = subprocess.check_output(["pdftohtml", "-xml", "-i", "-stdout", str(pdf)], text=True,
                                  stderr=subprocess.DEVNULL)
    level = {}
    for m in re.finditer(r'<fontspec id="(\d+)" size="(\d+)" family="[^+"]*\+?([^"]+)" '
                         r'color="([^"]+)"', xml):
        fid, size, fam, color = m.groups()
        if size == "17" and fam.startswith("Arial") and color == "#ef4144":
            level[fid] = 2
        elif size == "15" and fam == "Helvetica" and color == "#000000":
            level[fid] = 3
        elif size == "17" and fam.startswith("TimesNewRomanPS") and color == "#000000":
            level[fid] = 4
    italic15 = {m.group(1) for m in re.finditer(
        r'<fontspec id="(\d+)" size="15" family="[^+"]*\+?TimesNewRomanPS[^"]*" color="#000000"', xml)}
    pdf_level = {}
    for page in xml.split("<page ")[1:]:
        prev = None
        for m in re.finditer(r'<text top="(\d+)" left="(\d+)"[^>]*font="(\d+)"[^>]*>(.*?)</text>', page):
            top, left, f, raw = m.groups()
            t = _clean(html.unescape(re.sub("<[^>]+>", "", raw))).strip()
            if f in level and t:
                # a heading set on two lines: same font, next line down
                if prev and prev[1] == f and 0 < int(top) - prev[2] < 25:
                    del pdf_level[prev[0]]
                    t = prev[3] + " " + t
                pdf_level[_key(t)] = level[f]
                prev = (_key(t), f, int(top), t)
            else:
                prev = None
                if f in italic15 and raw.startswith("<i>") and t and len(t) <= 45 and not t.endswith("."):
                    pdf_level.setdefault(_key(t), 5)
    levels, unmatched = {}, []
    for s in app["sections"]:
        if s["id"] == "intro":
            continue
        lv = pdf_level.get(_key(s["title"]))
        if lv is None:
            unmatched.append(s["title"])
        elif lv != s["level"]:
            levels[s["id"]] = lv
    return levels, unmatched


def pdf_captions(pdf: Path):
    caps, cur = {}, None
    for _, t, k in pdf_body_lines(pdf):
        if k != "caption":
            continue
        m = re.match(r"Figure (\d+)[­-](\d+)\.\s*(.*)", t)
        if m:
            cur = f"{m.group(1)}-{m.group(2)}"
            caps[cur] = m.group(3)
        elif cur and not is_label(t):
            caps[cur] += " " + t.strip()
    return {k: _clean(v).strip() for k, v in caps.items()}


def caption_fixes(pdf: Path, app: dict):
    caps = pdf_captions(pdf)
    fixes = {}
    for s in app["sections"]:
        for b in s["blocks"]:
            if b["kind"] == "figure" and b["number"] in caps:
                if norm(caps[b["number"]]) != norm(b["caption"]):
                    fixes[b["number"]] = caps[b["number"]]
    return fixes


def hyphen_fixes(pdf: Path, app: dict):
    lines = pdf_body_lines(pdf)
    raw = subprocess.check_output(["pdftotext", "-raw", str(pdf), "-"], text=True,
                                  stderr=subprocess.DEVNULL)
    flat = re.sub(r"\s+", " ", raw.replace("­", "-"))
    text = " ".join((b.get("md") or b.get("caption") or " ".join(b.get("items", [])))
                    for s in app["sections"] for b in s["blocks"])
    fixes = set()
    for (_, a, _), (_, b, _) in zip(lines, lines[1:]):
        m1 = re.search(r"(\w+)[­-]$", a.rstrip())
        m2 = re.match(r"(\w+)", b.lstrip())
        if not (m1 and m2):
            continue
        joined = m1.group(1) + m2.group(1)
        pat = rf"\b{re.escape(joined)}\b"
        if re.search(pat, text, re.I) and not re.search(pat, flat, re.I):
            fixes.add(f"{m1.group(1)}-{m2.group(1)}")
    return sorted(fixes)


def write_corrections(book: str, chapter: int, atk: Path, out: Path, **manual):
    """manual: replace, insert_before, insert_after, append_to_section,
    insert_heading_before, list_start, check_ignore, extra captions/hyphen_fixes."""
    pdf = next((ROOT / "handbooks" / book.lower()).glob(f"ch{chapter:02d}-*.pdf"))
    app = json.loads((atk / "public/content" / book / "chapters" / f"ch-{chapter:02d}.json")
                     .read_text(encoding="utf-8"))
    levels, unmatched = heading_levels(pdf, app)
    caps = caption_fixes(pdf, app)
    for num in manual.pop("keep_app_captions", []):   # PDF caption polluted by figure text
        caps.pop(num, None)
    caps.update(manual.pop("captions", {}))
    hyph = sorted(set(hyphen_fixes(pdf, app)) | set(manual.pop("hyphen_fixes", [])))
    # formulas rewritten from stacked fractions can't be found in the PDF's text layer
    ignore = manual.setdefault("check_ignore", [])
    for key in ("replace", "insert_before", "insert_after"):
        for blocks in manual.get(key, {}).values():
            for b in blocks:
                if b.pop("formula", False):
                    for line in b["md"].split("  \n"):
                        ignore.append({"text": line, "reason": "Formula rewritten on one line "
                                       "from a stacked fraction in the PDF; read off a page render."})
    data = {
        "chapter": f"{book} ch-{chapter:02d}",
        "about": "Fixes applied by scripts/export_handbook.py on top of the AMT Handbooks app "
                 "data. Replacement text is taken from the FAA PDF (see the build script "
                 "beside this file, which regenerates it). Checked with "
                 "scripts/check_chapter.py.",
        "section_levels": levels,
        **{k: v for k, v in manual.items() if v},
        "captions": caps,
        "hyphen_fixes": hyph,
    }
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: {len(levels)} level fixes, {len(caps)} captions, "
          f"{len(hyph)} hyphen fixes, {len(manual.get('replace', {}))} replacements")
    if unmatched:
        print("  sections with no PDF heading:", unmatched)

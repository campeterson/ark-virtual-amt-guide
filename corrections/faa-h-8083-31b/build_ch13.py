"""Build corrections/faa-h-8083-31b/ch13.json: fixes for FAA-H-8083-31B Chapter 13 on
top of the AMT Handbooks app data. Replacement text is pulled from the FAA PDF with
scripts/pdf_grab.py, not typed.

    python3 corrections/faa-h-8083-31b/build_ch13.py --atk ../atk-amt-handbooks

Then re-export and check:
    python3 scripts/export_handbook.py --atk ../atk-amt-handbooks FAA-H-8083-31B 13
    python3 scripts/check_chapter.py handbooks/faa-h-8083-31b/ch13-aircraft-landing-gear-systems.md
"""
import argparse, json, re, html, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from pdf_grab import Grabber
from check_chapter import pdf_body_lines

ap = argparse.ArgumentParser()
ap.add_argument('--atk', required=True, type=Path, help='checkout of campeterson/atk-amt-handbooks')
args = ap.parse_args()
PDF = ROOT / 'handbooks/faa-h-8083-31b/ch13-aircraft-landing-gear-systems.pdf'
OUT = Path(__file__).with_name('ch13.json')
APP = args.atk / 'public/content/FAA-H-8083-31B/chapters/ch-13.json'
grab = Grabber(PDF).grab


def para(start, end, page, split_at=None):
    """One or more paragraph blocks from the PDF. Paragraph breaks come from the
    PDF's line spacing; split_at forces an extra break before that text."""
    text, pg = grab(start, end, page)
    if split_at:
        text = text.replace(' ' + split_at, '\n\n' + split_at)
    return [{"kind": "paragraph", "md": p.strip(), "printedPage": f"13-{pg}"}
            for p in text.split('\n\n') if p.strip()]


def unlabel(blocks, join=False):
    """Drop figure callout letters (A, B) that sit at body-text height on p13-35."""
    out = []
    for bl in blocks:
        md = re.sub(r'(?:\s+[AB])+$', '', bl['md']).strip()
        if re.fullmatch(r'[AB](\s+[AB])*', md):
            continue
        out.append(dict(bl, md=md))
    if join and out:
        out = [dict(out[0], md=' '.join(b['md'] for b in out))]
    return out


def page_of(start, page):
    return f"13-{grab(start, start.split()[-1], page)[1]}"


app = json.load(open(APP))
blocks = {b['id']: b for s in app['sections'] for b in s['blocks']}


def app_md(i):
    return blocks[i]['md']


# ---- heading levels from the PDF's heading styles --------------------------
FONT_LEVEL = {}
xml = subprocess.check_output(['pdftohtml', '-xml', '-i', '-stdout', str(PDF)], text=True, stderr=subprocess.DEVNULL)
for m in re.finditer(r'<fontspec id="(\d+)" size="(\d+)" family="[^+]*\+([^"]+)" color="([^"]+)"', xml):
    fid, size, fam, color = m.groups()
    if size == '17' and fam.startswith('Arial') and color == '#ef4144':
        FONT_LEVEL[fid] = 2          # A-head
    elif size == '15' and fam == 'Helvetica' and color == '#000000':
        FONT_LEVEL[fid] = 3          # B-head
    elif size == '17' and fam.startswith('TimesNewRomanPS') and color == '#000000':
        FONT_LEVEL[fid] = 4          # C-head
heads = []
for pn, page in enumerate(xml.split('<page ')[1:], 1):
    prev = None
    for m in re.finditer(r'<text top="(\d+)" left="(\d+)"[^>]*font="(\d+)"[^>]*>(.*?)</text>', page):
        top, left, f, t = m.groups()
        if f not in FONT_LEVEL:
            prev = None
            continue
        t = html.unescape(re.sub('<[^>]+>', '', t)).replace('­', '-').strip()
        # a heading set on two lines: same font, next line down
        if prev and prev[2] == f and 0 < int(top) - prev[1] < 25 and prev[3] == pn:
            heads[-1] = (heads[-1][0] + ' ' + t, int(top), f, pn)
        else:
            heads.append((t, int(top), f, pn))
        prev = heads[-1]
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower().replace('&', 'and'))
pdf_level = {norm(t): FONT_LEVEL[f] for t, _, f, _ in heads}
# D-heads: italic Times 15pt lines that are exactly a section title
for m in re.finditer(r'<text [^>]*font="(\d+)"[^>]*><i>([^<]+)</i></text>', xml):
    spec = re.search(r'<fontspec id="%s" size="(\d+)" family="[^+]*\+([^"]+)"' % m.group(1), xml)
    if spec and spec.group(1) == '15' and spec.group(2).startswith('TimesNewRomanPS'):
        t = html.unescape(m.group(2)).replace('\u00ad', '-').strip()
        pdf_level.setdefault(norm(t), 5)
section_levels, unmatched = {}, []
for s in app['sections']:
    if s['id'] == 'intro':
        continue
    lv = pdf_level.get(norm(s['title']))
    if lv is None:
        unmatched.append(s['title'])
    elif lv != s['level']:
        section_levels[s['id']] = lv
if unmatched:
    print('sections with no PDF heading:', unmatched)

# ---- text corrections -------------------------------------------------------
replace = {
    # tricycle gear: app merged two paragraphs and dropped the steering sentences
    "ch-13-b0011": para('The nose gear of a few', '[Figure 13-7]', 3)
                   + para('The main gear on a tricycle', 'Boeing 777.', 4),
    # metering pin: two columns merged line by line
    "ch-13-b0025": para('Most shock struts employ', '[Figure 13-17]', 7),
    # power pack extension: the app split this paragraph and put its end first
    "ch-13-b0059": [],
    "ch-13-b0060": para('When the flight deck gear selection', 'down and locked.', 17),
    # power pack retraction: two columns merged
    "ch-13-b0061": para('To raise the gear,', 'opens again.', 19),
    # position indicator lines: one line each, as printed
    "ch-13-b0077": [{"kind": "paragraph", "printedPage": "13-23",
                     "md": "Off = gear up and locked  \nRed = unsafe  \nGreen = down and locked"}],
    "ch-13-b0078": [],
    # vane-type damper: second half of the paragraph missing
    "ch-13-b0118": para('A vane-type shimmy damper is sometime', 'end of the unit.', 32),
    # inboard / outboard wheel half: two columns merged
    "ch-13-b0126": unlabel(para('An overinflation safety plug', 'inflation and deflation.', 34), join=True),
    "ch-13-b0127": unlabel(para('The outboard wheel half bolts', 'fixed gear aircraft.', 34), join=True),
    # floating disc brake: text after "shown in Figure 13-80." dropped
    "ch-13-b0165": para('A floating disc brake is illustrated', 'These linings are stationary.', 41),
    # multiple-disc: one paragraph split in two blocks
    "ch-13-b0175": [{"kind": "paragraph", "printedPage": "13-46",
                     "md": app_md('ch-13-b0175') + ' ' + app_md('ch-13-b0176')}],
    "ch-13-b0176": [],
    # segmented rotor: rest of the pressure plate paragraph and the backing plate paragraph dropped
    "ch-13-b0180": para('A pressure plate is a flat', 'can also be used.', 46)
                   + para('Any number of alternating', '[Figure 13-87]', 47),
    # expander tube end / brake actuating systems start: merged
    "ch-13-b0192": para('They tend to take a setback', 'disc brake systems.', 49),
    "ch-13-b0193": para('The various brake assemblies', 'actuating systems:', 49),
    # master cylinder compensating port: merged
    "ch-13-b0200": para('Hydraulic fluid expands', 'keep out dust.', 50),
    # power brakes: fragment + merged paragraph
    "ch-13-b0209": [],
    "ch-13-b0210": para('Large and high-performance aircraft are equipped', 'through linkages.', 54),
    # Boeing 737 metering valve: text after "illustrated in" dropped
    "ch-13-b0214": para('A brake metering valve from a Boeing', 'as required.', 55),
    # control units / anti-skid control valves: merged across the heading
    "ch-13-b0238": para('The error output voltage', 'depending on this value.', 61),
    "ch-13-b0239": para('Anti-skid control valves are fast-acting', '[Figure 13-111]', 61)
                   + para('As pressure is adjusted to the brakes', 'Figure 13-104.', 62),
    # ground test: merged with the Anti-Skid System Tests paragraph
    "ch-13-b0244": para('Ground tests vary slightly', 'parameters.', 64, split_at='Much of the anti-skid'),
    # pressure bleed: text after "illustrated in" dropped
    "ch-13-b0259": para('The typical pressure bleed', 'brake lines.', 67),
}

retraction_checks = grab('3.', 'vibration.', 29)[0].split('\n\n')
insert_before = {
    # chapter opening paragraph missing
    "ch-13-b0001": para('Aircraft landing gear supports', '[Figure 13-1]', 1),
}
insert_after = {
    # retraction test checklist items 3-6 missing
    "ch-13-b0104": [{"kind": "list", "ordered": True, "start": 3, "printedPage": "13-29",
                     "items": [re.sub(r'^\d+\.\s*', '', x) for x in retraction_checks]}],
}
append_to_section = {
    # this section has no text in the app; its paragraph was merged into Ground Test
    "Anti-Skid-System-Tests": para('It is important to know the status', 'normal brake operation.', 64),
}
insert_heading_before = {
    "ch-13-b0105": {"title": "Nose Wheel Steering Systems", "level": 2, "printedPage": "13-29"},
    "ch-13-b0119": {"title": "Non-Hydraulic Shimmy Damper", "level": 4, "printedPage": "13-33"},
}
list_start = {"ch-13-b0041": 3, "ch-13-b0044": 8}

# words the app joined where the PDF breaks a hyphenated compound at a line end
hyphen_fixes = ["single-engine", "gear-down", "lock-out", "to-metal", "high-pressure",
                "rotor-disc", "non-rotating", "non-aircraft", "wheel-like", "fluid-filled",
                "Mineral-based", "over-tightening", "low-pressure", "two-number", "10-inch"]

# captions the app cut short or merged: rebuilt from the PDF's caption lines
_caps, _cur = {}, None
for _, t, k in pdf_body_lines(PDF):
    if k != 'caption':
        continue
    m = re.match(r'Figure (\d+)[\u00ad-](\d+)\.\s*(.*)', t)
    if m:
        _cur = f'{m.group(1)}-{m.group(2)}'
        _caps[_cur] = m.group(3)
    elif _cur and (len(t.strip()) >= 8 or t.strip().endswith('.')):
        _caps[_cur] += ' ' + t.strip()
clean = lambda t: t.replace('\u00ad', '-').replace('\u2019', "'")
captions = {n: clean(_caps[n]) for n in ('13-68', '13-71')}

out = {
    "chapter": "FAA-H-8083-31B ch-13",
    "about": "Fixes applied by scripts/export_handbook.py on top of the AMT Handbooks app data. "
             "Every replacement text was taken from the FAA PDF column by column "
             "(see build_ch13.py, which regenerates this file). "
             "Checked with scripts/check_chapter.py.",
    "section_levels": section_levels,
    "insert_heading_before": insert_heading_before,
    "replace": replace,
    "insert_before": insert_before,
    "insert_after": insert_after,
    "append_to_section": append_to_section,
    "list_start": list_start,
    "hyphen_fixes": hyphen_fixes,
    "captions": captions,
    "check_ignore": [
        {"text": "Ozone (O3) and oxygen (O2) cause degradation of tire compounds.",
         "reason": "The subscripts put this PDF line outside body-text height; text checked by eye."},
        {"text": "The rotors and stators are relatively thin, only about 1⁄8-inch thick.",
         "reason": "The fraction's superscript 1 is set outside body-text height; text checked by eye."},
    ],
}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print('wrote', OUT, len(section_levels), 'level fixes,', len(replace), 'replacements')

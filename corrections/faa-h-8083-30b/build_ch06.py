"""Build corrections/faa-h-8083-30b/ch06.json (FAA-H-8083-30B Chapter 6, Aircraft
Weight & Balance). Text fixes are pulled from the FAA PDF with pdf_grab.

Formulas: the PDF sets these as stacked fractions, which the app flattened into
scrambled lines ("F × L CG = D – ( ) W"). They are rewritten here on one line, with
the fraction bar shown as ÷ and the numerator and denominator in parentheses where
needed. Every formula was read off a render of the PDF page. Nothing else changes.

    python3 corrections/faa-h-8083-30b/build_ch06.py --atk ../atk-amt-handbooks
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from corrections_lib import write_corrections  # noqa: E402
from pdf_grab import Grabber  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--atk", required=True, type=Path)
args = ap.parse_args()
PDF = ROOT / "handbooks/faa-h-8083-30b/ch06-aircraft-weight-and-balance.pdf"
g = Grabber(PDF)


def para(start, end, page, fix=None):
    paras = g.grab_paras(start, end, page)
    text = "\n\n".join(t for t, _ in paras)
    for a, b in (fix or {}).items():
        assert a in text, a
        text = text.replace(a, b)
    pages = [pg for _, pg in paras]
    if len(text.split("\n\n")) != len(pages):     # a fix joined or split paragraphs
        pages = [pages[0]] * len(text.split("\n\n"))
    return [{"kind": "paragraph", "md": p.strip(), "printedPage": f"6-{pg}"}
            for p, pg in zip(text.split("\n\n"), pages) if p.strip()]


def lines(page, *formula_lines):
    """A formula worked over several lines, kept as separate lines."""
    return [{"kind": "paragraph", "md": "  \n".join(formula_lines), "printedPage": f"6-{page}",
             "formula": True}]


def heading(title, level, page):
    return [{"kind": "heading", "title": title, "level": level, "printedPage": f"6-{page}"}]


app_list = {
    "ch-06-b0135": ["Airplane empty weight: 1,850 lb"],
}

write_corrections(
    "FAA-H-8083-30B", 6, args.atk, Path(__file__).with_name("ch06.json"),
    list_start={"ch-06-b0051": 10},
    # heading runs over a page break; the app kept only the first line
    section_titles={"Datum-Forward-of-the-Main-Wheels-Tail-Wheel":
                    "Datum Forward of the Main Wheels–Tail Wheel Landing Gear"},
    keep_app_captions=["6-54", "6-55"],
    check_ignore=[
        {"text": "Figure 6-54. Center of gravity location on a large commercial transport.",
         "reason": "Labels inside the figure are set at caption height and run on after the "
                   "caption; the caption itself matches the PDF."},
        {"text": "Figure 6-55. Aircraft weight and balance report.",
         "reason": "Form text inside the figure is set at caption height; the caption itself "
                   "matches the PDF."},
        {"text": "Notice that the formula for each condition first determines the moment of the "
                 "nose (F × L ÷ W) wheel or tail (R × L ÷ W) wheel and then divides it by the "
                 "total weight of the airplane.",
         "reason": "The PDF line holds two inline fractions and is set taller than body text, so "
                   "the checker cannot read it; transcribed from a render of p. 6-16."},
        {"text": "Locating the CG of a tail wheel airplane is done in the same way as locating it "
                 "for a nosewheel airplane except the formulas use R × L ÷ W rather than F × L ÷ W.",
         "reason": "Inline fractions, as above; transcribed from a render of p. 6-18."},
        {"text": "Aircraft Current Empty Weight:",
         "reason": "Form field printed inside Figure 6-55 (a weight and balance report form), "
                   "not body text."},
        {"text": "Aircraft Current Empty Weight CG:",
         "reason": "Form field printed inside Figure 6-55, not body text."},
    ],
    replace={
        # four-column table paragraph: two columns merged
        "ch-06-b0039": para("To calculate the CG for the object", "shown in Figure 6-7.", 5),
        # CG range: paragraph cut off before "Figure 6-25."
        "ch-06-b0094": para("The data sheet identifies", "known as the CG envelope.", 15),
        # EWCG formulas (p. 6-16): inline fractions lost; "Formula 1" line run in
        "ch-06-b0105": para("The EWCG can be quickly", "(distance D).", 16,
                            fix={"moment\n\nby the total":
                                 "moment of the nose (F × L ÷ W) wheel or tail (R × L ÷ W) wheel "
                                 "and then divides it by the total"})
                       + [{"kind": "paragraph", "printedPage": "6-16",
                           "md": "Formula 1 Nosewheel airplanes with datum forward of the main wheels."}],
        "eq-06-001": [],
        "ch-06-b0106": [],
        "ch-06-b0107": [],
        "eq-06-002": lines(16, "CG = D – (F × L ÷ W)"),
        "eq-06-003": lines(16, "CG = – (D + F × L ÷ W)"),
        "eq-06-004": lines(16, "CG = D + (R × L ÷ W)"),
        "eq-06-005": lines(16, "CG = – D + (R × L ÷ W)"),
        # worked examples (pp. 6-17, 6-19)
        "eq-06-006": lines(17, "CG = D – (F × L ÷ W)", "= 128 – (340 × 78 ÷ 2,006)", "= 114.8"),
        "eq-06-007": lines(17, "CG = – (D + F × L ÷ W)", "= – (75 + 340 × 78 ÷ 2,006)", "= –88.2"),
        "eq-06-008": lines(19, "CG = D + (R × L ÷ W)", "= 7.5 + (67 × 222 ÷ 1,218)", "= 19.7"),
        "eq-06-009": lines(19, "CG = – D + (R × L ÷ W)", "= – 80 + (67 × 222 ÷ 1,218)", "= –67.8"),
        # adverse-loaded CG check data: one list split in three
        "ch-06-b0135": [{"kind": "list", "ordered": False, "printedPage": "6-20", "items": [
            "Airplane empty weight: 1,850 lb", "EWCG: +92.45\"", "CG limits: +89\" to +99\"",
            "Maximum weight: 3,200 lb",
            "Fuel capacity: 45 gal at +95\" (44 usable) 40 gal at +102\" (39 usable)"]}],
        "eq-06-010": [],
        "ch-06-b0136": [],
        # ballast formulas (pp. 6-22 to 6-24)
        "ch-06-b0147": lines(22, "Ballast weight needed = (Total wt. × dist. needed to shift CG) ÷ "
                                 "(Dist. between ballast and desired CG)"),
        "ch-06-b0149": lines(22, "Ballast weight needed = (Total wt. × dist. needed to shift CG) ÷ "
                                 "(Dist. between ballast and desired CG)"),
        "eq-06-011": lines(23, "= (3,034 lb × (0.6\")) ÷ 39\"", "= 46.68 lb"),
        "ch-06-b0158": lines(23, "Ballast weight = (Aircraft empty wt. × dist. out of limits) ÷ "
                                 "(Dist. between ballast and desired CG)"),
        "eq-06-012": lines(23, "= (1,876 lb × 0.8\") ÷ (228 – 33)"),
        "eq-06-013": lines(24, "= 1,500.8 ÷ 195"),
        "ch-06-b0159": lines(24, "= 7.7 lb")
                       + para("A block of lead weighing 7.7", "Do Not Remove.", 24),
        # "Weight & Balance for Large Airplanes" is an A-head, not a paragraph
        "ch-06-b0182": heading("Weight & Balance for Large Airplanes", 2, 28),
        # percent of MAC (pp. 6-28, 6-30)
        "ch-06-b0192": lines(28, "Percent of MAC = (CG – LEMAC) ÷ MAC × 100"),
        "ch-06-b0194": lines(28, "Percent of MAC = (CG – LEMAC) ÷ MAC × 100"),
        "eq-06-014": lines(30, "= (945 – 900) ÷ 180 × 100"),
        "ch-06-b0196": lines(30, "= 25 percent")
                       + para("If the CG is known in percent of MAC", "as follows:", 30),
    },
    insert_before={
        # tail wheel paragraph (p. 6-18) missing; its inline fractions were lost too
        "eq-06-008": para("Locating the CG of a tail wheel", "using this formula:", 18,
                          fix={"except the\n\nThe distance":
                               "except the formulas use R × L ÷ W rather than F × L ÷ W.\n\n"
                               "The distance"}),
    },
)

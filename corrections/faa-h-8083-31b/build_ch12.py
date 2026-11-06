"""Build corrections/faa-h-8083-31b/ch12.json (FAA-H-8083-31B Chapter 12, Hydraulic &
Pneumatic Power Systems). Text fixes are pulled from the FAA PDF with pdf_grab.

    python3 corrections/faa-h-8083-31b/build_ch12.py --atk ../atk-amt-handbooks
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
PDF = ROOT / "handbooks/faa-h-8083-31b/ch12-hydraulic-and-pneumatic-power-systems.pdf"
g = Grabber(PDF)


def para(start, end, page):
    return [{"kind": "paragraph", "md": t.strip(), "printedPage": f"12-{pg}"}
            for t, pg in g.grab_paras(start, end, page) if t.strip()]


def heading(title, level, page):
    return [{"kind": "heading", "title": title, "level": level, "printedPage": f"12-{page}"}]


ptu, _ = g.grab("System B EDP pressure drops", "but not up.", 40)

write_corrections(
    "FAA-H-8083-31B", 12, args.atk, Path(__file__).with_name("ch12.json"),
    insert_heading_before_section={
        # the B-head "Valves" (p. 12-22) is missing; its C-heads follow it
        "Flow-Control-Valves": {"title": "Valves", "level": 3, "printedPage": "12-22"},
    },
    check_ignore=[
        {"text": "The pump output is changed automatically by a pump compensator within the pump.",
         "reason": "Sentence crosses a column break with only \"pump.\" in the next column, "
                   "too short for the checker's split test; checked by eye against p. 12-19."},
    ],
    replace={
        # piston pump: the app split this paragraph and put its second half first
        "ch-12-b0097": [],
        "ch-12-b0099": para("Piston pumps can be constant", "[Figure 12-26]", 17),
        # variable-displacement pump: middle of the paragraph and a D-head missing
        "ch-12-b0104": para("A variable-displacement pump has", "[Figure 12-29]", 19)
                       + heading("Basic Pumping Operation", 5, 19)
                       + para("The aircraft's engine rotates", "valve block).", 19),
        # PTU: paragraph cut off at "The"; its condition list was missing
        "ch-12-b0196": para("The purpose of the PTU is", "conditions are met:", 39)
                       + [{"kind": "list", "ordered": False, "printedPage": "12-40",
                           "items": [x.strip() for x in ptu.replace("\n\n", " ").split(" • ")]
                           if " • " in ptu else ["System B EDP pressure drops below limits.",
                                                 "Aircraft airborne.",
                                                 "Flaps are less than 15° but not up."]}],
        # Boeing 777: two columns merged across the next heading
        "ch-12-b0202": para("The Boeing 777 is equipped", "center system flight controls.", 41),
        "ch-12-b0203": para("The left and right hydraulic systems are functionally",
                            "[Figure 12-67]", 41),
    },
)

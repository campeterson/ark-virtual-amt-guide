"""Build corrections/faa-h-8083-31b/ch01.json (FAA-H-8083-31B Chapter 1, Aircraft
Structures). Text fixes are pulled from the FAA PDF with pdf_grab.

    python3 corrections/faa-h-8083-31b/build_ch01.py --atk ../atk-amt-handbooks
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from corrections_lib import write_corrections  # noqa: E402
from pdf_grab import Grabber  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--atk", required=True, type=Path)
args = ap.parse_args()
PDF = ROOT / "handbooks/faa-h-8083-31b/ch01-aircraft-structures.pdf"
g = Grabber(PDF)
app = json.loads((args.atk / "public/content/FAA-H-8083-31B/chapters/ch-01.json").read_text())
blocks = {b["id"]: b for s in app["sections"] for b in s["blocks"]}


def para(start, end, page):
    return [{"kind": "paragraph", "md": t.strip(), "printedPage": f"1-{pg}"}
            for t, pg in g.grab_paras(start, end, page) if t.strip()]


def heading(title, level, page):
    return [{"kind": "heading", "title": title, "level": level, "printedPage": f"1-{page}"}]


# location stations list: the app cut the last item and put the rest of the list
# (and the following paragraphs) out of order
stations = blocks["ch-01-b0155"]
flap, _ = g.grab("Flap station (KS)", "edge of the flap.", 37)
items = stations["items"][:-1] + [flap] + blocks["ch-01-b0158"]["items"]

write_corrections(
    "FAA-H-8083-31B", 1, args.atk, Path(__file__).with_name("ch01.json"),
    check_ignore=[
        {"text": "A NOTAR® antitorque system has no visible rotor mounted on the tail boom.",
         "reason": "The ® is set as a superscript outside body-text height; text checked by eye."},
    ],
    replace={
        # history: paragraph cut at a column end; the 1920s and 1930s paragraphs dropped
        "ch-01-b0009": para("Leading up to World War I", "developed during this period.", 2),
        # nacelles: text after "can be seen in Figure 1-45." dropped
        "ch-01-b0086": para("An example of a turbojet engine nacelle", "into the engine.", 19),
        # rudder: end of the paragraph dropped; the next A-head was missing
        "ch-01-b0105": para("As with the other primary flight controls", "maneuver the aircraft.", 25)
                       + heading("Dual Purpose Flight Control Surfaces", 2, 26),
        # trim tab: text after "as shown in Figure 1-70." dropped
        "ch-01-b0124": para("Occasionally, a simple light aircraft", "usually sufficient.", 30),
        # location numbering
        "ch-01-b0155": [{"kind": "list", "ordered": stations["ordered"], "items": items,
                         "printedPage": stations["printedPage"]}],
        "ch-01-b0156": [],
        "ch-01-b0157": [],
        "ch-01-b0158": [],
        "ch-01-b0160": para("Another method is used to facilitate", "transport category aircraft.", 38),
    },
    insert_before={
        # access & inspection panels: first paragraph merged into the zone paragraph
        "fig-01-90": para("Quick access to the accessories", "and other openings.", 38),
    },
)

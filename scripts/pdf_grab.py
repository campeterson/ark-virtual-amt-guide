"""Pull handbook text straight from an FAA PDF, for writing chapter corrections.

    from pdf_grab import Grabber
    g = Grabber("handbooks/faa-h-8083-31b/ch13-aircraft-landing-gear-systems.pdf")
    text, page = g.grab("Most shock struts employ", "[Figure 13-17]", page=7)

grab() returns the body text from the first line containing `start` (on or after
`page`) through the line containing `end`, reading each page left column then
right. Captions, figure labels, headings and page numbers are left out by line
height (measured from the PDF, as in check_chapter.py). Paragraph breaks (a
vertical gap clearly larger than the normal line spacing) come back as blank lines. `page` is the PDF page number of the chapter file.
"""
import re,html,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from check_chapter import _all_lines,line_heights


class Grabber:
    def __init__(self, pdf):
        self.pdf=str(pdf); self._L=None

    def lines(self):
        if self._L: return self._L
        self._L=_read_lines(self.pdf); return self._L

    def grab(self,start,end,page=None):
        return _grab(self.lines(),start,end,page)


def _read_lines(pdf):
    """Body lines as (page, text, column, y, gap_limit)."""
    lines=list(_all_lines(Path(pdf)))
    bmin,bmax,_,_=line_heights(lines)
    out,steps=[],[]
    pages={}
    for pn,w,x0,y0,h,t in lines:
        t=html.unescape(t)
        if not bmin<=h<=bmax or re.fullmatch(r'\d+-\d+',t.strip()): continue
        pages.setdefault(pn,[]).append((0 if x0<w/2 else 1,y0,x0,t))
    for pn in sorted(pages):
        ls=sorted(pages[pn])
        steps+=[b[1]-a[1] for a,b in zip(ls,ls[1:]) if a[0]==b[0] and 0<b[1]-a[1]<40]
        out+=[(pn,t,c,y) for c,y,_,t in ls]
    gap=1.3*statistics.median(steps)   # normal line spacing x 1.3
    return [(pn,t,c,y,gap) for pn,t,c,y in out]
def clean(t):
    return t.replace('­','-').replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"')
def _grab(L,start,end,page=None):
    i=next(k for k,(p,t,*_) in enumerate(L) if start in clean(t) and (page is None or p>=page))
    j=next(k for k in range(i,len(L)) if end in clean(L[k][1]))
    s=''
    for k in range(i,j+1):
        t=clean(L[k][1]).strip()
        if k==i: t=t[t.index(start):]
        if k==j: t=t[:t.index(end)+len(end)] if k!=i else t[:t.index(end)+len(end)]
        if k>i and L[k][0]==L[k-1][0] and L[k][2]==L[k-1][2] and L[k][3]-L[k-1][3]>L[k][4]: s+='\n\n'+t
        elif s.endswith('-'): s+=t
        else: s+=(' ' if s else '')+t
    return s, L[i][0]

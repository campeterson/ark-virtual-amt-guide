"""Pull handbook text straight from an FAA PDF, for writing chapter corrections.

    from pdf_grab import Grabber
    g = Grabber("handbooks/faa-h-8083-31b/ch13-aircraft-landing-gear-systems.pdf")
    text, page = g.grab("Most shock struts employ", "[Figure 13-17]", page=7)

grab() returns the body text from the first line containing `start` (on or after
`page`) through the line containing `end`, reading each page left column then
right. Captions, figure labels, headings and page numbers are left out by line
height. Paragraph breaks (a vertical gap of more than 16 pt) come back as blank
lines. `page` is the PDF page number of the chapter file.
"""
import re,subprocess,html
LINE_RE=re.compile(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>',re.S)
WORD_RE=re.compile(r'>([^<]*)</word>')
BODY_MIN,BODY_MAX=10.7,11.7  # body-text line height (pt) in the FAA-H-8083 handbooks


class Grabber:
    def __init__(self, pdf):
        self.pdf=str(pdf); self._L=None

    def lines(self):
        if self._L: return self._L
        self._L=_read_lines(self.pdf); return self._L

    def grab(self,start,end,page=None):
        return _grab(self.lines(),start,end,page)


def _read_lines(pdf):
    xml=subprocess.check_output(['pdftotext','-bbox-layout',pdf,'-'],text=True)
    out=[]
    for pn,page in enumerate(xml.split('<page ')[1:],1):
        w=float(re.search(r'width="([\d.]+)"',page).group(1)); ls=[]
        for m in LINE_RE.finditer(page):
            x0,y0,x1,y1=map(float,m.groups()[:4]); t=html.unescape(' '.join(WORD_RE.findall(m.group(5))))
            h=y1-y0
            if not BODY_MIN<=h<=BODY_MAX or re.fullmatch(r'\d+-\d+',t.strip()): continue
            ls.append((0 if x0<w/2 else 1,y0,x0,t))
        ls.sort(); out+=[(pn,t,c,y) for c,y,_,t in ls]
    return out
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
        if k>i and L[k][0]==L[k-1][0] and L[k][2]==L[k-1][2] and L[k][3]-L[k-1][3]>16: s+='\n\n'+t
        elif s.endswith('-'): s+=t
        else: s+=(' ' if s else '')+t
    return s, L[i][0]

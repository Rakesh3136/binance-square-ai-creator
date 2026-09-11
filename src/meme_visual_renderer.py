"""Real-world-feeling, license-safe crypto meme renderer for Binance Square.

Uses public-domain or CC0 Wikimedia Commons photographs when available, then
adds original crypto/trader meme captions tied to the current market move. It
avoids copying famous meme images and remembers recent sources/treatments to
prevent repetition. A synthetic fallback is deliberately not published: a meme
lane must have a real compatible-license photo or fail closed.
"""
from __future__ import annotations
import hashlib, json, random, textwrap
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/live/visual.png'; CTX=ROOT/'data/live/publication_context.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; HISTORY=ROOT/'data/intelligence/meme_visual_history.json'
W,H=1600,900; UA='BinanceSquareAICreator/2.2 (Wikimedia Commons public-domain visual research)'; LICENSES=('CC0','Public domain')
def load(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
def symbol():
    c,p=load(CTX),load(PREFLIGHT); return str(c.get('symbol') or (p.get('selected_opportunity') or {}).get('symbol') or 'CRYPTO').upper().replace('$','').replace('USDT','')
def move():
    try:return float((load(PREFLIGHT).get('selected_opportunity') or {}).get('price_change_24h'))
    except Exception:return None
def seed():
    c=load(CTX); return int(hashlib.sha256(f"{symbol()}|{c.get('headline','')}|{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}".encode()).hexdigest()[:12],16)
def font(size,bold=False):
    names=['DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf','LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf']
    for n in names:
        for root in ('/usr/share/fonts/truetype/dejavu','/usr/share/fonts/truetype/liberation2'):
            p=Path(root)/n
            if p.exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default()
def commons_photo(query,recent):
    params={'action':'query','format':'json','generator':'search','gsrnamespace':'6','gsrlimit':'30','gsrsearch':query,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':'1600'}
    try:
        req=Request('https://commons.wikimedia.org/w/api.php?'+urlencode(params),headers={'User-Agent':UA})
        with urlopen(req,timeout=12) as r:data=json.loads(r.read().decode('utf-8'))
    except Exception:return None,{}
    pages=list(((data.get('query') or {}).get('pages') or {}).values()); random.Random(seed()+len(query)).shuffle(pages)
    for page in pages:
        info=(page.get('imageinfo') or [{}])[0]; meta=info.get('extmetadata') or {}; lic=str((meta.get('LicenseShortName') or {}).get('value','')); title=str(page.get('title') or ''); image_url=info.get('thumburl') or info.get('url')
        if not image_url or title in recent or not any(x.lower() in lic.lower() for x in LICENSES):continue
        try:
            req=Request(image_url,headers={'User-Agent':UA})
            with urlopen(req,timeout=15) as r:image=Image.open(BytesIO(r.read())).convert('RGB')
            return image,{'title':title,'url':image_url,'license':lic,'source':'Wikimedia Commons'}
        except Exception:continue
    return None,{}
def get_photo(recent):
    m=move(); queries=['person shocked phone','man surprised computer','person facepalm office','trader reaction'] if m is not None and m<=-4 else ['person celebrating phone','happy trader computer','person cheering','crowd celebration'] if m is not None and m>=4 else ['person looking at phone','person confused phone','office reaction computer','person waiting']
    random.Random(seed()).shuffle(queries)
    for q in queries:
        image,meta=commons_photo(q,recent)
        if image is not None:return image,meta
    return None,{}
def caption(draw,text,box,size,dark=False):
    x1,y1,x2,y2=box; f=font(size,True); lines=textwrap.wrap(text,width=max(12,int((x2-x1)/(size*.55)))); y=y1
    for line in lines:
        b=draw.textbbox((0,0),line,font=f,stroke_width=2); tw=b[2]-b[0]; x=x1+((x2-x1)-tw)//2; fill=(18,18,18,255) if dark else (255,255,255,255); stroke=(255,255,255,120) if dark else (0,0,0,220)
        draw.text((x+3,y+3),line,font=f,fill=(0,0,0,190),stroke_width=5,stroke_fill=(0,0,0,180)); draw.text((x,y),line,font=f,fill=fill,stroke_width=2,stroke_fill=stroke); y+=size+10
def render(photo,treatment):
    photo=ImageOps.fit(ImageOps.exif_transpose(photo).convert('RGB'),(W,H),method=Image.Resampling.LANCZOS,centering=(.5,.48)); photo=ImageEnhance.Contrast(photo).enhance(1.08); photo=ImageEnhance.Color(photo).enhance(1.05); photo=photo.filter(ImageFilter.UnsharpMask(radius=1.2,percent=110,threshold=3)); base=photo.convert('RGBA'); over=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(over); s,m=symbol(),move(); mt=f'{m:+.1f}%' if m is not None else 'another move'
    if m is not None and m<=-4:top='ME: “I WILL WAIT FOR CONFIRMATION.”'; bottom=f'${s} MOVES {mt} BEFORE I FINISH MY SENTENCE.'
    elif m is not None and m>=4:top='ME: “I AM NOT FOMO-ING.”'; bottom=f'${s}: “THAT IS CUTE.”  •  {mt} LATER'
    else:top=f'ME CHECKING ${s} ONE MORE TIME'; bottom='THE MARKET: “YOU REALLY WANT TO DO THIS TODAY?”'
    if treatment=='top_bottom':d.rounded_rectangle((70,55,1530,255),30,fill=(0,0,0,175)); caption(d,top,(110,85,1490,230),52); d.rounded_rectangle((220,690,1380,850),28,fill=(0,0,0,190)); caption(d,bottom,(255,710,1345,825),38)
    elif treatment=='reaction_strip':d.rounded_rectangle((70,55,1530,290),34,fill=(255,255,255,238)); caption(d,top,(110,85,1490,260),50,True); d.rounded_rectangle((170,690,1430,850),28,fill=(0,0,0,185)); caption(d,bottom,(205,710,1395,825),38)
    elif treatment=='minimal':caption(d,top,(100,55,1500,210),58); caption(d,bottom,(170,735,1430,855),38)
    else:d.rounded_rectangle((80,70,900,245),28,fill=(0,0,0,160)); caption(d,top,(110,95,870,225),40); d.rounded_rectangle((870,650,1515,850),25,fill=(0,0,0,185)); caption(d,bottom,(900,675,1485,825),31)
    d.text((50,850),f'${s}  •  market move {mt}',font=font(22,True),fill=(255,255,255,230),stroke_width=2,stroke_fill=(0,0,0,190)); return Image.alpha_composite(base,over).convert('RGB')
def main():
    history=load(HISTORY); recent=set(str(x) for x in (history.get('sources') or [])[-8:]); photo,source=get_photo(recent)
    if photo is None: raise SystemExit('No compatible-license real-world photo found; meme publication blocked to prevent synthetic/fake visuals.')
    treatments=['top_bottom','reaction_strip','minimal','split_caption']; recent_treatments=history.get('treatments') or []; available=[x for x in treatments if x not in recent_treatments[-2:]] or treatments; treatment=random.Random(seed()).choice(available)
    OUT.parent.mkdir(parents=True,exist_ok=True); render(photo,treatment).save(OUT,'PNG',optimize=True)
    sources=(history.get('sources') or [])[-8:]+[str(source.get('title') or source.get('url') or 'photo')]; treatments_hist=(recent_treatments[-8:]+[treatment])[-8:]
    save(HISTORY,{'version':'2.2','updated_at':datetime.now(timezone.utc).isoformat(),'sources':sources[-8:],'treatments':treatments_hist,'policy':'Only public-domain or CC0 real-world photos; original captions; no famous meme copying; fail closed if no real photo is available.'})
    print(json.dumps({'status':'VISUAL_RENDERED','path':str(OUT),'symbol':symbol(),'type':'real_world_photo_meme','source':source,'treatment':treatment},separators=(',',':')))
if __name__=='__main__':main()

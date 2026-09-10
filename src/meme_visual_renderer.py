"""Render an original, license-safe crypto trader meme for Square.

No third-party meme image is copied. The renderer uses typography, panels and
simple original shapes so the joke can be tied to the selected asset and the
actual editorial context.
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/live/visual.png'; CTX=ROOT/'data/live/publication_context.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'

def load(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def symbol():
    ctx=load(CTX); pre=load(PREFLIGHT)
    return str(ctx.get('symbol') or (pre.get('selected_opportunity') or {}).get('symbol') or 'CRYPTO').upper().replace('$','').replace('USDT','')

def main():
    s=symbol(); selected=(load(PREFLIGHT).get('selected_opportunity') or {}); move=selected.get('price_change_24h')
    try: move_text=f'{float(move):+.1f}%'
    except Exception: move_text='another red candle'
    fig,ax=plt.subplots(figsize=(12,6.75),dpi=160); ax.set_xlim(0,12); ax.set_ylim(0,6.75); ax.axis('off')
    fig.patch.set_facecolor('#111827'); ax.set_facecolor('#111827')
    ax.text(0.55,6.25,f'${s} TRADER MOMENT',fontsize=26,fontweight='bold',color='white',va='center')
    ax.text(0.55,5.82,'You said you would wait. The market heard you.',fontsize=13,color='#cbd5e1',va='center')
    panels=[(0.45,3.15,3.55,2.15),(4.20,3.15,3.55,2.15),(7.95,3.15,3.55,2.15),(0.45,0.55,11.05,2.25)]
    captions=['ME: “I WILL WAIT FOR CONFIRMATION.”','THE CHART: one more candle…',f'ME: “OK, BUT WHAT ABOUT ${s}?”',f'PORTFOLIO THERAPY: {move_text}  •  I definitely meant to do that']
    for i,(x,y,w,h) in enumerate(panels):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.03,rounding_size=0.12',facecolor='#1f2937',edgecolor='#374151',linewidth=1.5))
        if i<3:
            ax.add_patch(Circle((x+w/2,y+h*0.56),0.35,facecolor='#f3f4f6',edgecolor='#94a3b8'))
            ax.plot([x+w/2,x+w/2-0.38,x+w/2+0.38],[y+h*0.42,y+h*0.12,y+h*0.12],linewidth=7,solid_capstyle='round')
            ax.plot([x+w/2-0.2,x+w/2+0.2],[y+h*0.28,y+h*0.28],linewidth=5,solid_capstyle='round')
            if i==1: ax.plot([x+0.55,x+1.35,x+2.1,x+2.85],[y+1.35,y+1.65,y+0.8,y+0.55],linewidth=4)
            ax.text(x+0.25,y+0.22,captions[i],fontsize=10.5,color='white',va='bottom')
        else:
            ax.text(x+0.45,y+h*0.58,captions[i],fontsize=21,fontweight='bold',color='white',va='center')
            ax.text(x+0.45,y+h*0.25,'No guarantees. Just trader pain, pattern recognition and a little self-awareness.',fontsize=12,color='#cbd5e1',va='center')
    OUT.parent.mkdir(parents=True,exist_ok=True); fig.savefig(OUT,bbox_inches='tight',facecolor=fig.get_facecolor()); plt.close(fig)
    print(json.dumps({'status':'VISUAL_RENDERED','path':str(OUT),'symbol':s,'type':'original_crypto_meme'},indent=2))

if __name__=='__main__':main()

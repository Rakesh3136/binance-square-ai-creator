import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { chromium } from 'playwright';

const LIVE_VISUAL='data/live/visual.png';
const META='data/live/visual_metadata.json';
const ROOT=process.cwd();
function normalizeBase(symbol){let s=String(symbol||'').toUpperCase().trim().replace(/^BINANCE:/,'').replace(/USDT$/,'');return s.replace(/[^A-Z0-9]/g,'');}
function load(rel){return fs.readFile(path.resolve(ROOT,rel),'utf8').then(x=>JSON.parse(x)).catch(()=>({}));}
async function main(){
  const frozen=await load('data/live/authoritative_opportunity.json');
  const context=await load('data/live/publication_context.json');
  const base=normalizeBase(frozen.symbol||context.symbol);
  if(!base) throw new Error('No frozen authoritative Binance symbol');
  const tvSymbol=`BINANCE:${base}USDT`;
  const tvUrl=`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}&interval=60&theme=dark`;
  const html=`<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1440px;height:900px;background:#131722;overflow:hidden}.tradingview-widget-container{width:1440px;height:900px}</style></head><body><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget" style="width:100%;height:100%"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{"autosize":false,"symbol":${JSON.stringify(tvSymbol)},"interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","allow_symbol_change":false,"calendar":false,"support_host":"https://www.tradingview.com","width":1440,"height":900,"hide_top_toolbar":false,"hide_legend":false,"hide_side_toolbar":true,"withdateranges":true,"save_image":false,"studies":[]}</script></div></body></html>`;
  await fs.mkdir('data/live',{recursive:true});
  await fs.writeFile(path.resolve('data/live/tradingview_capture.html'),html,'utf8');
  await fs.writeFile(path.resolve(META),JSON.stringify({status:'RENDERING',provider:'TradingView',tradingview_symbol:tvSymbol,base_symbol:base,timeframe:'1H',url:tvUrl},null,2));
  const server=http.createServer(async(req,res)=>{try{const p=req.url==='/'?path.resolve('data/live/tradingview_capture.html'):null;if(!p){res.writeHead(404);return res.end()}const body=await fs.readFile(p);res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});res.end(body)}catch(e){res.writeHead(500);res.end(String(e));}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port;
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  page.on('console',m=>console.log(`[TradingView] ${m.type()}: ${m.text()}`));
  page.on('pageerror',e=>console.log(`[TradingView] pageerror: ${e.message}`));
  try{
    await page.goto(`http://127.0.0.1:${port}/`,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForTimeout(20000);
    const iframeCount=await page.locator('iframe').count();
    const bodyText=(await page.locator('body').innerText().catch(()=>''))||'';
    if(iframeCount<1) throw new Error('TradingView advanced-chart iframe did not load');
    await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});
    const stat=await fs.stat(LIVE_VISUAL);
    if(stat.size<50000) throw new Error(`TradingView chart screenshot is invalid or blank: ${stat.size} bytes`);
    const metadata={status:'TRADINGVIEW_CREATED',provider:'TradingView',tradingview_symbol:tvSymbol,base_symbol:base,timeframe:'1H',url:tvUrl,output:LIVE_VISUAL,bytes:stat.size,iframe_count:iframeCount,body_text_sample:bodyText.slice(0,200)};
    await fs.writeFile(path.resolve(META),JSON.stringify(metadata,null,2));
    console.log(JSON.stringify(metadata,null,2));
  }finally{await browser.close();server.close();}
}
main().catch(err=>{console.error(err.stack||err);process.exit(1);});

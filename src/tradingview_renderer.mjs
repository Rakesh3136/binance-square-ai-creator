import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { chromium } from 'playwright';

const LIVE_VISUAL='data/live/visual.png', META='data/live/visual_metadata.json', ROOT=process.cwd();
function base(s){return String(s||'').toUpperCase().trim().replace(/^BINANCE:/,'').replace(/USDT$/,'').replace(/[^A-Z0-9]/g,'');}
async function load(rel){try{return JSON.parse(await fs.readFile(path.resolve(ROOT,rel),'utf8'));}catch{return {};}}
async function latestReport(){try{const d=path.resolve(ROOT,'data/reports');const n=(await fs.readdir(d)).filter(x=>x.endsWith('-multi-agent.json'));const a=await Promise.all(n.map(async x=>({x,m:(await fs.stat(path.join(d,x))).mtimeMs})));a.sort((p,q)=>q.m-p.m);return a.length?load(path.join('data/reports',a[0].x)):{};}catch{return {};}}
function uniq(arr){return [...new Set(arr.map(base).filter(x=>/^[A-Z0-9]{2,15}$/.test(x)))];}
function chooseSymbols(pre,context,report,brief){
 const selected=pre.selected_opportunity||{}, primary=base(selected.symbol||selected.topic||context.symbol||context.symbol_usdt||report.draft?.symbol);
 const requested=brief.chart_symbols||brief.primary_story?.chart_symbols||[];
 let pair=uniq([primary,...requested]);
 if((selected.news_title||brief.primary_story?.news_title)&&pair.length<2) pair=uniq([primary,'BTC']);
 if(!pair.length) throw new Error('No authoritative symbol available for TradingView capture');
 return pair.slice(0,2);
}
function widget(sym,width,height){const tv=`BINANCE:${sym}USDT`;return `<div style="width:${width}px;height:${height}px"><div class="tradingview-widget-container" style="width:100%;height:100%"><div class="tradingview-widget-container__widget" style="width:100%;height:100%"></div><script src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{"autosize":false,"symbol":${JSON.stringify(tv)},"interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","allow_symbol_change":false,"calendar":false,"support_host":"https://www.tradingview.com","width":${width},"height":${height},"hide_top_toolbar":true,"hide_side_toolbar":true,"hide_legend":false,"withdateranges":false,"save_image":false,"studies":["Volume@tv-basicstudies","RSI@tv-basicstudies"]}</script></div></div>`;}
async function main(){
 const pre=await load('data/live/editorial_preflight.json'),ctx=await load('data/live/publication_context.json'),report=await latestReport(),brief=await load('data/live/content_director_brief.json');
 const syms=chooseSymbols(pre,ctx,report,brief), W=1800,H=900, pair=syms.length>1;
 const cells=syms.map(s=>widget(s,pair?900:1800,H)).join('');
 const html=`<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:${W}px;height:${H}px;background:#131722;overflow:hidden}body{display:flex}</style></head><body>${cells}</body></html>`;
 await fs.mkdir('data/live',{recursive:true});await fs.writeFile(path.resolve('data/live/tradingview_capture.html'),html,'utf8');
 await fs.writeFile(path.resolve(META),JSON.stringify({status:'RENDERING',provider:'TradingView',tradingview_symbols:syms.map(s=>`BINANCE:${s}USDT`),timeframe:'1H',visual_mode:pair?'TRADINGVIEW_CHART_PAIR':'TRADINGVIEW_CHART_ONLY',overlays:false,output:LIVE_VISUAL},null,2));
 const server=http.createServer(async(req,res)=>{try{if(req.url!=='/'){res.writeHead(404);return res.end();}res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store'});res.end(await fs.readFile(path.resolve('data/live/tradingview_capture.html')));}catch(e){res.writeHead(500);res.end(String(e));}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;const browser=await chromium.launch({headless:true,args:['--disable-blink-features=AutomationControlled','--disable-dev-shm-usage']});const page=await browser.newPage({viewport:{width:W,height:H},deviceScaleFactor:1});
 page.on('console',m=>console.log(`[TradingView] ${m.type()}: ${m.text()}`));page.on('pageerror',e=>console.log(`[TradingView] pageerror: ${e.message}`));
 try{await page.goto(`http://127.0.0.1:${port}/`,{waitUntil:'domcontentloaded',timeout:30000});await page.waitForSelector('iframe',{timeout:30000});await page.waitForTimeout(45000);const boxes=await page.locator('iframe').evaluateAll(els=>els.map(e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,src:e.src||''};}));const usable=boxes.filter(b=>b.width>=700&&b.height>=600);if(usable.length<syms.length)throw new Error(`TradingView iframes not usable: ${JSON.stringify(boxes)}`);const bad=await page.evaluate(()=>document.querySelectorAll('[id="level-panel"],[id="story-panel"],[id="news-panel"],[id="question-panel"]').length);if(bad)throw new Error('Custom overlay detected in chart-only renderer');await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});const stat=await fs.stat(LIVE_VISUAL);if(stat.size<40000)throw new Error(`TradingView screenshot too small: ${stat.size} bytes`);await fs.writeFile(path.resolve(META),JSON.stringify({status:'TRADINGVIEW_CREATED',provider:'TradingView',tradingview_symbols:syms.map(s=>`BINANCE:${s}USDT`),timeframe:'1H',visual_mode:pair?'TRADINGVIEW_CHART_PAIR':'TRADINGVIEW_CHART_ONLY',overlays:false,iframe_boxes:boxes,bytes:stat.size,output:LIVE_VISUAL},null,2));console.log(JSON.stringify({status:'OK',symbols:syms,mode:pair?'PAIR':'SINGLE',bytes:stat.size},null,2));}
 finally{await browser.close();server.close();}}
main().catch(e=>{console.error(e.stack||e);process.exit(1);});

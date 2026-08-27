import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const REPORT_DIR='data/reports';
const LIVE_VISUAL='data/live/visual.png';
const META='data/live/visual_metadata.json';

function latestReport(files){
  return files.filter(f=>f.endsWith('-multi-agent.json')).sort((a,b)=>b.localeCompare(a))[0];
}
function normalizeBase(symbol){
  let s=String(symbol||'').toUpperCase().trim().replace(/^BINANCE:/,'').replace(/USDT$/,'');
  return s.replace(/[^A-Z0-9]/g,'');
}
function extractTickers(text){
  const out=[]; const re=/\$?([A-Z0-9]{2,12})(?:USDT)?\b/g; let m;
  while((m=re.exec(String(text||'').toUpperCase()))){
    const s=m[1]; if(s && !['THE','THIS','CHART','USDT'].includes(s) && !out.includes(s)) out.push(s);
  }
  return out;
}

async function main(){
  const files=await fs.readdir(REPORT_DIR); const reportName=latestReport(files);
  if(!reportName) throw new Error('No fresh multi-agent report found');
  const reportPath=path.join(REPORT_DIR,reportName); const report=JSON.parse(await fs.readFile(reportPath,'utf8'));
  const draft=report.draft||{}; const post=String(draft.post||draft.text||'').trim();
  const preflight=JSON.parse(await fs.readFile('data/live/editorial_preflight.json','utf8').catch(()=> '{}'));
  const selected=preflight.selected_opportunity||{};
  const base=normalizeBase(draft.symbol||selected.symbol||((report.research||{}).strongest_signal)||extractTickers(post)[0]);
  if(!base) throw new Error('Cannot determine the selected Binance symbol');
  const tvUrl=`https://www.tradingview.com/chart/?symbol=BINANCE%3A${base}USDT&interval=60&theme=dark`;
  await fs.mkdir('data/live',{recursive:true});
  await fs.writeFile(META,JSON.stringify({status:'RENDERING',provider:'TradingView',tradingview_symbol:`BINANCE:${base}USDT`,base_symbol:base,timeframe:'1H',url:tvUrl,report:reportPath},null,2));

  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  page.on('console',m=>console.log(`[TradingView] ${m.type()}: ${m.text()}`));
  page.on('pageerror',e=>console.log(`[TradingView] pageerror: ${e.message}`));
  try{
    await page.goto(tvUrl,{waitUntil:'domcontentloaded',timeout:60000});
    await page.waitForTimeout(12000);
    await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});
  }finally{await browser.close();}
  const stat=await fs.stat(LIVE_VISUAL);
  if(stat.size<50000) throw new Error(`TradingView chart screenshot is invalid or blank: ${stat.size} bytes`);
  const metadata={status:'TRADINGVIEW_CREATED',provider:'TradingView',tradingview_symbol:`BINANCE:${base}USDT`,base_symbol:base,timeframe:'1H',url:tvUrl,report:reportPath,output:LIVE_VISUAL,bytes:stat.size};
  await fs.writeFile(META,JSON.stringify(metadata,null,2)); console.log(JSON.stringify(metadata,null,2));
}
main().catch(err=>{console.error(err.stack||err);process.exit(1);});

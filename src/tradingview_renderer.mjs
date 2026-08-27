import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const REPORT_DIR='data/reports';
const LIVE_VISUAL='data/live/visual.png';
const META='data/live/visual_metadata.json';

function latestReport(files){ return files.filter(f=>f.endsWith('-multi-agent.json')).sort((a,b)=>b.localeCompare(a))[0]; }
function normalizeBase(symbol){
  let s=String(symbol||'').toUpperCase().trim().replace(/^BINANCE:/,'').replace(/USDT$/,'');
  return s.replace(/[^A-Z0-9]/g,'');
}

async function main(){
  const files=await fs.readdir(REPORT_DIR); const reportName=latestReport(files);
  if(!reportName) throw new Error('No fresh multi-agent report found');
  const reportPath=path.join(REPORT_DIR,reportName);
  const report=JSON.parse(await fs.readFile(reportPath,'utf8'));
  const draft=report.draft||{};
  const preflight=JSON.parse(await fs.readFile('data/live/editorial_preflight.json','utf8').catch(()=> '{}'));
  const selected=preflight.selected_opportunity||{};
  const base=normalizeBase(selected.symbol||draft.symbol);
  if(!base) throw new Error('Cannot determine authoritative selected Binance symbol');

  const tvSymbol=`BINANCE:${base}USDT`;
  const tvUrl=`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}&interval=60&theme=dark`;
  await fs.mkdir('data/live',{recursive:true});
  await fs.writeFile(META,JSON.stringify({status:'RENDERING',provider:'TradingView',tradingview_symbol:tvSymbol,base_symbol:base,timeframe:'1H',url:tvUrl,report:reportPath},null,2));

  // Use TradingView's official embeddable chart widget instead of relying on the full
  // TradingView app page, which can render a blank/login/challenge page in headless CI.
  const html=`<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1440px;height:900px;background:#131722;overflow:hidden}#tv_chart{width:1440px;height:900px}</style></head><body><div id="tv_chart"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({container_id:'tv_chart',width:1440,height:900,symbol:${JSON.stringify(tvSymbol)},interval:'60',timezone:'Etc/UTC',theme:'dark',style:'1',locale:'en',enable_publishing:false,hide_top_toolbar:false,hide_legend:false,save_image:false,allow_symbol_change:false,withdateranges:true,hide_side_toolbar:true});</script></body></html>`;
  const htmlPath=path.resolve('data/live/tradingview_capture.html');
  await fs.writeFile(htmlPath,html,'utf8');

  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  page.on('console',m=>console.log(`[TradingView] ${m.type()}: ${m.text()}`));
  page.on('pageerror',e=>console.log(`[TradingView] pageerror: ${e.message}`));
  try{
    await page.goto(`file://${htmlPath}`,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForTimeout(15000);
    const iframeCount=await page.locator('iframe').count();
    if(iframeCount<1) throw new Error('TradingView widget iframe did not load');
    await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});
  }finally{ await browser.close(); }

  const stat=await fs.stat(LIVE_VISUAL);
  if(stat.size<50000) throw new Error(`TradingView chart screenshot is invalid or blank: ${stat.size} bytes`);
  const metadata={status:'TRADINGVIEW_CREATED',provider:'TradingView',tradingview_symbol:tvSymbol,base_symbol:base,timeframe:'1H',url:tvUrl,report:reportPath,output:LIVE_VISUAL,bytes:stat.size};
  await fs.writeFile(META,JSON.stringify(metadata,null,2));
  console.log(JSON.stringify(metadata,null,2));
}
main().catch(err=>{console.error(err.stack||err);process.exit(1);});

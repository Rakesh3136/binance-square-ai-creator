import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { chromium } from 'playwright';

const LIVE_VISUAL = 'data/live/visual.png';
const META = 'data/live/visual_metadata.json';
const ROOT = process.cwd();

function normalizeBase(symbol) {
  const s = String(symbol || '').toUpperCase().trim().replace(/^BINANCE:/, '').replace(/USDT$/, '');
  return s.replace(/[^A-Z0-9]/g, '');
}

async function load(rel) {
  try { return JSON.parse(await fs.readFile(path.resolve(ROOT, rel), 'utf8')); }
  catch { return {}; }
}

async function latestReport() {
  try {
    const dir = path.resolve(ROOT, 'data/reports');
    const names = (await fs.readdir(dir)).filter(x => x.endsWith('-multi-agent.json'));
    const stats = await Promise.all(names.map(async name => ({ name, mtime: (await fs.stat(path.join(dir, name))).mtimeMs })));
    stats.sort((a, b) => b.mtime - a.mtime);
    return stats.length ? load(path.join('data/reports', stats[0].name)) : {};
  } catch { return {}; }
}

function selectedSymbol(preflight, context, report) {
  const selected = preflight.selected_opportunity || {};
  const candidates = [selected.symbol, selected.topic, context.symbol, context.symbol_usdt, report.draft?.symbol];
  for (const value of candidates) {
    const base = normalizeBase(value);
    if (/^[A-Z0-9]{2,15}$/.test(base)) return base;
  }
  return '';
}

async function main() {
  const preflight = await load('data/live/editorial_preflight.json');
  const context = await load('data/live/publication_context.json');
  const report = await latestReport();
  const base = selectedSymbol(preflight, context, report);
  if (!base) throw new Error('No authoritative Binance symbol available for TradingView capture');

  const tvSymbol = `BINANCE:${base}USDT`;
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}&interval=60&theme=dark`;
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1440px;height:900px;background:#131722;overflow:hidden}</style></head><body><div class="tradingview-widget-container" style="width:1440px;height:900px"><div class="tradingview-widget-container__widget" style="width:100%;height:100%"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{"autosize":false,"symbol":${JSON.stringify(tvSymbol)},"interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","allow_symbol_change":false,"calendar":false,"support_host":"https://www.tradingview.com","width":1440,"height":900,"hide_top_toolbar":true,"hide_legend":false,"hide_side_toolbar":true,"withdateranges":false,"save_image":false,"studies":["Volume@tv-basicstudies","RSI@tv-basicstudies"]}</script></div></body></html>`;

  await fs.mkdir('data/live', { recursive: true });
  await fs.writeFile(path.resolve('data/live/tradingview_capture.html'), html, 'utf8');
  await fs.writeFile(path.resolve(META), JSON.stringify({
    status:'RENDERING', provider:'TradingView', tradingview_symbol:tvSymbol,
    base_symbol:base, timeframe:'1H', url:tvUrl, visual_mode:'TRADINGVIEW_CHART_ONLY',
    overlays:false, output:LIVE_VISUAL
  }, null, 2));

  const server = http.createServer(async (req, res) => {
    try {
      if (req.url !== '/') { res.writeHead(404); return res.end(); }
      const body = await fs.readFile(path.resolve('data/live/tradingview_capture.html'));
      res.writeHead(200, {'content-type':'text/html; charset=utf-8','cache-control':'no-store'}); res.end(body);
    } catch (e) { res.writeHead(500); res.end(String(e)); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const browser = await chromium.launch({ headless:true, args:['--disable-blink-features=AutomationControlled','--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport:{width:1440,height:900}, deviceScaleFactor:1 });
  page.on('console', m => console.log(`[TradingView] ${m.type()}: ${m.text()}`));
  page.on('pageerror', e => console.log(`[TradingView] pageerror: ${e.message}`));
  try {
    await page.goto(`http://127.0.0.1:${port}/`, {waitUntil:'domcontentloaded', timeout:30000});
    await page.waitForSelector('iframe', {timeout:30000});
    await page.waitForTimeout(45000);
    const boxes = await page.locator('iframe').evaluateAll(els => els.map(e => { const r=e.getBoundingClientRect(); return {width:r.width,height:r.height,src:e.src||''}; }));
    const usable = boxes.find(b => b.width >= 1000 && b.height >= 600);
    if (!usable) throw new Error(`TradingView iframe not usable: ${JSON.stringify(boxes)}`);
    const bodyMetrics = await page.evaluate(() => ({
      bodyText:(document.body.innerText||'').length,
      iframeCount:document.querySelectorAll('iframe').length,
      customOverlayCount:document.querySelectorAll('[id="level-panel"],[id="story-panel"],[id="news-panel"],[id="question-panel"]').length
    }));
    if (bodyMetrics.customOverlayCount !== 0) throw new Error('Custom overlay detected in chart-only renderer');
    await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});
    const stat = await fs.stat(LIVE_VISUAL);
    if (stat.size < 25000) throw new Error(`TradingView screenshot too small: ${stat.size} bytes`);
    const metadata = {
      status:'TRADINGVIEW_CREATED', provider:'TradingView', tradingview_symbol:tvSymbol,
      base_symbol:base, timeframe:'1H', url:tvUrl, output:LIVE_VISUAL, bytes:stat.size,
      iframe_boxes:boxes, render_metrics:bodyMetrics, visual_mode:'TRADINGVIEW_CHART_ONLY',
      overlays:false, indicators:['Volume','RSI']
    };
    await fs.writeFile(path.resolve(META), JSON.stringify(metadata,null,2));
    console.log(JSON.stringify(metadata,null,2));
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch(err => { console.error(err.stack || err); process.exit(1); });

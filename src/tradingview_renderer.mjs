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

function fmt(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  return n >= 1 ? n.toFixed(4).replace(/0+$/, '').replace(/\.$/, '') : n.toPrecision(6);
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

function escapeHtml(value) {
  return String(value || '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
}

function cleanText(value, max = 170) {
  return String(value || '').replace(/[#*_`]/g, '').replace(/\s+/g, ' ').trim().slice(0, max);
}

function extractFreshNews(news) {
  const ts = Date.parse(String(news?.generated_at || ''));
  if (!Number.isFinite(ts) || Date.now() - ts > 48 * 3600 * 1000 || Date.now() < ts) return null;
  for (const article of (news.articles || [])) {
    if (!article || !article.title) continue;
    const raw = String(article.summary || '');
    const match = raw.match(/<img[^>]+src=[\"']([^\"']+)/i);
    return {
      source: String(article.source || 'News'),
      title: cleanText(String(article.title).replace(/<[^>]+>/g, ''), 150),
      image_url: match ? match[1] : '',
    };
  }
  return null;
}

function chooseVisualMode(report, freshNews) {
  const style = String(report.editorial_style || report.draft?.editorial_style || report.draft?.style || '').toLowerCase();
  if (freshNews && /(news|breaking|reaction|macro|listing)/.test(style)) return 'NEWS + CHART';
  if (/(volume|gainer|loser|momentum)/.test(style)) return 'MOMENTUM MAP';
  if (/(breakout|fakeout)/.test(style)) return 'BREAKOUT TEST';
  if (/(compare|coin vs|versus)/.test(style)) return 'MARKET CHECK';
  if (/(liquidation|risk)/.test(style)) return 'RISK MAP';
  return 'TRADINGVIEW SETUP';
}

async function main() {
  const frozen = await load('data/live/authoritative_opportunity.json');
  const context = await load('data/live/publication_context.json');
  const report = await latestReport();
  const news = await load('data/live/news_snapshot.json');
  const base = normalizeBase(frozen.symbol || context.symbol || report.draft?.symbol);
  if (!base) throw new Error('No frozen authoritative Binance symbol');

  const tvSymbol = `BINANCE:${base}USDT`;
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}&interval=60&theme=dark`;
  const levels = report.research?.chart_levels || report.draft?.technical_levels || {};
  const levelData = {
    current_price: levels.current_price,
    support: levels.support,
    resistance: levels.resistance,
    tp1: levels.tp1,
    target: levels.target,
    invalidation: levels.invalidation,
    direction: levels.direction || 'SCENARIO'
  };
  const freshNews = extractFreshNews(news);
  const mode = chooseVisualMode(report, freshNews);
  const hook = cleanText(report.draft?.hook || report.draft?.title || report.hook || '', 150);
  const question = cleanText(report.draft?.question || report.draft?.discussion_question || '', 120);

  const levelPanel = `<div id="level-panel"><div class="lp-title">${escapeHtml(base)} · 1H TECHNICAL MAP</div><div class="lp-grid"><span>PRICE</span><b>${fmt(levelData.current_price)}</b><span>SUPPORT</span><b>${fmt(levelData.support)}</b><span>RESISTANCE</span><b>${fmt(levelData.resistance)}</b><span>TP1</span><b>${fmt(levelData.tp1)}</b><span>TARGET</span><b>${fmt(levelData.target)}</b><span>INVALIDATION</span><b>${fmt(levelData.invalidation)}</b></div><div class="lp-note">${escapeHtml(String(levelData.direction).replace(/_/g, ' '))} · live chart context · scenario, not guarantee</div></div>`;

  const storyPanel = `<div id="story-panel"><div class="story-mode">${escapeHtml(mode)}</div><div class="story-symbol">$${escapeHtml(base)}</div>${hook ? `<div class="story-hook">${escapeHtml(hook)}</div>` : ''}<div class="story-foot">1H · Binance · TradingView</div></div>`;

  const newsPanel = freshNews ? `<div id="news-panel">${freshNews.image_url ? `<img src="${escapeHtml(freshNews.image_url)}" alt="" onerror="this.remove()">` : '<div class="news-icon">📰</div>'}<div><div class="news-kicker">📰 ${escapeHtml(freshNews.source)}</div><div class="news-title">${escapeHtml(freshNews.title)}</div></div></div>` : '';
  const questionPanel = question ? `<div id="question-panel">💬 ${escapeHtml(question)}</div>` : '';

  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;width:1440px;height:900px;background:#131722;overflow:hidden;font-family:Arial,sans-serif}
  .tradingview-widget-container{width:1440px;height:900px}
  #level-panel,#story-panel,#news-panel,#question-panel{position:fixed;z-index:20;background:rgba(19,23,34,.95);border:1px solid rgba(255,255,255,.20);border-radius:12px;color:#fff;box-sizing:border-box;box-shadow:0 8px 28px rgba(0,0,0,.45);pointer-events:none}
  #level-panel{right:24px;top:70px;width:330px;padding:14px 16px}.lp-title{font-size:16px;font-weight:700;letter-spacing:.4px;margin-bottom:10px}.lp-grid{display:grid;grid-template-columns:1fr auto;gap:7px 12px;font-size:13px}.lp-grid span{opacity:.72}.lp-grid b{font-size:14px}.lp-note{margin-top:11px;font-size:11px;line-height:1.35;opacity:.68}
  #story-panel{left:24px;top:24px;width:440px;padding:14px 16px}.story-mode{font-size:11px;font-weight:700;letter-spacing:1px;opacity:.72}.story-symbol{font-size:24px;font-weight:800;margin:4px 0}.story-hook{font-size:16px;line-height:1.28;font-weight:600}.story-foot{margin-top:8px;font-size:10px;opacity:.55}
  #news-panel{left:24px;bottom:24px;width:480px;min-height:76px;display:flex;gap:12px;align-items:center;padding:10px 12px}.news-icon{width:58px;height:52px;display:flex;align-items:center;justify-content:center;font-size:28px}.news-panel img,#news-panel img{width:82px;height:58px;object-fit:cover;border-radius:8px}.news-kicker{font-size:11px;font-weight:700;opacity:.78;margin-bottom:5px}.news-title{font-size:13px;line-height:1.25;font-weight:600}
  #question-panel{right:24px;bottom:24px;max-width:430px;padding:11px 14px;font-size:12px;line-height:1.3;font-weight:600}
</style></head><body><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget" style="width:100%;height:100%"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{"autosize":false,"symbol":${JSON.stringify(tvSymbol)},"interval":"60","timezone":"Etc/UTC","theme":"dark","style":"1","locale":"en","allow_symbol_change":false,"calendar":false,"support_host":"https://www.tradingview.com","width":1440,"height":900,"hide_top_toolbar":false,"hide_legend":true,"hide_side_toolbar":true,"withdateranges":true,"save_image":false,"studies":["Volume@tv-basicstudies","RSI@tv-basicstudies"]}</script></div>${storyPanel}${levelPanel}${newsPanel}${questionPanel}</body></html>`;

  await fs.mkdir('data/live', { recursive: true });
  await fs.writeFile(path.resolve('data/live/tradingview_capture.html'), html, 'utf8');
  await fs.writeFile(path.resolve(META), JSON.stringify({ status:'RENDERING', provider:'TradingView', tradingview_symbol:tvSymbol, base_symbol:base, timeframe:'1H', url:tvUrl, visual_mode:mode, technical_levels:levelData, news_overlay:freshNews || null }, null, 2));

  const server = http.createServer(async (req, res) => {
    try {
      const p = req.url === '/' ? path.resolve('data/live/tradingview_capture.html') : null;
      if (!p) { res.writeHead(404); return res.end(); }
      const body = await fs.readFile(p);
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
    const iframeCount = await page.locator('iframe').count();
    const boxes = await page.locator('iframe').evaluateAll(els => els.map(e => { const r=e.getBoundingClientRect(); return {width:r.width,height:r.height,src:e.src||''}; }));
    const usable = boxes.find(b => b.width >= 1000 && b.height >= 600);
    if (!usable) throw new Error(`TradingView iframe not usable: count=${iframeCount} boxes=${JSON.stringify(boxes)}`);
    const bodyMetrics = await page.evaluate(() => ({ bodyText:(document.body.innerText||'').length, canvas:document.querySelectorAll('canvas').length, images:document.images.length, iframes:document.querySelectorAll('iframe').length }));
    console.log(`[TradingView] render metrics ${JSON.stringify(bodyMetrics)}`);
    await page.screenshot({path:path.resolve(LIVE_VISUAL),type:'png',fullPage:false});
    const stat = await fs.stat(LIVE_VISUAL);
    if (stat.size < 25000) throw new Error(`TradingView screenshot too small: ${stat.size} bytes`);
    const metadata = {status:'TRADINGVIEW_CREATED',provider:'TradingView',tradingview_symbol:tvSymbol,base_symbol:base,timeframe:'1H',url:tvUrl,output:LIVE_VISUAL,bytes:stat.size,iframe_count:iframeCount,iframe_boxes:boxes,render_metrics:bodyMetrics,visual_mode:mode,technical_levels:levelData,indicators:['Volume','RSI'],news_overlay:freshNews||null};
    await fs.writeFile(path.resolve(META), JSON.stringify(metadata,null,2));
    console.log(JSON.stringify(metadata,null,2));
  } finally { await browser.close(); server.close(); }
}

main().catch(err => { console.error(err.stack || err); process.exit(1); });

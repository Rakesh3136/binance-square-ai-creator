import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const REPORT_DIR = 'data/reports';
const LIVE_VISUAL = 'data/live/visual.png';
const META = 'data/live/visual_metadata.json';
const HTML = '/tmp/tradingview-square-chart.html';

function latestReport(files) {
  return files
    .filter((f) => f.endsWith('-multi-agent.json'))
    .sort((a, b) => b.localeCompare(a))[0];
}

function extractTickers(text) {
  const out = [];
  const re = /\$?([A-Z0-9]{2,12})USDT\b/g;
  let m;
  while ((m = re.exec(String(text || '').toUpperCase()))) {
    if (!out.includes(m[1])) out.push(m[1]);
  }
  return out;
}

function normalizeBase(symbol) {
  let s = String(symbol || '').toUpperCase().trim();
  s = s.replace(/^BINANCE:/, '').replace(/USDT$/, '');
  return s.replace(/[^A-Z0-9]/g, '');
}

async function main() {
  const files = await fs.readdir(REPORT_DIR);
  const reportName = latestReport(files);
  if (!reportName) throw new Error('No multi-agent report found');

  const reportPath = path.join(REPORT_DIR, reportName);
  const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
  const draft = report.draft || {};
  const lane = report.selected_editorial_lane || {};
  const preflight = JSON.parse(await fs.readFile('data/live/editorial_preflight.json', 'utf8').catch(() => '{}'));
  const selected = preflight.selected_opportunity || {};
  const post = String(draft.post || draft.text || report.post || report.text || '').trim();

  const postTickers = extractTickers(post);
  const laneSymbol = normalizeBase(lane.symbol || selected.symbol || '');
  const laneInPost = laneSymbol && postTickers.includes(laneSymbol);
  const base = laneInPost ? laneSymbol : (postTickers[0] || laneSymbol);
  if (!base) throw new Error('Cannot determine the main Binance symbol from the fresh post');

  const tvSymbol = `BINANCE:${base}USDT`;
  const title = String((report.visual_plan || {}).title || 'Market Structure');
  const output = path.resolve(LIVE_VISUAL);
  const metadata = {
    status: 'RENDERING',
    provider: 'TradingView',
    tradingview_symbol: tvSymbol,
    base_symbol: base,
    timeframe: '1H',
    post_tickers: postTickers,
    report: reportPath,
    title,
  };
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(META, JSON.stringify(metadata, null, 2));

  const html = `<!doctype html>
<html><head><meta charset="utf-8"><title>${title.replace(/</g, '&lt;')}</title>
<style>html,body{margin:0;width:100%;height:100%;background:#131722;overflow:hidden}.wrap{width:1400px;height:820px;margin:0 auto}.tradingview-widget-container{width:100%;height:100%}.tradingview-widget-container__widget{width:100%;height:calc(100% - 32px)}.tradingview-widget-copyright{height:32px;font:12px Arial;color:#9aa4b2;padding:8px 12px;box-sizing:border-box}.tradingview-widget-copyright a{color:#2962ff;text-decoration:none}</style></head>
<body><div class="wrap"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/symbols/${base}USDT/" rel="noopener nofollow">${base}USDT chart</a> by TradingView</div></div></div>
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
${JSON.stringify({
  autosize: true,
  symbol: tvSymbol,
  interval: '60',
  timezone: 'exchange',
  theme: 'dark',
  style: '1',
  locale: 'en',
  hide_side_toolbar: true,
  hide_top_toolbar: false,
  allow_symbol_change: false,
  save_image: false,
  withdateranges: false,
  hide_volume: false,
  support_host: 'https://www.tradingview.com',
  studies: ['EMA@tv-basicstudies', 'EMA@tv-basicstudies', 'RSI@tv-basicstudies'],
  show_popup_button: false,
  details: false,
  calendar: false,
  hotlist: false,
  news: [],
  backgroundColor: 'rgba(19, 23, 34, 1)',
  gridColor: 'rgba(42, 46, 57, 0.6)',
})}
</script></div></body></html>`;
  await fs.writeFile(HTML, html);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 820 }, deviceScaleFactor: 1 });
  page.on('console', (msg) => console.log(`[TradingView] ${msg.type()}: ${msg.text()}`));
  page.on('pageerror', (err) => console.log(`[TradingView] pageerror: ${err.message}`));

  try {
    await page.goto(`file://${HTML}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.locator('iframe').first().waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(9000);
    await page.screenshot({ path: output, type: 'png' });
  } finally {
    await browser.close();
  }

  const stat = await fs.stat(output);
  if (stat.size < 20000) throw new Error(`TradingView screenshot is suspiciously small: ${stat.size} bytes`);

  metadata.status = 'TRADINGVIEW_CREATED';
  metadata.output = LIVE_VISUAL;
  metadata.bytes = stat.size;
  await fs.writeFile(META, JSON.stringify(metadata, null, 2));
  console.log(JSON.stringify(metadata, null, 2));
}

main().catch((err) => {
  console.error(err.stack || err);
  process.exit(1);
});

// 生成社交分享卡（Open Graph / Twitter Card）底图：1200×630 PNG → assets/og/
//
// 为什么要有：地图链接发到微信 / Twitter / Slack 时，抓的是 og:image。
// 明信片底图是 1024×1536 竖版，直接当 og:image 会被平台裁得只剩中间一条，
// 所以这里把「竖版明信片 + 行程标题 + 统计」重排成 1200×630 横版。
//
// 幂等：已存在的卡默认跳过，加 --force 全量重画。
// 用法（仓库根目录）：
//   node tools/gen_og_cards.mjs           # 只补缺的
//   node tools/gen_og_cards.mjs --force   # 全部重画
//   node tools/gen_og_cards.mjs --only kyoto_6d
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const MAPS_DIR = path.join(ROOT, 'maps');
const CARDS_DIR = path.join(ROOT, 'assets', 'postcards');
const OUT_DIR = path.join(ROOT, 'assets', 'og');
const SHOT = { type: 'jpeg', quality: 86 }; // 插画底图，JPEG 比 PNG 小 ~6x 且肉眼无差

const FORCE = process.argv.includes('--force');
const ONLY = (() => {
  const i = process.argv.indexOf('--only');
  return i > -1 ? process.argv[i + 1] : null;
})();

fs.mkdirSync(OUT_DIR, { recursive: true });

// ---------- 从地图 HTML 里抽卡片文案 ----------
const stripEmoji = (s) => s.replace(/^[\p{Extended_Pictographic}️\s]+/u, '').trim();
const firstEmoji = (s) => (s.match(/\p{Extended_Pictographic}/u) || [''])[0];

function readMeta(file) {
  const html = fs.readFileSync(file, 'utf-8');
  const slug = path.basename(file, '.html');
  let meta = {};
  const m = html.match(/const META = (\{.*?\});\n/s);
  if (m) { try { meta = JSON.parse(m[1]); } catch { /* 老地图格式不同，走下面的兜底 */ } }

  // 老地图（big_island / kyoto_6d / yellowstone_5d）没有 META 常量，从 <title> 兜底
  const titleTag = (html.match(/<title>(.*?)<\/title>/s) || [, ''])[1].replace(/\s*·\s*LiveMap\s*$/, '').trim();
  // 老地图标题形如「夏威夷大岛 7 天精准攻略地图 · Big Island Interactive Map」，
  // 对 OG 卡太长，只留分隔符前那段并去掉「精准攻略地图」这类赘词。
  const rawTitle = (meta.title || titleTag).split(/\s*[·|]\s*/)[0]
    .replace(/\s*(精准)?攻略地图\s*$/, '').trim();

  // POI 数：新地图 "lat": / 老地图 lat:
  const poiCount = (html.match(/["']?lat["']?\s*:/g) || []).length - (meta.map_center ? 0 : 0);
  const days = meta.total_days || Number((slug.match(/_(\d+)d$/) || [, 0])[1]) || 0;

  return {
    slug,
    title: stripEmoji(meta.title_short || rawTitle) || slug,
    emoji: meta.header_emoji || firstEmoji(rawTitle) || '🗺️',
    eyebrow: (meta.eyebrow || '').split('·')[0].trim().toUpperCase(),
    days,
    poi: Math.max(0, poiCount - 1), // 减掉 map_center 那一处
    accent: meta.accent || '#c9803f',
    budget: (meta.stats || []).find((s) => /花费|budget/i.test(s.label || ''))?.num || '',
    transport: (meta.stats || []).find((s) => /交通|transport/i.test(s.label || ''))?.num || '',
  };
}

// ---------- 卡片 HTML ----------
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function cardHTML(meta, postcardDataUri) {
  const chips = [
    meta.days ? `${meta.days} 天` : '',
    meta.poi ? `${meta.poi} 个景点` : '',
    meta.transport,
    meta.budget,
  ].filter(Boolean);

  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{width:1200px;height:630px;overflow:hidden;
    font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,sans-serif;
    display:flex;background:#12161f;color:#fff}
  .left{flex:1;padding:64px 56px 48px;display:flex;flex-direction:column;justify-content:space-between;
    background:radial-gradient(ellipse at 10% 0%, #22293a 0%, #141a26 55%, #0b0f18 100%);position:relative}
  .left::after{content:"";position:absolute;inset:0;
    background:linear-gradient(90deg,transparent 82%,rgba(0,0,0,.55) 100%)}
  .brand{display:flex;align-items:center;gap:10px;font-size:20px;letter-spacing:.22em;font-weight:800;
    color:${meta.accent};text-transform:uppercase}
  .eyebrow{margin-top:34px;font-size:20px;letter-spacing:.2em;color:#8b98ac;font-weight:700}
  .title{margin-top:14px;font-size:${meta.title.length > 12 ? 58 : 68}px;line-height:1.16;font-weight:900;
    letter-spacing:-.01em;max-width:9.2em}
  .emoji{font-size:56px;margin-right:12px;vertical-align:-6px}
  .chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
  .chip{padding:9px 18px;border-radius:999px;font-size:22px;font-weight:700;color:#e7eef7;
    background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14)}
  .foot{font-size:21px;color:#7d8a9c;font-weight:600;position:relative;z-index:3;max-width:15.5em}
  .foot b{color:#c3ceda}
  .right{width:430px;position:relative;flex-shrink:0}
  .right img{width:100%;height:100%;object-fit:cover;object-position:center 22%}
  .fade{position:absolute;inset:0;z-index:2;pointer-events:none;
    background:linear-gradient(90deg,rgba(15,20,30,1) 0%,rgba(15,20,30,.7) 13%,rgba(15,20,30,.2) 32%,transparent 58%)}
  .noimg{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:180px;
    background:linear-gradient(150deg,#1d2534,#0d1219)}
</style></head><body>
  <div class="left">
    <div>
      <div class="brand">◆ LiveMap 活地图</div>
      ${meta.eyebrow ? `<div class="eyebrow">${esc(meta.eyebrow)}</div>` : ''}
      <div class="title"><span class="emoji">${meta.emoji}</span>${esc(meta.title)}</div>
      <div class="chips">${chips.map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</div>
    </div>
    <div class="foot">真实底图 · 门票价格 · 拍照点<br><b>单文件 HTML，发出去就能看</b></div>
  </div>
  <div class="right">${postcardDataUri
    ? `<img src="${postcardDataUri}">`
    : `<div class="noimg">${meta.emoji}</div>`}<div class="fade"></div></div>
</body></html>`;
}

// 站点级卡片（Hub 首页）
function siteHTML(collage, mapCount, poiCount) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{width:1200px;height:630px;overflow:hidden;position:relative;color:#fff;
    font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,sans-serif;
    background:radial-gradient(ellipse at 50% -10%, #1c2333 0%, #0e1320 58%, #05080f 100%)}
  .strip{position:absolute;inset:0;display:flex;opacity:.30}
  .strip img{flex:1;height:100%;object-fit:cover;object-position:center 25%}
  .scrim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(6,9,16,.62),rgba(6,9,16,.93))}
  .wrap{position:relative;height:100%;display:flex;flex-direction:column;justify-content:center;
    align-items:center;text-align:center;padding:0 80px}
  .brand{font-size:22px;letter-spacing:.34em;font-weight:800;color:#f4c065;text-transform:uppercase}
  h1{margin-top:22px;font-size:76px;line-height:1.18;font-weight:900;letter-spacing:-.015em}
  h1 em{font-style:normal;color:#f4c065}
  p{margin-top:24px;font-size:28px;color:#a9b6c6;font-weight:600}
  .chips{display:flex;gap:14px;margin-top:36px}
  .chip{padding:11px 24px;border-radius:999px;font-size:24px;font-weight:700;color:#e7eef7;
    background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15)}
</style></head><body>
  <div class="strip">${collage.map((d) => `<img src="${d}">`).join('')}</div>
  <div class="scrim"></div>
  <div class="wrap">
    <div class="brand">◆ LiveMap 活地图</div>
    <h1>把旅行攻略<br>变成一张能<em>「看」</em>的地图</h1>
    <p>输入目的地 → 10 秒生成可交互活地图 → 发给同伴一眼秒懂</p>
    <div class="chips">
      <span class="chip">🗺️ ${mapCount} 条现成行程</span>
      <span class="chip">📍 ${poiCount}+ 个景点</span>
      <span class="chip">📦 单文件 HTML</span>
    </div>
  </div>
</body></html>`;
}

const dataUri = (p) => (fs.existsSync(p) ? `data:image/png;base64,${fs.readFileSync(p).toString('base64')}` : null);

// ---------- 主流程 ----------
const files = fs.readdirSync(MAPS_DIR).filter((f) => f.endsWith('.html')).sort();
const metas = files.map((f) => readMeta(path.join(MAPS_DIR, f)));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });

let made = 0, skipped = 0;
for (const meta of metas) {
  if (ONLY && meta.slug !== ONLY) continue;
  const out = path.join(OUT_DIR, `${meta.slug}.jpg`);
  if (!FORCE && fs.existsSync(out)) { skipped++; continue; }
  await page.setContent(cardHTML(meta, dataUri(path.join(CARDS_DIR, `${meta.slug}.png`))), { waitUntil: 'load' });
  await page.screenshot({ path: out, ...SHOT });
  made++;
  console.log(`🖼  ${meta.slug}.jpg  ← ${meta.title} (${meta.days}天/${meta.poi}点)`);
}

// 站点卡
const siteOut = path.join(OUT_DIR, '_site.jpg');
if (!ONLY && (FORCE || !fs.existsSync(siteOut))) {
  const picks = ['usnp_top20_5d', 'kyoto_6d', 'southwest_8d', 'alaska_summer_7d']
    .map((s) => dataUri(path.join(CARDS_DIR, `${s}.png`))).filter(Boolean);
  const totalPoi = metas.reduce((a, m) => a + m.poi, 0);
  await page.setContent(siteHTML(picks, metas.length, Math.floor(totalPoi / 10) * 10), { waitUntil: 'load' });
  await page.screenshot({ path: siteOut, ...SHOT });
  made++;
  console.log('🖼  _site.jpg  ← Hub 站点卡');
}

await browser.close();
console.log(`\n✅ OG 卡片：新生成 ${made} 张，跳过已存在 ${skipped} 张 → assets/og/`);

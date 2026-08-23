// 生成 README / 文档用的产品截图 → docs/img/
// 用法（仓库根目录，先起好静态站）：
//   python3 generator/build_static.py --out dist
//   BASE_URL=http://localhost:8010 node tools/shot_readme.mjs
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const BASE = process.env.BASE_URL || 'http://localhost:8000';
const OUT = path.join(ROOT, 'docs', 'img');
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const SHOT = { type: 'jpeg', quality: 90 };
const shot = async (name, fn, viewport = { width: 1440, height: 900 }) => {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1.5 });
  await fn(page);
  const file = path.join(OUT, `${name}.jpg`);
  await page.screenshot({ path: file, ...SHOT });
  await page.close();
  console.log('📸', path.relative(ROOT, file));
};

// 等地图脚本就绪
const ready = (page) =>
  page.waitForFunction(() => typeof filterPOIs === 'function' && Object.keys(markers).length > 0, { timeout: 20000 });

// 1. Hub 首屏
await shot('hub', async (p) => {
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(900);
});

// 2. Hub 画廊
await shot('hub-gallery', async (p) => {
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.querySelector('.gallery, #gallery, .cards')?.scrollIntoView({ block: 'start' }));
  await p.waitForTimeout(1600); // 等卡片懒加载的目的地图
});

// 3. 全程总览（日签 + 分色路线）
await shot('map-overview', async (p) => {
  await p.goto(`${BASE}/maps/southwest_8d.html`, { waitUntil: 'networkidle' });
  await ready(p);
  await p.evaluate(() => { currentDay = 'all'; filterPOIs(); });
  await p.waitForTimeout(1400);
});

// 4. 单日视图 + POI 详情面板
// 走真实点击（而不是直接改 currentDay），否则 Day Tab 的高亮不会跟着变，截图会自相矛盾。
await shot('map-poi', async (p) => {
  await p.goto(`${BASE}/maps/kyoto_budget_5d.html`, { waitUntil: 'networkidle' });
  await ready(p);
  await p.click('.day-tabs .tab[data-day="2"]');
  await p.waitForTimeout(900);
  await p.evaluate(() => showDetail(POIs.find((x) => String(x.day) === '2')));
  // 等 Wikimedia 四宫格真的搜到图（搜不到就是 emoji 兜底，那张截图不能用）
  await p.waitForFunction(
    () => document.querySelectorAll('.poi-hero-cell img').length >= 3, { timeout: 15000 },
  ).catch(() => console.warn('   ⚠️ 四宫格没搜到图，本张截图会是 emoji 兜底'));
  await p.waitForTimeout(1200);
});

// 5. 行程海报（分享增长回路）—— 只截海报本体，不要弹窗外壳
{
  const page = await browser.newPage({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 1.5 });
  await page.goto(`${BASE}/maps/yellowstone_5d.html`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof generatePoster === 'function', { timeout: 20000 });
  await page.click('#posterFab');
  await page.waitForSelector('#posterModal.show', { timeout: 10000 });
  await page.waitForTimeout(2500); // 等明信片底图 + 二维码
  const file = path.join(OUT, 'poster.jpg');
  await page.locator('#posterStage .ps-root').screenshot({ path: file, ...SHOT });
  await page.close();
  console.log('📸', path.relative(ROOT, file));
}

await browser.close();

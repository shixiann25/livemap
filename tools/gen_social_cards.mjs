// 批量导出小红书素材 → docs/social/
//
// 每条行程出两张：
//   <slug>_poster.jpg   1080×1440（3:4，小红书推荐比例）——行程海报，自带二维码
//   <slug>_map.jpg      1080×1440 —— 全程总览地图，竖版裁切
//
// 为什么是海报而不是截图：海报是产品自带的分享物，一张图里有目的地、天数、
// 每天的主题、玩点数量和二维码，本身就是一条完整的笔记配图。
//
// 用法（仓库根目录，先起好静态站）：
//   BASE_URL=http://localhost:8010 node tools/gen_social_cards.mjs
//   BASE_URL=... node tools/gen_social_cards.mjs kyoto_6d southwest_8d   # 只出指定几张
import { chromium } from 'playwright';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const BASE = process.env.BASE_URL || 'http://localhost:8000';
const OUT = path.join(ROOT, 'docs', 'social');
const ONLY = process.argv.slice(2);

// 小红书竖图推荐 3:4。海报本身就是 3:4，按比例放大即可；
// 地图是横的，用竖视口重新渲染再截，比裁切横图保留的信息多。
const W = 1080, H = 1440;
// 出 JPEG 不出 PNG：64 张 PNG 有 89 MB，进不了仓库；q92 只要 24 MB，
// 而且小红书上传后本来就会重新编码，无损在这里没有意义。
const SHOT = { type: 'jpeg', quality: 92 };

fs.mkdirSync(OUT, { recursive: true });
const maps = fs.readdirSync(path.join(ROOT, 'dist', 'maps'))
  .filter((f) => f.endsWith('.html'))
  .map((f) => f.replace('.html', ''))
  .filter((s) => !ONLY.length || ONLY.includes(s))
  .sort();

// 尺寸不精确的话小红书会自己裁，不如我们自己控制
function exact(file) {
  try {
    execFileSync('sips', ['-z', String(H), String(W), file], { stdio: 'pipe' });
  } catch { /* sips 只有 macOS 有；没有就保持原尺寸，比例本来就是对的 */ }
}

const browser = await chromium.launch();
let okPoster = 0, okMap = 0;
const failed = [];

for (const slug of maps) {
  // ---------- 海报（3:4，自带二维码）----------
  try {
    // deviceScaleFactor 让 454px 宽的舞台按 2.4 倍输出，正好 ≈1080
    const p = await browser.newPage({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 2.4 });
    await p.goto(`${BASE}/maps/${slug}.html`, { waitUntil: 'networkidle' });
    await p.waitForFunction(() => typeof generatePoster === 'function', { timeout: 20000 });
    await p.click('#posterFab');
    await p.waitForSelector('#posterModal.show', { timeout: 10000 });
    await p.waitForTimeout(2800);            // 等明信片底图 + 二维码画完
    const f = path.join(OUT, `${slug}_poster.jpg`);
    await p.locator('#posterStage .ps-root').screenshot({ path: f, ...SHOT });
    await p.close();
    exact(f);                                // deviceScaleFactor 出来是 1090×1454，收到正好 1080×1440
    okPoster++;
  } catch (e) {
    failed.push(`${slug} 海报: ${e.message.slice(0, 60)}`);
  }

  // ---------- 竖版整屏（标题 + 路线）----------
  // 用移动端宽度渲染：模板在 ≤768px 会切成单列，天然就是竖版，
  // 比把横向地图裁成 3:4 保留的信息多得多（标题、Day Tab、图例都在）。
  try {
    const p = await browser.newPage({ viewport: { width: W / 2, height: H / 2 }, deviceScaleFactor: 2 });
    await p.goto(`${BASE}/maps/${slug}.html`, { waitUntil: 'networkidle' });
    await p.waitForFunction(
      () => typeof filterPOIs === 'function' && Object.keys(markers).length > 0, { timeout: 20000 });
    await p.evaluate(() => { currentDay = 'all'; filterPOIs(); });
    // 藏掉浮动 UI：海报按钮、打卡进度条、「我的点」——它们压住图例和日签，
    // 而且推广图里不需要出现操作入口
    await p.addStyleTag({ content:
      '#posterFab,.lm-progress,.lm-addbtn,#lmEdFab{display:none!important}' });
    await p.waitForTimeout(2600);            // 等 fitBounds 动画 + 标签防重叠跑完
    await p.screenshot({ path: path.join(OUT, `${slug}_map.jpg`), ...SHOT });   // 整屏，不是只截 #map
    await p.close();
    okMap++;
  } catch (e) {
    failed.push(`${slug} 竖版: ${e.message.slice(0, 60)}`);
  }

  process.stdout.write(`\r  已完成 ${okPoster}/${maps.length} 海报 · ${okMap}/${maps.length} 地图`);
}
await browser.close();

console.log(`\n✅ 素材已出 → ${path.relative(ROOT, OUT)}/`);
console.log(`   海报 ${okPoster} 张 · 总览地图 ${okMap} 张`);
if (failed.length) {
  console.log(`⚠️  ${failed.length} 张失败：`);
  failed.slice(0, 8).forEach((f) => console.log('   ·', f));
}

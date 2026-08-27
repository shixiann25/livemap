// 录一段产品演示，导出 GIF → docs/img/demo.gif
//
// 为什么要 GIF 而不是截图：这个产品的说服力在「切换那一下」——
// 每天换一种颜色、路线跟着变、点开景点有实拍图。静态截图看起来只是一张地图，
// 动起来才看得出它是活的。README 首屏、X、Reddit 都要用同一个文件。
//
// 用法（仓库根目录，先起好静态站）：
//   BASE_URL=http://localhost:8010 node tools/gen_demo_gif.mjs
//   BASE_URL=... node tools/gen_demo_gif.mjs southwest_8d      # 换一张图录
import { chromium } from 'playwright';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const BASE = process.env.BASE_URL || 'http://localhost:8000';
const MAP = process.argv[2] || 'southwest_8d';
const OUT = path.join(ROOT, 'docs', 'img', 'demo.gif');
const TMP = '/tmp/itinera_demo';

// 录制尺寸偏小是有意的：GIF 没有帧间压缩，每一帧都是一整张图，
// 1440 宽录 12 秒能到几十 MB，README 里根本加载不出来。
const VIEW = { width: 1200, height: 760 };
const FPS = Number(process.env.GIF_FPS || 10);
const GIF_WIDTH = Number(process.env.GIF_WIDTH || 700);
// 调色板大小：Esri 瓦片的颜色比原来的 CARTO 丰富，192 色会把文件顶到 7 MB+。
// 160 色肉眼几乎无差，省近 2 MB。
const GIF_COLORS = Number(process.env.GIF_COLORS || 160);

fs.rmSync(TMP, { recursive: true, force: true });
fs.mkdirSync(TMP, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: VIEW,
  deviceScaleFactor: 1,
  recordVideo: { dir: TMP, size: VIEW },
});
const page = await ctx.newPage();

const wait = (ms) => page.waitForTimeout(ms);

console.log(`🎬 录制 ${MAP} …`);
await page.goto(`${BASE}/maps/${MAP}.html`, { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => typeof filterPOIs === 'function' && Object.keys(markers).length > 0,
  { timeout: 20000 },
);
await wait(1300);                       // 停一下：让人先看清「一屏看完整趟」

// 逐天切换——这是整个演示的核心，路线和配色跟着变
const days = await page.evaluate(() =>
  [...new Set(POIs.map((p) => p.day))].sort((a, b) => a - b).slice(0, 3));   // 三天足够展示「每天一种颜色」，多了只是拖长文件
for (const d of days) {
  await page.click(`.day-tabs .tab[data-day="${d}"]`);
  await wait(1250);
}

// 回到全程总览，再点开一个景点看详情（四宫格实拍是第二个记忆点）
await page.click('.day-tabs .tab[data-day="all"]');
await wait(1000);
await page.click(`.day-tabs .tab[data-day="${days[1]}"]`);
await wait(800);
await page.evaluate((d) => showDetail(POIs.find((x) => String(x.day) === String(d))), days[1]);
// 刻意不滚页面：整屏平移会让每一帧的像素全变，GIF 没有帧间压缩，
// 一个滚动动作能把文件撑大两三成。详情面板本来就在右侧可见。
await wait(2900);                       // 等四宫格把图搜出来

await ctx.close();                      // 视频在 context 关闭时才落盘
await browser.close();

const webm = fs.readdirSync(TMP).find((f) => f.endsWith('.webm'));
if (!webm) {
  console.error('❌ 没录到视频');
  process.exit(1);
}
const src = path.join(TMP, webm);

// 两遍调色板：先统计整段视频的颜色分布，再用它编码。
// 单遍编码会让地图的渐变和实拍图糊成色块。
console.log('🎨 转 GIF（两遍调色板）…');
const filters =
  `fps=${FPS},scale=${GIF_WIDTH}:-1:flags=lanczos,` +
  `split[s0][s1];[s0]palettegen=max_colors=${GIF_COLORS}:stats_mode=diff[p];` +
  `[s1][p]paletteuse=dither=bayer:bayer_scale=3`;
execFileSync('ffmpeg', ['-y', '-i', src, '-vf', filters, '-loop', '0', OUT], { stdio: 'pipe' });

const kb = Math.round(fs.statSync(OUT).size / 1024);
console.log(`✅ ${path.relative(ROOT, OUT)} — ${kb} KB @ ${GIF_WIDTH}px / ${FPS}fps`);
if (kb > 6000) {
  console.warn('⚠️  超过 6 MB，GitHub 上会加载很慢。调小 GIF_WIDTH / GIF_FPS / GIF_COLORS 再跑一次。');
}

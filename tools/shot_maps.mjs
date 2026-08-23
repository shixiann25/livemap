// 截图复核：对指定 地图×天 渲染并存 PNG，供以「用户视角」肉眼检查重叠/挤压/清晰度。
// 用法：node shot_maps.mjs '<json jobs>'  例如：
//   node shot_maps.mjs '[["kyoto_budget_5d.html",1],["orlando_5d.html",1]]'
// 不传参数则自动对每张图的 Day1 各截一张。
import { chromium } from 'playwright';
import fs from 'fs';

const BASE = (process.env.BASE_URL || 'http://localhost:8000') + '/maps';
const ROOT = new URL('..', import.meta.url).pathname;
const MAPS_DIR = process.env.MAPS_DIR || `${ROOT}dist/maps`;
const OUT_DIR = '/tmp/livemap_qa';
fs.mkdirSync(OUT_DIR, { recursive: true });

let jobs = [];
if (process.argv[2]) {
  jobs = JSON.parse(process.argv[2]);
} else {
  jobs = fs.readdirSync(MAPS_DIR).filter(f => f.endsWith('.html')).sort().map(f => [f, 1]);
}

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const outs = [];
for (const [f, d] of jobs) {
  await p.goto(`${BASE}/${f}`, { waitUntil: 'networkidle', timeout: 20000 });
  await p.waitForFunction(() => typeof filterPOIs === 'function' && Object.keys(markers).length > 0, { timeout: 10000 }).catch(() => {});
  await p.evaluate((dd) => { currentDay = String(dd); filterPOIs(); }, d);
  await p.waitForTimeout(700);
  const out = `${OUT_DIR}/${f.replace('.html', '')}_d${d}.png`;
  await p.screenshot({ path: out });
  outs.push(out);
  console.log(out);
}
await b.close();

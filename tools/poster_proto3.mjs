// 海报原型 v3：整张背景换成 AI 卡通明信片插画 + 渐变压暗 scrim + 毛玻璃内容卡 + 路线浮在插画上。
import { chromium } from 'playwright';
import fs from 'fs';

const MAP = process.argv[2] || 'yellowstone_5d.html';
const BG  = process.argv[3] || '/tmp/livemap_qa/postcard_yellowstone.png';
const OUT = `/tmp/livemap_qa/poster3_${MAP.replace('.html','')}.png`;
const bgData = 'data:image/png;base64,' + fs.readFileSync(BG).toString('base64');

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1440 }, deviceScaleFactor: 2 });
await p.goto(`${process.env.BASE_URL || 'http://localhost:8000'}/maps/${MAP}`, { waitUntil: 'domcontentloaded' });
await p.waitForFunction(() => { try { return typeof POIs!=='undefined' && typeof DAYS!=='undefined'; } catch(e){ return false; } }, { timeout: 15000 });
const data = await p.evaluate(() => {
  const title=(document.title.split('·')[0]||document.title).trim();
  const dn=Object.keys(DAYS).map(Number).sort((a,b)=>a-b);
  const days=dn.map(d=>{const pts=POIs.filter(x=>x.day===d).sort((a,b)=>a.num-b.num);
    return{d,theme:dayThemeText(d),color:(DAYS[d]||{}).color||'#888',where:(DAYS[d]||{}).where||'',
      pois:pts.map(x=>({name:x.name_cn||x.name,icon:x.icon,lat:x.lat,lng:x.lng}))};});
  const flat=POIs.slice().sort((a,b)=>a.day===b.day?a.num-b.num:a.day-b.day)
    .map(x=>({day:x.day,lat:x.lat,lng:x.lng,color:(DAYS[x.day]||{}).color||'#888'}));
  return{title,days,flat,count:POIs.length};
});

const W=1000,H=460,PAD=64;
const lats=data.flat.map(p=>p.lat),lngs=data.flat.map(p=>p.lng);
const minLat=Math.min(...lats),maxLat=Math.max(...lats),minLng=Math.min(...lngs),maxLng=Math.max(...lngs);
const spanLat=(maxLat-minLat)||0.01,spanLng=(maxLng-minLng)||0.01;
const sc=Math.min((W-2*PAD)/spanLng,(H-2*PAD)/spanLat);
const offX=(W-spanLng*sc)/2,offY=(H-spanLat*sc)/2;
const X=l=>+(offX+(l-minLng)*sc).toFixed(1),Y=l=>+(offY+(maxLat-l)*sc).toFixed(1);
const pts=data.flat.map(p=>({...p,x:X(p.lng),y:Y(p.lat)}));
const glow=pts.slice(1).map((p,i)=>`<line x1="${pts[i].x}" y1="${pts[i].y}" x2="${p.x}" y2="${p.y}" stroke="${p.color}" stroke-width="16" stroke-linecap="round" opacity="0.45" filter="url(#bl)"/>`).join('');
const segs=pts.slice(1).map((p,i)=>`<line x1="${pts[i].x}" y1="${pts[i].y}" x2="${p.x}" y2="${p.y}" stroke="${p.color}" stroke-width="6" stroke-linecap="round"/>`).join('');
const dots=pts.map(p=>`<circle cx="${p.x}" cy="${p.y}" r="7" fill="${p.color}" stroke="#fff" stroke-width="3"/>`).join('');
const badges=data.days.map(day=>{const dp=day.pois.map(q=>({x:X(q.lng),y:Y(q.lat)}));if(!dp.length)return'';
  const cx=dp.reduce((s,q)=>s+q.x,0)/dp.length,cy=dp.reduce((s,q)=>s+q.y,0)/dp.length;
  return`<g><circle cx="${cx.toFixed(1)}" cy="${(cy-2).toFixed(1)}" r="21" fill="${day.color}" stroke="#fff" stroke-width="3.5"/>
  <text x="${cx.toFixed(1)}" y="${(cy+6).toFixed(1)}" fill="#fff" font-size="21" font-weight="900" text-anchor="middle" font-family="PingFang SC,sans-serif">${day.d}</text></g>`;}).join('');

const clean=s=>(s||'').replace(/^\d+\.\s*/,'').trim();
const trunc=s=>{const t=clean(s);return t.length>9?t.slice(0,9)+'…':t;};
const dayRows=data.days.map(day=>{
  const theme=day.theme;
  const spots=day.pois.slice(0,5).map(q=>`<span class="spot">${q.icon||'📍'} ${trunc(q.name)}</span>`).join('');
  const more=day.pois.length>5?`<span class="spot more">+${day.pois.length-5}</span>`:'';
  return`<div class="drow"><div class="dbadge" style="background:${day.color}">D${day.d}</div>
  <div class="dhead"><div class="dtheme">${theme}</div><div class="dcount">${day.pois.length} 个玩点</div></div>
  <div class="spots">${spots}${more}</div></div>`;}).join('');

const html=`<!doctype html><html><head><meta charset="utf-8"><style>
 *{margin:0;padding:0;box-sizing:border-box}
 body{width:1080px;height:1440px;font-family:'PingFang SC','Hiragino Sans GB',sans-serif;position:relative;overflow:hidden;color:#fff}
 .bg{position:absolute;inset:0;background:url('${bgData}') center/cover no-repeat}
 .scrim{position:absolute;inset:0;background:
   linear-gradient(180deg,rgba(15,22,18,.62) 0%,rgba(15,22,18,.20) 26%,rgba(15,22,18,.30) 56%,rgba(12,18,14,.86) 100%)}
 .wrap{position:relative;padding:50px 54px 42px;height:100%;display:flex;flex-direction:column}
 .top{display:flex;justify-content:space-between;align-items:flex-start}
 .kicker{font-size:21px;font-weight:800;letter-spacing:3px;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.5)}
 .kicker span{background:#e7b24a;color:#1a130a;padding:3px 12px;border-radius:8px;margin-right:10px;letter-spacing:1px}
 .seal{width:88px;height:88px;border-radius:50%;border:2px solid #fff;color:#fff;display:flex;flex-direction:column;
   align-items:center;justify-content:center;font-weight:900;font-size:18px;text-align:center;transform:rotate(-8deg);
   background:rgba(0,0,0,.18);backdrop-filter:blur(2px)}
 .seal small{font-size:11px;letter-spacing:2px;opacity:.85}
 h1{font-size:60px;font-weight:900;line-height:1.08;margin:14px 0 8px;letter-spacing:1px;text-shadow:0 3px 16px rgba(0,0,0,.55)}
 .chips{display:flex;gap:12px}
 .chip{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.30);border-radius:30px;padding:8px 18px;
   font-size:21px;font-weight:800;backdrop-filter:blur(6px)}
 .chip b{color:#ffd47a}
 .mapcard{margin:18px 0;border-radius:24px;overflow:hidden;flex:0 0 auto;border:1px solid rgba(255,255,255,.22);
   background:rgba(10,16,13,.34);backdrop-filter:blur(3px);box-shadow:0 18px 44px rgba(0,0,0,.40)}
 svg{display:block;width:100%;height:auto}
 .days{display:flex;flex-direction:column;gap:10px;flex:1 1 auto;justify-content:center}
 .drow{display:flex;align-items:center;gap:16px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.20);
   border-radius:16px;padding:11px 18px;backdrop-filter:blur(8px)}
 .dbadge{flex:0 0 auto;width:54px;height:54px;border-radius:14px;color:#fff;font-weight:900;font-size:23px;
   display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(0,0,0,.3)}
 .dhead{flex:0 0 288px}
 .dtheme{font-size:25px;font-weight:900;line-height:1.12;text-shadow:0 1px 6px rgba(0,0,0,.4)}
 .dcount{font-size:15px;color:#cdd6c2;font-weight:700;margin-top:2px}
 .spots{flex:1 1 auto;display:flex;flex-wrap:wrap;gap:7px;align-content:center}
 .spot{font-size:16px;font-weight:700;color:#eef2e6;background:rgba(255,255,255,.15);
   border:1px solid rgba(255,255,255,.20);border-radius:9px;padding:4px 11px;white-space:nowrap}
 .spot.more{color:#cdd6c2;background:rgba(255,255,255,.08)}
 .footer{display:flex;align-items:center;gap:20px;margin-top:14px;background:rgba(8,14,10,.62);
   border:1px solid rgba(255,255,255,.14);border-radius:20px;padding:18px 26px;backdrop-filter:blur(8px)}
 .qr{flex:0 0 auto;width:98px;height:98px;border-radius:13px;background:#fff;padding:9px}
 .qr div{width:100%;height:100%;border-radius:6px;background:
   conic-gradient(from 0deg,#0e1a14 25%,#fff 0 50%,#0e1a14 0 75%,#fff 0) 0 0/27px 27px,#0e1a14}
 .fcta b{font-size:28px;font-weight:900}
 .fcta p{font-size:19px;opacity:.85;margin-top:6px;line-height:1.4}
</style></head><body>
 <div class="bg"></div><div class="scrim"></div>
 <div class="wrap">
  <div class="top"><div class="kicker"><span>LiveMap</span>活地图 · 精准行程</div>
    <div class="seal">甄选<small>CURATED</small></div></div>
  <h1>${data.title}</h1>
  <div class="chips"><div class="chip">📅 <b>${data.days.length}</b> 天</div>
    <div class="chip">📍 <b>${data.count}</b> 个精选点</div><div class="chip">🚗 自驾路线</div></div>
  <div class="mapcard"><svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    <defs><filter id="bl"><feGaussianBlur stdDeviation="6"/></filter></defs>${glow}${segs}${dots}${badges}</svg></div>
  <div class="days">${dayRows}</div>
  <div class="footer"><div class="qr"><div></div></div>
    <div class="fcta"><b>扫码查看可交互活地图</b><p>每个点位有图片 · 攻略 · 营业时间 · 路线 — 还能一键生成你自己的行程海报</p></div></div>
 </div></body></html>`;

await p.setContent(html,{waitUntil:'networkidle'});
await p.waitForTimeout(350);
await p.screenshot({ path: OUT });
await b.close();
console.log('✅ poster →', OUT);

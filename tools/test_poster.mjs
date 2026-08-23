import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 1 });
const errs=[];
p.on('console', m=>{ if(m.type()==='error') errs.push(m.text()); });
await p.goto(`${process.env.BASE_URL || 'http://localhost:8000'}/maps/yellowstone_5d.html`, { waitUntil: 'networkidle', timeout: 30000 });
await p.waitForFunction(()=>typeof generatePoster==='function' && typeof QRCode!=='undefined' && typeof html2canvas!=='undefined', {timeout:15000});
await p.click('#posterFab');
await p.waitForSelector('#posterModal.show', {timeout:8000});
await p.waitForTimeout(1200); // 等 postcard 图 + QR
const info = await p.evaluate(()=>{
  const qr=document.querySelector('#posterQR img,#posterQR canvas');
  const bg=document.querySelector('#posterStage .ps-bg');
  return { qr: !!qr, bgStyle:(bg&&bg.getAttribute('style')||'').slice(0,60), rows:document.querySelectorAll('#posterStage .ps-row').length, spots:document.querySelectorAll('#posterStage .ps-spot').length };
});
console.log('MODAL:', JSON.stringify(info));
// 测试 html2canvas 真能出图
const dataLen = await p.evaluate(async ()=>{
  const c = await html2canvas(document.querySelector('#posterStage .ps-root'),{useCORS:true,backgroundColor:null,scale:1,width:1080,height:1440});
  return c.toDataURL('image/png').length;
});
console.log('html2canvas PNG dataURL 长度:', dataLen);
await p.screenshot({ path: '/tmp/livemap_qa/poster_modal.png' });
console.log('CONSOLE ERRORS:', errs.length, errs.slice(0,3).join(' | '));
await b.close();

// 当质量门用：任何一项不达标就非 0 退出，别让 CI 绿着放行
const fails = [];
if (!info.qr) fails.push('二维码没渲染出来');
if (!/postcards\//.test(info.bgStyle)) fails.push('海报底图不是明信片：' + info.bgStyle);
if (!info.rows) fails.push('行程行数为 0');
if (!info.spots) fails.push('景点数为 0');
if (dataLen < 50000) fails.push('html2canvas 出图过小（' + dataLen + ' 字节 dataURL）');
if (errs.length) fails.push(errs.length + ' 条控制台报错');
if (fails.length) {
  console.error('❌ POSTER E2E FAILED:\n  - ' + fails.join('\n  - '));
  process.exitCode = 1;
} else {
  console.log('✅ POSTER E2E PASSED');
}

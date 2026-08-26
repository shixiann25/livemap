#!/usr/bin/env python3
"""把 8 张地图升级到 v0.7：POI 上下导航 + Lightbox 翻图 + 距离时间 + 出行前清单 + Plan B + GPX 导出"""
import json
import re
from pathlib import Path

MAPS_DIR = Path(__file__).parent.parent / "maps"

# ========== 1. POI 导航 + Lightbox + 距离 + GPX 的 CSS ==========
CSS_BLOCK = """
  /* v0.7 新增 */
  .poi-nav-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .poi-nav-arrows { display: flex; align-items: center; gap: 4px; }
  .nav-arrow { background: rgba(0,0,0,0.08); border: none; color: inherit; width: 28px; height: 28px; border-radius: 6px; font-size: 18px; font-weight: 700; cursor: pointer; line-height: 1; display: flex; align-items: center; justify-content: center; opacity: 0.7; }
  .nav-arrow:hover { background: rgba(0,0,0,0.15); opacity: 1; }
  .nav-arrow:disabled { opacity: 0.2; cursor: not-allowed; }
  .nav-counter { font-size: 10.5px; opacity: 0.7; min-width: 50px; text-align: center; font-weight: 600; }
  .day-route-distance { font-size: 10px; padding: 4px 0 4px 30px; opacity: 0.75; display: flex; align-items: center; gap: 6px; line-height: 1.4; }
  .day-route-distance::before { content: '↓'; font-weight: 700; opacity: 0.5; }
  .day-route-distance .dot-sep { opacity: 0.4; }
  .lightbox-arrow { position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; width: 48px; height: 48px; border-radius: 50%; font-size: 28px; cursor: pointer; backdrop-filter: blur(8px); transition: all 0.15s; display: flex; align-items: center; justify-content: center; line-height: 1; }
  .lightbox-arrow:hover { background: rgba(255,255,255,0.2); transform: translateY(-50%) scale(1.1); }
  .lightbox-arrow:disabled { opacity: 0.2; cursor: not-allowed; }
  .lightbox-prev { left: 30px; }
  .lightbox-next { right: 30px; }
  .lightbox-dots { position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; }
  .lightbox-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.4); cursor: pointer; transition: all 0.2s; }
  .lightbox-dot.active { background: #fff; transform: scale(1.4); }
  @media (max-width: 768px) {
    .lightbox-arrow { width: 36px; height: 36px; font-size: 22px; }
    .lightbox-prev { left: 10px; }
    .lightbox-next { right: 10px; }
  }
  .pretrip-card { background: linear-gradient(135deg, rgba(74,141,181,0.12) 0%, rgba(45,95,138,0.06) 100%); border: 1px solid rgba(74,141,181,0.3); border-left: 3px solid #2d5f8a; border-radius: 10px; padding: 12px 14px; margin: 14px 0 8px; }
  .pretrip-title { font-size: 11px; font-weight: 700; color: #2d5f8a; letter-spacing: 1px; margin-bottom: 8px; }
  .pretrip-row { font-size: 11.5px; line-height: 1.5; padding: 3px 0; display: flex; gap: 6px; }
  .pretrip-row .pretrip-label { opacity: 0.7; flex-shrink: 0; min-width: 50px; font-weight: 600; }
  .planb-card { background: linear-gradient(135deg, rgba(74,141,181,0.1) 0%, rgba(45,95,138,0.05) 100%); border-left: 3px solid #4a8db5; border-radius: 8px; padding: 10px 12px; margin: 10px 0 8px; font-size: 11.5px; line-height: 1.55; }
  .gpx-export { width: 100%; padding: 11px; background: linear-gradient(135deg, #58a87c 0%, #1f7a5a 100%); border: none; border-radius: 8px; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; margin-top: 14px; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.15s; }
  .gpx-export:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(31,122,90,0.4); }
"""

# ========== 2. JS 函数（导航 + 距离 + GPX + Lightbox 翻图）==========
JS_FUNCTIONS = """

// === v0.7: POI 上下导航 + Lightbox 翻图 + 距离 + GPX ===
function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371, toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1), dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat/2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng/2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
function renderDistance(km) {
  const realKm = km * 1.3;
  const walkMin = Math.round(realKm / 5 * 60);
  const driveMin = Math.round(realKm / 30 * 60);
  const distStr = realKm < 1 ? `${Math.round(realKm * 1000)} m` : `${realKm.toFixed(1)} km`;
  let modes = '';
  if (realKm < 1.5) modes = `🚶 ${walkMin} min`;
  else if (realKm < 5) modes = `🚶 ${walkMin} min <span class="dot-sep">·</span> 🚕 ${driveMin} min`;
  else modes = `🚕 ${driveMin} min`;
  return `<div class="day-route-distance">${distStr} <span class="dot-sep">·</span> ${modes}</div>`;
}
window.navPoi = function(delta) {
  const list = window._navPoiList || [];
  const idx = (window._navPoiIdx || 0) + delta;
  if (idx < 0 || idx >= list.length) return;
  showDetail(list[idx]);
};
window._lbImages = []; window._lbIdx = 0;
const _origOpenLb = window.openLightbox;
window.openLightbox = function(url) {
  const allImgs = Array.from(document.querySelectorAll('.poi-hero-cell img')).map(i => i.src);
  window._lbImages = allImgs.length ? allImgs : [url];
  window._lbIdx = Math.max(0, window._lbImages.indexOf(url));
  if (window._lbIdx < 0) { window._lbImages = [url]; window._lbIdx = 0; }
  _showLightbox();
};
function _showLightbox() {
  document.getElementById('lightboxImg').src = window._lbImages[window._lbIdx];
  document.getElementById('lightbox').classList.add('show');
  const dotsEl = document.getElementById('lightboxDots');
  if (dotsEl) {
    dotsEl.innerHTML = window._lbImages.map((_, i) =>
      `<span class="lightbox-dot${i === window._lbIdx ? ' active' : ''}" onclick="window._lbIdx=${i};_showLightbox();"></span>`
    ).join('');
  }
  const prev = document.querySelector('.lightbox-prev');
  const next = document.querySelector('.lightbox-next');
  if (prev) prev.disabled = window._lbIdx <= 0;
  if (next) next.disabled = window._lbIdx >= window._lbImages.length - 1;
}
window.navLightbox = function(delta) {
  const newIdx = window._lbIdx + delta;
  if (newIdx < 0 || newIdx >= window._lbImages.length) return;
  window._lbIdx = newIdx;
  _showLightbox();
};
document.addEventListener('keydown', (e) => {
  if (document.getElementById('lightbox').classList.contains('show')) {
    if (e.key === 'ArrowLeft') navLightbox(-1);
    if (e.key === 'ArrowRight') navLightbox(1);
    if (e.key === 'Escape') closeLightbox();
  } else if (document.getElementById('poiDetail').classList.contains('show')) {
    if (e.key === 'ArrowLeft') navPoi(-1);
    if (e.key === 'ArrowRight') navPoi(1);
    if (e.key === 'Escape') closeDetail();
  }
});
window.exportGPX = function() {
  const totalDays = Math.max(...POIs.map(p => p.day));
  const sorted = [...POIs].sort((a, b) => a.day === b.day ? a.num - b.num : a.day - b.day);
  let gpx = `<?xml version="1.0" encoding="UTF-8"?>\\n<gpx version="1.1" creator="Itinera" xmlns="http://www.topografix.com/GPX/1/1">\\n`;
  gpx += `  <metadata><name>Itinera Trip</name><desc>Generated by Itinera</desc></metadata>\\n`;
  sorted.forEach(p => {
    const desc = (p.desc||'').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));
    gpx += `  <wpt lat="${p.lat}" lon="${p.lng}"><name>Day${p.day}.${p.num} ${p.icon} ${p.name}</name><desc>${desc}</desc><type>${p.tags?.[0]||'POI'}</type></wpt>\\n`;
  });
  for (let d = 1; d <= totalDays; d++) {
    const points = POIs.filter(p => p.day === d).sort((a, b) => a.num - b.num);
    if (points.length < 2) continue;
    const dt = (typeof DAYS !== 'undefined' && DAYS[d]) ? DAYS[d].title : `Day ${d}`;
    gpx += `  <trk><name>${dt}</name><trkseg>\\n`;
    points.forEach(p => { gpx += `    <trkpt lat="${p.lat}" lon="${p.lng}"><name>${p.name}</name></trkpt>\\n`; });
    gpx += `  </trkseg></trk>\\n`;
  }
  gpx += `</gpx>`;
  const blob = new Blob([gpx], { type: 'application/gpx+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `livemap_${Date.now()}.gpx`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
};
"""


def upgrade(path: Path):
    src = path.read_text(encoding="utf-8")
    if "exportGPX" in src and "haversineKm" in src:
        return False, "已升级"

    # 1. CSS 注入
    if "haversineKm" not in src:
        src = src.replace("</style>", CSS_BLOCK + "\n</style>", 1)

    # 2. Lightbox HTML 升级：加箭头 + dots
    OLD_LB = '<div class="lightbox" id="lightbox" onclick="closeLightbox()">'
    if OLD_LB in src and "lightbox-arrow" not in src:
        # 找到 lightbox 整块替换
        pat = re.compile(r'<div class="lightbox" id="lightbox" onclick="closeLightbox\(\)">\s*<span class="lightbox-close">×</span>\s*<img id="lightboxImg" alt="">\s*</div>', re.DOTALL)
        new_lb = '''<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close" onclick="event.stopPropagation();closeLightbox();">×</span>
  <button class="lightbox-arrow lightbox-prev" onclick="event.stopPropagation();navLightbox(-1);">‹</button>
  <img id="lightboxImg" alt="" onclick="event.stopPropagation();">
  <button class="lightbox-arrow lightbox-next" onclick="event.stopPropagation();navLightbox(1);">›</button>
  <div class="lightbox-dots" id="lightboxDots" onclick="event.stopPropagation();"></div>
</div>'''
        src = pat.sub(new_lb, src)

    # 3. POI nav bar：把 back-btn 包裹起来
    if 'poi-nav-bar' not in src:
        OLD_BACK_PATTERNS = [
            ('<button class="back-btn" onclick="closeDetail()">← 返回行程</button>\n        <div class="poi-hero" id="pdHero">',
             '<div class="poi-nav-bar">\n          <button class="back-btn" onclick="closeDetail()">← 返回行程</button>\n          <div class="poi-nav-arrows">\n            <button class="nav-arrow" id="prevPoiBtn" onclick="navPoi(-1)">‹</button>\n            <span class="nav-counter" id="poiCounter">1 / 1</span>\n            <button class="nav-arrow" id="nextPoiBtn" onclick="navPoi(1)">›</button>\n          </div>\n        </div>\n        <div class="poi-hero" id="pdHero">'),
            ('<button class="back-btn" onclick="closeDetail()">← 返回行程</button>',
             '<div class="poi-nav-bar"><button class="back-btn" onclick="closeDetail()">← 返回行程</button><div class="poi-nav-arrows"><button class="nav-arrow" id="prevPoiBtn" onclick="navPoi(-1)">‹</button><span class="nav-counter" id="poiCounter">1 / 1</span><button class="nav-arrow" id="nextPoiBtn" onclick="navPoi(1)">›</button></div></div>'),
        ]
        for old, new in OLD_BACK_PATTERNS:
            if old in src:
                src = src.replace(old, new, 1)
                break

    # 4. showDetail 里加更新 counter 的逻辑（在 pdGmaps 那行后注入）
    if 'window._navPoiList' not in src:
        marker = "document.getElementById('pdGmaps').href = `https://www.google.com/maps/search/?api=1&query=${p.lat},${p.lng}`;"
        if marker in src:
            inject = marker + """
  // POI 上下导航
  const allPois = POIs.filter(x => typeof currentDay === 'undefined' || currentDay === 'all' || String(x.day) === String(currentDay))
    .sort((a, b) => a.day === b.day ? a.num - b.num : a.day - b.day);
  const _idx = allPois.findIndex(x => x.id === p.id);
  const _cnt = document.getElementById('poiCounter');
  if (_cnt) _cnt.textContent = `${_idx + 1} / ${allPois.length}`;
  const _prev = document.getElementById('prevPoiBtn');
  const _next = document.getElementById('nextPoiBtn');
  if (_prev) _prev.disabled = _idx <= 0;
  if (_next) _next.disabled = _idx >= allPois.length - 1;
  window._navPoiList = allPois; window._navPoiIdx = _idx;"""
            src = src.replace(marker, inject, 1)

    # 5. 路线列表加距离（在 day 视图渲染列表 .map 之后）
    if 'renderDistance' not in src.split('// === v0.7')[0]:  # 不重复注入
        # 找 points.map(p => `<li onclick=...) 并改成带距离
        OLD_MAP_PATTERNS = [
            (r"const listItems = points\.map\(p => `(.*?)`\)\.join\(''\);",),
        ]
        for (pat_str,) in OLD_MAP_PATTERNS:
            pat = re.compile(pat_str, re.DOTALL)
            m = pat.search(src)
            if m and 'renderDistance' not in m.group(0):
                inner = m.group(1)
                new_code = f"""const listItems = points.map((p, i) => {{
      let liHtml = `{inner}`;
      if (i < points.length - 1) {{ liHtml += renderDistance(haversineKm(p.lat, p.lng, points[i+1].lat, points[i+1].lng)); }}
      return liHtml;
    }}).join('');"""
                src = src[:m.start()] + new_code + src[m.end():]
                break

    # 6. JS 函数注入（在 </script> 前最后）
    if 'haversineKm' not in src:
        src = src.replace("</script>\n</body>", JS_FUNCTIONS + "\n</script>\n</body>", 1)

    path.write_text(src, encoding="utf-8")
    return True, "OK"


if __name__ == "__main__":
    for f in sorted(MAPS_DIR.glob("*.html")):
        ok, msg = upgrade(f)
        flag = "✅" if ok else "⏭️ "
        print(f"  {flag} {f.name}: {msg}")

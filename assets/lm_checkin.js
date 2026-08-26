/* Itinera · 打卡 checklist + 自定义点（本地 localStorage，按地图 slug 隔离）
   依赖页面全局：POIs, DAYS, map, markers, showDetail。数据也喂给海报（window._lmCustom / _lmVisitedCount）。*/
(function () {
  if (typeof POIs === 'undefined' || typeof map === 'undefined' || !map) return;
  const SLUG = (location.pathname.split('/').pop() || 'map').replace('.html', '');
  const LS = {
    get(k, d) { try { const v = JSON.parse(localStorage.getItem('lm_' + k + '_' + SLUG)); return v == null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('lm_' + k + '_' + SLUG, JSON.stringify(v)); } catch (e) {} }
  };
  let visited = new Set(LS.get('visited', []));
  let custom = LS.get('custom', []); // [{id,name,note,lat,lng}]
  const customMarkers = {};
  let curPOI = null, addMode = false;

  // 暴露给海报
  window._lmVisited = visited;
  window._lmCustom = custom;
  window._lmVisitedCount = () => [...visited].filter(id => POIs.some(p => p.id === id)).length;

  // ---------- 样式 ----------
  const css = document.createElement('style');
  css.textContent = `
    .lm-progress{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:9997;
      display:flex;align-items:center;gap:9px;padding:7px 15px;border-radius:22px;font-size:13px;font-weight:800;
      color:#2b3a30;background:rgba(255,255,255,0.94);box-shadow:0 2px 12px rgba(0,0,0,0.18);backdrop-filter:blur(6px);cursor:default}
    .lm-progress .bar{width:90px;height:7px;border-radius:4px;background:#e2e6df;overflow:hidden}
    .lm-progress .bar i{display:block;height:100%;background:linear-gradient(90deg,#58a87c,#1f7a5a);width:0%}
    .lm-addbtn{position:fixed;right:16px;bottom:74px;z-index:9998;display:inline-flex;align-items:center;gap:7px;
      padding:11px 16px;border:none;border-radius:24px;cursor:pointer;font-size:14px;font-weight:800;color:#fff;
      background:linear-gradient(135deg,#7b61c9,#5a3fa8);box-shadow:0 6px 18px rgba(90,63,168,.4);transition:transform .15s}
    .lm-addbtn:hover{transform:translateY(-2px)}
    .lm-addbtn.active{background:linear-gradient(135deg,#c2542e,#9a3a1e)}
    .lm-checkbtn{width:100%;margin:6px 0 12px;padding:11px;border-radius:9px;border:1.5px solid #58a87c;cursor:pointer;
      font-size:14px;font-weight:800;color:#1f7a5a;background:#eefaf2;transition:all .15s}
    .lm-checkbtn.done{background:linear-gradient(135deg,#58a87c,#1f7a5a);color:#fff;border-color:#1f7a5a}
    .poi-pin.lm-visited::after{content:"✓";position:absolute;top:-7px;right:-7px;width:18px;height:18px;border-radius:50%;
      background:#1f7a5a;color:#fff;font-size:12px;font-weight:900;line-height:18px;text-align:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)}
    .lm-cpin{display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50% 50% 50% 0;
      transform:rotate(-45deg);background:linear-gradient(135deg,#7b61c9,#5a3fa8);box-shadow:0 3px 9px rgba(0,0,0,.4);border:2px solid #fff}
    .lm-cpin span{transform:rotate(45deg);font-size:16px}
    .lm-hint{position:fixed;top:54px;left:50%;transform:translateX(-50%);z-index:10001;padding:9px 18px;border-radius:20px;
      background:rgba(20,24,20,.9);color:#fff;font-size:13px;font-weight:700;box-shadow:0 4px 14px rgba(0,0,0,.3)}
    .lm-modal{position:fixed;inset:0;z-index:10002;display:none;align-items:center;justify-content:center;background:rgba(15,18,16,.6)}
    .lm-modal.show{display:flex}
    .lm-card{width:300px;background:#fff;border-radius:16px;padding:20px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
    .lm-card h4{margin:0 0 12px;font-size:17px;color:#2b3a30}
    .lm-card input,.lm-card textarea{width:100%;box-sizing:border-box;padding:9px 11px;margin-bottom:10px;border:1px solid #d8ddd4;
      border-radius:8px;font-size:14px;font-family:inherit;resize:vertical}
    .lm-card .row{display:flex;gap:8px;margin-top:4px}
    .lm-card button{flex:1;padding:10px;border:none;border-radius:8px;font-size:14px;font-weight:800;cursor:pointer}
    .lm-save{background:linear-gradient(135deg,#7b61c9,#5a3fa8);color:#fff}
    .lm-cancel{background:#eee;color:#555}
    .lm-del{background:#fbe9e7;color:#c1440e;flex:0 0 auto;padding:10px 14px}
  `;
  document.head.appendChild(css);

  // ---------- 进度条 ----------
  const prog = document.createElement('div');
  prog.className = 'lm-progress';
  prog.innerHTML = `<span>🎯 已打卡 <b class="n">0</b>/${POIs.length}</span><span class="bar"><i></i></span>`;
  document.body.appendChild(prog);
  function updateProgress() {
    const n = window._lmVisitedCount();
    prog.querySelector('.n').textContent = n;
    prog.querySelector('.bar i').style.width = (POIs.length ? Math.round(n / POIs.length * 100) : 0) + '%';
  }

  // ---------- 标记打卡徽章 ----------
  function applyBadges() {
    document.querySelectorAll('.poi-pin').forEach(el => {
      el.classList.toggle('lm-visited', visited.has(el.getAttribute('data-id')));
    });
  }
  function toggleVisited(id) {
    if (!id) return;
    if (visited.has(id)) visited.delete(id); else visited.add(id);
    LS.set('visited', [...visited]);
    updateProgress(); applyBadges(); updateCheckBtn();
  }

  // ---------- 详情面板「打卡」按钮 ----------
  const checkBtn = document.createElement('button');
  checkBtn.className = 'lm-checkbtn';
  checkBtn.onclick = () => { if (curPOI) toggleVisited(curPOI.id); };
  function updateCheckBtn() {
    if (!curPOI) return;
    const done = visited.has(curPOI.id);
    checkBtn.classList.toggle('done', done);
    checkBtn.textContent = done ? '✓ 已打卡（点击取消）' : '✓ 标记我去过这里';
  }
  function mountCheckBtn() {
    const meta = document.getElementById('pdMeta');
    if (meta && !meta.parentNode.querySelector('.lm-checkbtn')) meta.insertAdjacentElement('afterend', checkBtn);
  }
  // 监听详情面板内容变化，识别当前 POI（用 pdGmaps 的经纬度兜底匹配）
  const pdName = document.getElementById('pdName');
  if (pdName) {
    const obs = new MutationObserver(() => {
      mountCheckBtn();
      const g = document.getElementById('pdGmaps');
      const m = g && /query=(-?\d+\.?\d*),(-?\d+\.?\d*)/.exec(g.getAttribute('href') || '');
      if (m) {
        const la = +m[1], ln = +m[2];
        curPOI = POIs.find(p => Math.abs(p.lat - la) < 1e-4 && Math.abs(p.lng - ln) < 1e-4) || curPOI;
      }
      updateCheckBtn();
    });
    obs.observe(pdName, { childList: true, characterData: true, subtree: true });
  }

  // ---------- 自定义点 ----------
  const cIcon = (typeof L !== 'undefined') ? () => L.divIcon({ className: 'lm-cpin-wrap', html: '<div class="lm-cpin"><span>📍</span></div>', iconSize: [34, 34], iconAnchor: [17, 32] }) : null;
  function renderCustom() {
    custom.forEach(c => {
      if (customMarkers[c.id]) return;
      const mk = L.marker([c.lat, c.lng], { icon: cIcon() }).addTo(map);
      mk.on('click', () => openEditor(c.id));
      mk.bindTooltip('📍 ' + c.name, { direction: 'top' });
      customMarkers[c.id] = mk;
    });
    window._lmCustom = custom;
  }
  function saveCustomArr() { LS.set('custom', custom); window._lmCustom = custom; }

  // ---------- 地理编码（搜地点）----------
  async function geocode(q) {
    if (!q) return [];
    try { const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=6&accept-language=zh&q=' + encodeURIComponent(q)); return r.ok ? await r.json() : []; }
    catch (e) { return []; }
  }
  async function translateZhEn(q) {
    try { const r = await fetch('https://api.mymemory.translated.net/get?langpair=zh|en&q=' + encodeURIComponent(q)); const d = await r.json(); const t = d && d.responseData && d.responseData.translatedText; return (t && t.trim()) ? t.trim() : ''; }
    catch (e) { return ''; }
  }
  // 中文先查 OSM，没命中就翻成英文再查
  async function smartGeo(q) {
    let hits = await geocode(q), note = '';
    if (!hits.length && /[一-鿿]/.test(q)) {
      const en = await translateZhEn(q);
      if (en) { const h2 = await geocode(en); if (h2.length) { hits = h2; note = '已按英文「' + en + '」搜索'; } }
    }
    return { hits, note };
  }

  // ---------- 添加/编辑弹窗 ----------
  const modal = document.createElement('div');
  modal.className = 'lm-modal';
  modal.innerHTML = `<div class="lm-card">
    <h4 class="t">添加我的点</h4>
    <div class="lm-search">
      <div style="display:flex;gap:6px"><input class="sq" placeholder="🔍 搜地点，如 Universal Studios" style="flex:1"><button class="lm-sbtn" type="button" style="flex:0 0 auto;background:#eef6ff;color:#1f6fd0">搜</button></div>
      <div class="sres" style="margin-top:6px"></div>
      <div class="sloc" style="display:none;font-size:12px;color:#1f7a5a;font-weight:700;margin:2px 0"></div>
      <button class="lm-mapbtn" type="button" style="background:#f0f0f5;color:#555;margin-bottom:6px">📍 或点地图选位置</button>
    </div>
    <input class="nm" placeholder="名字，如『超好吃的拉面店』" maxlength="20">
    <textarea class="nt" rows="2" placeholder="备注（可选）" maxlength="80"></textarea>
    <div class="row">
      <button class="lm-del" style="display:none">删除</button>
      <button class="lm-cancel">取消</button>
      <button class="lm-save">保存</button>
    </div></div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });
  let editing = null, pending = null;
  function openModal(title, name, note, isEdit) {
    modal.querySelector('.t').textContent = title;
    modal.querySelector('.nm').value = name || '';
    modal.querySelector('.nt').value = note || '';
    modal.querySelector('.lm-del').style.display = isEdit ? 'block' : 'none';
    modal.querySelector('.lm-search').style.display = isEdit ? 'none' : 'block';
    modal.querySelector('.sq').value = ''; modal.querySelector('.sres').innerHTML = '';
    const loc = modal.querySelector('.sloc'); loc.style.display = pending ? 'block' : 'none'; loc.textContent = pending ? '✓ 已选位置，点保存即可' : '';
    modal.classList.add('show');
    setTimeout(() => modal.querySelector(isEdit ? '.nm' : '.sq').focus(), 50);
  }
  const runSearch = async () => {
    const q = modal.querySelector('.sq').value.trim(); if (!q) return;
    const res = modal.querySelector('.sres');
    res.innerHTML = '<div style="font-size:12px;color:#9aa;padding:3px">搜索中…（中文自动翻译后再查）</div>';
    const { hits, note } = await smartGeo(q);
    if (!hits.length) { res.innerHTML = '<div style="font-size:12px;color:#c1440e;padding:3px">没找到 · 海外景点用英文官方名（如 Universal Studios Florida）</div>'; return; }
    res.innerHTML = note ? '<div style="font-size:11px;color:#8a948c;margin-bottom:4px">' + note + '</div>' : '';
    hits.forEach(h => {
      const it = document.createElement('div');
      it.style.cssText = 'padding:6px 8px;border:1px solid #e3ece5;border-radius:7px;margin-bottom:4px;cursor:pointer;font-size:12px;background:#fff';
      it.textContent = '📍 ' + (h.display_name || '').slice(0, 48);
      it.onclick = () => {
        pending = { lat: +(+h.lat).toFixed(5), lng: +(+h.lon).toFixed(5) };
        if (!modal.querySelector('.nm').value) modal.querySelector('.nm').value = q;
        const loc = modal.querySelector('.sloc'); loc.style.display = 'block'; loc.textContent = '✓ 已定位「' + q + '」，点保存即可';
        res.innerHTML = ''; try { map.setView([pending.lat, pending.lng], Math.max(map.getZoom(), 12)); } catch (e) {}
      };
      res.appendChild(it);
    });
  };
  modal.querySelector('.lm-sbtn').onclick = runSearch;
  modal.querySelector('.sq').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); runSearch(); } });
  modal.querySelector('.lm-mapbtn').onclick = () => { modal.classList.remove('show'); setAddMode(true); };
  modal.querySelector('.lm-cancel').onclick = () => { modal.classList.remove('show'); editing = pending = null; };
  modal.querySelector('.lm-save').onclick = () => {
    const name = modal.querySelector('.nm').value.trim() || '我的点';
    const note = modal.querySelector('.nt').value.trim();
    if (editing) {
      const c = custom.find(x => x.id === editing); if (c) { c.name = name; c.note = note; customMarkers[editing].setTooltipContent('📍 ' + name); }
    } else if (pending) {
      const c = { id: 'c' + Date.now(), name, note, lat: pending.lat, lng: pending.lng };
      custom.push(c); renderCustom();
    } else { alert('请先搜索地点，或点「📍 或点地图选位置」'); return; }
    saveCustomArr(); modal.classList.remove('show'); editing = pending = null;
  };
  modal.querySelector('.lm-del').onclick = () => {
    if (editing) { custom = custom.filter(x => x.id !== editing); if (customMarkers[editing]) { map.removeLayer(customMarkers[editing]); delete customMarkers[editing]; } saveCustomArr(); }
    modal.classList.remove('show'); editing = pending = null;
  };
  function openEditor(id) { const c = custom.find(x => x.id === id); if (c) { editing = id; pending = null; openModal('编辑我的点', c.name, c.note, true); } }

  // ---------- 添加模式 ----------
  const addBtn = document.createElement('button');
  addBtn.className = 'lm-addbtn';
  addBtn.innerHTML = '➕ 我的点';
  document.body.appendChild(addBtn);
  let hint = null;
  function setAddMode(on) {
    addMode = on; addBtn.classList.toggle('active', on);
    addBtn.innerHTML = on ? '✕ 取消添加' : '➕ 我的点';
    document.getElementById('map').style.cursor = on ? 'crosshair' : '';
    if (on && !hint) { hint = document.createElement('div'); hint.className = 'lm-hint'; hint.textContent = '点击地图任意位置添加你的点'; document.body.appendChild(hint); }
    if (!on && hint) { hint.remove(); hint = null; }
  }
  addBtn.onclick = () => {
    if (addMode) { setAddMode(false); return; }
    editing = null; pending = null;
    openModal('添加我的点', '', '', false);
  };
  map.on('click', e => {
    if (!addMode) return;
    pending = { lat: +e.latlng.lat.toFixed(5), lng: +e.latlng.lng.toFixed(5) }; editing = null;
    setAddMode(false);
    openModal('添加我的点', '', '', false);
  });

  // ---------- 初始化 ----------
  function init() { updateProgress(); applyBadges(); renderCustom(); }
  if (document.readyState === 'complete') setTimeout(init, 300);
  else window.addEventListener('load', () => setTimeout(init, 300));
  // 标记可能在地图渲染后才出现，补一次
  setTimeout(applyBadges, 1500);
})();

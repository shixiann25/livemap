/* LiveMap · 可视化地图编辑器（仅在 server.py 后端在线时启用，保存写回地图文件）。
   依赖：POIs, DAYS, META, map, render（保存走 server.py /api/save → render_html）。*/
(function () {
  if (typeof POIs === 'undefined' || typeof DAYS === 'undefined' || typeof map === 'undefined') return;
  const FILE = location.pathname.split('/').pop();
  let data = null, addMode = false, dirty = false;

  // 静态站（GitHub Pages）没有后端，构建期注入 LIVEMAP_STATIC 直接跳过探测，
  // 免得每张图都往控制台扔一个 404。
  if (window.LIVEMAP_STATIC) return;
  // 仅当后端存在（server.py 提供 /api/list）才挂编辑器
  fetch('/api/list').then(r => { if (r.ok) boot(); }).catch(() => {});

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function reconstruct() {
    const legend = [...document.querySelectorAll('.legend-item')].map(it => {
      const dot = it.querySelector('.legend-dot');
      const icon = dot ? dot.textContent.trim() : '';
      return { icon, label: it.textContent.replace(icon, '').trim(), color: dot ? (dot.style.background || '#888') : '#888' };
    });
    return { meta: clone(typeof META !== 'undefined' ? META : { title: document.title }), days: clone(DAYS), pois: clone(POIs), legend };
  }

  function boot() {
    data = reconstruct();
    const css = document.createElement('style');
    css.textContent = `
      #lmEdFab{position:fixed;right:16px;bottom:132px;z-index:9998;display:inline-flex;align-items:center;gap:7px;
        padding:11px 16px;border:none;border-radius:24px;cursor:pointer;font-size:14px;font-weight:800;color:#fff;
        background:linear-gradient(135deg,#2c8a6b,#176b4f);box-shadow:0 6px 18px rgba(23,107,79,.4)}
      #lmEdDrawer{position:fixed;top:0;right:0;width:380px;max-width:92vw;height:100%;z-index:10005;background:#fbfaf6;
        box-shadow:-6px 0 30px rgba(0,0,0,.25);transform:translateX(100%);transition:transform .25s;display:flex;flex-direction:column}
      #lmEdDrawer.show{transform:none}
      .lmed-h{padding:14px 16px;background:#176b4f;color:#fff;font-weight:800;display:flex;justify-content:space-between;align-items:center}
      .lmed-h button{background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:8px;padding:5px 10px;cursor:pointer;font-weight:700}
      .lmed-body{flex:1;overflow:auto;padding:14px 16px}
      .lmed-sec{font-size:12px;font-weight:800;color:#176b4f;margin:14px 0 8px;letter-spacing:1px}
      .lmed-f{margin-bottom:8px}
      .lmed-f label{display:block;font-size:11px;color:#6a7a70;margin-bottom:3px;font-weight:700}
      .lmed-f input,.lmed-f textarea,.lmed-f select{width:100%;box-sizing:border-box;padding:7px 9px;border:1px solid #d8ddd4;border-radius:7px;font-size:13px;font-family:inherit}
      .lmed-poi{border:1px solid #e2e6df;border-radius:10px;margin-bottom:9px;background:#fff;overflow:hidden}
      .lmed-poi>summary{padding:9px 12px;cursor:pointer;font-weight:700;font-size:13px;list-style:none;display:flex;justify-content:space-between;align-items:center}
      .lmed-poi>summary::-webkit-details-marker{display:none}
      .lmed-poi .in{padding:10px 12px;border-top:1px solid #eee}
      .lmed-row{display:flex;gap:8px}.lmed-row>*{flex:1}
      .lmed-del{background:#fbe9e7;color:#c1440e;border:none;border-radius:7px;padding:6px 10px;cursor:pointer;font-weight:700;font-size:12px}
      .lmed-foot{padding:12px 16px;border-top:1px solid #e2e6df;display:flex;gap:8px;background:#fff}
      .lmed-foot button{flex:1;padding:11px;border:none;border-radius:9px;font-weight:800;cursor:pointer;font-size:14px}
      .lmed-add{background:#eef6ff;color:#1f6fd0}.lmed-save{background:linear-gradient(135deg,#2c8a6b,#176b4f);color:#fff}
      .lmed-hint2{position:fixed;top:54px;left:50%;transform:translateX(-50%);z-index:10006;padding:9px 18px;border-radius:20px;background:rgba(20,24,20,.9);color:#fff;font-size:13px;font-weight:700}
    `;
    document.head.appendChild(css);

    const fab = document.createElement('button');
    fab.id = 'lmEdFab'; fab.innerHTML = '✏️ 编辑地图';
    fab.onclick = () => drawer.classList.toggle('show');
    document.body.appendChild(fab);

    const drawer = document.createElement('div');
    drawer.id = 'lmEdDrawer';
    document.body.appendChild(drawer);
    render();

    async function geocode(q) {
      if (!q) return [];
      try {
        const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=6&accept-language=zh&q=' + encodeURIComponent(q));
        return r.ok ? await r.json() : [];
      } catch (e) { return []; }
    }
    async function translateZhEn(q) {
      try { const r = await fetch('https://api.mymemory.translated.net/get?langpair=zh|en&q=' + encodeURIComponent(q)); const d = await r.json(); const t = d && d.responseData && d.responseData.translatedText; return (t && t.trim()) ? t.trim() : ''; }
      catch (e) { return ''; }
    }
    async function smartGeo(q) {
      let hits = await geocode(q), note = '';
      if (!hits.length && /[一-鿿]/.test(q)) {
        const en = await translateZhEn(q);
        if (en) { const h2 = await geocode(en); if (h2.length) { hits = h2; note = '已按英文「' + en + '」搜索'; } }
      }
      return { hits, note };
    }
    function addPOI(lat, lng, name) {
      const day = 1, num = data.pois.filter(x => x.day === day).length + 1;
      data.pois.push({ id: 'p' + Date.now(), day, num, name: name || '新景点', name_cn: name || '新景点', en: '', lat: +(+lat).toFixed(5), lng: +(+lng).toFixed(5), icon: '📍', color: (data.days[day] || {}).color || '#888', desc: '', tags: [], time: '' });
      dirty = true; render(); drawer.classList.add('show');
      try { map.setView([lat, lng], Math.max(map.getZoom(), 10)); } catch (e) {}
    }
    function buildSearch() {
      const wrap = document.createElement('div');
      const sec = document.createElement('div'); sec.className = 'lmed-sec'; sec.textContent = '🔍 搜景点自动加点'; wrap.appendChild(sec);
      const row = document.createElement('div'); row.className = 'lmed-row';
      const inp = document.createElement('input'); inp.placeholder = '景点名，如 都江堰 / Eiffel Tower';
      const btn = document.createElement('button'); btn.textContent = '搜索'; btn.className = 'lmed-add'; btn.style.cssText = 'flex:0 0 64px;border-radius:7px;padding:7px';
      row.appendChild(inp); row.appendChild(btn); wrap.appendChild(row);
      const res = document.createElement('div'); res.style.cssText = 'margin-top:6px'; wrap.appendChild(res);
      const run = async () => {
        const q = inp.value.trim(); if (!q) return;
        res.innerHTML = '<div style="font-size:12px;color:#9aa;padding:4px">搜索中…（中文自动翻译后再查）</div>';
        const { hits, note } = await smartGeo(q);
        if (!hits.length) { res.innerHTML = '<div style="font-size:12px;color:#c1440e;padding:4px">没找到 · 海外景点用英文官方名（如 Universal Studios Florida）</div>'; return; }
        res.innerHTML = note ? '<div style="font-size:11px;color:#8a948c;padding:0 0 4px">' + note + '</div>' : '';
        hits.forEach(h => {
          const it = document.createElement('div');
          it.style.cssText = 'padding:7px 9px;border:1px solid #e2e6df;border-radius:7px;margin-bottom:5px;cursor:pointer;font-size:12px;background:#fff';
          it.innerHTML = `<b>📍 ${q}</b><br><span style="color:#8a948c">${(h.display_name || '').slice(0, 50)}</span>`;
          it.onclick = () => addPOI(h.lat, h.lon, q);
          res.appendChild(it);
        });
      };
      btn.onclick = run;
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') run(); });
      return wrap;
    }

    function field(label, val, oninput, type, opts) {
      const f = document.createElement('div'); f.className = 'lmed-f';
      f.innerHTML = `<label>${label}</label>`;
      let el;
      if (type === 'textarea') { el = document.createElement('textarea'); el.rows = 2; }
      else if (type === 'select') { el = document.createElement('select'); (opts || []).forEach(o => { const op = document.createElement('option'); op.value = o; op.textContent = o; el.appendChild(op); }); }
      else { el = document.createElement('input'); if (type) el.type = type; }
      el.value = val == null ? '' : val;
      el.addEventListener('input', () => { oninput(el.value); dirty = true; });
      f.appendChild(el); return f;
    }

    function render() {
      drawer.innerHTML = '';
      const h = document.createElement('div'); h.className = 'lmed-h';
      h.innerHTML = `<span>✏️ 编辑地图</span>`;
      const x = document.createElement('button'); x.textContent = '收起'; x.onclick = () => drawer.classList.remove('show'); h.appendChild(x);
      drawer.appendChild(h);

      const body = document.createElement('div'); body.className = 'lmed-body';
      body.appendChild(buildSearch());
      // 行程信息
      const s1 = document.createElement('div'); s1.className = 'lmed-sec'; s1.textContent = '行程信息'; body.appendChild(s1);
      body.appendChild(field('标题', data.meta.title, v => data.meta.title = v));
      body.appendChild(field('副标题', data.meta.subtitle, v => data.meta.subtitle = v));
      // 每日主题
      const s2 = document.createElement('div'); s2.className = 'lmed-sec'; s2.textContent = '每日主题'; body.appendChild(s2);
      Object.keys(data.days).sort((a, b) => a - b).forEach(d => {
        const row = document.createElement('div'); row.className = 'lmed-row';
        row.appendChild(field('Day ' + d + ' 标题', data.days[d].title, v => data.days[d].title = v));
        const c = field('色', data.days[d].color, v => data.days[d].color = v, 'color'); c.style.flex = '0 0 56px'; row.appendChild(c);
        body.appendChild(row);
      });
      // POI 列表
      const s3 = document.createElement('div'); s3.className = 'lmed-sec'; s3.textContent = `景点 POI（${data.pois.length}）`; body.appendChild(s3);
      data.pois.slice().sort((a, b) => a.day === b.day ? a.num - b.num : a.day - b.day).forEach(p => body.appendChild(poiCard(p)));
      drawer.appendChild(body);

      const foot = document.createElement('div'); foot.className = 'lmed-foot';
      const add = document.createElement('button'); add.className = 'lmed-add'; add.textContent = '➕ 加点'; add.onclick = startAdd;
      const save = document.createElement('button'); save.className = 'lmed-save'; save.textContent = '💾 保存到地图'; save.onclick = doSave;
      foot.appendChild(add); foot.appendChild(save); drawer.appendChild(foot);
    }

    function poiCard(p) {
      const d = document.createElement('details'); d.className = 'lmed-poi';
      const sm = document.createElement('summary');
      sm.innerHTML = `<span>${p.icon || '📍'} ${p.name_cn || p.name || '未命名'}</span><span style="color:#9aa;font-size:11px">D${p.day}·${p.num}</span>`;
      d.appendChild(sm);
      const inn = document.createElement('div'); inn.className = 'in';
      inn.appendChild(field('名字', p.name_cn || p.name, v => { p.name = v; p.name_cn = v; sm.querySelector('span').textContent = `${p.icon || '📍'} ${v}`; }));
      const r1 = document.createElement('div'); r1.className = 'lmed-row';
      r1.appendChild(field('第几天', String(p.day), v => p.day = +v || 1, 'number'));
      r1.appendChild(field('当天顺序', String(p.num), v => p.num = +v || 1, 'number'));
      r1.appendChild(field('图标', p.icon, v => p.icon = v));
      inn.appendChild(r1);
      const r2 = document.createElement('div'); r2.className = 'lmed-row';
      r2.appendChild(field('时间', p.time, v => p.time = v));
      r2.appendChild(field('标签(逗号)', (p.tags || []).join(','), v => p.tags = v.split(/[,，]/).map(s => s.trim()).filter(Boolean)));
      inn.appendChild(r2);
      inn.appendChild(field('简介', p.desc, v => p.desc = v, 'textarea'));
      const r3 = document.createElement('div'); r3.className = 'lmed-row';
      r3.appendChild(field('纬度', p.lat, v => p.lat = parseFloat(v), 'number'));
      r3.appendChild(field('经度', p.lng, v => p.lng = parseFloat(v), 'number'));
      inn.appendChild(r3);
      const btns = document.createElement('div'); btns.className = 'lmed-row'; btns.style.marginTop = '4px';
      const loc = document.createElement('button'); loc.className = 'lmed-add'; loc.style.cssText = 'border-radius:7px;padding:6px'; loc.textContent = '🔍 按名定位';
      loc.onclick = async () => {
        loc.textContent = '定位中…';
        const hits = await geocode(p.name_cn || p.name);
        if (hits[0]) { p.lat = +(+hits[0].lat).toFixed(5); p.lng = +(+hits[0].lon).toFixed(5); dirty = true; try { map.setView([p.lat, p.lng], Math.max(map.getZoom(), 10)); } catch (e) {} render(); }
        else { loc.textContent = '✗ 没找到'; setTimeout(() => loc.textContent = '🔍 按名定位', 1500); }
      };
      const del = document.createElement('button'); del.className = 'lmed-del'; del.textContent = '删除此点';
      del.onclick = () => { data.pois = data.pois.filter(x => x !== p); dirty = true; render(); };
      btns.appendChild(loc); btns.appendChild(del); inn.appendChild(btns); d.appendChild(inn);
      return d;
    }

    let hint = null;
    function startAdd() {
      addMode = true; drawer.classList.remove('show');
      document.getElementById('map').style.cursor = 'crosshair';
      hint = document.createElement('div'); hint.className = 'lmed-hint2'; hint.textContent = '点击地图放置新景点'; document.body.appendChild(hint);
    }
    map.on('click', e => {
      if (!addMode) return;
      addMode = false; document.getElementById('map').style.cursor = ''; if (hint) { hint.remove(); hint = null; }
      addPOI(e.latlng.lat, e.latlng.lng, '新景点');
    });

    function doSave(ev) {
      const btn = ev.target; const old = btn.textContent; btn.textContent = '保存中…'; btn.disabled = true;
      fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: FILE, data }) })
        .then(r => r.json()).then(j => {
          if (j.success) { btn.textContent = '✓ 已保存，刷新中'; setTimeout(() => location.reload(), 500); }
          else { alert('保存失败：' + (j.error || '未知')); btn.textContent = old; btn.disabled = false; }
        }).catch(e => { alert('保存失败：' + e.message); btn.textContent = old; btn.disabled = false; });
    }
  }
})();

# Itinera · 换机继续开发指南

旅行地图项目：把目的地 → POI → 渲染成单文件交互式 Leaflet HTML 地图，静态部署到 GitHub Pages。

## 0. 最快的方式（推荐）：直接 clone
代码已在 GitHub，新电脑上：
```bash
git clone https://github.com/zxz19951104/livemap.git
cd livemap
```
（本 zip 包已含 `.git`，解压后同样能 `git pull` / `git push`，无需重新 clone。）

## 1. 环境依赖
- **Python 3.9+**：`pip install openai`
- **Node 18+**（仅 QA/海报工具用）：
  ```bash
  npm install playwright
  npx playwright install chromium
  ```

## 2. 配置密钥（必须，未随包提供）
复制模板并填入你的火山引擎 key：
```bash
cp generator/.env.example generator/.env
# 编辑 generator/.env，填 VOLC_API_KEY
```
> 旧电脑上的 `generator/.env` 也可直接拷过来。**切勿提交到 git**（已在 .gitignore）。

## 3. 本地预览
```bash
cd generator && python3 build_static.py --out ../dist   # 构建静态站到 dist/
cd ../dist && python3 -m http.server 8000               # 浏览器开 http://localhost:8000
```
> 注意：编辑 `maps/*.html`、`generator/template.html`、`assets/*` 后，**必须重新 build** 才会反映到 `dist/`（dist 是 gitignored，CI 会在 push 后自动重建并部署）。

## 4. 生成新地图 / 明信片（花 token）
```bash
cd generator
# 新地图（示例：拉森 3 天，SJC 往返）
python3 generate.py "拉森火山国家公园" 3 --pref "从 SJC 机场出发自驾往返" --slug lassen_volcanic
# 给某地点生成 AI 卡通明信片底图
python3 gen_postcard.py "Yellowstone National Park" ../assets/postcards/yellowstone_5d.png
# 批量补全所有地图明信片（变体复用，幂等）
python3 gen_all_postcards.py
# 给地图回填中文名 name_cn / 汉化日主题（幂等）
python3 add_name_cn.py --all
```

## 5. QA（改完地图 UI 必跑 —— 见 ~/.claude/skills/itinera-qa）
从仓库根目录运行（ESM 依赖相对路径）：
```bash
node tools/audit_maps.mjs    # 真实渲染审计：验收标准 重叠=0 超界=0 错误=0
node tools/shot_maps.mjs '[["yellowstone_5d.html","all"]]'  # 用户视角截图复核 → /tmp/livemap_qa/
node tools/test_poster.mjs   # 海报功能 E2E
```

## 6. 关键文件地图
| 路径 | 作用 |
|---|---|
| `generator/template.html` | 地图模板（占位符），新地图由它渲染 |
| `maps/*.html` | 30 张成品单文件地图（源） |
| `generator/generate.py` | 目的地 → POI JSON → HTML |
| `generator/build_static.py` | 打包 dist/（拷 maps + assets + 注入 Hub 列表） |
| `assets/postcards/*.png` | 每张图的 AI 卡通明信片底（海报背景） |
| `assets/lm_checkin.js` | 打卡 checklist + 自定义点（localStorage） |
| `index.html` | Hub 落地页（自助生成 + 地图卡片） |
| `PROJECT_STATE.md` / `PRD_Itinera.md` / `DEPLOY.md` | 项目状态 / 需求 / 部署 |

## 7. 部署
push 到 `main` → GitHub Actions 自动 build dist 并发布 GitHub Pages。
线上：https://shixiann25.github.io/itinera/

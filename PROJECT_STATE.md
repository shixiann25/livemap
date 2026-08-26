# LiveMap · 项目状态快照

> 给 Claude Code `/clear` 之后快速恢复上下文用。每次重大改动后更新本文件。
> 上次更新：2026-08-23

---

## 一句话

「目的地 + 天数 + 偏好」→ 一个可交互的**单文件 HTML 旅行地图**（~110 KB，离线可看，微信能发）。
产品动机和指标见 [PRD_LiveMap.md](PRD_LiveMap.md)，对外介绍见 [README.md](README.md)。

## 当前规模

- **32 张成品地图 / 560+ POI**，覆盖美国国家公园、日本、韩国、泰国、西班牙、九寨沟
- 四种出行模式：标准 / J 人精算 / P 人随性 / 中产舒适 / 穷游省钱
- 线上两个入口：
  - **只读镜像**（秒开）https://shixiann25.github.io/livemap/ —— GitHub Pages，CI 自动发布
  - **完整版**（可在线生成）https://livemap-b1im.onrender.com/ —— Render 免费档，闲置会休眠，
    冷启动首次访问要等 50 秒以上
- 模型：`doubao-seed-2-1-pro-260628`（火山方舟）。**实测约每个景点 15 秒**：
  1 天 4 个点 60s，5 天 20 个点 3 分 24 秒。所以生成走流式，超时 600s

## 关键路径

```
~/livemap/
├── index.html                Hub 落地页（输入框 + 画廊）
├── maps/*.html               32 张成品（自包含单文件）
├── generator/
│   ├── template.html         地图模板（占位符）
│   ├── generate.py           目的地 → LLM → POI JSON → HTML
│   ├── build_static.py       打包 dist/：注入画廊列表 + OG 分享卡标签
│   ├── patch_maps.py         给 32 张成品批量回填模板改动（幂等，CI 会 --check）
│   ├── mapmeta.py            从成品 HTML 反解元信息（标题/emoji/标签/天数/POI 数）
│   ├── server.py             本地 & Render 后端：/api/generate /api/list /api/save
│   ├── gen_postcard.py       单张 AI 明信片
│   ├── gen_all_postcards.py  批量补齐明信片（幂等）
│   └── .env                  VOLC_API_KEY（gitignored，未随仓库提供）
├── assets/
│   ├── postcards/*.png       每图一张 AI 明信片（页头底图 / 卡片配图 / 海报底）
│   ├── og/*.jpg              每图一张社交分享卡 1200×630（+ _site.jpg 站点卡）
│   ├── lm_checkin.js         打卡 checklist + 自定义点（localStorage）
│   └── lm_editor.js          可视化编辑器（仅后端在线时挂载）
├── tools/*.mjs               Playwright：渲染审计 / 截图 / 海报 E2E / 分享卡 / README 图
└── docs/img/*.jpg            README 用产品截图
```

## 常用命令

```bash
# 构建 + 本地预览
python3 generator/build_static.py --out dist
python3 -m http.server 8000 --directory dist

# 生成新地图（花 token）
python3 generator/generate.py "巴黎" 5 --pref 美食 --slug paris
python3 generator/gen_postcard.py "Paris" assets/postcards/paris_5d.png
node tools/gen_og_cards.mjs          # 幂等，只补缺的；--force 全量重画

# 在线生成（需 generator/.env 里的 VOLC_API_KEY）
python3 generator/server.py          # http://localhost:5005

# QA（改完地图 UI 必跑）
python3 generator/patch_maps.py --check
node tools/audit_maps.mjs            # 验收：重叠 0 · 超界 0 · 错误 0
node tools/test_poster.mjs
```

## 架构上的两条硬约束

**1. 地图是「生成的产物」，不是「运行的应用」。**
纯 vanilla JS + Leaflet，没有框架、没有构建产物、没有运行时数据请求。因为产物必须能双击打开、能微信发、断网能看。任何「加个框架就好了」的想法都会破坏这条。

**2. 成品是单文件副本，模板改动不会自动流下去。**
改了 `generator/template.html` 里的运行时逻辑，32 张成品**不会跟着变**。必须在 `generator/patch_maps.py` 里登记一条补丁（旧写法 → 新写法 + 幂等 marker），然后跑一遍回填。CI 的 `--check` 会拦住忘了回填的 PR。

## 踩过的坑（别再踩）

**❌ 不要用 MutationObserver 监听 body 子树**——会和 Day Tab 切换的 innerHTML 重渲染产生竞态，历史上 L、M、P 三次升级都栽在这。要改行为就 regex patch 源码，或 `const _orig = showDetail; window.showDetail = ...`。

**❌ 不要对带 query 的外部 URL 直接判扩展名**——Wikimedia 给缩略图挂了 `?utm_source=…`，`/\.(jpg)$/` 于是全军覆没，32 张图的四宫格静默回退 emoji 且不报错。判之前先 `split(/[?#]/)[0]`。

**❌ 不要拿市场话术当搜索词**——维基是全文搜索，永远有结果但不保证对。`"Classical Budget Tour in Kyoto"` 搜出 Taiwan，`"SOUTHWEST"` 搜出陶器条目，页头一度挂着人像照。现在：本地明信片优先 → 搜索词只用具体地名 → 命中标题必须和查询词共享实词。

**❌ 不要在老三张手写地图里假设 `META` 存在**——`big_island_7d` / `kyoto_6d` / `yellowstone_5d` 没有 `const META`，直接写 `META.eyebrow` 会抛 ReferenceError，把整个 `initHeroBg` 连带兜底逻辑一起干掉。写 `typeof META !== 'undefined' &&`。

**❌ 别把豆包模型 ID 当常量**——豆包模型名带日期后缀（`doubao-seed-2-1-pro-260628`），旧版本会静悄悄下架。`doubao-1-5-pro-32k-250115` 就是这么没的，配置不改就一直报「模型不存在」，看起来像 key 错了。`call_volcengine` 已带候选回退链，换代时把新 ID 放 `VOLC_MODEL_FALLBACKS` 首位即可。

**❌ 顶层 `const` 别被更早执行的函数引用**——`loadCardScenery()` 在 `const _tryImg` 声明之前就被 `renderGallery()` 调到，撞 TDZ。用 `function` 声明。

## 发布 skill / plugin

同一个 `skill/livemap/` 目录同时是 **skill 目录**和 **plugin 目录**（SKILL.md 在根，
按官方规则会作为单个 skill 加载），所以只维护一份。

- 仓库根 `.claude-plugin/marketplace.json` 让别人能 `/plugin marketplace add shixiann25/livemap`
- `skill/livemap/.claude-plugin/plugin.json` 是插件清单

**改完模板要做三件事**，否则别人装到的还是旧版：

```bash
python3 skill/build_skill.py            # 重建 skill 包
claude plugin validate skill/livemap    # 校验插件清单
claude plugin validate .                # 校验 marketplace
# 版本号变了就同步改 plugin.json 和 marketplace.json 里的 version（claude plugin tag 会校验两者一致）
cd skill && zip -rq /tmp/livemap-skill.zip livemap
gh release create skill-vX.Y /tmp/livemap-skill.zip --repo shixiann25/livemap --notes "..."
```

⚠️ **别信文档信校验器**：官方文档里写的 `displayName`（plugin）和根级 `description`
（marketplace）实际会被 `claude plugin validate` 拒掉；marketplace 的描述要放在
`metadata.description` 下。

## 待办

**上线可用**
- [x] Render 常驻后端已上线，首页生成按钮真的能用了
- [ ] 新生成的地图没有 AI 明信片（`assets/postcards/<slug>.png` 不存在），页头会回退到维基搜图，
      质量不稳定。要么让 server.py 生成后异步补一张（约 ¥0.2），要么无明信片时干脆只用主题渐变
- [ ] Render 免费档磁盘临时：访客生成的图重启即丢
- [x] 公网防刷：每日额度（全站 40 / 单 IP 5，命中存量不占额度）+ 公网关闭匿名编辑保存
- [x] 缺 key 时降级成只读模式而不是整站起不来
- [x] 豆包模型 ID 换代到 `doubao-seed-2-1-pro-260628` + 候选回退链

**分享增长**
- [x] 每张地图的 OG / Twitter 分享卡（`assets/og/`，构建期注入 `dist/`）
- [ ] 短链 + 生成结果持久化（对象存储），跑通 PRD 的完整分享回路

**工程质量**
- [x] `audit_maps.mjs` 非 0 退出 + 慢机器复测，可当 CI 质量门
- [x] `patch_maps.py --check` 拦住「模板改了但成品没回填」
- [ ] 审计范围扩到移动端视口
- [ ] 单图瘦身到 100 KB 以内（现 98–120 KB）

**产品**
- [ ] 「独门绝技」条目可点击 → 跳对应 POI 详情 / 展开深度介绍

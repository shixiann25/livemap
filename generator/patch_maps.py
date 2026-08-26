#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「已生成的单文件地图」批量打补丁。

为什么需要这个东西
------------------
每张 maps/*.html 都是自包含的单文件产物（这是产品卖点：能 AirDrop、能离线看），
代价是模板里修的 bug 不会自动流到已生成的 32 张图上。所以每次改模板的运行时逻辑，
都要同时把同一处改动回填到全部成品。这个脚本就是干这件事的登记处。

约定
----
每条补丁声明 name / why / olds（可能的旧写法，老三张手写图常常只是换了行或转义不同）
/ new / marker（打过之后一定存在的字符串，用来保证幂等）。

用法
----
    python3 generator/patch_maps.py            # 打全部未打的补丁
    python3 generator/patch_maps.py --check    # 只报告，不写文件（CI 用，未打完返回 1）
    python3 generator/patch_maps.py --only wikimedia-thumb-query
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- 补丁 1
# Wikimedia 给缩略图 URL 挂了 ?utm_source=…&utm_campaign=parser，
# isGoodImage 用 /\.(jpg|jpeg|png)$/ 判扩展名 → 一张都过不了 → POI 4 宫格全站回退 emoji。
IMG_OLDS = [
    ("function isGoodImage(url) { return url && /\\.(jpg|jpeg|png)$/i.test(url) "
     "&& !/logo|icon|seal|coat[_-]of[_-]arms|svg|flag|map|chart/i.test(url); }"),
    ("function isGoodImage(url) {\n"
     "  return url && /\\.(jpg|jpeg|png)$/i.test(url)\n"
     "    && !/logo|icon|seal|coat[_-]of[_-]arms|svg|flag|map|chart/i.test(url);\n"
     "}"),
]
IMG_NEW = (
    "function isGoodImage(url) {\n"
    "  if (!url) return false;\n"
    "  // Wikimedia 会给缩略图挂 ?utm_source=…&utm_campaign=parser，\n"
    "  // 直接对整个 URL 判 /\\.(jpg)$/ 会全军覆没，所以先切掉 query/hash。\n"
    "  const path = String(url).split(/[?#]/)[0];\n"
    "  return /\\.(jpg|jpeg|png)$/i.test(path)\n"
    "    && !/logo|icon|seal|coat[_-]of[_-]arms|svg|flag|map|chart/i.test(path);\n"
    "}"
)

# ---------------------------------------------------------------- 补丁 2
# 页头大图用 META.subtitle 当搜索词，而 subtitle 是市场话术
# （"Classical Budget Tour in Kyoto"），维基搜出来的第一条能是「Taiwan」。
# 改成只用具体地名：国家公园 → eyebrow 里的目的地 → 前几个 POI 的英文名。
_HERO_OLD_TMPL = (
    "    const queries = [];\n"
    "    const np = POIs.find(p => /national park/i.test(p.en || '') || /国家公园/.test(p.name || ''));\n"
    "    if (np) queries.push((np.en || np.search) + ' landscape');\n"
    "    (META.subtitle || '').split(/[{sep}]/).map(s => s.trim())"
    ".filter(s => s && !/livemap|\\d{{4}}/i.test(s)).forEach(s => queries.push(s + ' landscape'));\n"
    "    if (POIs[0]) queries.push((POIs[0].search || POIs[0].en || POIs[0].name) + ' landscape');"
)
HERO_OLDS = [
    _HERO_OLD_TMPL.format(sep="·•・|"),
    _HERO_OLD_TMPL.format(sep="\\u00b7\\u2022\\u30fb|"),
]
# 注意 typeof META：老三张手写地图根本没有 META 常量，
# 直接写 META.eyebrow 会抛 ReferenceError，把整个 initHeroBg（连同明信片兜底）一起带走。
_HERO_BODY = (
    "    const queries = [];\n"
    "    const np = POIs.find(p => /national park/i.test(p.en || '') || /国家公园/.test(p.name || ''));\n"
    "    if (np) queries.push((np.en || np.search) + ' landscape');\n"
    "    const place = {place_expr}.split(/[·•・|]/)[0].trim();\n"
    "    if (/^[\\x20-\\x7e]+$/.test(place) && !/livemap|\\d{{4}}/i.test(place)) "
    "queries.push(place + ' landscape');\n"
    "    POIs.slice(0, 3).forEach(p => {{ const n = p.search || p.en; if (n) queries.push(n + ' landscape'); }});"
)
_HERO_HEAD = (
    "    // 页头大图的搜索词只用「具体地名」。\n"
    "    // 别拿 META.subtitle：那是市场话术（如 'Classical Budget Tour in Kyoto'），\n"
    "    // 维基全文搜第一条可能是完全无关的条目（真实案例：搜出了 Taiwan）。\n"
)
# 上一版漏了 typeof 守卫，已经打进过文件里，所以它也算「旧写法」，要能被再次升级。
HERO_PLACE_UNGUARDED = "(META.eyebrow || '')"
HERO_PLACE_GUARDED = "String((typeof META !== 'undefined' && META.eyebrow) || '')"
HERO_OLDS.append(_HERO_HEAD + _HERO_BODY.format(place_expr=HERO_PLACE_UNGUARDED))
HERO_NEW = _HERO_HEAD + _HERO_BODY.format(place_expr=HERO_PLACE_GUARDED)

# ---------------------------------------------------------------- 补丁 3
# media-list 是「文章里出现的所有图，按出现顺序」，第一张常常是地图/示意图/岩画之类，
# 而条目主图（leadImage）才是那张标准风景照。排序时把它顶到最前，
# 页头大图和 POI 四宫格的第一格质量立刻不一样。
LEAD_OLD = (
    "    const urls = [];\n"
    "    for (const item of (md.items || [])) {\n"
    "      if (item.type !== 'image') continue;"
)
LEAD_NEW = (
    "    const urls = [];\n"
    "    // media-list 按图片在文章里出现的顺序返回，头几张常是地图/示意图；\n"
    "    // 条目主图 leadImage 才是那张标准风景照，先把它顶上来。\n"
    "    const mediaItems = (md.items || []).filter(i => i.type === 'image')\n"
    "      .sort((a, b) => (b.leadImage === true) - (a.leadImage === true));\n"
    "    for (const item of mediaItems) {"
)

# ---------------------------------------------------------------- 补丁 4
# 维基是全文搜索：词不沾边也一定会还你一个「最相关」条目。
# 真实案例：'SOUTHWEST landscape' → 一篇讲陶器的条目；
#          'Classical Budget Tour in Kyoto landscape' → Taiwan。
# 于是页头挂着一张跟目的地毫无关系的图。加一道实词重合校验，宁可不出图也别出错图。
RELEVANCE_OLD = (
    "    const title = sd.query?.search?.[0]?.title;\n"
    "    if (!title) return [];"
)
RELEVANCE_NEW = (
    "    const title = sd.query?.search?.[0]?.title;\n"
    "    if (!title) return [];\n"
    "    // 维基是全文搜索，词不沾边也会还你一个「最相关」条目\n"
    "    // （真实案例：'SOUTHWEST landscape' → 一篇陶器条目；'…Tour in Kyoto' → Taiwan）。\n"
    "    // 命中标题至少要和查询词共享一个实词，否则宁可不出图，也别出错图。\n"
    "    const _kw = (s) => (String(s).toLowerCase().match(/[a-z]{3,}/g) || [])\n"
    "      .filter(w => !['landscape', 'the', 'and', 'national', 'park', 'city'].includes(w));\n"
    "    const _q = _kw(query), _t = new Set(_kw(title));\n"
    "    if (_q.length && !_q.some(w => _t.has(w))) return [];   // 中文查询 _q 为空，跳过校验"
)

# ---------------------------------------------------------------- 补丁 5
# 页头大图别再抽维基彩票了。每张地图都已经有一张专门为它画的 AI 明信片
# （assets/postcards/<slug>.png，海报功能在用），它一定切题、一定好看、不依赖搜索命中。
# 维基那条路降级成兜底：只有明信片缺失时才走。
# 抽彩票的真实后果：西南环线页头挂过一张 Sheldon Adelson 的人像，巴塞罗那挂过 Walter Wild。
POSTCARD_OLD = (
    "    (async () => {\n"
    "      for (const q of queries) {\n"
    "        if (!q) continue;"
)
POSTCARD_NEW = (
    "    (async () => {\n"
    "      // 先用这张图自己的 AI 明信片当页头底图：一定切题，不看搜索脸色。\n"
    "      // 维基搜图留作兜底——它会把 'SOUTHWEST' 搜成陶器、把人像当风景。\n"
    "      const slug = (location.pathname.split('/').pop() || '').replace(/\\.html$/, '');\n"
    "      if (slug) {\n"
    "        const local = '../assets/postcards/' + slug + '.png';\n"
    "        const ok = await new Promise(res => {\n"
    "          const im = new Image();\n"
    "          im.onload = () => res(true); im.onerror = () => res(false); im.src = local;\n"
    "        });\n"
    "        if (ok) {\n"
    "          hero.style.backgroundImage = 'url(\"' + local + '\")';\n"
    "          hero.style.backgroundPosition = 'center 26%';   // 明信片是竖版，主体偏上\n"
    "          header.classList.add('has-hero');\n"
    "          return;\n"
    "        }\n"
    "      }\n"
    "      for (const q of queries) {\n"
    "        if (!q) continue;"
)


# ---------------------------------------------------------------- 补丁 6
# renderFoods 用「手写 emoji 白名单 + 没有 /u 标志」的正则剥条目开头的 emoji。
# emoji 是代理对，没有 /u 时字符类里存的是半个字符；名单里的 🍜🍣🍡… 共享同一个
# 高位代理 D83C，于是任何名单外、但同属 U+1F3xx 段的 emoji（如 🍲）都会被砍掉高位代理，
# 留下一个孤立的低位代理 → encodeURIComponent 抛 URIError。
# 这个异常是在 showDetail 里同步抛的，后面所有渲染全部中断：
# 四宫格永远停在「搜索中」，美食、导航按钮一个都不出来。
# renderPhotoSpots 的 slice(0, 25) 同理会把 emoji 劈成两半。
#
# 两处一起修：用 \p{Extended_Pictographic} + /u 认整个 emoji，
# 再给拼出来的搜索串加一道去落单代理的兜底。
# 锚点用函数定义本身，不要带上面那行注释——老三张和几张早期图的注释文案不同，
# 带上注释会漏掉它们，而 safeQuery 的调用点又是全量打的，会留下「调用了未定义函数」的坏状态。
# 锚点必须选「前面不可能有修饰符、且 33 个文件里写法完全一致」的顶层语句。
# 教训：先前锚在 `function renderPhotoSpots(poi) {` 上，而 9 张老图写的是
# `async function renderPhotoSpots(poi) {`——子串匹配把 async 和它的函数劈开了，
# async 跑去修饰新插入的 safeQuery，原函数里的 await 变非法，整个脚本解析失败。
SURROGATE_OLDS = ["const imgCache = {};"]
SURROGATE_NEW = "const imgCache = {};\n\n// 拼 Google 搜索串前先去掉落单的代理项。\n// 上游任何一次 slice/replace 都可能把一个 emoji 劈成两半，剩下的孤立代理\n// 会让 encodeURIComponent 抛 URIError——而它是在 showDetail 里同步抛的，\n// 整个详情面板会停在半截：四宫格一直转圈、美食和导航按钮都不渲染。\nfunction safeQuery(s) {\n  // [...str] 按码点迭代：合法代理对会作为一个整体出来（码点 > 0xFFFF），\n  // 只有落单的代理才会以单个码元的形式出现，据此筛掉。\n  return [...String(s)].filter(ch => {\n    const c = ch.codePointAt(0);\n    return !(c >= 0xD800 && c <= 0xDFFF);\n  }).join('');\n}"

FOOD_EMOJI_OLDS = [
    "    let name = f.replace(/^[🍡🍜🍣🍵🍢🍰🍦🥩🥪🍤🥩🍷🍕🍺☕🍔🍱🍣🥟🥗🥨🍩🥯🍴🍝🥢🐟🦀🦪🍇🥃🍫🍳🍻🍂🌮🥙🍞🧀🧊🌭🥒🥢🍙🍡🥃]+\\s*/, '').replace(/[（(].*$/, '').trim();",
    "    let name = f.replace(/^[🍡🍜🍣🍵🍢🍰🍦🥩🥪🍤🍷🍕🍺☕🍔🍱🥟🥗🥨🍩🥯🍴🍝🥢🐟🦀🦪🍇🥃🍫🍳🍻🌮🥙🍞🧀🧊🌭🥒🍙]+\\s*/, '').replace(/[（(].*$/, '').trim();",
]
FOOD_EMOJI_NEW = "    // 认整个 emoji：\\p{Extended_Pictographic} + /u。\n    // 手写 emoji 白名单 + 没有 /u 会劈开代理对：名单外但同段的 emoji（如 🍲）\n    // 只被砍掉高位代理，留下孤立低位代理，后面 encodeURIComponent 直接抛 URIError。\n    let name = f.replace(/^(?:\\p{Extended_Pictographic}|\\uFE0F|\\u200D)+\\s*/u, '')\n                .replace(/[（(].*$/, '').trim();"

QUERY_OLDS = ["""    const gImg = `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(q)}`;"""]
QUERY_NEW = """    const gImg = `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(safeQuery(q))}`;"""

FOODQ_OLDS = ["""    const query = `${name} ${cityHint}`.trim();"""]
FOODQ_NEW = """    const query = safeQuery(`${name} ${cityHint}`.trim());"""

PATCHES = [
    {
        "name": "wikimedia-thumb-query",
        "why": "Wikimedia 缩略图带 ?utm_source= 导致 POI 4 宫格全站回退 emoji",
        "olds": IMG_OLDS,
        "new": IMG_NEW,
        "marker": "const path = String(url).split(/[?#]/)[0];",
    },
    {
        "name": "hero-query-place-only",
        "why": "页头大图用 subtitle 当搜索词，搜出无关图片（Kyoto → Taiwan）",
        "olds": HERO_OLDS,
        "new": HERO_NEW,
        "marker": "const place = " + HERO_PLACE_GUARDED,
    },
    {
        "name": "prefer-wiki-lead-image",
        "why": "维基 media-list 首图常是地图/示意图，条目主图 leadImage 才是风景照",
        "olds": [LEAD_OLD],
        "new": LEAD_NEW,
        "marker": "const mediaItems = (md.items || []).filter(i => i.type === 'image')",
    },
    {
        "name": "wiki-title-relevance-guard",
        "why": "维基全文搜索必返回结果，词不沾边也会挂上无关图（SOUTHWEST → 陶器条目）",
        "olds": [RELEVANCE_OLD],
        "new": RELEVANCE_NEW,
        "marker": "if (_q.length && !_q.some(w => _t.has(w))) return [];",
    },
    {
        "name": "hero-use-postcard",
        "why": "页头大图改用本图自带的 AI 明信片，维基搜图降为兜底（曾挂出人像照）",
        "olds": [POSTCARD_OLD],
        "new": POSTCARD_NEW,
        "marker": "const local = '../assets/postcards/' + slug + '.png';",
    },
    {
        "name": "safe-query-helper",
        "why": "拼 Google 搜索串时落单的代理项会让 encodeURIComponent 抛错，打断整个详情面板",
        "olds": SURROGATE_OLDS,
        "new": SURROGATE_NEW,
        "marker": "function safeQuery(s) {",
    },
    {
        "name": "food-emoji-unicode-regex",
        "why": "美食条目开头 emoji 的白名单正则没加 /u，名单外的 emoji（如 🍲）会被劈成半个字符",
        "olds": FOOD_EMOJI_OLDS,
        "new": FOOD_EMOJI_NEW,
        "marker": "|\\uFE0F|\\u200D)+\\s*/u",
    },
    {
        "name": "safe-query-photospots",
        "why": "拍照点的 slice(0,25) 会切断 emoji，搜索串要过 safeQuery",
        "olds": QUERY_OLDS,
        "new": QUERY_NEW,
        "marker": "encodeURIComponent(safeQuery(q))",
    },
    {
        "name": "safe-query-foods",
        "why": "美食搜索串同样要过 safeQuery",
        "olds": FOODQ_OLDS,
        "new": FOODQ_NEW,
        "marker": "const query = safeQuery(",
    },
]


def targets():
    yield ROOT / "generator" / "template.html"
    yield from sorted((ROOT / "maps").glob("*.html"))


def main():
    ap = argparse.ArgumentParser(description="批量给已生成的单文件地图打补丁")
    ap.add_argument("--check", action="store_true", help="只报告，不写文件；有未打的补丁则退出码 1")
    ap.add_argument("--only", help="只跑指定名字的补丁")
    args = ap.parse_args()

    patches = [p for p in PATCHES if not args.only or p["name"] == args.only]
    if args.only and not patches:
        print(f"❌ 没有叫 {args.only} 的补丁，可选：{', '.join(p['name'] for p in PATCHES)}")
        return 2

    files = list(targets())
    pending = 0
    for patch in patches:
        todo, done, miss = [], [], []
        for f in files:
            s = f.read_text(encoding="utf-8")
            if patch["marker"] in s:
                done.append(f)
                continue
            hit = next((o for o in patch["olds"] if o in s), None)
            if hit:
                todo.append(f)
                if not args.check:
                    f.write_text(s.replace(hit, patch["new"]), encoding="utf-8")
            else:
                miss.append(f)

        pending += len(todo) + len(miss)
        verb = "待打" if args.check else "已打"
        icon = "⚠️ " if (args.check and todo) or miss else "✅"
        print(f"{icon} {patch['name']}：{verb} {len(todo)} · 已是新版 {len(done)} · 未匹配 {len(miss)}")
        print(f"     ↳ {patch['why']}")
        for f in miss:
            print(f"     ⚠️  没找到可替换的旧代码：{f.relative_to(ROOT)}")

    if args.check and pending:
        print("\n❌ 有文件没跟上模板改动，跑 `python3 generator/patch_maps.py` 回填")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

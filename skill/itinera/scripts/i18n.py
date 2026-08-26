#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把渲染出来的地图翻译成别的语言。

思路：为什么是「渲染后替换」而不是给模板做 i18n
------------------------------------------------
模板里写死的界面文字有 70 来处，散在 HTML 文本节点、JS 模板字符串、
CSS 类名里。给它做参数化要动 1400 行模板的几十个点，而那份模板同时供
主站的 32 张成品和网页版生成器使用——改坏了波及面很大。

换个角度：**行程数据本来就是用目标语言写的**（Claude 直接用英文写景点名和描述），
所以渲染完之后，文件里剩下的中文一定是界面文字。这让替换范围变成一个封闭集合，
而且有个可验证的收敛条件：翻完之后页面上不该再出现任何中文。
`--verify` 就是查这个。

加一门语言 = 往 LANGS 里加一个 dict，不用碰任何别的代码。
"""
import re
import sys
from pathlib import Path


# 标签词表：英文输出时 tags 用右边这套词。
# 它同时驱动三处：标签胶囊配色（CSS 类名）、缺 duration 时的时长推断、以及可读性。
# 三处必须用同一套词，否则英文图的标签会全变成默认灰色。
TAG_MAP = {
    "必看": "Must-see", "必去": "Must-visit", "地标": "Landmark", "震撼": "Epic",
    "米其林": "Michelin", "美食": "Food", "小吃": "Street food",
    "寺庙": "Temple", "神社": "Shrine", "传统": "Historic", "体验": "Experience",
    "观景": "Viewpoint", "夜景": "Night view", "自然": "Nature", "竹林": "Bamboo",
    "海滩": "Beach", "野生动物": "Wildlife", "火山": "Volcano", "地热": "Geothermal",
    "温泉": "Hot spring", "喷泉": "Geyser", "峡谷": "Canyon", "湖泊": "Lake",
    "瀑布": "Waterfall", "观星": "Stargazing", "夜潜": "Night dive", "浮潜": "Snorkel",
    "徒步": "Hiking", "独家": "Insider", "冒险": "Adventure", "小镇": "Town",
    "亲子": "Family", "免费": "Free", "交通": "Transit",
}

# ---------------------------------------------------------------- 英文
EN_LITERAL = {
    # —— 导航 / 地图控件 ——
    "🗺️ Itinera 首页": "🗺️ Itinera Home",
    "🗺️ 简洁": "🗺️ Clean",
    "🌄 地形": "🌄 Terrain",
    "🛰️ 实景": "🛰️ Satellite",
    "👆 单指滑动浏览页面 · 双指拖动 / 缩放地图":
        "👆 One finger scrolls the page · two fingers pan / zoom the map",

    # —— 景点详情 ——
    "← 返回行程": "← Back to itinerary",
    "上一个 POI (←)": "Previous stop (←)",
    "下一个 POI (→)": "Next stop (→)",
    "💴 门票/价格": "💴 Ticket",
    "⏰ 营业时间": "⏰ Hours",
    "⏱️ 建议游玩": "⏱️ Time needed",
    "建议在此 POI 停留的时间": "How long to budget for this stop",
    "📸 拍照打卡点": "📸 Photo spots",
    "🍜 推荐美食（点击 📍 跳 Google Maps）": "🍜 Where to eat (tap 📍 for Google Maps)",
    "⭐ 米其林 / 高级餐厅": "⭐ Michelin / fine dining",
    "⚠️ 避雷提醒": "⚠️ Watch out for",
    "📍 在 Google Maps 打开导航": "📍 Open in Google Maps",
    "🔍 搜索 4 张图片中...": "🔍 Finding photos…",
    "🔍 Google Images 看更多 →": "🔍 More on Google Images →",
    "🔍 Google 搜攻略": "🔍 Search guides",
    "🖼️ 看图片": "🖼️ Photos",
    "📕 小红书": "📕 Xiaohongshu",
    "📖 百度攻略": "📖 Baidu guides",
    "🔍 搜图": "🔍 Find photo",
    "→ 跳详情": "→ open",

    # —— 单日视图 ——
    "🏨 推荐酒店": "🏨 Where to stay",
    "酒店数据待补充 · 重新生成可获取 AI 推荐":
        "No hotel picked yet — regenerate to get a recommendation",
    "💴 价格": "💴 Price",
    "📍 地址": "📍 Address",
    "🚗 停车": "🚗 Parking",
    "✨ 亮点": "✨ Why here",
    "🌐 官网/直订": "🌐 Book direct",
    "🔗 Booking 搜": "🔗 Find on Booking",
    "🚗 自驾路线": "🚗 Driving route",

    # —— 全程视图 ——
    "✈️ 出行前必看": "✈️ Before you go",
    "🛂 签证": "🛂 Visa",
    "🔌 电压": "🔌 Power",
    "📱 网络": "📱 Data",
    "💴 换汇": "💴 Money",
    "💵 小费": "💵 Tipping",
    "🚨 急救": "🚨 Emergency",
    "⬇️ 导出 GPX（导入 Google My Maps / Garmin / 离线地图）":
        "⬇️ Export GPX (for Google My Maps / Garmin / offline apps)",

    # —— 海报 ——
    "📸 生成行程海报": "📸 Make a shareable poster",
    "⬇️ 下载海报": "⬇️ Download poster",
    "生成中…": "Rendering…",
    "生成失败：": "Failed: ",
    "关闭": "Close",
    "_海报.png": "_poster.png",
    "扫码查看可交互旅行地图": "Scan for the interactive map",
    "旅行地图 · 精准行程": "Itinera · a trip you can see",
    "保存后发小红书/朋友圈 · 扫码可回到这张旅行地图":
        "Save and share — the QR code opens this map",
    "每个点位有图片 · 攻略 · 营业时间 · 路线 — 还能一键生成你自己的行程海报":
        "Every stop has photos, hours, tips and routing — and you can export a poster like this",

    # —— 打卡 / 我的点（lm_checkin.js，构建时已内联）——
    "🎯 已打卡": "🎯 Visited",
    "✅ 已打卡": "✅ Visited",
    "✓ 标记我去过这里": "✓ Mark as visited",
    "✓ 已打卡（点击取消）": "✓ Visited (tap to undo)",
    "➕ 我的点": "➕ My pins",
    "📍 我的点": "📍 My pins",
    "添加我的点": "Add a pin",
    "编辑我的点": "Edit pin",
    "✕ 取消添加": "✕ Cancel",
    "📍 或点地图选位置": "📍 …or tap the map",
    "✓ 已选位置，点保存即可": "✓ Location set — hit Save",
    "点击地图任意位置添加你的点": "Tap anywhere on the map to drop a pin",
    "名字，如『超好吃的拉面店』": "Name, e.g. “that great ramen place”",
    "备注（可选）": "Notes (optional)",
    "🔍 搜地点，如 Universal Studios": "🔍 Search a place, e.g. Universal Studios",
    "搜索中…（中文自动翻译后再查）": "Searching…",
    "没找到 · 海外景点用英文官方名（如 Universal Studios Florida）":
        "Not found — try the official English name (e.g. Universal Studios Florida)",
    "请先搜索地点，或点「📍 或点地图选位置」": "Search for a place first, or tap the map",
    "已按英文「": "Searched in English for “",
    "」搜索": "”",
    "✓ 已定位「": "✓ Found “",
    "」，点保存即可": "” — hit Save",
    "保存": "Save",
    "删除": "Delete",
    "取消": "Cancel",
    "搜": "Search",

    # —— 带 JS 模板变量的串，只能整串匹配 ——
    "全部 ${TOTAL_DAYS} 天": "All ${TOTAL_DAYS} days",
    "返回全部 ${TOTAL_DAYS} 天行程": "Back to all ${TOTAL_DAYS} days",
    "含 ${POIs.length} 个核心景点": "${POIs.length} stops",
    "${pois.length} 个玩点": "${pois.length} stops",
    "甄选": "PICKS",
    "我的点": "My pin",
    "' 攻略'": "' travel guide'",

    # —— 时长默认值 ——
    "半天": "half day",
    "全天": "full day",
    "— 抵达/离港": "— arrival / departure",
    "— 路过/换乘": "— passing through",

    # —— 货币名 ——
    "日元": "JPY", "美元": "USD", "欧元": "EUR", "英镑": "GBP",
    "韩元": "KRW", "泰铢": "THB", "澳元": "AUD", "加元": "CAD", "外币": "local currency",
}

EN_REGEX = [
    (r"全部 (\d+) 天", r"All \1 days"),
    (r"</b> 天</div>", r"</b> days</div>"),
    (r"个精选点", r" stops"),
    (r"(\d+) 个玩点", r"\1 stops"),
    (r"约 ([\d.]+) 小时", r"about \1 h"),
    (r"([\d.]+(?:\s*[-–~]\s*[\d.]+)?) 小时", r"\1 h"),
    (r"([\d]+(?:\s*[-–~]\s*[\d]+)?) 分钟", r"\1 min"),
]

# 结构性改动：不是换词，是换行为
EN_PATCHES = [
    # 英文读者不需要看人民币。原来的显示是「¥117（€15 欧元）」，很别扭。
    ("function renderPriceWithRMB(priceStr, origCurrency) {",
     "function renderPriceWithRMB(priceStr, origCurrency) {\n"
     "  return priceStr;   // 非中文输出：不换算，直接显示作者写的原价"),
    # 上面那行一关，标签里的「[RMB · 含X原价]」就没意义了
    ('<span style="color:#c97b5a;font-weight:800;">[RMB · 含{{CURRENCY_LABEL}}原价]</span>', ""),
    ("价格为人民币（RMB）·括号内为{{CURRENCY_LABEL}}原价", "Ticket price"),
    # 「必看」这类标签的红色高亮是按中文类名匹配的，补上英文别名
    (".tag-必去, .tag-必看, .tag-地标 {",
     ".tag-必去, .tag-必看, .tag-地标, .tag-Must-see, .tag-Must-visit, .tag-Landmark, .tag-Iconic {"),
    ('<html lang="zh-CN">', '<html lang="en">'),
]

# 票价那几处含已被替换掉的货币名（渲染时 {{CURRENCY_LABEL}} 早就变成 EUR 了），
# 所以只能用正则兜
EN_REGEX += [
    (r"价格为人民币（RMB）·括号内为\w+原价", "Ticket price"),
    (r'<span style="color:#c97b5a;font-weight:800;">\[RMB · 含\w+原价\]</span>', ""),
    (r"价格已换算为人民币 · 汇率[^<]*", "Prices as listed by the author"),
]

# 标签配色和时长推断都按中文关键词匹配，英文标签会全部落空。
# 把 CSS 选择器和 tags.includes() 里的中文换成词表里的英文，两边就对上了。
for _zh, _en in TAG_MAP.items():
    EN_PATCHES.append((f".tag-{_zh}", f".tag-{_en.replace(' ', '-')}"))
    EN_PATCHES.append((f"tags.includes('{_zh}')", f"tags.includes('{_en}')"))

LANGS = {
    "en": {"literal": EN_LITERAL, "regex": EN_REGEX, "patches": EN_PATCHES},
}


def translate(html: str, lang: str) -> str:
    if lang in ("zh", "zh-CN", "", None):
        return html
    spec = LANGS.get(lang)
    if not spec:
        sys.exit(f"❌ 还不支持 {lang}。已支持：zh（原生）+ {', '.join(LANGS)}。"
                 f"加一门语言只需往 scripts/i18n.py 的 LANGS 里加一个 dict。")

    for old, new in spec["patches"]:
        html = html.replace(old, new)
    # 长串优先，避免「💴 价格」把「💴 门票/价格」切一半
    for zh_s in sorted(spec["literal"], key=len, reverse=True):
        html = html.replace(zh_s, spec["literal"][zh_s])
    for pat, rep in spec["regex"]:
        html = re.sub(pat, rep, html)
    return html


def leftover_chinese(html: str):
    """翻完之后还剩哪些**用户看得见**的中文。给渲染后的自检用。

    要排掉三类假阳性，否则噪音淹没真问题：
      · <style> 块里的中文其实是类选择器（.tag-必看），页面上看不到
      · /* */ 和 // 注释
      · JS 里用来匹配中文的正则（如 /[一-龥]/）
    前提是数据本身已经是目标语言写的——这样剩下的中文才必然是漏翻的界面文字。
    """
    # 挖空而不是删除：删了会让行号错位，报出来的位置没法直接跳过去看
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    html = re.sub(r"<style[^>]*>.*?</style>", blank, html, flags=re.S)   # 里面的中文是类选择器
    html = re.sub(r"/\*.*?\*/", blank, html, flags=re.S)                 # 块注释
    html = re.sub(r"<!--.*?-->", blank, html, flags=re.S)                # HTML 注释

    out = []
    for i, line in enumerate(html.splitlines(), 1):
        body = re.sub(r"//.*$", "", line)                    # 行注释
        # 含中文的正则字面量（/国家公园/、/(年|月|天)/g 之类）——是匹配用的，不是给人看的
        body = re.sub(r"/(?:[^/\\\n]|\\.)*[一-鿿](?:[^/\\\n]|\\.)*/[gimsuy]*", "", body)
        for m in re.findall(r"[一-鿿]+[^<>\"\'`\n]*", body):
            t = m.strip()
            if t:
                out.append((i, t))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("用法：python3 i18n.py <已渲染的 html> [--verify]")
    p = Path(sys.argv[1])
    rest = leftover_chinese(p.read_text(encoding="utf-8"))
    if "--verify" in sys.argv:
        if rest:
            print(f"⚠️ 还有 {len(rest)} 处中文没翻：")
            for ln, s in rest[:30]:
                print(f"   L{ln}: {s[:70]}")
            sys.exit(1)
        print("✅ 没有残留中文")
    else:
        print(f"{len(rest)} 处残留")

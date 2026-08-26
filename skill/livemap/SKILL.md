---
name: livemap
description: Turn a destination + number of days + preferences into an interactive travel map — real basemap, colour-coded daily routes, ticket prices and opening hours, photo spots and food picks — output as a single self-contained ~110KB HTML file you can double-click or send to a friend. Also edits existing maps: add stops, split a day, switch travel mode. Works in English or Chinese. Use when the user asks to plan a trip, build an itinerary, make a travel map, or turn a guide into a map. 中文触发：把「目的地 + 天数 + 偏好」变成一张可交互的旅行活地图，输出单文件 HTML，双击就能看、发微信就能分享。当用户说「帮我规划 XX N 天」「做个 XX 的行程」「生成一张旅行地图」「把这个攻略变成地图」，或提到活地图 / LiveMap 时使用。也能改已有地图：加景点、删一天、换模式。
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# LiveMap · 旅行活地图

把行程变成一张**能看**的地图，而不是又一堵文字墙。

产物是**一个自包含的 HTML 文件**（~110 KB）：真实 Leaflet 底图、每天一色的路线、
每个景点的门票/营业时间/建议时长、四宫格实拍图、拍照点、美食、雨天 Plan B、
GPX 导出、打卡 checklist、一键出行程海报。双击能打开，断网能看，发微信能传。

## 你在这条链路里做什么

```
用户："京都 6 天，想深度一点"
        ↓
   你写行程 JSON       ← 这一步就是你，不调任何外部 AI，不需要 API key
        ↓
   python3 scripts/render.py trip.json 京都6天.html
        ↓
   一个单文件 HTML
```

**景点数据完全由你生成**。坐标、门票、营业时间、避坑 tip 全靠你的世界知识——
这是整个产物质量的唯一来源，值得认真对待。

## 流程

### 1. 先问清楚

用户很少一次说全。**缺的就问，不要替他猜**——尤其天数和节奏，这两个直接决定景点数量，
猜错了整张图的密度就不对。一次把该问的问完，别挤牙膏。

| 要问的 | 为什么必须知道 | 没说时怎么办 |
|---|---|---|
| **目的地** | — | 必问 |
| **几天** | 决定 POI 总数和路线结构 | 必问 |
| **节奏**：紧凑 / 标准 / 松弛 | 紧凑 = 每天 5-6 个点，松弛 = 2-3 个。同样 5 天，紧凑排 25 个点，松弛只排 12 个，是两张完全不同的图 | 默认标准，但值得顺口问一句 |
| **有没有一定要去的地方** | 用户心里往往有个「冲着它去的」点。漏了它整张图就白做 | 主动问。用户说了就必须排进去，不许因为冷门或绕路换掉 |
| **语言** | 决定界面和内容语言 | 用户用什么语言跟你说话就用什么，别问 |
| 偏好（美食 / 亲子 / 摄影…） | 影响选点倾向 | 没说就均衡，不用追问 |

问法举个例子，一条消息问完，别一问一答挤三轮：

> 好，京都 6 天。再确认三件事就开工：
> ① 节奏想紧凑一点（每天 5-6 个点）还是松一点（每天 2-3 个，留时间发呆）？
> ② 有没有一定要去的地方？
> ③ 有什么特别想侧重的——美食、寺庙、还是拍照？

顺带留意有没有暗示出行模式（「精打细算」「随便逛逛」「住好点」「穷游」），
对应 `reference/schema.md` 里的四种模式；没提就标准模式，不用专门追问。

**语言**：用户用中文问就出中文图，用英文问就在 `meta.lang` 填 `"en"`，
并且**所有文案都用英文写**——标题、景点名、desc、tip、酒店、出行前必看，全部。
界面文字会自动跟着翻。目前支持 `zh` 和 `en`。

### 2. 读规格

**动手写 JSON 之前先读 `reference/schema.md`。** 那是渲染器唯一认的数据契约，
字段很多（meta 17 个字段、每个 POI 10+ 个字段），凭印象写必然缺件。

`reference/example.json`（首尔 3 天 / 中文）和 `reference/example_en.json`（里斯本 2 天 / 英文）
是两份跑通过的真实数据，拿不准某个字段长什么样就去翻它们。

### 3. 写 JSON

写进一个临时文件，比如 `/tmp/livemap/kyoto.json`。

几条最容易翻车的，先记住：

- **景点数按节奏定档**：紧凑 天数×5~6 / 标准 天数×4 / 松弛 天数×2~3。定了档就别偷懒少给。
- **经纬度必须真实**，精确到小数点后 4 位。这是产品的命门——坐标错了地图就是废的。
  不确定的地点宁可换一个你有把握的，也不要编一个坐标。
- **desc 写独家信息**，不写百科。「几点去人少」「哪个门进不用排队」「别在主街买纪念品」
  才是攻略；「始建于 XXX 年，是著名的 XXX」是废话。
- **预算要自洽**。「预计花费/人」必须 ≥ 住宿均摊总和。这是最常见的自相矛盾。
- **每天的景点按地理就近排序**，别让路线来回折返。
- **用户点名的地方一个都不能少**。绕路就调整当天其他安排去迁就它，并在 `day.tip` 里说明取舍。
- **英文输出时 `tags` 用固定词表**（Must-see / Landmark / Viewpoint / Food / Temple / Nature /
  Beach / Hiking / Free / Family …，完整表在 `scripts/i18n.py` 的 `TAG_MAP`）。
  标签配色和时长推断都按这套词匹配，自创词会掉成默认灰。

### 4. 渲染

```bash
python3 scripts/render.py /tmp/livemap/kyoto.json ~/Desktop/京都6天.html
```

渲染前会校验结构，缺字段会明确告诉你缺哪个。**报错就回去补 JSON 再渲染**，
不要绕过校验。

### 5. 交付

告诉用户文件在哪，以及三件他们会关心的事：
双击就能打开 · 可以直接发微信/AirDrop · 断网也能看。

想改就改——「第 3 天太赶了，拆成两天」「加两个小众点」「换成穷游版」——
改 JSON 重新渲染即可，这比重新生成一遍快得多，也是这个 skill 比网页版强的地方。

## 修改已有地图

用户拿着一个之前生成的 HTML 想改时，**不要去改 HTML**——那是渲染产物，1400 行，
改它既容易改坏又留不下可复用的东西。正确做法是把数据抠回来：

```bash
python3 scripts/extract.py 旧地图.html > /tmp/livemap/trip.json
```

改这份 JSON，然后重新渲染（第 4 步）。

抠不出来说明那不是本 skill 生成的地图（或版本太老），那就按新的重写一份。

## 边界

- **不查实时信息**。门票和营业时间来自你的知识，可能过时——生成后提醒用户
  出行前核对官网，尤其是季节性关闭的景点。
- **不做机票酒店预订**，只给推荐和地址。
- **明信片底图缺失**是正常的。主仓库那 32 张有专门用 AI 画的插画底图，
  skill 生成的没有，页头会退回到维基搜图或主题渐变。不影响任何功能。
- **不要手改 `scripts/` 里的文件**。它们由主仓库
  [shixiann25/livemap](https://github.com/shixiann25/livemap) 的
  `skill/build_skill.py` 自动生成，改了下次构建就没了。

## 文件

| 路径 | 作用 |
|---|---|
| `reference/schema.md` | **动手前必读**：完整数据契约 + 四种出行模式规则 |
| `reference/example.json` | 跑通过的真实样例（首尔 3 天 / 12 个景点） |
| `scripts/render.py` | JSON → 单文件 HTML，带结构校验 |
| `scripts/extract.py` | 已有地图 HTML → JSON，用于修改已生成的行程 |
| `scripts/i18n.py` | 界面翻译（zh / en）+ 标签词表。加语言只需加一个 dict |
| `scripts/template.html` | 地图模板，已内联全部依赖 |
| `scripts/generate.py` | 渲染引擎（`--data` 路径不碰网络、不需要 key） |

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Itinera Generator · v0.3
========================
把目的地 → POI JSON → 渲染成交互式 HTML 旅行地图。

3 种使用模式：

1. AI 模式（需 ANTHROPIC_API_KEY）
   $ export ANTHROPIC_API_KEY=sk-ant-xxx
   $ python3 generate.py "巴黎" 5 --pref 美食,博物馆 --open

2. 用已有 JSON 数据渲染
   $ python3 generate.py --data data/hokkaido.json --open

3. 测试：用内置 mock 数据
   $ python3 generate.py --mock --open
"""

import argparse
import json
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAPS_DIR = ROOT / "maps"
GEN_DIR = Path(__file__).parent
TEMPLATE_PATH = GEN_DIR / "template.html"
DATA_DIR = GEN_DIR / "data"
ENV_FILE = GEN_DIR / ".env"

# 自动从 .env 文件读 API key（.env 优先于空的 shell env var）
def load_env_file():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip(); v = v.strip().strip('"').strip("'")
                # 只要 .env 有值，就用（覆盖空 env 或不存在）
                if k and v and not os.environ.get(k):
                    os.environ[k] = v
load_env_file()

# 配色预设（用 color_scheme 字段映射）
COLOR_SCHEMES = {
    "warm": {  # 黄石/秋季暖色
        "BG_LIGHT": "#f5ecdc", "BG_MID": "#ead5b8", "BG_DARK": "#d4b888",
        "TEXT_DARK": "#3a2818", "TEXT_MID": "#7a5a3a", "TEXT_FAINT": "#b89060",
        "HEADER_BG_1": "rgba(255, 230, 200, 0.85)", "HEADER_BG_2": "rgba(248, 200, 150, 0.7)",
        "ACCENT": "#c2542e", "ACCENT_LIGHT": "#e8a85e", "ACCENT_GLOW": "rgba(194, 84, 46, 0.8)",
        "ACCENT_BORDER": "rgba(180, 120, 60, 0.25)", "ACCENT_BG": "rgba(232, 168, 94, 0.18)", "ACCENT_BG_HOVER": "rgba(232, 168, 94, 0.35)",
        "H1_GRAD_1": "#c2542e", "H1_GRAD_2": "#b8722e", "H1_GRAD_3": "#6b4a2e",
    },
    "sakura": {  # 京都樱花粉
        "BG_LIGHT": "#f5ebe0", "BG_MID": "#e8d5c4", "BG_DARK": "#d4b8a0",
        "TEXT_DARK": "#3a2828", "TEXT_MID": "#7a5a5a", "TEXT_FAINT": "#b89090",
        "HEADER_BG_1": "rgba(255, 240, 245, 0.85)", "HEADER_BG_2": "rgba(248, 220, 230, 0.7)",
        "ACCENT": "#b04060", "ACCENT_LIGHT": "#e8a8b8", "ACCENT_GLOW": "rgba(176, 64, 96, 0.8)",
        "ACCENT_BORDER": "rgba(180, 100, 130, 0.25)", "ACCENT_BG": "rgba(232, 168, 184, 0.18)", "ACCENT_BG_HOVER": "rgba(232, 168, 184, 0.35)",
        "H1_GRAD_1": "#c2542e", "H1_GRAD_2": "#b04060", "H1_GRAD_3": "#6b4a7e",
    },
    "ocean": {  # 海岛蓝绿
        "BG_LIGHT": "#dbf0e8", "BG_MID": "#b8dccb", "BG_DARK": "#94c0a8",
        "TEXT_DARK": "#1a3a2a", "TEXT_MID": "#4a6a5a", "TEXT_FAINT": "#6a8a7a",
        "HEADER_BG_1": "rgba(190, 235, 215, 0.85)", "HEADER_BG_2": "rgba(150, 215, 185, 0.7)",
        "ACCENT": "#1f7a5a", "ACCENT_LIGHT": "#58a87c", "ACCENT_GLOW": "rgba(31, 122, 90, 0.8)",
        "ACCENT_BORDER": "rgba(50, 130, 90, 0.25)", "ACCENT_BG": "rgba(88, 168, 124, 0.18)", "ACCENT_BG_HOVER": "rgba(88, 168, 124, 0.35)",
        "H1_GRAD_1": "#c2542e", "H1_GRAD_2": "#1f7a5a", "H1_GRAD_3": "#2d5f8a",
    },
    "snow": {  # 北海道雪国冷色
        "BG_LIGHT": "#e8f0f5", "BG_MID": "#c8dde8", "BG_DARK": "#a0bccc",
        "TEXT_DARK": "#1a2838", "TEXT_MID": "#4a5a6a", "TEXT_FAINT": "#7a8a9a",
        "HEADER_BG_1": "rgba(220, 235, 250, 0.85)", "HEADER_BG_2": "rgba(180, 210, 235, 0.7)",
        "ACCENT": "#3a6f9a", "ACCENT_LIGHT": "#7ab0d4", "ACCENT_GLOW": "rgba(58, 111, 154, 0.8)",
        "ACCENT_BORDER": "rgba(80, 130, 170, 0.25)", "ACCENT_BG": "rgba(122, 176, 212, 0.18)", "ACCENT_BG_HOVER": "rgba(122, 176, 212, 0.35)",
        "H1_GRAD_1": "#3a6f9a", "H1_GRAD_2": "#5a8ab0", "H1_GRAD_3": "#a0bcd4",
    },
    "forest": {  # 森林深绿
        "BG_LIGHT": "#e5ede0", "BG_MID": "#c4d6b8", "BG_DARK": "#9ab48a",
        "TEXT_DARK": "#1c2818", "TEXT_MID": "#4a5a3a", "TEXT_FAINT": "#7a8a6a",
        "HEADER_BG_1": "rgba(220, 240, 200, 0.85)", "HEADER_BG_2": "rgba(180, 210, 150, 0.7)",
        "ACCENT": "#3a6a32", "ACCENT_LIGHT": "#7a9a4d", "ACCENT_GLOW": "rgba(58, 106, 50, 0.8)",
        "ACCENT_BORDER": "rgba(80, 130, 60, 0.25)", "ACCENT_BG": "rgba(122, 154, 77, 0.18)", "ACCENT_BG_HOVER": "rgba(122, 154, 77, 0.35)",
        "H1_GRAD_1": "#3a6a32", "H1_GRAD_2": "#7a9a4d", "H1_GRAD_3": "#b8a85e",
    },
}

# 货币 → 汇率 + 中文
CURRENCY_LABELS = {
    "JPY": ("日元", 0.05), "USD": ("美元", 7.2), "EUR": ("欧元", 7.8),
    "GBP": ("英镑", 9.0), "KRW": ("韩元", 0.0055), "THB": ("泰铢", 0.21),
    "AUD": ("澳元", 4.8), "CAD": ("加元", 5.3),
}

MODE_PROFILES = {
    "j": {
        "label": "J 人精算",
        "rule": """【J 人模式】严格时间表：每个 POI 都给精确到分钟的到访区间（如 '09:30-10:45'），写在 desc 开头。day.tip 必须包含『当天最优交通顺序』。POI 顺序必须严格按地理最短路径，不允许折返。给出每天的 buffer 时间用于排队/吃饭。预算控制精细，价格区间收窄到 ±10%。""",
    },
    "p": {
        "label": "P 人随性",
        "rule": """【P 人模式】不卡时间，每天给 2-3 个『必做』+2-3 个『有空再去』的可选 POI（用 tag 区分『必看』vs 『备选』）。day.tip 写『不想去 A 就换 B』的备选方案。强调氛围感而非打卡数：少一两个景点没关系。鼓励 walk-in、街边发现。""",
    },
    "middle": {
        "label": "中产舒适",
        "rule": """【中产模式】酒店给当地 4-5 星（按目的地物价定档，发达国家可能 ¥1500-3500/晚，东南亚 ¥600-1500/晚），餐厅必含 1-2 家米其林/亚洲 50 佳/本地高端店。交通推荐打车/包车而非地铁。POI desc 侧重『最佳体验时段』和『私享』玩法，避开旺季人潮。预算按『实际加总』给（住宿+餐饮+门票+当地交通），通常是穷游档的 2-3 倍。""",
    },
    "budget": {
        "label": "穷游省钱",
        "rule": """【穷游模式】酒店给青旅/民宿/经济型连锁（按目的地物价定最低档：东南亚 ¥80-250/晚，发达国家/热门国家公园即便最省也常要 ¥500-900/晚），餐厅必含街边/夜市/本地人吃的平价店。交通优先公交/地铁/夜巴/廉价航空/拼车。POI 优先免费或低价，desc 必须给『省钱 tip』如学生证打折/淡季半价/免费时段。⚠️ 注意：穷游≠不要钱，预算仍须按实际加总，不可低于住宿总和。""",
    },
}

CLAUDE_PROMPT = """你是资深旅行规划师。为以下需求生成完整的 POI JSON 数据：

目的地：{destination}
天数：{days}
偏好：{prefs}
模式：{mode_rule}

输出严格 JSON 格式（无 Markdown 代码块、无前后说明）：
{{
  "meta": {{
    "title": "中文长标题（含 emoji），如 '⛩️ 京都 6 天古都深度'",
    "title_short": "短标题，如 '京都古都深度环游'",
    "subtitle": "ENGLISH SUBTITLE",
    "eyebrow": "DESTINATION · ITINERA · 2026 格式",
    "header_emoji": "单个代表 emoji",
    "lang": "输出语言：zh（默认，可省略）| en。填 en 时【所有】文案都要用英文写：标题、景点名、desc、tip、酒店、pretrip 全部",
    "color_scheme": "warm|sakura|ocean|snow|forest 五选一（依目的地气质）",
    "currency": "JPY|USD|EUR|GBP|KRW|THB|AUD|CAD（依目的地）",
    "map_center": [纬度, 经度],
    "map_zoom": 10 (城市紧凑用 11-12，国家公园用 9-10),
    "where_summary": "进出方式简述，如 '关西机场进/出'",
    "all_tip": "⭐ 必须 250-400 字，结构化说明，让读者一眼看懂【为什么这样安排】。强制 4 段，每段用 \\n\\n 分隔：\\n\\n🎯 主题定调（30-50 字）：这是一趟什么风味的旅行？比如『不是打卡式扫景点，而是一条主题串联的故事线』、『围绕 XX 体验的精炼路线』，要有诗意有灵魂，不是流水账。\\n\\n🎬 节奏递进（60-100 字）：解释为什么是这个天数顺序——是【浅入深】还是【深到浅】？是【西→东】还是【从城市→自然→回归】？每天扮演什么角色（如 Day1 调时差打底/Day2 高潮/Day3 慢节奏告别）。读者看完应该理解这个顺序的智慧而不是随机堆砌。\\n\\n🗺️ 路线设计（60-100 字）：为什么不来回折返？哪几天是同一基地不换酒店？跨城/换酒店的安排逻辑。配合预算和体能曲线说明。\\n\\n💡 实用建议（50-80 字）：航线进出建议、必带物品、避雷月份、订票时机等可执行的 tip。",
    "stats": [
      {{"num": "5", "label": "天数", "hint": "DAYS"}},
      {{"num": "20", "label": "景点", "hint": "POI"}},
      {{"num": "¥XK-YK", "label": "预计花费/人", "hint": "BUDGET / PERSON", "tooltip": "不含国际机票，含食宿门票当地交通。算法：住宿总和(每晚价×晚数，双人房按2人均摊)+餐饮(每天×天数)+门票总和+当地交通，再给上下浮区间"}},
      {{"num": "租车|地铁|JR Pass|公交|步行", "label": "交通方式", "hint": "TRANSPORT", "tooltip": "推荐主要交通方式"}}
    ],
    "highlight_title": "🔥 XX 独门绝技",
    "highlight_items": ["<b>项目1</b>（解释）", "<b>项目2</b>（解释）", ...4-5 条],
    "warning_title": "⚠️ 安全/礼仪/避坑",
    "warning_text": "1-2 句最重要的注意事项",
    "footer": "DESTINATION · 一句话标语 · 2026",
    "pretrip": {{
      "visa": "中国护照签证情况，如 '免签 90 天' 或 '需提前办签证（¥X 元，X 个工作日）'",
      "voltage": "电压/插头类型，如 '220V · A型插头（需转换头）'",
      "sim": "网络方案，如 'eSIM 推荐 Airalo（¥80/5GB）· 当地买卡 ¥X'",
      "currency": "货币换汇 tip，如 '¥1 RMB ≈ ¥X 当地币 · 推荐银联卡免手续费'",
      "tipping": "小费文化，如 '不需小费' 或 '餐厅 15-20%'",
      "emergency": "紧急电话，如 '110 报警/120 急救/中国大使馆 +X'"
    }}
  }},
  "days": {{
    "1": {{
      "color": "#hex",
      "title": "Day 1 · 主题",
      "where": "📍 住宿地（区域）",
      "tip": "💡 当日关键 tip",
      "hotel": {{
        "name_cn": "中文酒店名",
        "name_en": "English Hotel Name",
        "address": "完整地址（用于 Google Maps 跳转）",
        "price": "¥XXX-XXX/晚（原币种 + RMB 等价 任选）",
        "parking": "停车信息，如 '免费' '$25/晚' '不提供' '需街边付费泊车'",
        "highlights": "1 句话说亮点，如 '步行 5 分钟到地铁/园区班车/海景房'",
        "url": "可选：直接预订链接（Booking/官网/Agoda）"
      }},
      "plan_b": "💧 雨天/旺季备选：如果原计划景点关闭/暴雨/人爆满，今天换成 X+Y（室内为主），如 '改去 XX 博物馆 + YY 商场 + ZZ 美食街'"
    }},
    ...
  }},
  "pois": [
    {{
      "id": "短英文 id（唯一）",
      "day": 1, "num": 1,
      "name": "中文名（≤8字最佳）",
      "name_cn": "纯中文景点名（≤9字，绝不含英文字母；海报/标签显示用）",
      "en": "English Name",
      "lat": 精确到 0.0001 度的纬度,
      "lng": 精确到 0.0001 度的经度,
      "icon": "单个 emoji",
      "color": "#hex（按类别）",
      "search": "Wikipedia 英文搜索关键词（用于图片搜索）",
      "price": "原币种符号 + 数字, 如 '$35/车' 或 '¥500' 或 '免费'",
      "hours": "营业时间，如 '9:00-17:00' 或 '24h'",
      "duration": "建议游玩时长，如 '30 分钟' '1-1.5 小时' '半天' '全天' '— 抵达/离港'（仅交通点）",
      "desc": "150 字内：1 句话亮点 + 实用 tip（避坑/最佳时段）",
      "tags": ["必看","必去","地标","震撼","野生动物","自然","喷泉","地热","温泉","瀑布","峡谷","观景","湖泊","亲子","免费","小镇","美食","小吃","独家","夜景","传统","体验","寺庙","神社","火山"] 从中选 1-3 个,
      "time": "上午|中午|下午|傍晚|晚上|早 X 点",
      "photo_spots": ["📸 拍照点1（具体怎么拍）", "📸 拍照点2", ...2-3 条],
      "foods": ["🍜 美食推荐1（价位）", "🍜 美食推荐2", ...2-4 条]
    }}
  ],
  "legend": [
    {{"color": "#hex", "icon": "emoji", "label": "类别"}},
    ...6-8 条
  ]
}}

⚠️ 强制规则（违反即重生成）：
1. ⭐ **POI 数量按「节奏」定档**（需求里没说就按标准）：
   · 紧凑 = days × 5~6 —— 体力好、想尽量多看，每天排满
   · 标准 = days × 4（±1）—— 默认档
   · 松弛 = days × 2~3 —— 慢游 / 带老人小孩 / 想留白，宁可少而深
   例：5 天标准 → 19-21 个；5 天松弛 → 10-15 个；5 天紧凑 → 25-30 个。
   **在选定的档位里不要偷懒少给**，也不要越档。
2. 每天必须有 day:1, day:2, ..., day:N 全覆盖，每天的 POI 数与上面的档位一致
   （紧凑 5-6 个 / 标准 3-5 个 / 松弛 2-3 个）
3. 每天的 POI 按地理就近顺序排列（避免来回折返）
4. 每天至少 1 个 "必看" 或 "必去" tag
5. ⭐ **用户点名要去的地方必须出现**：需求里提到「一定要去 X」「想看 Y」「冲着 Z 去的」，
   X/Y/Z 必须作为 POI 出现，并排进合理的那一天；不要因为它冷门或绕路就换成更热门的替代品。
   如果它确实和其他点距离过远，就调整当天的其他安排去迁就它，并在 day.tip 里说明取舍。
6. desc 必须含独家信息（门票/最佳时间/避坑/小众玩法），**不要写百科介绍**
7. 颜色按类别：寺庙 #6b4a7e / 神社 #b04060 / 自然 #5a7a4a / 美食 #c97b5a / 观景 #6b7a6e / 海滩 #1f7a5a / 地热 #d4854e / 峡谷 #c2542e / 湖 #4a8db5 / 交通 #4a5d52
8. 经纬度必须真实精确到 4 位小数（Google 一搜就能验证）
9. price 必须用原币种符号（¥/$/€/£/₩/฿）+ 数字，如 "¥500" "$35/车"
10. legend 给出与 POI 颜色一致的 6-8 条类别图例
11. ⭐ **预算自洽（最常出错，务必检查）**：「预计花费/人」必须和你列出的酒店价、门票价逻辑一致，不能凭感觉拍脑袋。计算步骤：
    (a) 住宿 = 各晚酒店价 × 晚数（双人标间按 2 人均摊，即每人付一半）；
    (b) 餐饮 = 每人每天餐费 × 天数（穷游低/中产高）；
    (c) 门票 = 所有 POI 门票之和；
    (d) 当地交通 = 租车/打车/公交估算（租车按 2-4 人均摊）；
    (e) 预计花费/人 ≈ a+b+c+d，给一个 ±15% 的区间。
    ❗ 硬性检查：预计花费/人 必须 ≥ 住宿均摊总和。例：5 晚 × $150/晚 ÷ 2 人 ≈ $375 ≈ ¥2700 住宿，那总花费绝不可能只有 ¥3-4K，至少 ¥5-7K。**发现矛盾就重算，不要输出自相矛盾的数字。**
12. 货币：中文输出时，stats 里的金额换算成人民币(¥)，price/hotel 保留目的地原币符号。
    **lang=en 时不要换算人民币**——stats 和 price 一律用目的地原币（读者不看人民币）。
13. **直接输出 JSON 对象，不要 ```json``` 代码块包裹，不要任何前后说明文字**"""


def _repair_json(text: str) -> str:
    """修复 LLM 常见 JSON 错误：尾逗号、智能引号、全角逗号/冒号。"""
    # 尾逗号： ,] 或 ,}
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # 全角标点（出现在结构位置，非字符串内难以区分；只在明显结构处替换风险大，跳过）
    return text


def _extract_json(text: str) -> dict:
    """从 LLM 响应中安全提取 JSON（带修复回退）。"""
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m: text = m.group(1).strip()
    # 去掉非 JSON 前后文（DeepSeek-R1 等会有 <think> 标签）
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    # 找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 回退：尝试修复尾逗号等常见错误
        return json.loads(_repair_json(text))


def _mode_rule(mode: str) -> str:
    m = (mode or "").strip().lower()
    profile = MODE_PROFILES.get(m)
    return profile["rule"] if profile else "（标准模式：均衡体验）"


def call_claude(destination: str, days: int, prefs: str, mode: str = "") -> dict:
    """Anthropic Claude API。"""
    try:
        import anthropic
    except ImportError:
        sys.exit("❌ 缺少依赖：pip install anthropic")
    client = anthropic.Anthropic()
    prompt = CLAUDE_PROMPT.format(destination=destination, days=days, prefs=prefs or "经典", mode_rule=_mode_rule(mode))
    print(f"🤖 [Claude] 生成 {destination} {days} 天 · 模式={mode or '标准'}...")
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(resp.content[0].text)


def call_volcengine(destination: str, days: int, prefs: str, mode: str = "") -> dict:
    """火山引擎 Ark API（OpenAI 兼容协议）。"""
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("❌ 缺少依赖：pip install openai")

    api_key = os.getenv("VOLC_API_KEY")
    if not api_key:
        sys.exit("❌ 未设 VOLC_API_KEY")
    # 模型 ID 优先用 VOLC_ENDPOINT_ID（推理接入点），否则用 VOLC_MODEL（直接模型名）。
    # 豆包模型名带日期后缀（doubao-seed-2-1-pro-2xxxxx），旧版本会下架——
    # 2026 年初 doubao-1-5-pro-32k-250115 就悄悄没了，配置不改就一直报「模型不存在」。
    # 所以这里像 gen_postcard.py 一样准备一串候选，挨个试，别让一个过期的 ID 卡死整条链路。
    VOLC_MODEL_FALLBACKS = [
        "doubao-seed-2-1-pro-260628",  # 主力：知识强，POI 坐标/票价靠它（2026-06-28 版）
        "doubao-seed-2-1-pro",         # 不带日期的别名，将来 260628 下架时兜一手
        "doubao-seed-2-1-turbo",       # 半价备选
        "doubao-seed-2-0-lite",
    ]
    configured = os.getenv("VOLC_ENDPOINT_ID") or os.getenv("VOLC_MODEL", "")
    candidates = ([configured] if configured else []) + [
        m for m in VOLC_MODEL_FALLBACKS if m != configured
    ]
    base_url = os.getenv("VOLC_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    # 超时放宽到 600s：走流式，所以这是「整段生成」的上限，不是「一次等待」。
    # 实测每个景点约 15 秒，8 天行程 20+ 个景点要五六分钟，180s 完全不够。
    client = OpenAI(api_key=api_key, base_url=base_url,
                    timeout=float(os.getenv("VOLC_TIMEOUT", "600")), max_retries=0)
    prompt = CLAUDE_PROMPT.format(destination=destination, days=days, prefs=prefs or "经典", mode_rule=_mode_rule(mode))

    model_errs = []
    for model in candidates:
        try:
            return _volc_one_model(client, model, prompt, destination, days, mode)
        except Exception as e:
            msg = str(e)
            # 只有「这个模型用不了」才换下一个；JSON 解析失败之类是模型本身的问题，换个 ID 也一样
            if not any(k in msg for k in ("does not exist", "NotFound", "404", "ModelNotOpen",
                                          "InvalidParameter", "not open", "未开通", "不存在")):
                raise
            model_errs.append(f"{model}: {msg[:110]}")
            print(f"  ⚠️ 模型 {model} 用不了，换下一个...")
    raise RuntimeError(
        "火山这边没有一个候选模型可用。请到方舟「开通管理」确认已开通的模型，"
        "把它的调用 ID 填进 VOLC_MODEL（或用推理接入点填 VOLC_ENDPOINT_ID）。\n  "
        + "\n  ".join(model_errs)
    )


def _volc_one_model(client, model, prompt, destination, days, mode):
    """用指定模型跑一次；JSON 解析失败会在同一个模型上重试 3 次。"""
    print(f"🤖 [火山 · {model}] 生成 {destination} {days} 天 · 模式={mode or '标准'}...")

    messages = [
        {"role": "system", "content": "你是资深旅行规划师，严格输出 JSON 格式，无任何前后说明。所有字符串内的引号必须用中文「」或转义，绝不出现裸的英文双引号。"},
        {"role": "user", "content": prompt},
    ]
    last_err = None
    for attempt in range(3):
        kwargs = dict(model=model, max_tokens=16000, temperature=0.4 if attempt else 0.7, messages=messages)
        # 关掉「深度思考」：doubao-seed-2.x 默认会先吐一大段思维链，
        # 而这个任务是照着知识列景点、不需要推理。开着的后果是又慢又贵
        # （思考 token 也按输出计费），实测能把一次请求拖到 5 分钟以上还不返回。
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        # 第 1 次尝试用 json_object 强制合法 JSON（部分豆包模型支持）
        if attempt == 0:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = time.time()
        try:
            content, usage = _stream_completion(client, kwargs)
        except Exception as e:
            msg = str(e).lower()
            # 老模型不认 response_format / thinking，逐个摘掉重试，别整个失败
            dropped = []
            if "response_format" in msg:
                kwargs.pop("response_format", None); dropped.append("response_format")
            if "thinking" in msg:
                kwargs.pop("extra_body", None); dropped.append("thinking")
            if not dropped:
                raise
            print(f"  ⚠️ 模型不认 {'/'.join(dropped)}，去掉重试...")
            content, usage = _stream_completion(client, kwargs)
        print(f"  ⏱ {time.time() - t0:.1f}s"
              + (f" · token 输入 {usage[0]} / 输出 {usage[1]}" if usage else "")
              + f" · 正文 {len(content)} 字")
        try:
            return _extract_json(content)
        except json.JSONDecodeError as e:
            last_err = e
            print(f"  ⚠️ 第 {attempt+1} 次 JSON 解析失败（{e}），重试...")
    raise last_err


def _stream_completion(client, kwargs):
    """流式收完整段文本，返回 (content, (prompt_tokens, completion_tokens) | None)。

    为什么必须流式：一次要 1 万多 token 的 JSON，模型大约每个景点 15 秒，
    5 天行程要四五分钟。非流式就是一条几分钟不吐字节的连接——浏览器、
    反向代理、平台负载均衡都可能当它僵死直接掐掉，而且中途完全看不到进度。
    流式下每个分片都在刷新连接，超时也只针对「多久没有新分片」。
    """
    kwargs = dict(kwargs, stream=True, stream_options={"include_usage": True})
    content, usage, chunks = [], None, 0
    for ch in client.chat.completions.create(**kwargs):
        if getattr(ch, "usage", None):
            usage = (ch.usage.prompt_tokens, ch.usage.completion_tokens)
        if not ch.choices:
            continue
        piece = ch.choices[0].delta.content
        if piece:
            content.append(piece)
            chunks += 1
            if chunks % 200 == 0:
                print(f"    … 已收 {sum(len(c) for c in content)} 字", flush=True)
    return "".join(content), usage


def call_llm(destination: str, days: int, prefs: str, mode: str = "") -> dict:
    """根据 LLM_PROVIDER 环境变量自动派发。"""
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    # 没显式指定时，按 key 存在性自动选（优先火山——便宜）
    if not provider:
        if os.getenv("VOLC_API_KEY"):
            provider = "volc"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            sys.exit("❌ 未设任何 LLM key（VOLC_API_KEY 或 ANTHROPIC_API_KEY）")

    if provider in ("volc", "volcengine", "ark"):
        return call_volcengine(destination, days, prefs, mode)
    elif provider in ("anthropic", "claude"):
        return call_claude(destination, days, prefs, mode)
    else:
        sys.exit(f"❌ 未知 LLM_PROVIDER：{provider}（应为 volc 或 anthropic）")


def get_color_scheme(name: str) -> dict:
    return COLOR_SCHEMES.get(name, COLOR_SCHEMES["warm"])


def render_html(data: dict) -> str:
    """把 JSON 数据塞进模板。"""
    if not TEMPLATE_PATH.exists():
        sys.exit(f"❌ 模板缺失：{TEMPLATE_PATH}")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    meta = data["meta"]
    days = data["days"]
    pois = data["pois"]
    legend = data.get("legend", [])

    # 配色
    scheme = get_color_scheme(meta.get("color_scheme", "warm"))

    # 货币标签
    currency = meta.get("currency", "USD")
    cur_label, cur_rate = CURRENCY_LABELS.get(currency, ("外币", 1))
    cur_symbol = {"JPY": "¥", "USD": "$", "EUR": "€", "GBP": "£", "KRW": "₩", "THB": "฿", "AUD": "A$", "CAD": "C$"}.get(currency, "$")
    fx_note = f"{cur_symbol}1 {currency} ≈ ¥{cur_rate:g} RMB"

    # Day tabs
    day_tabs = ""
    for d_str, d in days.items():
        title_short = d["title"].split(" · ", 1)[-1] if " · " in d["title"] else d["title"]
        day_tabs += f'\n    <div class="tab" data-day="{d_str}" style="color:{d["color"]}"><span class="dot"></span>Day {d_str} · {title_short}</div>'

    # Legend
    legend_html = "\n        ".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{l["color"]};color:#fff">{l["icon"]}</span>{l["label"]}</div>'
        for l in legend
    )

    # META JSON（注入 JS）
    meta_for_js = dict(meta)
    meta_for_js["total_days"] = len(days)
    meta_for_js["accent"] = scheme["ACCENT"]
    meta_for_js["accent_bg"] = scheme["ACCENT_BG"]
    meta_for_js["text_dark"] = scheme["TEXT_DARK"]
    meta_for_js["text_mid"] = scheme["TEXT_MID"]

    replacements = {
        "{{TITLE_PLAIN}}": re.sub(r"[^\w\s一-鿿]", "", meta["title"]).strip(),
        "{{TITLE}}": meta["title"],
        "{{SUBTITLE}}": meta["subtitle"],
        "{{EYEBROW}}": meta["eyebrow"],
        "{{HEADER_EMOJI}}": meta["header_emoji"],
        "{{TOTAL_DAYS}}": str(len(days)),
        "{{DAY_TABS}}": day_tabs,
        "{{LEGEND_ITEMS}}": legend_html,
        "{{FOOTER}}": meta.get("footer", "ITINERA · 2026"),
        "{{CURRENCY_LABEL}}": cur_label,
        "{{FX_NOTE}}": fx_note,
        "{{POIS_JSON}}": json.dumps(pois, ensure_ascii=False),
        "{{DAYS_JSON}}": json.dumps(days, ensure_ascii=False),
        "{{META_JSON}}": json.dumps(meta_for_js, ensure_ascii=False),
    }
    replacements.update({f"{{{{{k}}}}}": v for k, v in scheme.items()})

    out = template
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def slugify(text: str, fallback_meta: dict = None) -> str:
    """中文目的地 → 英文 slug。优先用预设映射，其次从 meta.eyebrow 提取英文。"""
    map_zh_to_en = {
        # 日本
        "京都": "kyoto", "东京": "tokyo", "大阪": "osaka", "北海道": "hokkaido",
        "札幌": "sapporo", "冲绳": "okinawa", "奈良": "nara", "镰仓": "kamakura",
        "富士山": "fuji",
        # 韩国
        "首尔": "seoul", "釜山": "busan", "济州": "jeju",
        # 东南亚
        "曼谷": "bangkok", "清迈": "chiangmai", "普吉": "phuket",
        "新加坡": "singapore", "吉隆坡": "kuala_lumpur",
        "巴厘岛": "bali", "雅加达": "jakarta",
        "胡志明": "ho_chi_minh", "河内": "hanoi",
        # 欧洲
        "巴黎": "paris", "伦敦": "london", "罗马": "rome", "米兰": "milan",
        "巴塞罗那": "barcelona", "马德里": "madrid",
        "柏林": "berlin", "维也纳": "vienna", "布拉格": "prague",
        "阿姆斯特丹": "amsterdam", "苏黎世": "zurich",
        "圣托里尼": "santorini", "雅典": "athens",
        "冰岛": "iceland", "挪威": "norway", "瑞士": "switzerland",
        "威尼斯": "venice", "佛罗伦萨": "florence",
        # 美国
        "纽约": "new_york", "洛杉矶": "la", "旧金山": "sf",
        "西雅图": "seattle", "拉斯维加斯": "vegas", "奥兰多": "orlando",
        "波士顿": "boston", "芝加哥": "chicago", "迈阿密": "miami",
        # 美国国家公园
        "黄石": "yellowstone", "大岛": "big_island", "夏威夷": "hawaii",
        "大峡谷": "grand_canyon", "约塞米蒂": "yosemite", "锡安": "zion",
        "羚羊峡谷": "antelope_canyon",
        # 中国
        "西藏": "tibet", "拉萨": "lhasa", "新疆": "xinjiang",
        "成都": "chengdu", "重庆": "chongqing", "云南": "yunnan",
        "大理": "dali", "丽江": "lijiang", "三亚": "sanya",
        "厦门": "xiamen", "杭州": "hangzhou", "西安": "xian",
        "桂林": "guilin", "张家界": "zhangjiajie",
        # 其他
        "悉尼": "sydney", "墨尔本": "melbourne",
        "迪拜": "dubai", "开罗": "cairo",
        "里约": "rio",
    }
    for zh, en in map_zh_to_en.items():
        if zh in text:
            return en
    # 兜底 1：尝试从 meta.eyebrow 提取英文（"DESTINATION · ITINERA · 2026"）
    if fallback_meta:
        eb = fallback_meta.get("eyebrow", "")
        first = eb.split("·")[0].strip().lower()
        first_slug = re.sub(r"[^a-z0-9]+", "_", first).strip("_")
        if first_slug and first_slug != "destination":
            return first_slug
    # 兜底 2：从 text 提取英文部分
    fallback = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return fallback or "destination"


def load_mock_data():
    """读 data/hokkaido.json 作为默认 mock。"""
    p = DATA_DIR / "hokkaido.json"
    if not p.exists():
        sys.exit(f"❌ Mock 数据缺失：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Itinera Generator · v0.3")
    parser.add_argument("destination", nargs="?", help="目的地，如 '京都' 或 'Kyoto'")
    parser.add_argument("days", nargs="?", type=int, help="天数")
    parser.add_argument("--pref", default="", help="偏好（逗号分隔）")
    parser.add_argument("--mode", default="", choices=["", "j", "p", "middle", "budget"], help="模式：j=J 人精算 / p=P 人随性 / middle=中产舒适 / budget=穷游省钱")
    parser.add_argument("--data", default=None, help="读已有 JSON 文件渲染")
    parser.add_argument("--mock", action="store_true", help="用内置北海道 mock 数据")
    parser.add_argument("--slug", default=None, help="自定义文件名 slug")
    parser.add_argument("--open", action="store_true", help="生成后浏览器自动打开")
    parser.add_argument("--save-json", action="store_true", help="同时保存 JSON 到 data/")
    args = parser.parse_args()

    # 选择数据源
    if args.data:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        slug = args.slug or Path(args.data).stem
        days = data["meta"].get("total_days", len(data["days"]))
    elif args.mock:
        data = load_mock_data()
        slug = args.slug or "hokkaido"
        days = len(data["days"])
    elif args.destination and args.days:
        if not (os.getenv("VOLC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
            sys.exit("❌ 未设 VOLC_API_KEY 或 ANTHROPIC_API_KEY。或用 --mock / --data 测试。")
        data = call_llm(args.destination, args.days, args.pref, args.mode)
        # mode 信息写入 meta，slug 后缀也带上
        if args.mode:
            data.setdefault("meta", {})["mode"] = args.mode
        suffix = f"_{args.mode}" if args.mode else ""
        slug = args.slug or (slugify(args.destination, data.get("meta")) + suffix)
        days = args.days
        if args.save_json:
            DATA_DIR.mkdir(exist_ok=True)
            json_out = DATA_DIR / f"{slug}.json"
            json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"💾 JSON 已存：{json_out}")
    else:
        parser.print_help()
        sys.exit(1)

    # 渲染并保存
    html = render_html(data)
    MAPS_DIR.mkdir(exist_ok=True)
    out = MAPS_DIR / f"{slug}_{days}d.html"
    out.write_text(html, encoding="utf-8")
    print(f"🗺️  地图已生成：{out}（{out.stat().st_size // 1024} KB）")

    if args.open:
        webbrowser.open(f"file://{out.absolute()}")
        print("🌐 已在浏览器打开")


if __name__ == "__main__":
    main()

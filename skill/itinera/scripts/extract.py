#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已生成的地图 HTML 里把行程 JSON 抠回来。

    python3 extract.py 旧地图.html > trip.json

用途：用户拿着一张之前生成的地图要改（加景点/拆天/换模式），
但手上没有当时的 JSON。改渲染出来的 1400 行 HTML 是自找麻烦——
抠回 JSON、改 JSON、重新渲染才对。
"""
import json
import re
import sys
from pathlib import Path

# 新模板把三个常量各压成一行；早期手写的地图是多行缩进的。两种都得认。
PATTERNS = {
    "meta": [r"const META = (\{.*?\});\s*\n", r"const META = (\{.*\});"],
    "days": [r"const DAYS = (\{.*?\});\s*\n", r"const DAYS = (\{.*\});"],
    "pois": [r"const POIs = (\[.*?\]);\s*\n", r"const POIs = (\[.*\]);"],
}


def grab(html, key):
    for pat in PATTERNS[key]:
        for m in re.finditer(pat, html, re.S):
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue          # 贪婪/惰性各试一轮，取第一个能解析的
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    html = Path(sys.argv[1]).read_text(encoding="utf-8")

    out, missing = {}, []
    for key in ("meta", "days", "pois"):
        got = grab(html, key)
        if got is None:
            missing.append(key)
        else:
            out[key] = got
    if missing:
        sys.exit(f"❌ 抠不出 {'/'.join(missing)} —— 这个 HTML 可能不是 Itinera 生成的，"
                 f"或者版本太老。只能重新写一份 JSON 了。")

    # legend 是从 DOM 里渲染的，不是 JS 常量，单独用正则捞
    legend = [
        {"icon": i.strip(), "label": l.strip(), "color": c.strip()}
        for c, i, l in re.findall(
            r'class="legend-dot" style="background:([^;\"]+)[^>]*>(.*?)</span>\s*([^<]+?)\s*</div>',
            html, re.S)
    ]
    if legend:
        out["legend"] = legend

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"✅ 抠出 {len(out['pois'])} 个景点 · {len(out['days'])} 天"
          f" · {len(out.get('legend', []))} 条图例", file=sys.stderr)


if __name__ == "__main__":
    main()

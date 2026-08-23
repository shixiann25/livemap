#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行程 JSON → 单文件交互式地图 HTML。

    python3 render.py trip.json 京都6天.html

不需要任何 API key、不联网、只用 Python 标准库——景点数据是你（Claude）自己写的，
这一步纯粹是把它塞进模板渲染。

渲染前会校验数据结构，缺字段直接告诉你缺哪个，而不是产出一张坏图。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import render_html  # noqa: E402
from i18n import LANGS, translate, leftover_chinese  # noqa: E402

REQUIRED_META = ["title", "title_short", "subtitle", "eyebrow", "header_emoji",
                 "color_scheme", "currency", "map_center", "map_zoom",
                 "all_tip", "stats", "footer"]
REQUIRED_POI = ["id", "day", "num", "name", "en", "lat", "lng", "icon", "color", "desc"]


def validate(data):
    problems = []
    for key in ("meta", "days", "pois"):
        if key not in data:
            problems.append(f"顶层缺 `{key}`")
    if problems:
        return problems

    meta = data["meta"]
    for k in REQUIRED_META:
        if k not in meta:
            problems.append(f"meta 缺 `{k}`")
    lang = (meta.get("lang") or "zh").lower()
    if lang not in ("zh", "zh-cn") and lang not in LANGS:
        problems.append(f"meta.lang={lang!r} 还没有界面翻译。"
                        f"目前支持 zh + {', '.join(LANGS)}；"
                        f"要加新语言就往 scripts/i18n.py 的 LANGS 里加一个 dict")
    if meta.get("color_scheme") not in ("warm", "sakura", "ocean", "snow", "forest"):
        problems.append(f"meta.color_scheme 必须是 warm/sakura/ocean/snow/forest 之一，"
                        f"现在是 {meta.get('color_scheme')!r}")
    center = meta.get("map_center")
    if not (isinstance(center, list) and len(center) == 2):
        problems.append("meta.map_center 必须是 [纬度, 经度]")

    days = data["days"]
    if not isinstance(days, dict) or not days:
        problems.append("days 必须是非空对象，键是 \"1\" \"2\" … 的字符串")
    else:
        for d, v in days.items():
            for k in ("color", "title", "where", "tip"):
                if k not in v:
                    problems.append(f"days[{d}] 缺 `{k}`")

    pois = data["pois"]
    if not isinstance(pois, list) or not pois:
        problems.append("pois 必须是非空数组")
    else:
        for i, p in enumerate(pois):
            for k in REQUIRED_POI:
                if k not in p:
                    problems.append(f"pois[{i}]（{p.get('name', '?')}）缺 `{k}`")
            if str(p.get("day")) not in days:
                problems.append(f"pois[{i}]（{p.get('name', '?')}）的 day={p.get('day')} "
                                f"在 days 里不存在")
        # 坐标像不像真的：全 0 或全一样，多半是模型偷懒没查
        coords = {(p.get("lat"), p.get("lng")) for p in pois if "lat" in p}
        if len(coords) < max(2, len(pois) // 2):
            problems.append("大量 POI 共用同一组经纬度——坐标八成是编的，请逐个核对")
    return problems


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"❌ {src} 不是合法 JSON：{e}")

    problems = validate(data)
    if problems:
        sys.exit("❌ 数据结构有问题，先修好再渲染：\n  · " + "\n  · ".join(problems[:20]))

    lang = (data["meta"].get("lang") or "zh").lower()
    html = translate(render_html(data), lang)

    if lang not in ("zh", "zh-cn"):
        # 数据是用目标语言写的，所以剩下的中文只可能是漏翻的界面文字
        rest = leftover_chinese(html)
        if rest:
            print(f"⚠️  界面上还有 {len(rest)} 处中文没翻到（scripts/i18n.py 里补一下）：",
                  file=sys.stderr)
            for ln, s in rest[:8]:
                print(f"      L{ln}: {s[:60]}", file=sys.stderr)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html, encoding="utf-8")
    kb = dst.stat().st_size // 1024
    tag = "" if lang.startswith("zh") else f" · {lang}"
    print(f"🗺️  已生成：{dst}（{kb} KB · {len(data['pois'])} 个景点 · {len(data['days'])} 天{tag}）")
    print("   单文件，双击就能打开，也可以直接发微信 / AirDrop。")


if __name__ == "__main__":
    main()

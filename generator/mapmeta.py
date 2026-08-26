#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已生成的地图 HTML 中抽取卡片所需的元信息（中文标题/emoji/标签/配色/图片搜索词）。
供 build_static.py 与 server.py 共用，让 Hub 画廊卡片用真实标题而非 slug 猜测。"""
import json
import re

_META_RE = re.compile(r"const META = (\{.*?\});", re.S)
_EMOJI_PREFIX = re.compile(r"^[\U0001F000-\U0001FAFF☀-➿️\s]+")
_LEGEND_ITEM_RE = re.compile(
    r'class="legend-dot"[^>]*>(.*?)</span>\s*([^<]+?)\s*</div>', re.S
)


def _legend_tags(html, limit=4):
    tags = []
    for icon, label in _LEGEND_ITEM_RE.findall(html):
        icon, label = icon.strip(), label.strip()
        if label:
            tags.append(f"{icon} {label}".strip())
        if len(tags) >= limit:
            break
    return tags


def _clean_title(meta):
    t = (meta.get("title_short") or meta.get("title") or "").strip()
    return _EMOJI_PREFIX.sub("", t).strip()


def _image_query(meta):
    """优先用 eyebrow 的首段（多为地名，如 ALASKA / KYOTO / BARCELONA），
    否则取 subtitle 里最像英文地名的一段。"""
    eb = (meta.get("eyebrow") or "").split("·")[0].strip()
    if eb and re.search(r"[A-Za-z]", eb) and not re.search(r"livemap|\d{4}", eb, re.I):
        return eb
    for seg in re.split(r"[·•・|]", meta.get("subtitle") or ""):
        seg = seg.strip()
        if seg and re.search(r"[A-Za-z]", seg) and not re.search(r"livemap|\d{4}", seg, re.I):
            return seg
    return _clean_title(meta)


def _counts(html, meta, stem):
    """天数与 POI 数。新地图 POI 是 "lat": ，老三张（big_island/kyoto_6d/yellowstone_5d）是 lat: 。"""
    n = len(re.findall(r'["\']?lat["\']?\s*:', html))
    if meta.get("map_center"):
        n -= 1                                    # map_center 也是一处坐标，减掉
    days = meta.get("total_days") or 0
    if not days:
        m = re.search(r"_(\d+)d$", stem)
        days = int(m.group(1)) if m else 0
    return max(n, 0), days


def card_meta(html_path):
    """返回 {title, emoji, en, query, color_scheme, tags, poi, days}，解析失败时返回 {}。"""
    try:
        html = html_path.read_text(encoding="utf-8")
        m = _META_RE.search(html)
        if not m:
            return {}
        meta = json.loads(m.group(1))
        tags = _legend_tags(html)
        poi, days = _counts(html, meta, html_path.stem)
        en = (meta.get("eyebrow") or "").split("·")[0].strip() or _image_query(meta)
        return {
            "title": _clean_title(meta),
            "emoji": (meta.get("header_emoji") or "").strip(),
            "en": en.upper(),
            "query": _image_query(meta),
            "color_scheme": meta.get("color_scheme") or "",
            "tags": tags,
            "poi": poi,
            "days": days,
        }
    except Exception:
        return {}


def title_fallback(html_path):
    """没有 const META 的老地图：从 <title> 抠标题，并数出天数/POI 数。"""
    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception:
        return {}
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    raw = (t.group(1) if t else html_path.stem).replace("· Itinera", "").strip()
    raw = re.split(r"\s*[·|]\s*", raw)[0]
    raw = re.sub(r"\s*(精准)?攻略地图\s*$", "", raw).strip()
    poi, days = _counts(html, {}, html_path.stem)
    return {"title": _EMOJI_PREFIX.sub("", raw).strip() or html_path.stem,
            "emoji": (re.search(r"[\U0001F000-\U0001FAFF]", raw) or [""])[0] if re.search(r"[\U0001F000-\U0001FAFF]", raw) else "",
            "poi": poi, "days": days, "tags": _legend_tags(html)}

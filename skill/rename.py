#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性改名脚本：LiveMap / 活地图 → Itinera / 旅行地图。

为什么写成脚本而不是手改
------------------------
名字散在 1000+ 处：32 张成品地图的数据里、模板、生成器、文档、CI、i18n 词表。
手改必漏，而漏掉的地方要等有人看到「LIVEMAP · 2026」才发现。

为什么规则要排序
----------------
  · 「旅行活地图」必须先于「活地图」，否则会变成「旅行旅行地图」
  · 「livemap-skill」必须先于「livemap」，否则前缀被吃掉
  · Render 服务名 livemap-b1im.onrender.com 不能动——那是 Render 那边的独立命名，
    改了字符串反而指向一个不存在的服务

用法：
    python3 skill/rename.py --dry     # 只报告每条规则命中多少
    python3 skill/rename.py           # 真改
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 顺序敏感，别重排
RULES = [
    # —— 先处理会被后面规则吃掉的长串 ——
    ("旅行活地图", "旅行地图"),                    # 否则变成「旅行旅行地图」
    # 顺手修个真 bug：32 张成品的海报二维码一直指向上游作者的 GitHub Pages，
    # 扫码的人会跳到别人的站点
    ("zxz19951104.github.io/livemap", "shixiann25.github.io/itinera"),
    ("livemap-b1im.onrender.com", "\x00RENDER\x00"),  # 占位保护：Render 服务名不改
    ("shixiann25/livemap-skill", "shixiann25/itinera-skill"),
    ("livemap-skill", "itinera-skill"),
    ("shixiann25.github.io/livemap", "shixiann25.github.io/itinera"),
    ("shixiann25/livemap", "shixiann25/itinera"),
    ("skills/livemap", "skills/itinera"),
    ("skill/livemap", "skill/itinera"),

    # —— 展示用的名字 ——
    ("活地图", "旅行地图"),
    ("LIVEMAP", "ITINERA"),
    ("LiveMap", "Itinera"),

    # —— 剩下的小写 livemap：兜底 slug、正则过滤词 ——
    ("!/livemap|", "!/itinera|livemap|"),          # 过滤词保留旧名，老图的 eyebrow 才不会漏网
    ("|| 'livemap')", "|| 'itinera')"),
    ('ROOT / "skill" / "livemap"', 'ROOT / "skill" / "itinera"'),
    ("livemap skill 包", "Itinera skill 包"),
    ('"name": "livemap"', '"name": "itinera"'),
    ("name: livemap", "name: itinera"),            # SKILL.md frontmatter：这是 skill 的 ID
    ('"skills" / "livemap"', '"skills" / "itinera"'),
    ("||'livemap')", "||'itinera')"),               # 无空格变体，和上一条不是同一处
    ("livemapBackBtn", "itineraBackBtn"),
    ("LIVEMAP_STATIC", "ITINERA_STATIC"),
    ("LIVEMAP_SITE_URL", "ITINERA_SITE_URL"),

    # —— 还原被保护的串 ——
    ("\x00RENDER\x00", "livemap-b1im.onrender.com"),
]

SKIP_DIRS = {".git", "dist", "node_modules", "__pycache__", "docs"}
SKIP_FILES = {"rename.py"}   # 本脚本自己满是这些字符串，别自我改写
EXTS = {".html", ".py", ".md", ".mjs", ".json", ".yml", ".yaml", ".js", ".txt"}


def targets():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.name in SKIP_FILES:
            continue
        yield p


def main():
    ap = argparse.ArgumentParser(description="LiveMap → Itinera 改名")
    ap.add_argument("--dry", action="store_true", help="只报告命中数，不写文件")
    args = ap.parse_args()

    hits = {old: 0 for old, _ in RULES}
    touched, leftovers = [], []
    for f in targets():
        try:
            s = orig = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for old, new in RULES:
            n = s.count(old)
            if n:
                hits[old] += n
                s = s.replace(old, new)
        # 干跑也要按「改完之后」的文本统计残留，不能回头读原文件
        for line_no, line in enumerate(s.splitlines(), 1):
            if "livemap" in line.lower():
                leftovers.append((f.relative_to(ROOT), line_no, line.strip()[:88]))
        if s != orig:
            touched.append(f)
            if not args.dry:
                f.write_text(s, encoding="utf-8")

    print(f"{'（干跑）' if args.dry else '已改写'} {len(touched)} 个文件\n")
    for old, new in RULES:
        if old.startswith("\x00") or new.startswith("\x00"):
            continue
        print(f"  {hits[old]:>5} × {old!r} → {new!r}")

    print(f"\n改完后仍含 'livemap' 的行：{len(leftovers)} 行"
          f"（预期只剩 Render 服务名、/tmp 临时路径、以及故意保留的过滤词）")
    for rel, ln, txt in leftovers:
        print(f"   {rel}:{ln}  {txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

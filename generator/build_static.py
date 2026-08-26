#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Itinera 静态分享版构建器
========================
把 livemap/ 打包成纯静态 dist/，可直接部署到 GitHub Pages / Netlify / Vercel。
任何人都能浏览 Hub 画廊 + 所有已生成地图；AI 实时生成会优雅降级为「请本地运行」提示
（静态站点没有后端、不暴露 API key）。

用法：
    cd generator
    python3 build_static.py          # 输出到 ../dist
    python3 build_static.py --out /some/path

部署（GitHub Pages）：
    见 ../DEPLOY.md
"""
import argparse
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # livemap/
MAPS_DIR = ROOT / "maps"

from mapmeta import card_meta, title_fallback

# 站点公网地址：og:image / og:url 必须是绝对地址，平台不会解析相对路径。
# 换域名时用环境变量覆盖，不用改代码：ITINERA_SITE_URL=https://xxx python3 build_static.py
SITE_URL = os.environ.get("ITINERA_SITE_URL", "https://shixiann25.github.io/itinera").rstrip("/")
SITE_NAME = "Itinera 旅行地图"
SITE_DESC = ("跟着这本地图，打开你的旅行。一次旅行，收进一个可以随身带走的文件："
             "真实地图、每天一色的路线、门票与营业时间、拍照点与美食。单文件 HTML，发微信就能看。")


def _esc(s):
    return (str(s).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def og_block(*, title, desc, url, image, kind="website", favicon="🗺️"):
    """生成 Open Graph + Twitter Card 标签。

    为什么在构建期注入而不是写进 maps/*.html 源文件：
    源文件要保持「单文件、离线、可 AirDrop」的属性，塞死绝对 URL 会把它绑死在某个域名上。
    分享卡只在「以链接形式传播」时才有意义，所以只有 dist/ 需要。
    """
    t, d = _esc(title), _esc(desc)
    return (
        f'<meta name="description" content="{d}">\n'
        f'<meta property="og:type" content="{kind}">\n'
        f'<meta property="og:site_name" content="{_esc(SITE_NAME)}">\n'
        f'<meta property="og:locale" content="zh_CN">\n'
        f'<meta property="og:title" content="{t}">\n'
        f'<meta property="og:description" content="{d}">\n'
        f'<meta property="og:url" content="{_esc(url)}">\n'
        f'<meta property="og:image" content="{_esc(image)}">\n'
        f'<meta property="og:image:width" content="1200">\n'
        f'<meta property="og:image:height" content="630">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{t}">\n'
        f'<meta name="twitter:description" content="{d}">\n'
        f'<meta name="twitter:image" content="{_esc(image)}">\n'
        f'<link rel="canonical" href="{_esc(url)}">\n'
        # emoji favicon：零文件、零请求，浏览器标签页一眼认出是哪张图
        f'<link rel="icon" href="data:image/svg+xml,'
        f'%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E'
        f'%3Ctext y=%22.9em%22 font-size=%2290%22%3E{favicon or "🗺️"}%3C/text%3E%3C/svg%3E">\n'
    )


def inject_head(html, block):
    if "</head>" in html:
        return html.replace("</head>", block + "</head>", 1)
    return block + html


def map_desc(m):
    """「N 天 · N 个景点 · 标签1/标签2 —— 可交互旅行地图…」"""
    bits = []
    if m.get("days"):
        bits.append(f'{m["days"]} 天行程')
    if m.get("poi"):
        bits.append(f'{m["poi"]} 个景点')
    tags = [re.sub(r"^[^\w\u4e00-\u9fff]+", "", t).strip() for t in (m.get("tags") or [])][:3]
    if tags:
        bits.append(" / ".join(t for t in tags if t))
    head = " · ".join(bits)
    return f"{head} —— 可交互旅行地图：真实底图、每日路线、门票价格、拍照点与美食推荐，单文件 HTML 可直接分享。"



def collect_maps():
    maps = []
    for f in sorted(MAPS_DIR.glob("*.html")):
        entry = {
            "name": f.stem,
            "url": f"maps/{f.name}",          # 静态版用相对路径
            "size_kb": f.stat().st_size // 1024,
            "mtime": int(f.stat().st_mtime),
        }
        entry.update(card_meta(f) or title_fallback(f))   # title/emoji/en/tags/poi/days
        maps.append(entry)
    return maps


def build(out_dir: Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # 1. 拷贝地图（顺带给每张注入分享卡标签）
    shutil.copytree(MAPS_DIR, out_dir / "maps")

    # 2. 拷贝 PRD（Hub 底部有链接）
    for extra in ["PRD_Itinera.md", "README.md"]:
        src = ROOT / extra
        if src.exists():
            shutil.copy(src, out_dir / extra)

    # 2.5 拷贝静态资源（行程海报明信片底图等）
    assets_src = ROOT / "assets"
    if assets_src.exists():
        shutil.copytree(assets_src, out_dir / "assets")

    # 3. 处理 index.html：注入静态标志 + 地图列表
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    maps = collect_maps()

    # 3.1 每张地图注入 OG / Twitter 卡（只改 dist，源文件保持可离线单文件）
    og_count = 0
    for m in maps:
        f = out_dir / m["url"]
        title = m.get("title") or m["name"]
        emoji = (m.get("emoji") or "").strip()
        card = ROOT / "assets" / "og" / f'{m["name"]}.jpg'
        image = (f'{SITE_URL}/assets/og/{m["name"]}.jpg' if card.exists()
                 else f"{SITE_URL}/assets/og/_site.jpg")
        # 告诉页内脚本「这是静态站」：lm_editor.js 据此跳过 /api/list 探测
        head = '<script>window.ITINERA_STATIC=true;</script>\n' + og_block(
            title=f'{emoji} {title} · Itinera 旅行地图'.strip(),
            desc=map_desc(m),
            url=f'{SITE_URL}/{m["url"]}',
            image=image,
            kind="article",
            favicon=emoji or "🗺️",
        )
        f.write_text(inject_head(f.read_text(encoding="utf-8"), head), encoding="utf-8")
        og_count += 1
    inject = og_block(
        title="Itinera 旅行地图 · 把旅行攻略变成一张能「看」的地图",
        desc=SITE_DESC,
        url=f"{SITE_URL}/",
        image=f"{SITE_URL}/assets/og/_site.jpg",
    ) + (
        "<script>window.STATIC_DEPLOY=true;window.STATIC_MAPS="
        + json.dumps(maps, ensure_ascii=False)
        + ";</script>\n"
    )
    # 注入到 </head> 之前，确保在主脚本之前执行
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    # 静态版的硬编码热门链接 / PRD 链接保持相对路径即可（本来就是相对的）
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    # 4. GitHub Pages 不要 Jekyll 处理（否则下划线开头文件会被忽略）
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(f"✅ 静态站点已构建：{out_dir}")
    print(f"   - index.html（已注入 {len(maps)} 张地图列表）")
    print(f"   - maps/ {len(maps)} 张（已注入 {og_count} 份分享卡标签）")
    print(f"   - 站点地址（og:url 基准）：{SITE_URL}")
    print(f"   本地预览： cd {out_dir} && python3 -m http.server 8000")
    return maps


def main():
    ap = argparse.ArgumentParser(description="Itinera 静态分享版构建器")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="输出目录（默认 ../dist）")
    args = ap.parse_args()
    build(Path(args.out))


if __name__ == "__main__":
    main()

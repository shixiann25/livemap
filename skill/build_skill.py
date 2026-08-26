#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从主仓库构建 Itinera skill 包。

为什么要有构建步骤，而不是手写一份
----------------------------------
skill 要发给别人用，产物必须是**真·单文件 HTML**——不能像 maps/*.html 那样
引用 ../assets/ 下的东西。但主仓库的 template.html 就是那么引用的
（打卡脚本、编辑器脚本、AI 明信片）。手工维护两份模板必然分叉，
所以这里从主模板自动派生出 standalone 版本：

  - lm_checkin.js  → 内联进 HTML（打卡功能保留）
  - lm_editor.js   → 删掉（要 server.py 后端才有用，skill 场景没有）
  - 明信片/海报二维码 → 去掉指向作者仓库的硬编码兜底

用法：
    python3 skill/build_skill.py            # 构建到 skill/itinera/
    python3 skill/build_skill.py --check    # 只校验已构建的产物是否跟上主仓库（CI 用）
    python3 skill/build_skill.py --install  # 构建并安装到 ~/.claude/skills/itinera/
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skill" / "itinera"
SCRIPTS = SKILL_DIR / "scripts"

CHECKIN_TAG = '<script src="../assets/lm_checkin.js" defer></script>'
EDITOR_TAG = '<script src="../assets/lm_editor.js" defer></script>'

# 海报二维码在 file:// 下原本兜底到作者的 GitHub Pages。
# 别人用这个 skill 生成的地图不该指向作者的站点，改成指向项目本身（既诚实又算署名）。
OLD_QR_FALLBACK = "    u='https://shixiann25.github.io/itinera/maps/'+location.pathname.split('/').pop();"
NEW_QR_FALLBACK = (
    "    // 本地文件没有公网地址可扫，二维码退化成指向项目主页（顺带署名）\n"
    "    u='https://github.com/shixiann25/itinera';"
)


def build_template() -> str:
    tpl = (ROOT / "generator" / "template.html").read_text(encoding="utf-8")
    checkin = (ROOT / "assets" / "lm_checkin.js").read_text(encoding="utf-8")

    missing = [t for t in (CHECKIN_TAG, EDITOR_TAG, OLD_QR_FALLBACK) if t not in tpl]
    if missing:
        sys.exit("❌ 主模板结构变了，build_skill.py 的替换锚点没对上：\n  "
                 + "\n  ".join(m[:70] for m in missing))

    tpl = tpl.replace(
        CHECKIN_TAG,
        "<!-- lm_checkin.js 由 skill/build_skill.py 内联进来，保证产物是真单文件 -->\n"
        f"<script>\n{checkin}\n</script>",
    )
    tpl = tpl.replace(EDITOR_TAG + "\n", "")   # 编辑器要后端，skill 场景删掉
    tpl = tpl.replace(EDITOR_TAG, "")
    tpl = tpl.replace(OLD_QR_FALLBACK, NEW_QR_FALLBACK)

    leftovers = [ln.strip() for ln in tpl.splitlines()
                 if "../assets/" in ln and "postcards" not in ln]
    if leftovers:
        sys.exit("❌ 还有没处理干净的外部依赖，产物就不是单文件了：\n  "
                 + "\n  ".join(leftovers[:5]))
    return tpl


def build_schema_doc() -> str:
    """把 generate.py 里那份 POI 规格（CLAUDE_PROMPT + 四种模式）转成 skill 的参考文档。

    为什么要自动派生：这份规格是整个产品的数据契约，模板的每个占位符都对着它。
    手抄一份到 skill 里，改了主仓库就会悄悄分叉，而分叉的表现是「渲染出来缺一块」——
    很难查。所以从源头提取，`--check` 会盯着两边一致。
    """
    src = (ROOT / "generator" / "generate.py").read_text(encoding="utf-8")

    m = re.search(r'CLAUDE_PROMPT = """(.*?)"""', src, re.S)
    if not m:
        sys.exit("❌ 找不到 CLAUDE_PROMPT，build_skill.py 的提取锚点失效了")
    spec = m.group(1)
    # 原文是给 str.format() 用的，花括号是双写的，还带 {destination} 这类占位符
    spec = spec.replace("{{", "{").replace("}}", "}")
    spec = re.sub(r"^.*?输出严格 JSON 格式（无 Markdown 代码块、无前后说明）：\n", "", spec, flags=re.S)

    modes = re.search(r"MODE_PROFILES = \{(.*?)\n\}", src, re.S)
    mode_md = ""
    if modes:
        for key, label, rule in re.findall(
                r'"(\w+)":\s*\{\s*"label":\s*"([^"]+)",\s*"rule":\s*"""(.*?)""",', modes.group(0), re.S):
            mode_md += f"\n### `{key}` · {label}\n\n{rule.strip()}\n"

    return f"""# 行程 JSON 数据规格

这是渲染器唯一认的数据格式。**本文件由 `skill/build_skill.py` 从主仓库
`generator/generate.py` 的 `CLAUDE_PROMPT` 自动生成，不要手改。**

字段缺失或类型不对，`render.py` 会在渲染前拦下来并告诉你缺哪个。

---

## 结构

```jsonc
{spec.strip()}
```

---

## 出行模式（可选）

用户说「J 人」「穷游」「中产」「随性」时，在上面的基础上叠加对应规则：
{mode_md}
### 标准

不指定模式时按均衡体验来：不卡死时间表，也不刻意省钱。
"""


def build(check_only=False) -> bool:
    tpl = build_template()
    gen = (ROOT / "generator" / "generate.py").read_text(encoding="utf-8")
    schema = build_schema_doc()

    files = {
        SCRIPTS / "template.html": tpl,
        SCRIPTS / "generate.py": gen,
        SKILL_DIR / "reference" / "schema.md": schema,
    }
    stale = [p for p, want in files.items()
             if not p.exists() or p.read_text(encoding="utf-8") != want]

    if check_only:
        if stale:
            print("❌ skill 包没跟上主仓库，跑 `python3 skill/build_skill.py` 重建：")
            for p in stale:
                print(f"   · {p.relative_to(ROOT)}")
            return False
        print("✅ skill 包与主仓库同步")
        return True

    for p in files:
        p.parent.mkdir(parents=True, exist_ok=True)
    for p, want in files.items():
        p.write_text(want, encoding="utf-8")
    kb = len(tpl.encode()) // 1024
    print(f"✅ 构建完成 → {SKILL_DIR.relative_to(ROOT)}")
    print(f"   scripts/template.html   {kb} KB（已内联打卡脚本，无外部依赖）")
    print(f"   scripts/generate.py     渲染器（--data 路径不需要任何 API key）")
    print(f"   reference/schema.md     从主仓库 CLAUDE_PROMPT 自动派生")
    return True


DEFAULT_PUBLISH_DIR = Path.home() / "itinera-skill"

# 这些文件只属于独立仓库（面向人的 README、插件/市场清单），构建时不要覆盖它们。
PUBLISH_KEEP = {"README.md", ".git", ".gitignore", ".claude-plugin"}


def sync_to_repo(repo: Path) -> bool:
    """把 skill/itinera/ 的内容同步进独立的 skill 仓库。

    为什么要有这一步：独立仓库 shixiann25/itinera-skill 是**构建产物**，
    真正的源在主仓库（template.html / generate.py / CLAUDE_PROMPT）。
    手工拷来拷去必然某次忘记，别人装到的就是旧版。

    只同步 SKILL.md / scripts / reference；README 和清单归独立仓库自己维护。
    """
    if not (repo / ".git").exists():
        print(f"❌ {repo} 不像是个 git 仓库。先 clone：\n"
              f"   git clone https://github.com/shixiann25/itinera-skill.git {repo}")
        return False

    changed = []
    for item in sorted(SKILL_DIR.iterdir()):
        if item.name in PUBLISH_KEEP:
            continue
        dest = repo / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
            changed.append(item.name + "/")
        else:
            same = dest.exists() and dest.read_bytes() == item.read_bytes()
            shutil.copy2(item, dest)
            if not same:
                changed.append(item.name)

    print(f"📤 已同步到 {repo}")
    for c in changed:
        print(f"   · {c}")
    print("   接下来（本脚本不替你提交，改动值得你自己过一眼）：")
    print(f"     cd {repo} && git diff --stat && git add -A && git commit && git push")
    print("   ⚠️ 版本号变了记得同步改 .claude-plugin/plugin.json 和 marketplace.json 两处")
    return True


def main():
    ap = argparse.ArgumentParser(description="构建 Itinera skill 包")
    ap.add_argument("--check", action="store_true", help="只校验是否跟上主仓库；不同步则退出码 1")
    ap.add_argument("--install", action="store_true", help="构建后安装到 ~/.claude/skills/itinera/")
    ap.add_argument("--publish", metavar="REPO_DIR", nargs="?", const=str(DEFAULT_PUBLISH_DIR),
                    help="把构建产物同步进独立的 skill 仓库（默认 ../itinera-skill），只写不提交")
    args = ap.parse_args()

    ok = build(check_only=args.check)
    if not ok:
        return 1

    if args.publish:
        if not sync_to_repo(Path(args.publish).expanduser()):
            return 1

    if args.install:
        dest = Path.home() / ".claude" / "skills" / "itinera"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SKILL_DIR, dest)
        print(f"📦 已安装到 {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

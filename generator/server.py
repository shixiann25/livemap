#!/usr/bin/env python3
"""
LiveMap 本地服务 · v0.5
========================
让 Hub 真正能"输入目的地 → 点生成 → 浏览器自动出图"。

使用：
    cd generator
    python3 server.py

然后浏览器打开：http://localhost:5005

零依赖（只用 Python stdlib）· 零暴露 API key（key 留在 .env，不出本机）。
"""

import json
import os
import sys
import threading
import time
import http.server
import socketserver
import urllib.parse
from pathlib import Path

# 把 generator 加进 path，能 import generate.py 的函数
sys.path.insert(0, str(Path(__file__).parent))
from generate import (
    call_llm, render_html, slugify, load_env_file,
    MAPS_DIR, DATA_DIR, ROOT,
)

PORT = 5005


# ============ 公网防刷 ============
# 公网部署用的是「作者自己的」API key，等于谁都能花你的钱。
# 本地跑（PUBLIC_DEPLOY 未设）完全不限，公网模式才启用配额。
# 额度用完只影响新生成，画廊里的存量地图照常浏览。

def is_public():
    return os.getenv("PUBLIC_DEPLOY", "").lower() in ("1", "true", "yes")


def has_llm_key():
    """占位值（如 Render 表单里随手填的 changeme）不算数，否则会等到调用时才炸。"""
    for name in ("VOLC_API_KEY", "ANTHROPIC_API_KEY"):
        v = (os.getenv(name) or "").strip()
        if v and v.lower() not in ("changeme", "todo", "none", "null", "xxx", "placeholder"):
            return True
    return False


_quota_lock = threading.Lock()
_quota = {"day": None, "total": 0, "by_ip": {}}


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def quota_reject(ip):
    """放行返回 None，超额返回给用户看的中文提示。"""
    if not is_public():
        return None
    day_cap = int(os.getenv("DAILY_GENERATE_LIMIT", "40"))
    ip_cap = int(os.getenv("DAILY_GENERATE_LIMIT_PER_IP", "5"))
    with _quota_lock:
        if _quota["day"] != _today():
            _quota.update(day=_today(), total=0, by_ip={})
        if _quota["total"] >= day_cap:
            return (f"今天的免费生成额度（{day_cap} 张）已经用完了，明天再来～"
                    f"下面画廊里的地图随便看。")
        if _quota["by_ip"].get(ip, 0) >= ip_cap:
            return (f"你今天已经生成 {ip_cap} 张了，明天再来～"
                    f"想不限量可以把项目 clone 到本地跑 server.py。")
    return None


def quota_commit(ip):
    """只在真的调了 AI 之后才记账——命中存量缓存不花钱，不该占额度。"""
    if not is_public():
        return
    with _quota_lock:
        _quota["total"] += 1
        _quota["by_ip"][ip] = _quota["by_ip"].get(ip, 0) + 1


class LiveMapHandler(http.server.SimpleHTTPRequestHandler):
    """同时提供静态文件 + API 端点。"""

    def __init__(self, *args, **kwargs):
        # 静态文件根目录指向 livemap/
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def client_ip(self):
        # Render / 任何反代后面，真实 IP 在 X-Forwarded-For 的第一段
        fwd = self.headers.get("X-Forwarded-For", "")
        return (fwd.split(",")[0].strip() if fwd else self.client_address[0]) or "unknown"

    def log_message(self, fmt, *args):
        # 简化日志
        ts = self.log_date_time_string()
        print(f"[{ts}] {fmt % args}")

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/list":
            return self._list_maps()
        # 其他 GET 走默认静态文件
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/generate":
            return self._generate()
        if self.path == "/api/save":
            return self._save()
        self.send_error(404, "API not found")

    def _save(self):
        """可视化编辑器保存：收完整 data(meta/days/pois/legend) → render_html → 写回地图文件 + JSON 备份。

        注意：这个端点会覆盖 maps/ 下的文件。公网部署默认关闭——否则任何访客
        都能改掉你的地图。要在公网开编辑，设 LIVEMAP_EDIT_TOKEN，
        并让客户端带 X-LiveMap-Token 头。
        """
        token = os.getenv("LIVEMAP_EDIT_TOKEN")
        if is_public() and not token:
            return self._json(403, {"error": "公网部署已关闭编辑保存（设 LIVEMAP_EDIT_TOKEN 可开启）"})
        if token and self.headers.get("X-LiveMap-Token") != token:
            return self._json(403, {"error": "编辑令牌不正确"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            filename = (payload.get("filename") or "").strip()
            data = payload.get("data")
            # 安全：仅允许 maps/ 下的纯文件名
            if not filename.endswith(".html") or any(c in filename for c in ("/", "\\", "..")):
                return self._json(400, {"error": "非法文件名"})
            if not isinstance(data, dict) or not all(k in data for k in ("meta", "days", "pois")):
                return self._json(400, {"error": "数据缺 meta/days/pois"})
            data.setdefault("legend", [])
            html = render_html(data)
            MAPS_DIR.mkdir(exist_ok=True)
            (MAPS_DIR / filename).write_text(html, encoding="utf-8")
            DATA_DIR.mkdir(exist_ok=True)
            (DATA_DIR / (filename[:-5] + ".json")).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"💾 编辑已保存：{filename}（{len(data.get('pois', []))} POI）")
            return self._json(200, {"success": True, "map_url": f"/maps/{filename}"})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON 解析失败"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _generate(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)

            destination = (data.get("destination") or "").strip()
            days = int(data.get("days") or 5)
            pref = (data.get("pref") or "").strip()
            mode = (data.get("mode") or "").strip().lower()
            if mode not in ("", "j", "p", "middle", "budget"):
                mode = ""

            if not destination:
                return self._json(400, {"error": "请输入目的地"})
            if not (1 <= days <= 14):
                return self._json(400, {"error": "天数应在 1-14 之间"})
            if not has_llm_key():
                return self._json(503, {"error": "本站暂未配置 AI 生成后端，下面画廊里的地图可以照常浏览～"
                                                 "（想自己无限量生成：clone 仓库，配好 key 后本地跑 server.py）"})

            ip = self.client_ip()
            over = quota_reject(ip)
            if over:
                print(f"⛔ 配额拦截 {ip}：{destination} · {days} 天")
                return self._json(429, {"error": over})

            # —— 存量优先：先按 slug+mode+days 查本地是否已有，命中直接返回，不调 AI ——
            base_guess = slugify(destination)
            if base_guess and base_guess != "destination":
                cached_name = f"{base_guess}_{mode}_{days}d.html" if mode else f"{base_guess}_{days}d.html"
                cached_path = MAPS_DIR / cached_name
                if cached_path.exists():
                    print(f"\n♻️  命中存量地图：{cached_name}（跳过 AI，0 token）")
                    return self._json(200, {
                        "success": True,
                        "cached": True,
                        "map_url": f"/maps/{cached_name}",
                        "destination": destination,
                        "days": days,
                        "size_kb": cached_path.stat().st_size // 1024,
                    })

            print(f"\n🤖 生成请求：{destination} · {days} 天 · 偏好={pref or '无'} · 模式={mode or '标准'}")
            quota_commit(ip)   # 真要花 token 了才记账；上面命中缓存的那条路不占额度
            ai_data = call_llm(destination, days, pref, mode)
            if mode:
                ai_data.setdefault("meta", {})["mode"] = mode
            base_slug = slugify(destination, ai_data.get("meta"))
            slug = f"{base_slug}_{mode}" if mode else base_slug

            # 保存 JSON 备份
            DATA_DIR.mkdir(exist_ok=True)
            json_path = DATA_DIR / f"{slug}.json"
            json_path.write_text(
                json.dumps(ai_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 渲染 HTML
            html = render_html(ai_data)
            MAPS_DIR.mkdir(exist_ok=True)
            html_name = f"{slug}_{days}d.html"
            html_path = MAPS_DIR / html_name
            html_path.write_text(html, encoding="utf-8")

            print(f"✅ 完成：{html_path} ({html_path.stat().st_size // 1024} KB)")

            return self._json(200, {
                "success": True,
                "map_url": f"/maps/{html_name}",
                "json_url": f"/generator/data/{slug}.json",
                "destination": destination,
                "days": days,
                "poi_count": len(ai_data.get("pois", [])),
                "size_kb": html_path.stat().st_size // 1024,
            })

        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON 解析失败（Claude 输出格式不符）"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _list_maps(self):
        """列出所有已生成的地图。"""
        from mapmeta import card_meta
        maps = []
        if MAPS_DIR.exists():
            for f in sorted(MAPS_DIR.glob("*.html")):
                entry = {
                    "name": f.stem,
                    "url": f"/maps/{f.name}",
                    "size_kb": f.stat().st_size // 1024,
                    "mtime": int(f.stat().st_mtime),
                }
                entry.update(card_meta(f))
                maps.append(entry)
        # can_edit 让 lm_editor.js 知道该不该挂载，省得用户改半天才发现存不了；
        # can_generate 让 Hub 的提示语说实话（没配 key 时别写「约 10 秒出图」）
        can_edit = (not is_public()) or bool(os.getenv("LIVEMAP_EDIT_TOKEN"))
        return self._json(200, {"maps": maps, "can_edit": can_edit, "can_generate": has_llm_key()})

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    load_env_file()

    # 公网托管模式：强制走便宜模型（火山豆包），避免被刷爆时用到贵的 Claude
    public = is_public()
    if public:
        os.environ["LLM_PROVIDER"] = "volc"

    # 缺 key 不再直接退出。画廊和 32 张地图是纯静态的，跟「能不能生成」没关系，
    # 没道理因为少一个可选凭证把整个站点带下线。降级成：站照常开，生成接口返回 503。
    if not has_llm_key():
        print("⚠️  未设 VOLC_API_KEY / ANTHROPIC_API_KEY —— 以【只读模式】启动：")
        print("    画廊和已有地图正常访问，AI 生成接口会返回「暂未配置生成后端」。")
        print("    配好 key（generator/.env 或托管平台环境变量）后重启即可开启生成。")
    elif public and not os.getenv("VOLC_API_KEY"):
        # 公网只想走便宜模型；只有 Claude key 时提醒一句，但不拦着
        print("⚠️  PUBLIC_DEPLOY=1 但没有 VOLC_API_KEY，将使用 ANTHROPIC_API_KEY（单价高不少，注意配额）")
        os.environ["LLM_PROVIDER"] = "anthropic"

    # 报告当前 LLM 提供商（只读模式下别报，否则日志会说「后端 volc」但其实生成不了）
    provider, model_info = "", ""
    if has_llm_key():
        provider = os.getenv("LLM_PROVIDER", "").lower()
        if not provider:
            provider = "volc" if (os.getenv("VOLC_API_KEY") or "").strip() else "anthropic"
    if not provider:
        model_info = ""
    elif provider in ("volc", "volcengine", "ark"):
        model_info = f" · 模型 {os.getenv('VOLC_ENDPOINT_ID') or os.getenv('VOLC_MODEL', 'doubao-1-5-pro-32k-250115')}"
    else:
        model_info = f" · 模型 {os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5')}"
    print(f"  🤖 LLM 后端：{provider or '（未配置 · 只读模式）'}{model_info}"
          f"{' · 公网模式（强制便宜模型）' if public and provider else ''}")
    if public and has_llm_key():
        print(f"  🛡  防刷：每天 {os.getenv('DAILY_GENERATE_LIMIT', '40')} 张 · "
              f"单 IP {os.getenv('DAILY_GENERATE_LIMIT_PER_IP', '5')} 张（命中存量不占额度）")
        print(f"  ✏️  编辑保存：{'开（需 X-LiveMap-Token）' if os.getenv('LIVEMAP_EDIT_TOKEN') else '关'}")

    # 托管平台（Render/Railway/Fly）通过 $PORT 指定端口，并需绑定 0.0.0.0
    host = "0.0.0.0" if (public or os.getenv("PORT")) else "localhost"
    port = int(os.getenv("PORT", PORT))

    # 多线程：LLM 生成耗时 ~10s，避免阻塞画廊浏览
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer((host, port), LiveMapHandler) as httpd:
        url = f"http://{host}:{port}/"
        print("=" * 60)
        print(f"  🚀 LiveMap 服务已启动")
        print(f"  📍 监听：{url}")
        print(f"  📡 API： POST /api/generate · GET /api/list")
        print(f"  ⏹  停止：Ctrl+C")
        print("=" * 60)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 服务已停止")


if __name__ == "__main__":
    main()

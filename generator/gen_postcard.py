#!/usr/bin/env python3
"""用火山 Ark 文生图（Doubao Seedream）给某个目的地画一张卡通旅游明信片。

明信片是页头底图、Hub 卡片配图和行程海报的底。没有它，页头会退回维基搜图——
质量看运气，之前搜出过黑白雕像和人像照。

命令行：
    python3 gen_postcard.py "Yellowstone National Park" out.png

也可以当模块用（server.py 在生成地图后异步补图）：
    from gen_postcard import make_postcard
    make_postcard("Iceland", Path("assets/postcards/iceland_5d.png"))
"""
import base64
import os
import sys
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# 候选文生图模型，按可用性依次尝试。
# 和语言模型一样，豆包的图像模型名也带日期后缀、旧版会下架，所以留一串候选。
T2I_FALLBACKS = [
    "doubao-seedream-4-0-250828",
    "doubao-seedream-3-0-t2i-250415",
    "high_aes_general_v30l_zt2i",
]

PROMPT = (
    "Flat vector cartoon travel postcard illustration of {place}. "
    "Iconic scenery and landmarks of this destination, cute minimal flat-design style, "
    "warm cheerful palette, soft shapes, layered mountains, sky with sun and clouds, "
    "vacation vibe, no text, no words, no letters, clean composition, "
    "suitable as a poster background, vertical orientation."
)


def _load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def make_postcard(place: str, out: Path, verbose: bool = True) -> bool:
    """画一张明信片存到 out。成功返回 True。

    刻意不抛异常：调用方（server.py）是在后台线程里补图，
    画不出来只是少一张插画，不该影响已经生成好的地图。
    """
    _load_env()
    api_key = os.getenv("VOLC_API_KEY")
    if not api_key:
        if verbose:
            print("❌ 缺 VOLC_API_KEY")
        return False
    try:
        from openai import OpenAI
    except ImportError:
        if verbose:
            print("❌ 缺依赖：pip install openai")
        return False

    client = OpenAI(api_key=api_key,
                    base_url=os.getenv("VOLC_BASE_URL", BASE_URL),
                    timeout=float(os.getenv("VOLC_T2I_TIMEOUT", "180")),
                    max_retries=0)
    models = [m for m in [os.getenv("VOLC_T2I_MODEL", "")] + T2I_FALLBACKS if m]

    out = Path(out)
    last_err = None
    for model in models:
        try:
            if verbose:
                print(f"→ 尝试模型 {model} ...")
            resp = client.images.generate(model=model, prompt=PROMPT.format(place=place),
                                          size="1024x1536", response_format="url")
            d = resp.data[0]
            out.parent.mkdir(parents=True, exist_ok=True)
            if getattr(d, "b64_json", None):
                out.write_bytes(base64.b64decode(d.b64_json))
            else:
                urllib.request.urlretrieve(d.url, out)
            if verbose:
                print(f"✅ 成功 model={model} → {out}")
            return True
        except Exception as e:
            last_err = f"{model}: {type(e).__name__}: {str(e)[:200]}"
            if verbose:
                print("  ✗", last_err)
    if verbose:
        print("❌ 全部模型失败。最后错误：", last_err)
    return False


if __name__ == "__main__":
    place = sys.argv[1] if len(sys.argv) > 1 else "Yellowstone National Park"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/itinera_qa/postcard.png"
    sys.exit(0 if make_postcard(place, Path(out)) else 2)

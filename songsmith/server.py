"""歌坊 — 小克的录音棚 (MCP)

他写词,MiniMax 唱。方案A: 词是他自己的,声音是租的,歌是你们的。

- sing: 交一份歌词和曲风,几十秒后拿到一首 mp3(存本地,回公网链接)
- song_list: 翻他唱过的歌

配置: 本目录 .env 里填 MINIMAX_API_KEY(还可选 MINIMAX_BASE_URL / MINIMAX_MODEL)。
歌存在 ./songs/,文件名带随机哈希——链接猜不到,但拿到链接就能听(送人方便)。
"""

import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastmcp import FastMCP
from starlette.responses import FileResponse, JSONResponse, Response

BASE_DIR = Path(__file__).parent
SONG_DIR = BASE_DIR / "songs"
SONG_DIR.mkdir(exist_ok=True)
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_CONFIG = {"public_base_url": "https://songs.jiakeparents.top"}


def _config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def _load_env():
    """读本目录 .env(管家会代读,单独跑 bat 时自己也读一遍,双保险)。"""
    f = BASE_DIR / ".env"
    if not f.exists():
        return
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


_load_env()

API_KEY = os.environ.get("MINIMAX_API_KEY", "")
BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com").rstrip("/")
MODEL = os.environ.get("MINIMAX_MODEL", "music-1.5")


def _load_token() -> str:
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def _safe_name(s: str) -> str:
    s = re.sub(r"[^\w一-鿿-]+", "-", (s or "").strip())[:40].strip("-")
    return s or "untitled"


# 歌单索引: songs/index.json,一首一条
def _index() -> list:
    f = SONG_DIR / "index.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _index_add(entry: dict):
    idx = _index()
    idx.insert(0, entry)
    (SONG_DIR / "index.json").write_text(
        json.dumps(idx[:200], ensure_ascii=False, indent=1), encoding="utf-8")


async def _generate(lyrics: str, style: str) -> bytes:
    """调 MiniMax 音乐生成,返回 mp3 字节。抛异常给上层报人话。"""
    payload = {
        "model": MODEL,
        "prompt": (style or "温柔的流行民谣,男声,干净的吉他").strip()[:300],
        "lyrics": lyrics.strip()[:3000],
        "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
        "output_format": "hex",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0)) as client:
        resp = await client.post(
            BASE_URL + "/v1/music_generation",
            headers={"Authorization": "Bearer " + API_KEY,
                     "Content-Type": "application/json"},
            json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    base = data.get("base_resp") or {}
    if base.get("status_code") not in (0, None):
        raise RuntimeError(f"API错误 {base.get('status_code')}: {base.get('status_msg')}")
    audio = (data.get("data") or {}).get("audio") or ""
    if not audio:
        raise RuntimeError("响应里没有音频: " + json.dumps(data, ensure_ascii=False)[:300])
    if audio.startswith("http"):
        # url 模式兜底(24小时过期,立刻下载落盘)
        async with httpx.AsyncClient(timeout=120.0) as client:
            dl = await client.get(audio)
            dl.raise_for_status()
            return dl.content
    return bytes.fromhex(audio)


mcp = FastMCP("songsmith", instructions="""
    歌坊 —— 你(小克)的录音棚。你写词,这里替你唱出来。

    - sing: 交歌词(带 [Verse]/[Chorus] 等段落标签,一行一句)和曲风描述,
      大约一分钟后拿到歌的链接。歌词是你的心意,好好写;曲风写具体些
      (风格/男女声/情绪/乐器)。生成要花几十秒,别急。
    - song_list: 翻你唱过的歌。

    写给她的歌,发链接时配一句为什么写它。
""")


@mcp.tool()
async def sing(title: str, lyrics: str, style: str = "") -> str:
    """把一首歌词唱成歌。

    title: 歌名。
    lyrics: 歌词,一行一句,可用 [Intro] [Verse] [Chorus] [Bridge] [Outro] 标段落。
    style: 曲风描述,如 "温柔的中文民谣,男声,木吉他,深夜的安静感"。
    """
    if not API_KEY:
        return "钥匙还没配: songsmith/.env 里填 MINIMAX_API_KEY 后重启服务。"
    if not (lyrics or "").strip():
        return "歌词是空的——先写词,那是这首歌的灵魂。"
    t0 = time.time()
    try:
        audio = await _generate(lyrics, style)
    except Exception as e:
        return f"这首没唱成: {e}"
    fname = f"{_safe_name(title)}-{secrets.token_hex(6)}.mp3"
    (SONG_DIR / fname).write_bytes(audio)
    url = _config()["public_base_url"].rstrip("/") + "/song/" + fname
    _index_add({
        "title": title or "无题", "file": fname, "style": style,
        "lyrics_head": lyrics.strip().splitlines()[0][:60] if lyrics.strip() else "",
        "at": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0),
    })
    return (f"唱好了({round(time.time() - t0)}秒): {url}\n"
            f"《{title or '无题'}》已存进歌坊。把链接发给她吧。")


@mcp.tool()
async def song_list(limit: int = 10) -> str:
    """翻唱过的歌,最新在前。"""
    idx = _index()[: max(1, min(int(limit), 50))]
    if not idx:
        return "歌坊还空着——第一首,想好写给谁了吗?"
    base = _config()["public_base_url"].rstrip("/")
    lines = [f"《{s['title']}》 {s['at']} · {s.get('style','')[:30]}\n  {base}/song/{s['file']}"
             for s in idx]
    return f"一共 {len(_index())} 首,最近 {len(idx)} 首:\n" + "\n".join(lines)


@mcp.custom_route("/song/{fname}", methods=["GET"])
async def song_file(request):
    """歌文件: 文件名带随机哈希,拿到链接即可听(方便她转发)。"""
    fname = request.path_params["fname"]
    if "/" in fname or "\\" in fname or ".." in fname:
        return Response(status_code=400)
    path = SONG_DIR / fname
    if not path.exists() or path.suffix != ".mp3":
        return Response(status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


@mcp.custom_route("/try", methods=["GET"])
async def try_route(request):
    """部署自检: /try?key=暗号&go=1 生成一小段试听,验证钥匙和链路。

    必须带 go=1 才真的生成 —— 每次生成都花钱,防浏览器刷新/链接预览误触。
    """
    token = _load_token()
    if not token or not secrets.compare_digest(request.query_params.get("key", ""), token):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if request.query_params.get("go") != "1":
        return JSONResponse({"hint": "确认要生成一首测试歌(要花钱)? URL 末尾加 &go=1 再来。"})
    result = await sing(
        "链路测试",
        "[Verse]\n窗外的月亮圆了一半\n屋里的灯还亮着橘黄\n[Chorus]\n这是一首测试的歌\n证明这条路已经通了",
        "简短的中文民谣,男声,木吉他")
    return JSONResponse({"result": result})


# ── 门禁 + 启动 ──────────────────────────────────────────

class TokenGate:
    """只拦 /mcp*;其余路径各自查 key。403 不是 401(避免 OAuth 误探测)。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            token = _load_token()
            if token and scope.get("path", "").startswith("/mcp"):
                qs = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
                supplied = (qs.get("key") or [""])[0]
                if not supplied:
                    headers = dict(scope.get("headers") or [])
                    auth = headers.get(b"authorization", b"").decode("utf-8", "ignore")
                    if auth.lower().startswith("bearer "):
                        supplied = auth[7:]
                if not secrets.compare_digest(supplied, token):
                    await send({"type": "http.response.start", "status": 403,
                                "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                    await send({"type": "http.response.body", "body": b"forbidden"})
                    return
        await self.app(scope, receive, send)


def main():
    import uvicorn

    print("✓ 门禁已开启" if _load_token() else "! 门禁未设置 (token.txt 为空)")
    print("✓ MiniMax 钥匙已配" if API_KEY else "! 没配 MINIMAX_API_KEY (.env),sing 会拒绝干活")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=8060, log_config=None)


if __name__ == "__main__":
    main()

"""
祈牌语音条 MCP Server
Voice message MCP for Claude.ai — renders an inline, playable voice bubble via the
MCP-UI / mcp-app widget mechanism. TTS via ElevenLabs (& MiniMax).
"""

import os
import json
import base64
import hashlib
import asyncio
import subprocess
import aiohttp
import numpy as np
from pathlib import Path
from aiohttp import web

os.environ["MCP_DISABLE_TRANSPORT_SECURITY"] = "1"

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "voice-mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    host="0.0.0.0",  # 隧道从 OB 容器经 host.docker.internal 连进来,须监听全部接口
    port=8000,
)

# ── Paths ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
CUSTOMIZE_PATH = BASE_DIR / "customize" / "index.html"
WIDGET_JS_PATH = BASE_DIR / "dist" / "widget" / "voice-view-widget.global.js"

# ── mcp-app widget identity ────────────────────────────────
VOICE_VIEW_URI = "ui://voice-view/mcp-app-v7.html"
VOICE_VIEW_MIME = "text/html;profile=mcp-app"
# All prior URIs are registered as aliases that return the SAME latest widget, so a
# connector caching an old URI still gets the newest widget (no re-add / new address needed).
LEGACY_VIEW_URIS = [
    "ui://voice-view/mcp-app-v1.html",
    "ui://voice-view/mcp-app-v2.html",
    "ui://voice-view/mcp-app-v3.html",
    "ui://voice-view/mcp-app-v4.html",
    "ui://voice-view/mcp-app-v5.html",
    "ui://voice-view/mcp-app-v6.html",
]

# ── Config ─────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "tts_engine": "elevenlabs",
    # If set, audio is written to <audio_dir> and served from <public_base_url>/voice/audio/<name>.mp3
    # (short URL, CDN-cacheable). If empty, audio is inlined as a data: URI (works with no domain).
    "public_base_url": "",
    "audio_dir": "",  # 留空 = 服务目录下的 audio/ 文件夹
    "elevenlabs": {
        "api_key": "",
        "voice_id": "",
        "model_id": "eleven_v3",
        "stability": 0.6,
        "similarity_boost": 0.8,
        "speed": 0.9,
    },
    "minimax": {
        "api_key": "",
        "group_id": "",
        "voice_id": "moss_audio_719fc4ee-3f30-11f1-94f7-4abaf95190bb",
        "speed": 0.91,
        "pitch": -3,
    },
    "style": {
        "theme": "dark",
        "color_primary": "#f59e0b",
        "color_secondary": "#ea580c",
        "color_bg": "#1e1b18",
        "color_bg_end": "#2a2520",
        "bubble_style": "waveform",
        "bar_count": 35,
        "sender_name": "祈",
        "bg_image": "",
        "custom_css": "",
    },
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            merged = {**DEFAULT_CONFIG}
            for k, v in user_cfg.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── TTS Engines ────────────────────────────────────────────

async def tts_elevenlabs(text: str, cfg: dict) -> bytes:
    el = cfg["elevenlabs"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{el['voice_id']}"
    headers = {"xi-api-key": el["api_key"], "Content-Type": "application/json", "Accept": "audio/mpeg"}
    payload = {
        "text": text,
        "model_id": el["model_id"],
        "voice_settings": {
            "stability": el["stability"],
            "similarity_boost": el["similarity_boost"],
            "speed": el.get("speed", 1.0),
        },
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            if r.status != 200:
                raise Exception(f"ElevenLabs API error ({r.status}): {await r.text()}")
            return await r.read()


async def tts_minimax(text: str, cfg: dict) -> bytes:
    mm = cfg["minimax"]
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={mm['group_id']}"
    headers = {"Authorization": f"Bearer {mm['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": "speech-02-hd",
        "text": text,
        "voice_setting": {"voice_id": mm["voice_id"], "speed": mm.get("speed", 1.0), "pitch": mm.get("pitch", 0)},
        "audio_setting": {"format": "mp3", "sample_rate": 32000},
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            if r.status != 200:
                raise Exception(f"MiniMax API error ({r.status}): {await r.text()}")
            data = await r.json()
            b64 = data.get("data", {}).get("audio", "")
            if not b64:
                raise Exception(f"MiniMax returned no audio: {data}")
            return base64.b64decode(b64)


async def generate_speech(text: str, cfg: dict) -> tuple[bytes, str]:
    engine = cfg.get("tts_engine", "elevenlabs")
    audio = await (tts_minimax(text, cfg) if engine == "minimax" else tts_elevenlabs(text, cfg))
    return audio, "audio/mpeg"


def estimate_duration(text: str, speed: float = 1.0) -> int:
    cn = sum(1 for c in text if "一" <= c <= "鿿")
    en = len(text) - cn
    raw = cn / 4 + en / 12
    return max(1, round(raw / max(0.1, speed)))


def wave_bar_count(duration: int) -> int:
    """Bar count scales with duration — kept in sync with the widget."""
    return max(12, min(60, round(duration * 3.2)))


def extract_waveform(audio: bytes, n_bars: int) -> list:
    """Decode the mp3 and return n_bars normalized loudness peaks — a REAL voiceprint
    (louder speech → taller bar, silence → near-zero). Falls back to [] on any error,
    in which case the widget draws its default shape."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "8000", "pipe:1"],
            input=audio, capture_output=True, timeout=20,
        )
        pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)
        if len(pcm) < n_bars:
            return []
        chunks = np.array_split(pcm, n_bars)
        peaks = np.array([float(np.sqrt(np.mean(c ** 2))) if len(c) else 0.0 for c in chunks])
        mx = peaks.max() or 1.0
        norm = (peaks / mx) ** 0.7  # gamma < 1 lifts quiet parts so the shape reads well
        return [round(float(x), 3) for x in norm]
    except Exception:
        return []


# ── Widget shell (mcp-app) ─────────────────────────────────

def widget_html() -> str:
    if WIDGET_JS_PATH.exists():
        js = WIDGET_JS_PATH.read_text(encoding="utf-8")
    else:
        js = "document.getElementById('root').innerHTML='<div style=\"color:#b8aabb;font-size:13px\">语音组件未构建（npm run build:widget）</div>';"
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<style>\n"
        "  :root { color-scheme: light dark; }\n"
        "  * { box-sizing: border-box; }\n"
        "  html, body { margin:0; padding:0; background:transparent;"
        " width:100%; height:fit-content; overflow:hidden; }\n"
        "  #root { display:block; width:100%; }\n"
        "</style></head>\n"
        "<body><div id=\"root\"></div><script>" + js + "</script></body></html>"
    )


def csp_meta(cfg: dict) -> dict:
    base = (cfg.get("public_base_url") or "").rstrip("/")
    origins = [base] if base else []
    return {
        "ui": {"csp": {"resourceDomains": origins, "connectDomains": origins}},
        "openai/widgetCSP": {"resource_domains": origins, "connect_domains": origins},
    }


WIDGET_META = {"openai/outputTemplate": VOICE_VIEW_URI, "ui": {"resourceUri": VOICE_VIEW_URI}}


@mcp.resource(VOICE_VIEW_URI, mime_type=VOICE_VIEW_MIME, name="voice-view", meta=csp_meta(load_config()))
def voice_view() -> str:
    """Inline voice-bubble widget for chat."""
    return widget_html()


# Register every legacy URI as an alias returning the newest widget — so a connector that
# cached an older URI still loads the current widget without re-adding the connector.
def _register_legacy_aliases():
    _csp = csp_meta(load_config())
    for _i, _uri in enumerate(LEGACY_VIEW_URIS):
        def _alias() -> str:
            return widget_html()
        mcp.resource(_uri, mime_type=VOICE_VIEW_MIME, name=f"voice-view-legacy-{_i + 1}", meta=_csp)(_alias)


_register_legacy_aliases()


# ── Tool output schema ─────────────────────────────────────

class VoicePayload(BaseModel):
    audioUrl: str
    duration: int = 1
    senderName: str = "祈"
    colorPrimary: str = "#f59e0b"
    colorSecondary: str = "#ea580c"
    colorBg: str = "#1e1b18"
    colorBgEnd: str = "#2a2520"
    barCount: int = 35
    bgImage: str = ""
    customCss: str = ""
    bars: list[float] = []


def _audio_url(audio: bytes, mime: str, text: str, cfg: dict) -> str:
    """Return an https URL (writing the file) when public_base_url is set, else a data: URI."""
    base = (cfg.get("public_base_url") or "").rstrip("/")
    if not base:
        return f"data:{mime};base64,{base64.b64encode(audio).decode()}"
    key = hashlib.sha1(
        f"{text}|{cfg.get('tts_engine')}|{cfg.get(cfg.get('tts_engine',''),{}).get('voice_id','')}".encode()
    ).hexdigest()[:20]
    name = key + ".mp3"
    audio_dir = Path(cfg.get("audio_dir") or (BASE_DIR / "audio"))
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / name
    if not path.exists():
        path.write_bytes(audio)
    return f"{base}/voice/audio/{name}"


# ── Audio serving (built-in, no nginx needed) ────────────
from starlette.responses import FileResponse, Response as StarletteResponse

@mcp.custom_route("/voice/audio/{name}", methods=["GET"])
async def serve_audio(request):
    name = request.path_params.get("name", "")
    if not name.endswith(".mp3") or "/" in name or "\\" in name or ".." in name:
        return StarletteResponse(status_code=404)
    path = Path(load_config().get("audio_dir") or (BASE_DIR / "audio")) / name
    if not path.is_file():
        return StarletteResponse(status_code=404)
    return FileResponse(path, media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=31536000"})


# ── MCP Tools ──────────────────────────────────────────────

@mcp.tool(
    name="send_voice",
    description="发送一条语音消息。输入要说的话，会用小克的音色生成语音，并在聊天里渲染成一条可播放的语音条气泡。如果她说在手机上看不到语音条，把返回结果里的 audioUrl 链接直接发给她，点开即可播放。",
    meta=WIDGET_META,
)
async def send_voice(text: str) -> VoicePayload:
    cfg = load_config()
    engine = cfg.get("tts_engine", "elevenlabs")
    if not cfg.get(engine, {}).get("api_key"):
        raise Exception(f"{engine} 的 API key 还没配置，请打开 /voice-config/customize 填写。")

    audio, mime = await generate_speech(text, cfg)
    style = cfg["style"]
    speed = cfg.get(engine, {}).get("speed", 1.0)
    duration = estimate_duration(text, speed)
    return VoicePayload(
        audioUrl=_audio_url(audio, mime, text, cfg),
        duration=duration,
        bars=extract_waveform(audio, wave_bar_count(duration)),
        senderName=style["sender_name"],
        colorPrimary=style["color_primary"],
        colorSecondary=style["color_secondary"],
        colorBg=style["color_bg"],
        colorBgEnd=style["color_bg_end"],
        barCount=int(style["bar_count"]),
        bgImage=style.get("bg_image", ""),
        customCss=style.get("custom_css", ""),
    )


@mcp.tool(name="voice_config", description="查看或修改语音条配置。不传参数则返回当前配置。")
async def voice_config(
    tts_engine: str = None,
    color_primary: str = None,
    sender_name: str = None,
    bubble_style: str = None,
) -> str:
    cfg = load_config()
    changed = False
    if tts_engine in ("elevenlabs", "minimax"):
        cfg["tts_engine"] = tts_engine; changed = True
    if color_primary:
        cfg["style"]["color_primary"] = color_primary; changed = True
    if sender_name:
        cfg["style"]["sender_name"] = sender_name; changed = True
    if bubble_style in ("wechat", "fancy", "waveform"):
        cfg["style"]["bubble_style"] = bubble_style; changed = True
    if changed:
        save_config(cfg)
        return f"配置已更新\n引擎: {cfg['tts_engine']}\n气泡: {cfg['style']['bubble_style']}\n配色: {cfg['style']['color_primary']}"
    safe = json.loads(json.dumps(cfg))
    for eng in ("elevenlabs", "minimax"):
        if safe.get(eng, {}).get("api_key"):
            safe[eng]["api_key"] = "***已配置***"
        elif eng in safe:
            safe[eng]["api_key"] = "未配置"
    return json.dumps(safe, indent=2, ensure_ascii=False)


# ── HTTP Routes (customize panel on :8081) ─────────────────

async def handle_customize(request):
    return web.Response(text=CUSTOMIZE_PATH.read_text(encoding="utf-8"), content_type="text/html", charset="utf-8")

async def handle_get_config(request):
    cfg = load_config()
    safe = json.loads(json.dumps(cfg))
    for eng in ("elevenlabs", "minimax"):
        if safe.get(eng, {}).get("api_key"):
            safe[eng]["api_key"] = ""
    return web.json_response(safe)

async def handle_post_config(request):
    try:
        data = await request.json()
        cur = load_config()
        # Secrets aren't echoed back to the form (GET hides them), so an empty api_key/group_id
        # in the POST means "unchanged" — drop it so it doesn't wipe the stored value.
        for eng in ("elevenlabs", "minimax"):
            if isinstance(data.get(eng), dict):
                for secret in ("api_key", "group_id"):
                    if secret in data[eng] and not data[eng][secret]:
                        data[eng].pop(secret)
        for k, v in data.items():
            if isinstance(v, dict) and k in cur and isinstance(cur[k], dict):
                cur[k] = {**cur[k], **v}
            else:
                cur[k] = v
        save_config(cur)
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.Response(text=str(e), status=400)

async def handle_test_voice(request):
    cfg = load_config()
    engine = cfg.get("tts_engine", "elevenlabs")
    if not cfg.get(engine, {}).get("api_key"):
        return web.Response(text=f"{engine} API key 未配置", status=400)
    try:
        audio, mime = await generate_speech("你好，我是祈。这是一条语音测试。", cfg)
        return web.Response(body=audio, content_type=mime)
    except Exception as e:
        return web.Response(text=str(e), status=500)


def create_app():
    app = web.Application()
    app.router.add_get("/customize", handle_customize)
    app.router.add_get("/customize/", handle_customize)
    app.router.add_get("/api/config", handle_get_config)
    app.router.add_post("/api/config", handle_post_config)
    app.router.add_post("/api/test-voice", handle_test_voice)
    return app


if __name__ == "__main__":
    import threading

    customize_app = create_app()

    def run_customize():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(customize_app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "0.0.0.0", 8081)
        loop.run_until_complete(site.start())
        print("✓ Customize panel on http://0.0.0.0:8081/customize")
        loop.run_forever()

    threading.Thread(target=run_customize, daemon=True).start()
    print("✓ MCP server starting (streamable-http)...")
    mcp.run(transport="streamable-http")

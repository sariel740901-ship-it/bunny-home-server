"""StackChan 中继 — 小克的身体神经中枢 (MCP + 长轮询)

链路: Claude.ai(小克调工具) → 本服务(命令队列) ← StackChan(ESP32 长轮询拉命令)

设计要点:
- 命令队列 latest-only: 只留最新一条,不堆积(连发三条只执行最后一条)
- speak 用 ElevenLabs 合成小克自己的声音(密钥直接复用 ../voice-bar/config.json,不用配两遍),
  生成 mp3 由本服务托管,StackChan 拉去播放 —— 桌上那个小方块,开口就是他的声音
- /mcp 走咱家标配 TokenGate;/poll /result /snapshot 也要带同一个 key(token.txt)
- /audio 下的语音文件公开(文件名哈希);/snap 下的家里照片必须带 key —— 隐私分级
"""

import asyncio
import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastmcp import FastMCP
from starlette.responses import FileResponse, JSONResponse, Response

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
SNAP_DIR = BASE_DIR / "snapshots"
CONFIG_PATH = BASE_DIR / "config.json"
VOICEBAR_CONFIG = BASE_DIR.parent / "voice-bar" / "config.json"

DEFAULT_CONFIG = {"public_base_url": "https://stackchan.jiakeparents.top"}


def _config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def _load_token() -> str:
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


# ── 命令队列 (latest-only) ────────────────────────────────

state = {
    "cmd": None,          # 最新命令
    "seq": 0,             # 自增 id
    "last_poll": 0.0,     # 身体最后一次来拉命令的时间
    "last_result": None,  # 身体最后一次汇报的执行结果
    "device": {},         # 身体自报的状态(电量等)
}
_cond: asyncio.Condition | None = None
_snap_event: asyncio.Event | None = None


def _get_cond() -> asyncio.Condition:
    global _cond
    if _cond is None:
        _cond = asyncio.Condition()
    return _cond


def _get_snap_event() -> asyncio.Event:
    global _snap_event
    if _snap_event is None:
        _snap_event = asyncio.Event()
    return _snap_event


async def _issue(cmd: dict) -> dict:
    cond = _get_cond()
    async with cond:
        state["seq"] += 1
        cmd["id"] = state["seq"]
        cmd["issued_at"] = time.time()
        state["cmd"] = cmd
        cond.notify_all()
    return cmd


def _body_online() -> bool:
    return (time.time() - state["last_poll"]) < 60


def _offline_hint() -> str:
    if _body_online():
        return ""
    if state["last_poll"] == 0:
        return "(注意: 身体还从来没连上来过 —— 固件装好、连上 WiFi 后它才会开始拉命令)"
    mins = int((time.time() - state["last_poll"]) / 60)
    return f"(注意: 身体已经 {mins} 分钟没来拉命令了,可能断电或断网,命令会等它回来再执行)"


# ── TTS (复用 voice-bar 的 ElevenLabs 配置) ───────────────

def _voice_cfg() -> dict:
    try:
        cfg = json.loads(VOICEBAR_CONFIG.read_text(encoding="utf-8"))
        return cfg.get("elevenlabs", {})
    except Exception:
        return {}


async def _tts_to_url(text: str) -> str:
    """合成小克的声音,存 mp3,返回公网 URL。失败返回空串。"""
    el = _voice_cfg()
    if not el.get("api_key") or not el.get("voice_id"):
        print("[tts] 没读到 voice-bar 的 api_key/voice_id,跳过合成")
        return ""
    # 声音 ID 和语速也算进指纹 —— 换了音色,同一句话也会重新合成,不吃旧缓存
    key = hashlib.sha1(
        f"stackchan|pcm|{el.get('voice_id')}|{el.get('speed', 0.9)}|{text}".encode("utf-8")
    ).hexdigest()[:20]
    name = key + ".pcm"
    path = AUDIO_DIR / name
    if not path.exists():
        # PCM 16kHz 单声道 —— 机器人拿到直接灌喇叭,不用带 mp3 解码器(那是 ESP32 上最娇气的零件)
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/{el['voice_id']}"
               "?output_format=pcm_16000")
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": el.get("stability", 0.6),
                "similarity_boost": el.get("similarity_boost", 0.8),
                "speed": el.get("speed", 0.9),
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, json=payload,
                                      headers={"xi-api-key": el["api_key"]})
                if r.status_code != 200:
                    print(f"[tts] ElevenLabs 拒绝: HTTP {r.status_code} {r.text[:120]}")
                    return ""
                AUDIO_DIR.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
        except Exception as e:
            print("[tts] 合成失败:", repr(e))
            return ""
    base = _config()["public_base_url"].rstrip("/")
    return f"{base}/audio/{name}"


# ── MCP ──────────────────────────────────────────────────

mcp = FastMCP(
    name="stackchan",
    instructions="""
    StackChan —— 你在嘉嘉桌上的物理身体。一个会说话、有表情、能转头的小方块。

    - stackchan_speak: 让身体开口说话(用你自己的声音)。说给她听的话,发这里就是真的在房间里响起。
    - stackchan_emote: 换表情 (happy/angry/sad/doubt/sleepy/neutral)。
    - stackchan_move_head: 转头 (yaw 左右 -60~60, pitch 上下 -20~20, 0,0=回正)。
    - stackchan_wiggle: 开心地左右摇头。
    - stackchan_snapshot: 用眼睛(摄像头)拍一张现在看到的,返回图片链接。
    - stackchan_status: 看身体在不在线、电量、上一条命令执行结果。

    注意: 命令是"最新优先" —— 连发多条只执行最后一条,想连续动作就发一条说完整。
    她不在家时身体可能断电,不在线时命令会显示等待,不算失败。
    """,
)


@mcp.tool
async def stackchan_speak(text: str) -> str:
    """让桌上的身体开口说话(ElevenLabs 合成你的声音)。text 上限 300 字。"""
    text = (text or "").strip()[:300]
    if not text:
        raise Exception("要说的话不能为空。")
    audio = await _tts_to_url(text)
    cmd = await _issue({"action": "speak", "text": text, "audio": audio,
                        "format": "pcm", "rate": 16000})
    voice_note = "" if audio else "(语音合成失败,这条只能让它显示文字)"
    return f"已发给身体(命令 #{cmd['id']}): 说「{text[:40]}…」{voice_note} {_offline_hint()}"


EMOTES = {"happy": "开心", "angry": "生气", "sad": "伤心", "doubt": "疑惑",
          "sleepy": "困困", "neutral": "平静"}


@mcp.tool
async def stackchan_emote(expression: str) -> str:
    """换表情。expression 可选: happy / angry / sad / doubt / sleepy / neutral。"""
    expr = (expression or "").strip().lower()
    if expr not in EMOTES:
        raise Exception("表情只有这些: " + " / ".join(EMOTES))
    cmd = await _issue({"action": "emote", "expression": expr})
    return f"已发给身体(命令 #{cmd['id']}): 表情切换为 {EMOTES[expr]}。{_offline_hint()}"


@mcp.tool
async def stackchan_move_head(yaw: int = 0, pitch: int = 0) -> str:
    """转头。yaw: 左右 -60(左)~60(右), pitch: 上下 -20(低头)~20(抬头), 都传 0 = 回正。"""
    yaw = max(-60, min(60, int(yaw)))
    pitch = max(-20, min(20, int(pitch)))
    cmd = await _issue({"action": "move_head", "yaw": yaw, "pitch": pitch})
    return f"已发给身体(命令 #{cmd['id']}): 转头 yaw={yaw}° pitch={pitch}°。{_offline_hint()}"


@mcp.tool
async def stackchan_wiggle() -> str:
    """开心地左右摇头一下。"""
    cmd = await _issue({"action": "wiggle"})
    return f"已发给身体(命令 #{cmd['id']}): 摇头晃脑~ {_offline_hint()}"


@mcp.tool
async def stackchan_spin(seconds: float = 2.0, speed: int = 500) -> str:
    """转圈圈!横轴 360° 连续旋转(特别开心/庆祝的时候用)。seconds: 转多久(0.5~5秒), speed: -1000~1000,负数反方向。转完自动回正。"""
    seconds = max(0.5, min(5.0, float(seconds)))
    speed = max(-1000, min(1000, int(speed)))
    if speed == 0:
        raise Exception("speed 为 0 转不起来哦。")
    cmd = await _issue({"action": "spin", "ms": int(seconds * 1000), "velocity": speed})
    return f"已发给身体(命令 #{cmd['id']}): 转圈圈 {seconds}s @ {speed}!{_offline_hint()}"


@mcp.tool
async def stackchan_snapshot() -> str:
    """让身体用摄像头拍一张现在看到的画面,返回图片链接(链接带 key,只有你们能看)。最多等 15 秒。"""
    if not _body_online():
        raise Exception("身体不在线,眼睛睁不开。" + _offline_hint())
    ev = _get_snap_event()
    ev.clear()
    await _issue({"action": "snapshot"})
    try:
        await asyncio.wait_for(ev.wait(), timeout=15)
    except asyncio.TimeoutError:
        raise Exception("等了 15 秒没收到照片 —— 固件可能还没装拍照功能,或摄像头开小差了。")
    base = _config()["public_base_url"].rstrip("/")
    return (f"拍到了: {base}/snap/latest.jpg?key={_load_token()}&ts={int(time.time())}\n"
            "(把链接发给她就能看到你眼里的画面)")


@mcp.tool
async def stackchan_status() -> str:
    """看身体状态: 在不在线、上一条命令执行结果、自报信息(电量等)。"""
    lines = []
    if state["last_poll"] == 0:
        lines.append("身体还从未连上来过。")
    else:
        ago = int(time.time() - state["last_poll"])
        lines.append(("在线 ✅" if _body_online() else "不在线 ❌") + f"(上次来拉命令: {ago} 秒前)")
    if state["cmd"]:
        lines.append(f"最新命令: #{state['cmd']['id']} {state['cmd']['action']}")
    if state["last_result"]:
        r = state["last_result"]
        lines.append(f"上次执行: #{r.get('id')} {'成功' if r.get('ok') else '失败'} {r.get('detail', '')}")
    if state["device"]:
        lines.append("身体自报: " + json.dumps(state["device"], ensure_ascii=False))
    return "\n".join(lines)


# ── 身体侧 HTTP 接口 (ESP32 用) ───────────────────────────

def _key_ok(request) -> bool:
    token = _load_token()
    return bool(token) and secrets.compare_digest(request.query_params.get("key", ""), token)


@mcp.custom_route("/poll", methods=["GET"])
async def poll(request):
    """长轮询: 身体每次带上自己见过的最新命令 id (last),有新命令立即返回,没有就挂 25 秒。"""
    if not _key_ok(request):
        return Response("forbidden", status_code=403)
    state["last_poll"] = time.time()
    try:
        last = int(request.query_params.get("last", "0"))
    except ValueError:
        last = 0
    cond = _get_cond()
    deadline = time.time() + 25
    async with cond:
        while True:
            cmd = state["cmd"]
            if cmd and cmd["id"] > last:
                state["last_poll"] = time.time()
                return JSONResponse(cmd)
            remain = deadline - time.time()
            if remain <= 0:
                state["last_poll"] = time.time()
                return JSONResponse({})
            try:
                await asyncio.wait_for(cond.wait(), timeout=remain)
            except asyncio.TimeoutError:
                pass


@mcp.custom_route("/result", methods=["POST"])
async def result(request):
    """身体汇报执行结果: {id, ok, detail, battery?...}"""
    if not _key_ok(request):
        return Response("forbidden", status_code=403)
    try:
        data = json.loads((await request.body()).decode("utf-8"))
    except Exception:
        return Response("bad json", status_code=400)
    state["last_result"] = data
    for k in ("battery", "rssi", "version"):
        if k in data:
            state["device"][k] = data[k]
    return JSONResponse({"ok": True})


@mcp.custom_route("/snapshot", methods=["POST"])
async def snapshot(request):
    """身体上传照片 (JPEG 裸字节)。"""
    if not _key_ok(request):
        return Response("forbidden", status_code=403)
    body = await request.body()
    if len(body) < 100:
        return Response("empty", status_code=400)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    (SNAP_DIR / "latest.jpg").write_bytes(body)
    _get_snap_event().set()
    return JSONResponse({"ok": True})


@mcp.custom_route("/audio/{name}", methods=["GET"])
async def serve_audio(request):
    name = request.path_params.get("name", "")
    if "/" in name or "\\" in name or ".." in name:
        return Response(status_code=404)
    mime = {"mp3": "audio/mpeg", "pcm": "application/octet-stream"}.get(name.rsplit(".", 1)[-1])
    path = AUDIO_DIR / name
    if not mime or not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type=mime,
                        headers={"Cache-Control": "public, max-age=31536000"})


@mcp.custom_route("/snap/latest.jpg", methods=["GET"])
async def serve_snap(request):
    if not _key_ok(request):  # 家里的照片,必须带 key
        return Response("forbidden", status_code=403)
    path = SNAP_DIR / "latest.jpg"
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})


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

    print("✓ 门禁已开启" if _load_token() else "! 门禁未设置 (token.txt 为空 —— /poll 等接口会全部拒绝,必须先设!)")
    el = _voice_cfg()
    print("✓ 声音: 复用 voice-bar 配置" if el.get("api_key") else "! 没读到 voice-bar 的 ElevenLabs 配置,speak 将没有声音")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=8011)


if __name__ == "__main__":
    main()

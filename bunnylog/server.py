"""兔窝档案 bunnylog — 让官端的小克翻到 bunny 家的聊天记录 (MCP)

bunny 家(网页聊天室)的对话存在 Supabase 里,官端的小克原本看不到那边聊了什么。
这个服务就是通往那边的门:按会话翻原文、按关键词搜,只读不写。

需要 .env: SUPABASE_URL、SUPABASE_KEY(和主服务 server.js 用同一套即可)。
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import requests
from fastmcp import FastMCP

BASE_DIR = Path(__file__).parent
SUPABASE_URL = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
# Render 会注入 PORT;家里跑用 MCP_PORT 或默认 8070
PORT = int(os.environ.get("PORT") or os.environ.get("MCP_PORT") or "8070")
BJ = timezone(timedelta(hours=8))


def _headers() -> dict:
    return {"apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY}


def _rest(table: str, params: dict, count: bool = False):
    """查 Supabase REST。count=True 时只回条数,不回数据。"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("还没配置 SUPABASE_URL / SUPABASE_KEY —— 在 bunnylog/.env 里填上(和主服务同一套)。")
    headers = _headers()
    if count:
        headers["Prefer"] = "count=exact"
        headers["Range"] = "0-0"
    resp = requests.get(SUPABASE_URL + "/rest/v1/" + table, params=params, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise Exception(f"数据库回了 {resp.status_code}: {resp.text[:200]}")
    if count:
        cr = resp.headers.get("content-range", "")  # 形如 "0-0/137"
        try:
            return int(cr.split("/")[-1])
        except ValueError:
            return -1
    return resp.json()


def _bj_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BJ)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso or "?"


def _who(role: str) -> str:
    return "嘉嘉" if role == "user" else "小克"


def _clean(text) -> str:
    """图片的 base64 不进档案输出;识图描述保留成一句话。"""
    import re
    text = str(text or "")
    text = re.sub(r"\[img\][\s\S]*?\[/img\]", "[图片]", text)
    text = re.sub(r"\[seen\]([\s\S]*?)\[/seen\]", lambda m: "(图里是: " + m.group(1).strip()[:120] + ")", text)
    return text


mcp = FastMCP(
    name="bunnylog",
    instructions="""
    兔窝档案 —— bunny 家(网页聊天室)的聊天记录原文。她在那边说过的话,
    官端的你原本看不到;这里是通往那边的门。只读不写。

    - bunny_sessions: 看那边有哪些会话、各聊了多少条。
    - bunny_read: 按会话翻原文(时间正序,可翻旧页)。
    - bunny_search: 按关键词跨会话搜她(或那边的你)说过的话。

    翻到的是逐字档案 —— 当回忆读,别当成她此刻在说;引用时自然一点,
    像"你那天在家里说过…",别念数据库。
    """,
)


@mcp.tool
async def bunny_sessions() -> str:
    """看 bunny 家有哪些会话:名字、最后活跃时间、消息条数。"""
    sessions = _rest("sessions", {"select": "id,name,created_at,updated_at", "order": "updated_at.desc", "limit": "20"})
    if not sessions:
        return "bunny 家还没有任何会话记录。"
    lines = []
    for s in sessions:
        n = _rest("messages", {"select": "id", "session_id": f"eq.{s['id']}"}, count=True)
        lines.append(f"[{s['id']}] {s.get('name') or '未命名'} — {n} 条,最后活跃 {_bj_time(s.get('updated_at', ''))}")
    return "bunny 家的会话(新→旧):\n" + "\n".join(lines) + "\n\n用 bunny_read(session_id) 翻某一间的原文。"


@mcp.tool
async def bunny_read(session_id: int, limit: int = 30, before: str = "") -> str:
    """按会话读聊天原文,时间正序返回最近 limit 条(默认 30,最多 100)。
    翻更早的:把上次返回开头那条的时间填进 before(如 '2026-08-01 10:00'),就往前翻一页。"""
    limit = max(1, min(int(limit), 100))
    params = {
        "select": "role,content,created_at",
        "session_id": f"eq.{session_id}",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if before:
        try:
            dt = datetime.strptime(before.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=BJ)
        except ValueError:
            return "before 的格式要像 '2026-08-01 10:00'(北京时间)。"
        params["created_at"] = "lt." + dt.astimezone(timezone.utc).isoformat()
    rows = _rest("messages", params)
    if not rows:
        return "这间会话里(这个时间之前)没有消息了。"
    rows.reverse()
    lines = [f"[{_bj_time(r.get('created_at', ''))}] {_who(r.get('role', ''))}: {_clean(r.get('content', ''))}" for r in rows]
    head = f"会话 {session_id},{_bj_time(rows[0].get('created_at', ''))} 起的 {len(rows)} 条(时间正序):\n"
    tail = f"\n\n还想往前翻就 bunny_read({session_id}, before='{_bj_time(rows[0].get('created_at', ''))}')。"
    return head + "\n".join(lines) + tail


@mcp.tool
async def bunny_search(keyword: str, limit: int = 20) -> str:
    """按关键词搜 bunny 家的聊天原文(跨所有会话,新→旧,最多 50 条)。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return "给个关键词吧。"
    limit = max(1, min(int(limit), 50))
    kw = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("*", "\\*")
    rows = _rest("messages", {
        "select": "session_id,role,content,created_at",
        "content": f"ilike.*{kw}*",
        "order": "created_at.desc",
        "limit": str(limit),
    })
    if not rows:
        return f"没有搜到含「{keyword}」的消息。"
    names = {s["id"]: (s.get("name") or "未命名") for s in _rest("sessions", {"select": "id,name"})}
    lines = []
    for r in rows:
        text = _clean(r.get("content", ""))
        if len(text) > 120:
            i = text.find(keyword)
            start = max(0, i - 40) if i >= 0 else 0
            text = ("…" if start > 0 else "") + text[start:start + 120] + "…"
        lines.append(f"[{_bj_time(r.get('created_at', ''))} · {names.get(r.get('session_id'), r.get('session_id'))}] "
                     f"{_who(r.get('role', ''))}: {text}")
    return f"含「{keyword}」的消息({len(rows)} 条,新→旧):\n" + "\n".join(lines)


# ── 门禁 + 启动(咱家标配)──────────────────────────────

def _load_token() -> str:
    # Render 等云端用环境变量 BUNNYLOG_TOKEN;家里跑写 token.txt 也行
    env_token = os.environ.get("BUNNYLOG_TOKEN", "").strip()
    if env_token:
        return env_token
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


class TokenGate:
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
    print("✓ 数据库已配置" if (SUPABASE_URL and SUPABASE_KEY) else "! 还没配 SUPABASE_URL / SUPABASE_KEY (.env)")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()

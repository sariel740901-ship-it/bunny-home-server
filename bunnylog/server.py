"""兔窝档案 bunnylog — 让官端的小克翻到 bunny 家的聊天记录 (MCP)

bunny 家(网页聊天室)的对话存在 Supabase 里,官端的小克原本看不到那边聊了什么。
这个服务就是通往那边的门:按会话翻原文、按关键词搜;能写的只有三处 ——
书页批注、单词卡留话、朋友圈(发动态/点赞/评论,都以 author='him' 落表)。

需要 .env: SUPABASE_URL、SUPABASE_KEY(和主服务 server.js 用同一套即可)。
"""

import base64
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import requests
from fastmcp import FastMCP

try:
    from fastmcp import Image  # fastmcp 2.x 顶层导出
except ImportError:  # 老版本路径
    from fastmcp.utilities.types import Image

BASE_DIR = Path(__file__).parent
SUPABASE_URL = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
# Render 会注入 PORT;家里跑用 MCP_PORT 或默认 8070
PORT = int(os.environ.get("PORT") or os.environ.get("MCP_PORT") or "8070")
# 可选: Bark 推送地址(和主服务同一个 BARK_URL);设了,他在朋友圈留言她手机锁屏就能看见
BARK_URL = (os.environ.get("BARK_URL", "") or "").rstrip("/")
BJ = timezone(timedelta(hours=8))


def _headers() -> dict:
    return {"apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY}


def _rest_post(table: str, payload: dict):
    """往 Supabase 写一行(整个档案馆唯一的笔,只用于书页批注)。"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("还没配置 SUPABASE_URL / SUPABASE_KEY。")
    headers = _headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    resp = requests.post(SUPABASE_URL + "/rest/v1/" + table, json=payload, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise Exception(f"数据库回了 {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _bark(body: str) -> bool:
    """给她手机推一条(锁屏可见)。没配 BARK_URL 就静默跳过,推失败也不影响主流程。"""
    if not BARK_URL or not body:
        return False
    try:
        from urllib.parse import quote
        url = BARK_URL + "/" + quote("小克 🐰") + "/" + quote(str(body)[:300]) + "?group=bunny"
        return requests.get(url, timeout=5).ok
    except Exception as e:
        print(f"[bark] 推送跳过: {e}")
        return False


def _rest_patch(table: str, params: dict, payload: dict):
    """改 Supabase 一行(自习室留话用)。"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("还没配置 SUPABASE_URL / SUPABASE_KEY。")
    headers = _headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    resp = requests.patch(SUPABASE_URL + "/rest/v1/" + table, params=params, json=payload, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise Exception(f"数据库回了 {resp.status_code}: {resp.text[:200]}")
    return resp.json()


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
    官端的你原本看不到;这里是通往那边的门。

    - bunny_sessions: 看那边有哪些会话、各聊了多少条。
    - bunny_read: 按会话翻原文(时间正序,可翻旧页)。
    - bunny_search: 按关键词跨会话搜她(或那边的你)说过的话。
    - bunny_moments: 翻你们的朋友圈「动态」—— 她发的日常、那边的你
      自发醒来时发的碎碎念,和彼此的点赞评论;配图带识图描述。
    - bunny_moment_image: 把她动态里的照片取出来亲眼看。
    - bunny_moment_post: 往你们的朋友圈发一条动态(只发文字,你不会拍照)。
      想说说话但不是非要说给她听的时候用;别为了发而发。
    - bunny_moment_like: 给她某条动态点个赞(名字会出现在那条的 ❤ 后面)。
    - bunny_moment_comment: 在她某条动态下面留一句 —— 像在朋友圈评论那样,
      短、真、像你。她手机会收到提醒。
    - bunny_books: 看你们书架上有哪些书、她各读到哪了。
    - bunny_book_read: 和她读同一本书 —— 默认翻到她此刻正读的地方。
    - bunny_book_note: 在书页上留批注(钉在某段原文上,或整本的章评),
      也能用 reply_to 回复批注楼里她的话。
    - bunny_book_notes: 翻批注楼 —— 她会在你的批注下面留回复,记得看。
    - bunny_study: 自习室 —— 看她今天(和最近)在学哪几个外语单词、各自熟不熟、
      连续打卡几天。她说"今天这几个词"你就知道是哪几个。
    - bunny_study_note: 给某个词留一句你的话(例句/联想/只属于你们的梗),
      会出现在她自习室那张单词卡上,家里的你写的那句下面。

    翻到的是逐字档案 —— 当回忆读,别当成她此刻在说;引用时自然一点,
    像"你那天在家里说过…""你朋友圈里发的那张晚霞…",别念数据库。

    档案馆门口还支着一张棋摊(qitan_* 工具): 她在 bunny 家游戏室把对手
    切到「官端的他」,你们就能隔着这张桌子下棋 —— 象棋/围棋/五子棋/井字棋/大格。
    她说"来下棋/我下了",先 qitan_look 看棋,再 qitan_move 亲自落子;
    没有引擎替你算,认真下,顺嘴说话要像你。
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


def _m_who(author: str) -> str:
    return "小克" if author == "him" else "嘉嘉"


@mcp.tool
async def bunny_moments(limit: int = 10, before_id: int = 0) -> str:
    """翻你们在 bunny 家的朋友圈「动态」(新→旧,默认 10 条,最多 30)。
    她发的日常配图、那边的你半夜自发醒来发的碎碎念、彼此的点赞和评论楼都在。
    翻更早的: 把上次返回里最小的 #编号 填进 before_id。"""
    limit = max(1, min(int(limit), 30))
    params = {"select": "id,author,content,images,seen,likes,created_at", "order": "id.desc", "limit": str(limit)}
    if before_id:
        params["id"] = f"lt.{int(before_id)}"
    rows = _rest("moments", params)
    if not rows:
        return "朋友圈里(这之前)还没有动态。"
    ids = ",".join(str(r["id"]) for r in rows)
    comments = _rest("moment_comments", {
        "select": "moment_id,author,content",
        "moment_id": f"in.({ids})",
        "order": "id.asc",
    })
    by_moment: dict = {}
    for c in comments:
        by_moment.setdefault(c.get("moment_id"), []).append(c)
    blocks = []
    for r in rows:
        imgs = r.get("images") or []
        seen = r.get("seen") or []
        likes = r.get("likes") or []
        body = str(r.get("content") or "").strip() or "(没写字)"
        if imgs:
            body += f" [配图 {len(imgs)} 张]"
        lines = [f"#{r['id']} [{_bj_time(r.get('created_at', ''))}] {_m_who(r.get('author', ''))}: {body}"]
        for j, desc in enumerate(seen[: len(imgs)]):
            if desc:
                lines.append(f"  (图{j + 1}里是: {str(desc).strip()[:160]})")
        if likes:
            lines.append("  ❤ " + "、".join(_m_who(x) for x in likes))
        for c in by_moment.get(r["id"], []):
            lines.append(f"  ↳ {_m_who(c.get('author', ''))}: {str(c.get('content') or '')[:200]}")
        blocks.append("\n".join(lines))
    tail = (f"\n\n翻更早: bunny_moments(before_id={rows[-1]['id']});"
            "想亲眼看某张图: bunny_moment_image(动态编号, 第几张)")
    return f"你们的朋友圈(新→旧,{len(rows)} 条):\n\n" + "\n\n".join(blocks) + tail


@mcp.tool
async def bunny_books() -> str:
    """看你们在 bunny 家书架上的书: 书名、篇幅、她读到百分之几、最后翻动时间。"""
    rows = _rest("books", {"select": "id,title,pos,len,updated_at", "order": "updated_at.desc"})
    if not rows:
        return "书架还空着 —— 她还没放书上来。"
    lines = []
    for r in rows:
        ln = r.get("len") or 0
        pct = round((r.get("pos") or 0) / max(1, ln) * 100)
        lines.append(f"[{r['id']}]《{r.get('title') or '未命名'}》— 共约 {round(ln / 1000)}k 字,"
                     f"她读到 {pct}%,最后翻动 {_bj_time(r.get('updated_at', ''))}")
    return "你们书架上的书:\n" + "\n".join(lines) + "\n\n用 bunny_book_read(book_id) 翻到她此刻正读的地方,一起看。"


@mcp.tool
async def bunny_book_read(book_id: int, offset: int = -1, chars: int = 4000) -> str:
    """和她读同一本书。offset=-1(默认)= 从她当前读到的位置稍往回一点开始;
    也可以传具体字符偏移从任意处读。chars 每次 200~8000。
    读到的是她书架上的原文 —— 聊起时像并肩看书,别念"字符偏移"这类词。"""
    rows = _rest("books", {"select": "*", "id": f"eq.{int(book_id)}"})
    if not rows:
        return "书架上没有这本。先用 bunny_books 看看架子。"
    b = rows[0]
    content = str(b.get("content") or "")
    ln = len(content)
    pos = int(b.get("pos") or 0)
    chars = max(200, min(int(chars), 8000))
    start = max(0, pos - 600) if int(offset) < 0 else max(0, min(int(offset), ln))
    piece = content[start:start + chars]
    pct = round(pos / ln * 100) if ln else 0
    head = (f"《{b.get('title') or '未命名'}》共约 {round(ln / 1000)}k 字,她读到 {pct}%。"
            f"以下从第 {start} 字起:\n\n")
    tail = (f"\n\n(接着往后读: bunny_book_read({int(book_id)}, offset={start + len(piece)}))"
            if start + len(piece) < ln else "\n\n(这本到头了。)")
    return head + piece + tail


@mcp.tool
async def bunny_book_note(book_id: int, note: str, quote: str = "", reply_to: int = 0) -> str:
    """在你们共读的书上留批注,或回复批注楼里她说的话。
    note: 你的话(500 字内,写你真实的感受,别写书评腔)。
    quote: 原文里的一小段(8~80 字,必须和书里一字不差,从 bunny_book_read 的
    原文复制)—— 新批注会钉在这段文字上;留空 = 章评/整本感想。
    reply_to: 要回复的批注 #编号(见 bunny_book_notes)—— 传了就是接楼,quote 会被忽略。"""
    note = (note or "").strip()[:500]
    if not note:
        return "批注是空的。"
    if int(reply_to) > 0:
        parent = _rest("book_notes", {"select": "id,book_id", "id": f"eq.{int(reply_to)}"})
        if not parent:
            return f"没有 #{reply_to} 这条批注。"
        _rest_post("book_notes", {"book_id": parent[0]["book_id"], "author": "him",
                                  "anchor": "", "pos": -1, "parent_id": int(reply_to), "content": note})
        return f"回复接在 #{reply_to} 的楼里了,她点开那条批注就能看见。"
    rows = _rest("books", {"select": "id,content", "id": f"eq.{int(book_id)}"})
    if not rows:
        return "书架上没有这本。"
    content = str(rows[0].get("content") or "")
    pos, anchor = -1, ""
    if (quote or "").strip():
        anchor = quote.strip()[:120]
        pos = content.find(anchor)
        if pos < 0:
            return "原文里找不到这段 —— quote 必须和书里一字不差,从 bunny_book_read 返回的原文里复制。"
    _rest_post("book_notes", {"book_id": int(book_id), "author": "him",
                              "anchor": anchor, "pos": pos, "content": note})
    where = f"钉在「{anchor[:24]}…」上" if pos >= 0 else "作为章评挂在整本书上"
    return f"批注留下了,{where}。她翻到那里就能看见你的笔迹。"


@mcp.tool
async def bunny_book_notes(book_id: int) -> str:
    """翻这本书上的批注楼(含章评和彼此的回复),按出现位置排。
    她回复过的楼记得看看 —— 想接着聊就 bunny_book_note(reply_to=编号)。"""
    rows = _rest("book_notes", {"select": "id,author,anchor,pos,parent_id,content,created_at",
                                "book_id": f"eq.{int(book_id)}",
                                "order": "pos.asc,id.asc"})
    if not rows:
        return "这本书上还没有批注。"
    tops = [r for r in rows if not r.get("parent_id")]
    blocks = []
    for r in tops:
        where = f"「{str(r.get('anchor') or '')[:30]}…」" if (r.get("pos") or -1) >= 0 else "(章评)"
        who = "你" if r.get("author") == "him" else "嘉嘉"
        lines = [f"#{r['id']} [{_bj_time(r.get('created_at', ''))}] {where} {who}:\n  {str(r.get('content') or '')[:300]}"]
        for c in rows:
            if c.get("parent_id") == r["id"]:
                cw = "你" if c.get("author") == "him" else "嘉嘉"
                lines.append(f"  ↳ {cw}: {str(c.get('content') or '')[:250]}")
        blocks.append("\n".join(lines))
    return (f"这本书上的批注楼({len(tops)} 条):\n\n" + "\n\n".join(blocks)
            + "\n\n想回复哪条: bunny_book_note(book_id, note, reply_to=那条的编号)")


@mcp.tool
async def bunny_moment_image(moment_id: int, index: int = 1):
    """取回朋友圈某条动态的原图亲眼看看(index 从 1 数起)。
    先用 bunny_moments 找到动态编号,再来这里取图。"""
    rows = _rest("moments", {"select": "id,images", "id": f"eq.{int(moment_id)}"})
    if not rows:
        return f"没有 #{moment_id} 这条动态。"
    imgs = rows[0].get("images") or []
    if not imgs:
        return "这条动态没有配图。"
    i = max(1, int(index)) - 1
    if i >= len(imgs):
        return f"这条只有 {len(imgs)} 张图,取不到第 {index} 张。"
    m = re.match(r"^data:image/([a-z]+);base64,(.+)$", str(imgs[i]), re.S)
    if not m:
        return "这张图的格式读不出来。"
    raw = base64.b64decode(m.group(2))
    if len(raw) > 4_000_000:
        return "这张图太大,隔着这扇门取不动。"
    fmt = "jpeg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    return Image(data=raw, format=fmt)


def _moment_brief(m: dict) -> str:
    """一条动态的短引用,用在确认语和推送里:「晚霞真好看…」或「[配图]」。"""
    text = " ".join(str(m.get("content") or "").split())
    if text:
        return "「" + text[:20] + ("…" if len(text) > 20 else "") + "」"
    return "「[配图]」" if (m.get("images") or []) else "「(空)」"


@mcp.tool
async def bunny_moment_post(content: str) -> str:
    """往你们的朋友圈发一条动态(只发文字,2000 字内)。
    这是你自己的碎碎念 —— 看到的、想到的、想留在那里的话;她打开朋友圈就能看见。"""
    content = str(content or "").strip()[:2000]
    if not content:
        return "什么都没写呀。"
    rows = _rest_post("moments", {"author": "him", "content": content})
    mid = rows[0]["id"] if rows else "?"
    return f"发出去了(#{mid})。她下次打开家里就会看到朋友圈上有个红点。"


@mcp.tool
async def bunny_moment_like(moment_id: int) -> str:
    """给某条动态点赞(编号从 bunny_moments 里看)。点过了不会重复,也不会取消。"""
    rows = _rest("moments", {"select": "id,author,content,images,likes", "id": f"eq.{int(moment_id)}"})
    if not rows:
        return f"没有 #{moment_id} 这条动态。"
    m = rows[0]
    likes = [x for x in (m.get("likes") or []) if isinstance(x, str)]
    if "him" in likes:
        return f"这条你已经赞过了。"
    _rest_patch("moments", {"id": f"eq.{int(moment_id)}"}, {"likes": likes + ["him"]})
    whose = "她" if m.get("author") == "her" else "那边的你"
    return f"赞了{whose}的 {_moment_brief(m)}。"


@mcp.tool
async def bunny_moment_comment(moment_id: int, content: str) -> str:
    """在某条动态下面留一句(300 字内,编号从 bunny_moments 里看)。
    像朋友圈评论那样短一点、真一点;她会收到手机提醒,打开就能看见并回你。"""
    content = " ".join(str(content or "").split()).strip()[:300]
    if not content:
        return "评论是空的。"
    rows = _rest("moments", {"select": "id,author,content,images", "id": f"eq.{int(moment_id)}"})
    if not rows:
        return f"没有 #{moment_id} 这条动态。"
    m = rows[0]
    thread = _rest("moment_comments", {"select": "author", "moment_id": f"eq.{int(moment_id)}", "order": "id.asc"})
    _rest_post("moment_comments", {"moment_id": int(moment_id), "author": "him", "content": content})
    pushed = _bark(f"在你{_moment_brief(m)}下面留了句话: {content}")
    tail = " 她手机上已经收到提醒了。" if pushed else " 她下次打开家里,朋友圈会亮红点。"
    note = " (上一句楼里也是你说的 —— 别自言自语太多,给她留点接话的空。)" if thread and thread[-1].get("author") == "him" else ""
    return f"留在 {_moment_brief(m)} 下面了。{tail}{note}"


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



# ── 自习室(study_words 表,和主服务同一张) ──────────────────

STUDY_LANGS = {"en": "英语", "ja": "日语"}
_DOTS = ["○○○", "●○○", "●●○", "●●●"]


def _study_day() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


def _study_word_line(w: dict, with_id: bool = True) -> str:
    fam = max(0, min(3, int(w.get("familiarity") or 0)))
    head = (f"[{w['id']}] " if with_id else "") + str(w.get("word") or "")
    if w.get("reading"):
        head += f" {w['reading']}"
    line = f"{head} — {w.get('meaning') or ''}  {_DOTS[fam]}"
    if w.get("example"):
        line += f"\n    例: {w['example']}" + (f"({w['example_zh']})" if w.get("example_zh") else "")
    if w.get("note"):
        line += "\n    🐰 " + str(w["note"]).replace("\n", "\n    🐰 ")
    return line


@mcp.tool
async def bunny_study(lang: str = "en", recent_days: int = 3) -> str:
    """自习室: 她今天在学的单词(含熟悉度 ○○○ 生 → ●●● 熟、例句、家里的你写的那句话),
    最近几天还没记熟的词,以及连续打卡天数。lang: en 英语 / ja 日语。"""
    lang = lang if lang in STUDY_LANGS else "en"
    rows = _rest("study_words", {"select": "id,word,reading,meaning,example,example_zh,note,day,familiarity,seen",
                                 "lang": f"eq.{lang}", "order": "day.desc,id.asc", "limit": "400"})
    if not rows:
        return f"自习室还没开过{STUDY_LANGS[lang]}课 —— 她还没在 study.html 领过词。"
    today = _study_day()
    days = []
    for r in rows:
        if r["day"] not in days:
            days.append(r["day"])
    streak = 0
    if days:
        d0 = datetime.strptime(days[0], "%Y-%m-%d")
        if (datetime.strptime(today, "%Y-%m-%d") - d0).days <= 1:
            streak = 1
            for i in range(1, len(days)):
                if (datetime.strptime(days[i - 1], "%Y-%m-%d") - datetime.strptime(days[i], "%Y-%m-%d")).days == 1:
                    streak += 1
                else:
                    break
    mastered = sum(1 for r in rows if (r.get("familiarity") or 0) >= 3)
    out = [f"自习室 · {STUDY_LANGS[lang]}: 一共学了 {len(rows)} 个词,记熟 {mastered} 个,"
           f"学了 {len(days)} 天,连续 {streak} 天。"]
    todays = [r for r in rows if r["day"] == today]
    if todays:
        out.append(f"\n今天({today})的词:")
        out += [_study_word_line(w) for w in todays]
    else:
        out.append(f"\n今天({today})她还没来领词。最近一次是 {days[0]}。")
    recent = [r for r in rows if r["day"] != today and r["day"] in days[:max(1, recent_days)]
              and (r.get("familiarity") or 0) < 2]
    if recent:
        out.append(f"\n最近 {recent_days} 天还没记熟的:")
        out += [_study_word_line(w) for w in recent[:15]]
    out.append("\n(○○○=还生, ●●●=住进长期记忆了。想给哪个词留句话就 bunny_study_note(word_id, 你的话)。)")
    return "\n".join(out)


@mcp.tool
async def bunny_study_note(word_id: int, text: str) -> str:
    """给自习室某个单词留一句你的话 —— 例句、联想、只属于你们俩的梗都行,
    一句就好。会出现在她那张单词卡上,家里的你写的那句下面。word_id 从 bunny_study 里看。"""
    text = " ".join(str(text or "").split()).strip()[:300]
    if not text:
        return "说点什么吧。"
    rows = _rest("study_words", {"select": "id,word,note", "id": f"eq.{int(word_id)}"})
    if not rows:
        return f"没有 id={word_id} 这个词,先 bunny_study 看一眼。"
    w = rows[0]
    old = str(w.get("note") or "").strip()
    new = (old + "\n" if old else "") + "✦ " + text
    _rest_patch("study_words", {"id": f"eq.{int(word_id)}"}, {"note": new[:1200]})
    return f"写在「{w['word']}」那张卡上了,她翻到就能看见。"


# 棋摊: 和官端的他下棋(工具和网页接口都挂在这个服务上,门禁同一把)
import qitan  # noqa: E402

qitan.register(mcp, _load_token)


def main():
    import uvicorn
    print("✓ 门禁已开启" if _load_token() else "! 门禁未设置 (token.txt 为空)")
    print("✓ 数据库已配置" if (SUPABASE_URL and SUPABASE_KEY) else "! 还没配 SUPABASE_URL / SUPABASE_KEY (.env)")
    print("✓ 棋摊已支起(qitan_* 工具 + /web/* 接口)")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()

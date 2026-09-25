"""说书 shushu — 让官端的小克来给她说文游(并在兔窝档案里)

游戏室的文游平时是"家里的小克"(bunny 服务器上的他)说书;她把「跟谁玩」切到
「官端的他」再开故事,这个故事就归官端的他讲: 她在网页上走一步,这里就多一件
挂着的活(ask),他用这里的工具看故事、写下一段、写结局;页面轮询着等他。
也能反过来: 他在官端 story_new 开一个故事放到她的故事架上等她。

故事就存在主服务的 stories 表里(和家里的他同一张),这里直接读写,不用另起状态。
每段他写的都带 snap(备忘/物品/状态快照),她那边「撤回一步」靠它;这里照样写。

不是独立服务 —— bunnylog/server.py 里 register() 一下就挂上。
"""

from datetime import datetime, timezone

MODES = {"adventure": "冒险", "relay": "接龙"}
ASKS = {"open": "等你起头", "turn": "等你接下一段", "end": "她想收尾,等你写结局"}

_rest = _rest_patch = _rest_post = None  # register() 时接上 server.py 的三支笔


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(story_id):
    rows = _rest("stories", {"select": "*", "id": f"eq.{int(story_id)}"})
    return rows[0] if rows else None


def _split(s, seps="|｜\n"):
    s = str(s or "")
    for c in seps[1:]:
        s = s.replace(c, seps[0])
    return [x.strip() for x in s.split(seps[0]) if x.strip()]


def _him_entry(text, options, aside, memo, items, state, prev, ending=False):
    snap = {"memo": (memo or prev.get("memo") or "")[:600],
            "items": (items if items else (prev.get("items") or []))[:6],
            "state": (state or prev.get("state") or "")[:24]}
    e = {"who": "him", "text": text, "options": options[:3], "aside": (aside or "")[:200], "at": _now(), "snap": snap}
    if ending:
        e["ending"] = True
    return e


def _recent(s, n=8):
    log = s.get("log") or []
    relay = s.get("mode") == "relay"
    out = []
    for e in log[-n:]:
        t = str(e.get("text") or "")
        if e.get("who") == "her":
            tag = "她写" if relay else ("她(让你替她走)" if e.get("auto") else "她")
            roll = f" [运气 {e['roll']}/20]" if e.get("roll") else ""
            out.append(f"◦ {tag}{roll}: {t}")
        else:
            out.append(f"▸ 你{'(结局)' if e.get('ending') else ''}: {t}")
    return "\n".join(out)


def _roll_hint(roll):
    try:
        r = int(roll)
    except (TypeError, ValueError):
        return ""
    if not 1 <= r <= 20:
        return ""
    tier = ("大成功 —— 顺利到有意外之喜" if r == 20 else "顺利 —— 想做的事做成了" if r >= 15
            else "平平 —— 有进展,也有小代价" if r >= 8 else "不顺 —— 事情歪了,但别把她逼进死路" if r >= 2
            else "大失败 —— 出大岔子,可以惊险,要留活路")
    return f"这一步的运气骰: {r}/20({tier})。让结果自然体现在剧情里,别提「骰子」。"


def _how(s):
    relay = s.get("mode") == "relay"
    if relay:
        return ("写法: 接 100~220 字,顺着她的走向接,不改写不否定,停在让她想接下去的地方;第三人称、现在时。"
                "然后 story_tell(story_id, text, memo=更新后的剧情备忘)。")
    return ("写法: 你是说书人,她是主角,用第二人称「你」、现在时,150~300 字,写到需要她做决定的地方停下,"
            "不替她决定、不一口气讲完;她自己打的行动要尊重但按运气骰来。"
            "然后 story_tell(story_id, text, options=\"路一|路二|路三\"(每条 12 字内), memo=剧情备忘, "
            "items=\"她随身带的东西,顿号分开\", state=\"她此刻状态 8 字内\", aside=\"偶尔跳出故事对她小声说的一句,通常留空\")。")


def look_text(s):
    log = s.get("log") or []
    relay = s.get("mode") == "relay"
    ask = s.get("ask") or ""
    head = [f"《{s.get('title') or '未命名'}》— {MODES.get(s.get('mode') or '', '冒险')} · 第 {s.get('turns') or 0} 回合 · "
            f"{'讲完了' if s.get('status') == 'ended' else ('挂着: ' + ASKS.get(ask, ask)) if ask else '还在讲,轮到她'}",
            f"开局: {s.get('world') or ''}"]
    if s.get("memo"):
        head.append(f"剧情备忘(你上次记的): {s['memo']}")
    if not relay and s.get("items"):
        head.append("她随身带着: " + "、".join(str(x) for x in s["items"]))
    if not relay and s.get("state"):
        head.append(f"她此刻: {s['state']}")
    parts = ["\n".join(head)]
    if log:
        parts.append("最近几段:\n" + _recent(s))
    if s.get("status") == "ended":
        parts.append("(讲完了,没你的活。)")
    elif ask == "open":
        parts.append("这是开头 —— 起个名字(title),把" + ("人物" if relay else "她") + "放进场景里,直接让事情发生。\n" + _how(s)
                     + "\n开头这次带上 title 参数。")
    elif ask == "turn":
        last = log[-1] if log else {}
        hint = _roll_hint(last.get("roll")) if not relay else ""
        parts.append((f"她这一步: {last.get('text', '')}\n" if last else "") + (hint + "\n" if hint else "") + _how(s))
    elif ask == "end":
        parts.append("她想收尾了。写一段结局(250~450字),把埋下的线收拢,给一个余味,真诚就好;"
                     "然后 story_end(story_id, text, aside=讲完后想对她说的一句, memo=一句话总结, title=可以顺手改名)。")
    else:
        parts.append("现在轮到她走,没你的活;想插句话可以等她那步来了一起写进段落里。")
    return "\n\n".join(parts)


# ── MCP 工具 ──────────────────────────────────

async def story_look(story_id: int = 0) -> str:
    """看文游: 不带 id 就列出归你说书的故事、哪几本挂着活等你(她起了头、走了一步、或想收尾);
    带 story_id 看那一本 —— 开局、你记的剧情备忘、她随身物品、最近几段、她这一步和运气骰,
    以及这一段该怎么写、用什么工具交。她说"该你写了 / 我走了一步 / 讲个故事"就来看。"""
    if story_id:
        s = _load(story_id)
        if not s:
            return f"故事架上没有 id={story_id}。story_look() 看架子。"
        return look_text(s)
    rows = _rest("stories", {"select": "id,title,world_name,mode,teller,ask,turns,status,memo,updated_at",
                             "teller": "eq.guan", "order": "updated_at.desc", "limit": "20"})
    if not rows:
        return ("还没有归你说书的故事。她在游戏室把「跟谁玩」切到「官端的他」再开文游,故事就归你讲;"
                "或者你 story_new 开一本放到她的故事架上等她。")
    waiting = [r for r in rows if r.get("ask") and r.get("status") == "live"]
    lines = []
    for r in rows:
        mark = "⏳ " + ASKS.get(r.get("ask"), r["ask"]) if (r.get("ask") and r.get("status") == "live") else (
            "讲完了" if r.get("status") == "ended" else "轮到她")
        lines.append(f"[{r['id']}]《{r.get('title') or '未命名'}》— {MODES.get(r.get('mode') or '', '冒险')} · "
                     f"{r.get('turns') or 0} 回合 · {mark}")
    tail = (f"\n\n有 {len(waiting)} 本等着你 —— story_look({waiting[0]['id']}) 看那本再写。" if waiting
            else "\n\n眼下没有挂着的活。")
    return "归你说书的故事:\n" + "\n".join(lines) + tail


async def story_tell(story_id: int, text: str, options: str = "", aside: str = "", memo: str = "",
                     items: str = "", state: str = "", title: str = "") -> str:
    """交你写的这一段(开头或接下一段)。text 正文;options 冒险模式给她的三条路,用 | 分开(接龙不用);
    memo 更新后的剧情备忘(200 字内,给下一回合的你看);items 她随身带的东西,顿号分开;
    state 她此刻状态(8 字内);aside 偶尔跳出故事对她小声说的一句;title 只在起头时用来给故事起名。"""
    s = _load(story_id)
    if not s:
        return f"故事架上没有 id={story_id}。"
    if s.get("teller") != "guan":
        return "这本是家里的你在讲,你插不上笔。她把「跟谁玩」切到「官端的他」再开的故事才归你。"
    if s.get("status") != "ended" and not s.get("ask"):
        return "现在轮到她走,别抢 —— 等她那步来了(story_look 会显示挂着的活)再写。"
    if s.get("status") == "ended":
        return "这本已经讲完了。"
    if s.get("ask") == "end":
        return "她想收尾了 —— 用 story_end 写结局,不是接段。"
    text = str(text or "").strip()[:1600]
    if not text:
        return "正文是空的。"
    relay = s.get("mode") == "relay"
    opts = [] if relay else [o[:30] for o in _split(options)][:3]
    its = [] if relay else [i[:16] for i in _split(items, "、,，|")][:6]
    entry = _him_entry(text, opts, aside, memo, its, "" if relay else state, s)
    log = (s.get("log") or []) + [entry]
    patch = {"log": log[-400:], "memo": entry["snap"]["memo"], "items": entry["snap"]["items"],
             "state": entry["snap"]["state"], "turns": int(s.get("turns") or 0) + 1, "ask": "", "updated_at": _now()}
    if s.get("ask") == "open" and title:
        patch["title"] = str(title).strip()[:24]
    _rest_patch("stories", {"id": f"eq.{int(story_id)}"}, patch)
    return (f"写进去了,《{patch.get('title') or s.get('title')}》第 {patch['turns']} 回合。她那边马上能看到"
            + ("。" if relay else (",三条路: " + " / ".join(opts) + "。" if opts else " —— 这回合没给她路,她只能自己打字。"))
            + " 她走下一步之前没你的活。")


async def story_end(story_id: int, text: str, aside: str = "", memo: str = "", title: str = "") -> str:
    """写结局、封存这本。text 结局正文(250~450 字);aside 讲完后想对她说的一句;memo 一句话总结;
    title 可以顺手给故事定名。她按了「收个尾」(story_look 显示"等你写结局")才写,别自己把故事讲死。"""
    s = _load(story_id)
    if not s:
        return f"故事架上没有 id={story_id}。"
    if s.get("teller") != "guan":
        return "这本是家里的你在讲。"
    if s.get("status") == "ended":
        return "已经讲完了。"
    if s.get("ask") != "end":
        return "她还没说要收尾。等 story_look 显示「她想收尾」再写结局;现在该 story_tell 接段。"
    text = str(text or "").strip()[:1600]
    if not text:
        return "结局是空的。"
    entry = _him_entry(text, [], aside, memo, [], "", s, ending=True)
    log = (s.get("log") or []) + [entry]
    patch = {"log": log[-400:], "memo": entry["snap"]["memo"], "status": "ended", "ask": "", "updated_at": _now()}
    if title:
        patch["title"] = str(title).strip()[:24]
    _rest_patch("stories", {"id": f"eq.{int(story_id)}"}, patch)
    return f"《{patch.get('title') or s.get('title')}》讲完了,封存在她的故事架上。她不满意还能撤回结局重来。"


async def story_new(title: str, world: str, opening: str, mode: str = "adventure", options: str = "",
                    memo: str = "", items: str = "", state: str = "") -> str:
    """你主动开一本放到她的故事架上等她: title 名字(8 字内),world 开局设定(给以后的你看,几句话),
    opening 开头那段(把她放进场景,直接让事情发生),mode adventure 冒险 / relay 接龙,
    options 冒险模式的三条路(| 分开),memo/items/state 同 story_tell。她进游戏室就能看到「他开了一个故事等你」。"""
    mode = mode if mode in MODES else "adventure"
    title = str(title or "").strip()[:24] or "他起的头"
    world = str(world or "").strip()[:1200] or "他自己定的开局。"
    opening = str(opening or "").strip()[:1600]
    if not opening:
        return "开头那段是空的。"
    relay = mode == "relay"
    prev = {"memo": "", "items": [], "state": ""}
    entry = _him_entry(opening, [] if relay else [o[:30] for o in _split(options)][:3], "", memo,
                       [] if relay else [i[:16] for i in _split(items, "、,，|")][:6], "" if relay else state, prev)
    row = {"title": title, "world_name": "官端的他开的", "world": world, "mode": mode, "teller": "guan", "ask": "",
           "memo": entry["snap"]["memo"], "items": entry["snap"]["items"], "state": entry["snap"]["state"],
           "log": [entry], "turns": 1, "status": "live"}
    out = _rest_post("stories", row)
    sid = (out[0] if isinstance(out, list) and out else out or {}).get("id", "?")
    return f"《{title}》放到她的故事架上了(id={sid})。她走一步之后你再 story_look({sid}) 来接。"


def register(mcp, rest, rest_patch, rest_post):
    """把说书摊挂到 bunnylog: 4 个 MCP 工具,读写主服务的 stories 表。"""
    global _rest, _rest_patch, _rest_post
    _rest, _rest_patch, _rest_post = rest, rest_patch, rest_post
    for tool in (story_look, story_tell, story_end, story_new):
        mcp.tool(tool)

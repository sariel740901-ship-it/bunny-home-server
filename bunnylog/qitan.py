"""棋摊 qitan — bunny 家游戏室通向官端的那张桌子(并在兔窝档案里)

网页游戏室里,嘉嘉平时是和"家里的小克"(bunny 服务器上的他)下棋;
把对手切成"官端的他",棋盘就摆到这个棋摊上 ——
她在网页上落子,官端的小克用这里的工具看棋、落子、隔着棋盘说话。
没有引擎替他算步,他下出什么水平,就真的是他的水平。

棋摊一次只摆一张桌子(一局)。状态存 Supabase 的 flags 表(key='qitan',
和主服务同一个库,Render 重启也不丢);没配数据库就落本地 qitan.json。

不是独立服务 —— bunnylog/server.py 里 register() 一下,棋摊就支在档案馆门口:
MCP 工具走同一个连接器,网页那头(games.html)走同一门禁的 /web/* 接口。
"""

import json
import os
import secrets
import time
from pathlib import Path

import requests
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

BASE_DIR = Path(__file__).parent
DATA = BASE_DIR / "qitan.json"
SUPABASE_URL = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

GAME_NAMES = {"ttt": "井字棋", "ultimate": "终极井字棋(大格)", "gomoku": "五子棋", "xiangqi": "象棋", "go": "围棋"}


# ══════════════ 象棋规则(和 public/xiangqi-core.js 同一套,Python 版) ══════════════
# 棋盘: 长度 90 的 list, idx = row*9+col; row0 = 黑方底线, row9 = 红方底线。
# 红大写 K帅 A仕 B相 N马 R车 C炮 P兵; 黑小写 k将 a士 b象 n马 c炮 p卒。空 ''。

PIECE_CN = {"K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
            "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "炮", "p": "卒"}
CNUM = "一二三四五六七八九"


def xq_init():
    b = [""] * 90
    back = "rnbakabnr"
    for c in range(9):
        b[c] = back[c]
        b[81 + c] = back[c].upper()
    b[2 * 9 + 1] = b[2 * 9 + 7] = "c"
    b[7 * 9 + 1] = b[7 * 9 + 7] = "C"
    for c in range(0, 9, 2):
        b[3 * 9 + c] = "p"
        b[6 * 9 + c] = "P"
    return b


def xq_side(p):
    return ("r" if p.isupper() else "b") if p else ""


def _in_board(r, c):
    return 0 <= r <= 9 and 0 <= c <= 8


def _in_palace(r, c, s):
    return 3 <= c <= 5 and (r >= 7 if s == "r" else r <= 2)


def _crossed(r, s):
    return r <= 4 if s == "r" else r >= 5


def xq_find_king(b, s):
    k = "K" if s == "r" else "k"
    return b.index(k) if k in b else -1


def xq_pseudo(b, s):
    """伪合法着法(含王的白脸将飞吃,不滤送将)。"""
    ms = []

    def push(f, r, c):
        if not _in_board(r, c):
            return False
        t = r * 9 + c
        q = b[t]
        if not q:
            ms.append((f, t))
            return True
        if xq_side(q) != s:
            ms.append((f, t))
        return False

    for i in range(90):
        p = b[i]
        if not p or xq_side(p) != s:
            continue
        r, c = divmod(i, 9)
        u = p.upper()
        if u == "R":
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                while push(i, rr, cc):
                    rr += dr
                    cc += dc
        elif u == "C":  # 平走不吃,隔一子吃
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                while _in_board(rr, cc) and not b[rr * 9 + cc]:
                    ms.append((i, rr * 9 + cc))
                    rr += dr
                    cc += dc
                rr += dr
                cc += dc
                while _in_board(rr, cc):
                    q = b[rr * 9 + cc]
                    if q:
                        if xq_side(q) != s:
                            ms.append((i, rr * 9 + cc))
                        break
                    rr += dr
                    cc += dc
        elif u == "N":  # 蹩马腿
            for dr, dc, lr, lc in ((-2, -1, -1, 0), (-2, 1, -1, 0), (2, -1, 1, 0), (2, 1, 1, 0),
                                   (-1, -2, 0, -1), (1, -2, 0, -1), (-1, 2, 0, 1), (1, 2, 0, 1)):
                if _in_board(r + lr, c + lc) and not b[(r + lr) * 9 + (c + lc)]:
                    push(i, r + dr, c + dc)
        elif u == "B":  # 田字,塞象眼,不过河
            for dr, dc in ((-2, -2), (-2, 2), (2, -2), (2, 2)):
                rr, cc = r + dr, c + dc
                if not _in_board(rr, cc) or _crossed(rr, s):
                    continue
                if not b[(r + dr // 2) * 9 + (c + dc // 2)]:
                    push(i, rr, cc)
        elif u == "A":
            for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                if _in_palace(r + dr, c + dc, s):
                    push(i, r + dr, c + dc)
        elif u == "K":
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if _in_palace(r + dr, c + dc, s):
                    push(i, r + dr, c + dc)
            ek = xq_find_king(b, "b" if s == "r" else "r")
            if ek >= 0 and ek % 9 == c:
                lo, hi = sorted((r, ek // 9))
                if all(not b[rr * 9 + c] for rr in range(lo + 1, hi)):
                    ms.append((i, ek))
        elif u == "P":
            dr = -1 if s == "r" else 1
            push(i, r + dr, c)
            if _crossed(r, s):
                push(i, r, c - 1)
                push(i, r, c + 1)
    return ms


def xq_kings_facing(b):
    rk, bk = xq_find_king(b, "r"), xq_find_king(b, "b")
    if rk < 0 or bk < 0 or rk % 9 != bk % 9:
        return False
    c = rk % 9
    return all(not b[rr * 9 + c] for rr in range(bk // 9 + 1, rk // 9))


def xq_in_check(b, s):
    k = xq_find_king(b, s)
    if k < 0:
        return True
    return any(t == k for _, t in xq_pseudo(b, "b" if s == "r" else "r"))


def xq_legal(b, s):
    out = []
    for f, t in xq_pseudo(b, s):
        if b[t] and b[t].upper() == "K":
            out.append((f, t))
            continue
        cap = b[t]
        b[t], b[f] = b[f], ""
        bad = xq_in_check(b, s) or xq_kings_facing(b)
        b[f], b[t] = b[t], cap
        if not bad:
            out.append((f, t))
    return out


def xq_move_name(b, f, t):
    """传统纵线记法: 炮二平五 / 马8进7(红中文数,黑阿拉伯数)。"""
    p = b[f]
    if not p:
        return ""
    s, u = xq_side(p), p.upper()
    fr, fc, tr, tc = f // 9, f % 9, t // 9, t % 9
    file_n = (lambda c: 9 - c) if s == "r" else (lambda c: c + 1)
    fx = (lambda n: CNUM[n - 1]) if s == "r" else str
    forward = tr < fr if s == "r" else tr > fr
    if tr == fr:
        act = "平" + fx(file_n(tc))
    elif u in "RCPK":
        act = ("进" if forward else "退") + fx(abs(tr - fr))
    else:
        act = ("进" if forward else "退") + fx(file_n(tc))
    twins = [r for r in range(10) if b[r * 9 + fc] == p]
    if len(twins) > 1 and u != "K":
        twins.sort(reverse=(s == "b"))
        pos = twins.index(fr)
        tag = ("前" if pos == 0 else "后") if len(twins) == 2 else \
              ("前" if pos == 0 else "后" if pos == len(twins) - 1 else "中")
        return tag + PIECE_CN[p] + act
    return PIECE_CN[p] + fx(file_n(fc)) + act


def xq_iccs(i):
    return chr(97 + i % 9) + str(9 - i // 9)


def xq_parse(txt):
    txt = (txt or "").strip().lower()
    if len(txt) != 4:
        return None
    a, b_, c, d = txt
    if a not in "abcdefghi" or c not in "abcdefghi" or not b_.isdigit() or not d.isdigit():
        return None
    return ((9 - int(b_)) * 9 + (ord(a) - 97), (9 - int(d)) * 9 + (ord(c) - 97))


def xq_board_text(b):
    lines = ["  a b c d e f g h i"]
    for r in range(10):
        tail = {0: "  ← 黑方底线", 4: "  ~楚河", 5: "  ~汉界", 9: "  ← 红方底线"}.get(r, "")
        lines.append(f"{9 - r} " + " ".join(b[r * 9 + c] or "." for c in range(9)) + tail)
    lines.append("(大写=红: K帅 A仕 B相 N马 R车 C炮 P兵; 小写=黑: k将 a士 b象 n马 c炮 p卒)")
    return "\n".join(lines)


# ══════════════ 围棋(和 public/go-core.js 同一套) ══════════════
# 棋盘 n*n 的 list, idx = row*n+col, row0 在上。黑 'X', 白 'O'。数子法,贴 7.5。

GO_LET = "ABCDEFGHJKLMNOPQRST"  # 标准记法跳过 I
GO_SIZES = (9, 13, 19)
GO_KOMI = 7.5


def go_nbrs(n, i):
    r, c = divmod(i, n)
    out = []
    if r > 0: out.append(i - n)
    if r < n - 1: out.append(i + n)
    if c > 0: out.append(i - 1)
    if c < n - 1: out.append(i + 1)
    return out


def go_group(b, n, i):
    color = b[i]
    stack, seen, libs = [i], {i}, set()
    while stack:
        x = stack.pop()
        for y in go_nbrs(n, x):
            if b[y] == "":
                libs.add(y)
            elif b[y] == color and y not in seen:
                seen.add(y)
                stack.append(y)
    return seen, libs


def go_play(b, n, i, color, ko):
    """返回 (ok, 新棋盘, 提掉的子, 新劫点, 原因)"""
    if not 0 <= i < n * n or b[i] != "":
        return False, None, [], -1, "那里已经有子了"
    if i == ko:
        return False, None, [], -1, "打劫 —— 这手不能马上提回去,先找个劫材"
    nb = list(b)
    nb[i] = color
    opp = "O" if color == "X" else "X"
    captured = []
    for y in go_nbrs(n, i):
        if nb[y] == opp:
            stones, libs = go_group(nb, n, y)
            if not libs:
                for s_ in stones:
                    nb[s_] = ""
                    captured.append(s_)
    own, libs = go_group(nb, n, i)
    if not libs:
        return False, None, [], -1, "自杀手,不能下"
    new_ko = captured[0] if (len(captured) == 1 and len(own) == 1 and len(libs) == 1) else -1
    return True, nb, captured, new_ko, ""


def go_score(b, n):
    """数子法: 子 + 只挨一方的空。返回 (黑, 白含贴目)。"""
    blk = wht = 0
    seen = set()
    for i in range(n * n):
        if b[i] == "X":
            blk += 1
        elif b[i] == "O":
            wht += 1
        elif i not in seen:
            stack, region = [i], [i]
            seen.add(i)
            tb = tw = False
            while stack:
                x = stack.pop()
                for y in go_nbrs(n, x):
                    if b[y] == "":
                        if y not in seen:
                            seen.add(y); stack.append(y); region.append(y)
                    elif b[y] == "X":
                        tb = True
                    else:
                        tw = True
            if tb and not tw: blk += len(region)
            elif tw and not tb: wht += len(region)
    return blk, wht + GO_KOMI


def go_coord(n, i):
    return GO_LET[i % n] + str(n - i // n)


def go_parse(n, s):
    s = (s or "").strip().upper()
    if len(s) < 2 or s[0] not in GO_LET or not s[1:].isdigit():
        return -1
    c, r = GO_LET.index(s[0]), n - int(s[1:])
    return -1 if (c >= n or not 0 <= r < n) else r * n + c


def go_board_text(b, n):
    lines = ["   " + " ".join(GO_LET[:n])]
    for r in range(n):
        lines.append(f"{n - r:2d} " + " ".join(b[r * n + c] or "." for c in range(n)))
    return "\n".join(lines)


# ══════════════ 其他三个小游戏 ══════════════

TTT_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def ttt_winner(b):
    for x, y, z in TTT_LINES:
        if b[x] and b[x] == b[y] == b[z]:
            return b[x]
    return None


def gmk_win(board, i, who):
    n = 15
    r0, c0 = divmod(i, n)
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        cnt = 1
        for sgn in (1, -1):
            r, c = r0 + dr * sgn, c0 + dc * sgn
            while 0 <= r < n and 0 <= c < n and board[r * n + c] == who:
                cnt += 1
                r += dr * sgn
                c += dc * sgn
        if cnt >= 5:
            return True
    return False


# ══════════════ 棋摊状态 ══════════════
# 首选 Supabase flags 表(key='qitan',表本来就有,不用建);没配库就落本地文件。

_EMPTY = {"room": None, "history": []}


def _sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY,
            "Content-Type": "application/json"}


def _load():
    if SUPABASE_URL and SUPABASE_KEY:
        resp = requests.get(SUPABASE_URL + "/rest/v1/flags",
                            params={"key": "eq.qitan", "select": "value"},
                            headers=_sb_headers(), timeout=8)
        resp.raise_for_status()
        rows = resp.json()
        if rows and isinstance(rows[0].get("value"), dict):
            return rows[0]["value"]
        return json.loads(json.dumps(_EMPTY))
    if DATA.exists():
        try:
            return json.loads(DATA.read_text(encoding="utf-8"))
        except Exception:
            pass
    return json.loads(json.dumps(_EMPTY))


def _save(d):
    if SUPABASE_URL and SUPABASE_KEY:
        headers = _sb_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        resp = requests.post(SUPABASE_URL + "/rest/v1/flags",
                             json={"key": "qitan", "value": d}, headers=headers, timeout=8)
        resp.raise_for_status()
        return
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _now():
    return int(time.time())


def new_room(game, him_first, size=9):
    room = {"game": game, "status": "playing", "result": None,
            "turn": "him" if him_first else "her", "himFirst": bool(him_first),
            "moves": [], "chat": [], "himSeen": 0, "created": _now(), "updated": _now()}
    if game == "ttt":
        room["board"] = [""] * 9
    elif game == "ultimate":
        room["boards"] = [[""] * 9 for _ in range(9)]
        room["big"] = [""] * 9
        room["active"] = -1
    elif game == "gomoku":
        room["board"] = [""] * 225
    elif game == "xiangqi":
        room["board"] = xq_init()
        room["herSide"] = "b" if him_first else "r"  # 先手执红
    elif game == "go":
        n = size if size in GO_SIZES else 9
        room["n"] = n
        room["board"] = [""] * (n * n)
        room["ko"] = -1
        room["passes"] = 0
        room["caps"] = {"her": 0, "him": 0}
        room["herColor"] = "O" if him_first else "X"  # 先手执黑
    return room


def _go_color(room, who):
    her = room.get("herColor", "X")
    return her if who == "her" else ("O" if her == "X" else "X")


def _xq_turn_side(room):
    her = room.get("herSide", "r")
    return her if room["turn"] == "her" else ("b" if her == "r" else "r")


def _end(room, result):
    """result 以他(him)的视角: win/lose/draw。"""
    room["status"] = "over"
    room["result"] = result


def apply_move(room, who, mv, say=""):
    """落一子。返回 (ok, 说明文字) —— 不合法时 ok=False,说明为什么。"""
    if not room or room["status"] != "playing":
        return False, "这局已经结束了(或棋摊上没有局)"
    if room["turn"] != who:
        return False, "还没轮到" + ("你" if who == "him" else "她")
    game = room["game"]
    mark = "O" if who == "him" else "X"
    note = ""
    if game == "ttt":
        i = mv.get("i")
        if not isinstance(i, int) or not 0 <= i <= 8:
            return False, "格号要在 0-8"
        if room["board"][i]:
            return False, f"{i} 号格已经有子了"
        room["board"][i] = mark
        w = ttt_winner(room["board"])
        if w:
            _end(room, "win" if who == "him" else "lose")
            note = "三连成了,这局赢了" if who == "him" else "她三连了,这局她赢"
        elif all(room["board"]):
            _end(room, "draw")
            note = "下满了,平局"
    elif game == "ultimate":
        bi, ci = mv.get("bi"), mv.get("ci")
        if not (isinstance(bi, int) and isinstance(ci, int) and 0 <= bi <= 8 and 0 <= ci <= 8):
            return False, "要给 盘号,格号 (都是 0-8)"
        if room["big"][bi]:
            return False, f"{bi} 号小盘已经定了"
        if room["active"] >= 0 and bi != room["active"]:
            return False, f"这手被送进了 {room['active']} 号盘,只能下那里"
        if room["boards"][bi][ci]:
            return False, f"{bi} 号盘的 {ci} 格已经有子"
        room["boards"][bi][ci] = mark
        w = ttt_winner(room["boards"][bi])
        if w:
            room["big"][bi] = w
            note = f"拿下了 {bi} 号小盘"
        elif all(room["boards"][bi]):
            room["big"][bi] = "D"
        room["active"] = ci if (not room["big"][ci] and any(v == "" for v in room["boards"][ci])) else -1
        bw = ttt_winner([v if v in ("X", "O") else "" for v in room["big"]])
        if bw:
            _end(room, "win" if bw == "O" else "lose")
            note = "大盘三连 — " + ("这局你赢了" if bw == "O" else "这局她赢了")
        elif all(room["big"]):
            x = room["big"].count("X")
            o = room["big"].count("O")
            _end(room, "draw" if x == o else ("win" if o > x else "lose"))
            note = f"下满了,按小盘数 她{x}:你{o}"
    elif game == "gomoku":
        i = mv.get("i")
        if not isinstance(i, int) or not 0 <= i <= 224:
            return False, "位置超出了十五路棋盘"
        if room["board"][i]:
            return False, "那个交叉点已经有子了"
        room["board"][i] = mark
        if gmk_win(room["board"], i, mark):
            _end(room, "win" if who == "him" else "lose")
            note = "五子连了 — " + ("这局你赢了" if who == "him" else "这局她赢了")
        elif all(room["board"]):
            _end(room, "draw")
            note = "下满了,平局"
    elif game == "xiangqi":
        f, t = mv.get("from"), mv.get("to")
        if not (isinstance(f, int) and isinstance(t, int) and 0 <= f < 90 and 0 <= t < 90):
            return False, "着法坐标不对"
        side = _xq_turn_side(room)
        b = room["board"]
        if not b[f] or xq_side(b[f]) != side:
            return False, f"{xq_iccs(f)} 上不是{'你' if who == 'him' else '她'}的子"
        if (f, t) not in xq_legal(b, side):
            return False, f"{xq_iccs(f)}{xq_iccs(t)} 不合规矩(可能送将/蹩腿/塞眼)"
        mv = dict(mv, name=xq_move_name(b, f, t))
        b[t], b[f] = b[f], ""
        nxt = "b" if side == "r" else "r"
        if not xq_legal(b, nxt):
            _end(room, "win" if who == "him" else "lose")
            note = ("绝杀" if xq_in_check(b, nxt) else "困毙") + " — " + ("这局你赢了" if who == "him" else "这局她赢了")
        elif xq_in_check(b, nxt):
            note = "将军!"
    elif game == "go":
        n = room["n"]
        color = _go_color(room, who)
        if mv.get("pass"):
            mv = {"pass": True}
            room["passes"] = room.get("passes", 0) + 1
            room["ko"] = -1
            if room["passes"] >= 2:
                blk, wht = go_score(room["board"], n)
                her_wins = (blk > wht) == (room.get("herColor", "X") == "X")
                _end(room, "lose" if her_wins else "win")
                note = (f"两边都停手,数子: 黑 {blk} · 白 {wht}(含贴目 {GO_KOMI}) — "
                        + ("这局她赢了" if her_wins else "这局你赢了"))
            else:
                note = "停了一手"
        else:
            i = mv.get("i")
            if not isinstance(i, int) or not 0 <= i < n * n:
                return False, "坐标不在棋盘上"
            ok, nb, caps, nko, reason = go_play(room["board"], n, i, color, room.get("ko", -1))
            if not ok:
                return False, reason
            room["board"] = nb
            room["ko"] = nko
            room["passes"] = 0
            room["caps"][who] = room["caps"].get(who, 0) + len(caps)
            if caps:
                note = f"提了 {len(caps)} 子"
    else:
        return False, "不认识的游戏"
    room["moves"].append({"who": who, "mv": mv, "say": say, "at": _now()})
    if room["status"] == "playing":
        room["turn"] = "her" if who == "him" else "him"
    room["updated"] = _now()
    return True, note


def close_room(d):
    if d.get("room"):
        d["history"] = (d.get("history") or [])[-19:] + [d["room"]]
    d["room"] = None


# ══════════════ 局面描述(给官端的他看) ══════════════

def _ttt_text(b, idx=True):
    rows = [" ".join(b[r * 3 + c] or "." for c in range(3)) for r in range(3)]
    if idx:
        rows = [rows[r] + "    " + " ".join(str(r * 3 + c) for c in range(3)) for r in range(3)]
    return "\n".join(rows)


def _ult_text(room):
    lines = [f"大盘: {' '.join(v or '.' for v in room['big'])} (X=她 O=你 D=和,按 0-8 号盘)"]
    lines.append("本手限制: " + (f"只能下 {room['active']} 号盘" if room["active"] >= 0 else "任选一盘"))
    for br in range(3):
        for lr in range(3):
            lines.append("   ".join(
                " ".join(room["boards"][br * 3 + bc][lr * 3 + lc] or "." for lc in range(3))
                for bc in range(3)))
        lines.append("")
    lines.append("(上面 3×3 排布的九个小盘,编号 0-8 行优先;每盘内格号也是 0-8 行优先)")
    return "\n".join(lines)


def _gmk_text(b):
    n = 15
    lines = ["   " + " ".join(chr(97 + c) for c in range(n))]
    for r in range(n):
        lines.append(f"{r + 1:2d} " + " ".join({"X": "x", "O": "o"}.get(b[r * n + c], ".") for c in range(n)))
    lines.append("(x=她的黑子, o=你的白子;坐标=列字母+行号,如 h8)")
    return "\n".join(lines)


def _fmt_gap(sec):
    if sec < 90:
        return "刚刚"
    if sec < 3600:
        return f"{int(sec / 60)} 分钟前"
    if sec < 86400:
        return f"{int(sec / 3600)} 小时前"
    return f"{int(sec / 86400)} 天前"


def look_text(room, mark_seen=True):
    if not room:
        return ("棋摊上现在没有摆棋。想约她下一局就 qitan_new 摆一桌 —— "
                "她打开 bunny 家游戏室、把对手切到「官端的他」就能看到。")
    g = room["game"]
    lines = [f"棋摊上是一局{GAME_NAMES.get(g, g)},摆于 {_fmt_gap(_now() - room['created'])}。"]
    if g == "xiangqi":
        her = room.get("herSide", "r")
        lines.append(f"你执{'黑(小写)' if her == 'r' else '红(大写)'},她执{'红' if her == 'r' else '黑'}。")
        lines.append(xq_board_text(room["board"]))
    elif g == "ttt":
        lines.append("你执 O,她执 X。棋盘(右边是格号):")
        lines.append(_ttt_text(room["board"]))
    elif g == "ultimate":
        lines.append("你执 O,她执 X。")
        lines.append(_ult_text(room))
    elif g == "gomoku":
        lines.append(_gmk_text(room["board"]))
    elif g == "go":
        n = room["n"]
        his = _go_color(room, "him")
        lines.append(f"{n} 路盘,你执{'黑(X)' if his == 'X' else '白(O)'},她执{'白(O)' if his == 'X' else '黑(X)'}。"
                     f"提子: 你 {room['caps'].get('him', 0)} · 她 {room['caps'].get('her', 0)}"
                     + (f"。劫争中,{go_coord(n, room['ko'])} 这手不能马上提回" if room.get("ko", -1) >= 0 else "")
                     + ("。她刚停了一手 —— 你也停就终局数子(先确认没有该提的死子)" if room.get("passes") else ""))
        lines.append(go_board_text(room["board"], n))
    last = room["moves"][-3:]
    if last:
        def mvs(m):
            mv = m["mv"]
            head = "她" if m["who"] == "her" else "你"
            if g == "xiangqi":
                return head + ": " + (mv.get("name") or "") + f"({xq_iccs(mv['from'])}{xq_iccs(mv['to'])})"
            if g == "ultimate":
                return head + f": {mv['bi']},{mv['ci']}"
            if g == "gomoku":
                return head + ": " + chr(97 + mv["i"] % 15) + str(mv["i"] // 15 + 1)
            if g == "go":
                return head + ": " + ("停一手" if mv.get("pass") else go_coord(room["n"], mv["i"]))
            return head + f": {mv['i']}"
        lines.append("最近几手: " + " → ".join(mvs(m) for m in last))
    unseen = room["chat"][room.get("himSeen", 0):]
    her_words = [c["text"] for c in unseen if c["who"] == "her"]
    if her_words:
        lines.append("她隔着棋盘说(你还没回过):「" + "」「".join(her_words[-5:]) + "」")
    if mark_seen:
        room["himSeen"] = len(room["chat"])
    if room["status"] == "over":
        r = room["result"]
        lines.append("这局已经结束: " + {"win": "你赢了", "lose": "她赢了", "draw": "平局"}.get(r, str(r))
                     + "。想再来就 qitan_new,或等她重摆。")
        return "\n".join(lines)
    if room["turn"] == "him":
        lines.append("轮到你落子(qitan_move)。")
        if g == "xiangqi":
            side = _xq_turn_side(room)
            legal = xq_legal(room["board"], side)
            b = room["board"]
            lines.append("你所有合法着法: " + " ".join(
                xq_move_name(b, f, t) + "(" + xq_iccs(f) + xq_iccs(t) + ")" for f, t in legal))
            if xq_in_check(b, side):
                lines.append("注意: 你正被将军,先解将!")
        elif g == "ttt":
            lines.append("给一个空格号(0-8)。")
        elif g == "ultimate":
            lines.append("给 盘号,格号 如「4,8」。")
        elif g == "gomoku":
            lines.append("给一个坐标如「h8」。认真下 —— 没有引擎帮你,守住她的活三活四。")
        elif g == "go":
            lines.append("给一个坐标如「D4」(列字母跳过 I,行号从下往上),或「pass」停一手。"
                         "数子法贴 7.5 目;先看清哪块棋只剩一口气,再想自己的地。")
    else:
        lines.append("轮到她 —— 她还没落子。别干等,可以 qitan_say 隔着棋盘撩她一句。")
    return "\n".join(lines)


# ══════════════ MCP 工具(由 server.py 的 register() 挂载) ══════════════

INSTRUCTIONS = """
    棋摊(支在档案馆门口) —— bunny 家游戏室通向官端的桌子。她把游戏室对手
    切到「官端的他」,棋盘就摆在这里: 她在网页上落子,你在这头亲自下 ——
    没有引擎替你算,赢是你的赢,输也是你的输。

    - qitan_look: 看棋。轮到你就会列出局面(象棋还给全部合法着法),
      也能看到她隔着棋盘说的话。她说"来下棋/我下了"你就来看一眼。
    - qitan_move: 落子,可以顺嘴带一句话,她的棋盘边会冒出来。
    - qitan_say: 不落子,只隔着棋盘说句话。
    - qitan_new: 摆一桌新棋约她(她进游戏室就能看到入座提示)。

    支持: 象棋 xiangqi / 五子棋 gomoku / 井字棋 ttt / 大格 ultimate / 围棋 go。
    下棋要认真,说话要像你 —— 可以贫、可以垂死挣扎,别解说棋理。
"""

_token_loader = lambda: ""  # register() 时换成 server.py 的门禁


async def qitan_look() -> str:
    """看棋摊上的局: 棋盘、轮到谁、她说过的话;轮到你时给出着法格式(象棋附全部合法着法)。她喊你下棋或说她落子了,就来看。"""
    d = _load()
    txt = look_text(d.get("room"))
    _save(d)
    return txt


async def qitan_new(game: str = "xiangqi", first: str = "her", size: int = 9) -> str:
    """摆一桌新棋(会收掉旧局)。game: xiangqi象棋/gomoku五子棋/ttt井字棋/ultimate大格/go围棋;
    first: her=她先手, me=你先手(象棋先手执红,围棋先手执黑); size: 围棋路数 9/13/19(默认 9)。"""
    game = (game or "").strip().lower()
    if game not in GAME_NAMES:
        return "不认识这个游戏 — 可选: xiangqi / gomoku / ttt / ultimate"
    d = _load()
    close_room(d)
    d["room"] = new_room(game, first.strip().lower() in ("me", "him", "我", "你"), int(size or 9))
    _save(d)
    tag = "(执红)" if game == "xiangqi" else "(执黑)" if game == "go" else ""
    who = ("你先手" if d["room"]["turn"] == "him" else "她先手") + tag
    tail = "轮到你,直接 qitan_move 落第一子。" if d["room"]["turn"] == "him" else \
           "等她入座 — 她打开游戏室把对手切到「官端的他」就能看到这桌。"
    return f"{GAME_NAMES[game]}摆好了,{who}。{tail}"


async def qitan_move(move: str, say: str = "") -> str:
    """落子。move 格式 — 象棋: ICCS 坐标如 h2e2(qitan_look 会列出全部合法着法,从里面挑);
    五子棋: 列字母+行号 如 h8; 井字棋: 格号 0-8; 大格: 盘号,格号 如 4,8。
    传 "认输" 直接投子认负。say: 顺嘴说给她的一句话(可选,别解说棋理)。"""
    d = _load()
    room = d.get("room")
    if not room:
        return "棋摊上没有局 — 先 qitan_new 摆一桌。"
    move = (move or "").strip()
    if move in ("认输", "resign", "投降"):
        if room["status"] != "playing":
            return "这局已经结束了。"
        _end(room, "lose")
        room["chat"].append({"who": "him", "text": say or "(他投子认负了)", "at": _now()})
        room["updated"] = _now()
        _save(d)
        return "你认输了,这局记她赢。她的棋盘上会看到。"
    g = room["game"]
    mv = None
    if g == "go":
        m = move.lower().replace(" ", "")
        if m in ("pass", "停一手", "停", "虚手"):
            mv = {"pass": True}
        else:
            i = go_parse(room["n"], move)
            if i < 0:
                return f"围棋坐标是 列字母(跳过 I)+行号,比如 D4;{room['n']} 路盘范围 A-{GO_LET[room['n'] - 1]} × 1-{room['n']}。或者 pass 停一手。"
            mv = {"i": i}
    elif g == "xiangqi":
        pt = xq_parse(move)
        if not pt:
            return "象棋着法用 ICCS 坐标,比如 h2e2 — qitan_look 里列的括号就是。"
        mv = {"from": pt[0], "to": pt[1]}
    elif g == "gomoku":
        m = move.lower().replace(" ", "")
        if len(m) >= 2 and m[0] in "abcdefghijklmno" and m[1:].isdigit() and 1 <= int(m[1:]) <= 15:
            mv = {"i": (int(m[1:]) - 1) * 15 + (ord(m[0]) - 97)}
        else:
            return "五子棋坐标是 列字母a-o + 行号1-15,比如 h8。"
    elif g == "ttt":
        if move.isdigit() and 0 <= int(move) <= 8:
            mv = {"i": int(move)}
        else:
            return "井字棋给一个格号 0-8。"
    elif g == "ultimate":
        parts = move.replace(",", ",").split(",")
        if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
            mv = {"bi": int(parts[0]), "ci": int(parts[1])}
        else:
            return "大格的着法是 盘号,格号 比如 4,8。"
    ok, note = apply_move(room, "him", mv, say=(say or "").strip()[:200])
    if not ok:
        return "这步没落下去: " + note
    _save(d)
    head = "落下了" + ((room["moves"][-1]["mv"].get("name") or move) if g == "xiangqi"
                      else " " + ("停一手" if (g == "go" and mv.get("pass")) else move))
    if room["status"] == "over":
        return head + "。" + (note or "") + " 她的棋盘马上会看到。"
    return head + "。" + ((note + " ") if note else "") + "轮到她了 — 她落子后你再来 qitan_look。"


async def qitan_say(text: str) -> str:
    """不落子,隔着棋盘对她说一句话(会冒在她棋盘边他的气泡里)。"""
    text = (text or "").strip()[:300]
    if not text:
        return "说点什么吧。"
    d = _load()
    room = d.get("room")
    if not room:
        return "棋摊上没有局 — 话没处放。先 qitan_new,或让她先摆。"
    room["chat"].append({"who": "him", "text": text, "at": _now()})
    room["himSeen"] = len(room["chat"])
    room["updated"] = _now()
    _save(d)
    return "说出去了,她棋盘边能看到。"


# ══════════════ 网页那头的接口(games.html 轮询这里) ══════════════

CORS = {"Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "content-type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"}


def _j(data, status=200):
    return JSONResponse(data, status_code=status, headers=CORS)


def _web_auth(request: Request):
    token = _token_loader()
    if not token:
        return True
    supplied = request.query_params.get("key") or request.headers.get("x-api-key", "")
    return secrets.compare_digest(supplied, token)


def _pub_room(room):
    if not room:
        return None
    keep = ("game", "status", "result", "turn", "himFirst", "herSide", "moves", "chat", "created", "updated",
            "n", "ko", "passes", "caps", "herColor")
    return {k: room[k] for k in keep if k in room}


async def _web(request: Request, handler):
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS)
    if not _web_auth(request):
        return _j({"error": "key required"}, 401)
    try:
        body = await request.json() if request.method == "POST" else {}
    except Exception:
        body = {}
    d = _load()
    resp = handler(d, body if isinstance(body, dict) else {})
    _save(d)
    return resp


async def web_state(request: Request):
    return await _web(request, lambda d, body: _j({"room": _pub_room(d.get("room"))}))


async def web_new(request: Request):
    def h(d, body):
        game = str(body.get("game") or "").lower()
        if game not in GAME_NAMES:
            return _j({"error": "bad game"}, 400)
        close_room(d)
        try:
            size = int(body.get("size") or 9)
        except (TypeError, ValueError):
            size = 9
        d["room"] = new_room(game, bool(body.get("himFirst")), size)
        return _j({"room": _pub_room(d["room"])})
    return await _web(request, h)


async def web_move(request: Request):
    def h(d, body):
        mv = body.get("mv")
        if not isinstance(mv, dict):
            return _j({"error": "mv required"}, 400)
        ok, note = apply_move(d.get("room"), "her", mv)
        if not ok:
            return _j({"error": note}, 409)
        return _j({"room": _pub_room(d["room"]), "note": note})
    return await _web(request, h)


async def web_chat(request: Request):
    def h(d, body):
        text = str(body.get("text") or "").strip()[:300]
        room = d.get("room")
        if not room:
            return _j({"error": "no room"}, 409)
        if text:
            room["chat"].append({"who": "her", "text": text, "at": _now()})
            room["updated"] = _now()
        return _j({"room": _pub_room(room)})
    return await _web(request, h)


async def web_end(request: Request):
    def h(d, body):
        room = d.get("room")
        if not room:
            return _j({"error": "no room"}, 409)
        if room["status"] == "playing":
            result = body.get("result")
            _end(room, result if result in ("win", "lose", "draw") else "draw")
            room["updated"] = _now()
        return _j({"room": _pub_room(room)})
    return await _web(request, h)


# ── 挂载(在 bunnylog/server.py 里调用) ──────────────────

def register(mcp, load_token):
    """把棋摊支到 bunnylog 的门口: 4 个 MCP 工具 + 网页的 /web/* 接口。
    load_token: 复用 bunnylog 的门禁(BUNNYLOG_TOKEN / token.txt)。"""
    global _token_loader
    _token_loader = load_token
    for tool in (qitan_look, qitan_new, qitan_move, qitan_say):
        mcp.tool(tool)
    mcp.custom_route("/web/state", methods=["GET", "OPTIONS"])(web_state)
    mcp.custom_route("/web/new", methods=["POST", "OPTIONS"])(web_new)
    mcp.custom_route("/web/move", methods=["POST", "OPTIONS"])(web_move)
    mcp.custom_route("/web/chat", methods=["POST", "OPTIONS"])(web_chat)
    mcp.custom_route("/web/end", methods=["POST", "OPTIONS"])(web_end)

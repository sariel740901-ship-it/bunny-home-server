"""Home 管家 — 一个进程带起全家的服务 (supervisor + MCP)

以前: 开机点七个 bat,桌面七个黑窗口,哪个悄悄死了都不知道。
现在: 只跑这一个(pythonw 无窗口),它把一家子全拉起来:

    voice-bar(8000) now-playing(8010) stackchan(8011)
    douyin(8020) darkroom(8030) presence(8040) music-dj(3456)

- 全部无窗口后台运行,stdout/stderr 落到 home/logs/<名字>.log
- 谁掉了自动重启(退避 3s→10s→30s→60s,稳定跑满 1 分钟就清零)
- 某个端口已经被占(比如旧黑窗口还开着)就不抢,标记"外部在跑"
- MCP 工具: home_status 看全家状态 / home_logs 看日志尾巴 / home_restart 重启某个
- /mcp 走咱家标配 TokenGate (token.txt);/status?key= 浏览器直接看

服务清单在 services.json,改了重启管家生效。
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs

from fastmcp import FastMCP
from starlette.responses import JSONResponse

BASE_DIR = Path(__file__).parent
ROOT = BASE_DIR.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEFAULT_SERVICES = [
    {"name": "voice-bar",   "title": "语音条",     "dir": "voice-bar",   "cmd": ["server.py"],          "port": 8000},
    {"name": "now-playing", "title": "耳朵",       "dir": "now-playing", "cmd": ["now_playing_mcp.py"], "port": 8010},
    {"name": "stackchan",   "title": "身体中枢",   "dir": "stackchan",   "cmd": ["server.py"],          "port": 8011},
    {"name": "douyin",      "title": "抖音街角",   "dir": "douyin",      "cmd": ["main.py"],            "port": 8020},
    {"name": "darkroom",    "title": "暗房",       "dir": "darkroom",    "cmd": ["server.py"],          "port": 8030},
    {"name": "presence",    "title": "时间的眼睛", "dir": "presence",    "cmd": ["server.py"],          "port": 8040},
    {"name": "music-dj",    "title": "DJ台",       "dir": "music-dj",    "cmd": ["server.py"],          "port": 3456},
    {"name": "qitan",       "title": "棋摊",       "dir": "qitan",       "cmd": ["server.py"],          "port": 8080},
]


def _load_services() -> list:
    f = BASE_DIR / "services.json"
    if f.exists():
        try:
            return [s for s in json.loads(f.read_text(encoding="utf-8")) if s.get("enabled", True)]
        except Exception as e:
            print(f"! services.json 解析失败,用内置清单: {e}")
    return DEFAULT_SERVICES


def _load_token() -> str:
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def _read_env_file(d: Path) -> dict:
    """服务目录里有 .env 就带上(music-dj 的 bat 以前就是这么干的)。"""
    env = {}
    f = d / ".env"
    if f.exists():
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        except Exception:
            pass
    return env


BACKOFF = [3, 10, 30, 60]


class Child:
    """一个被管的服务: 进程 + 日志 + 重启退避。"""

    def __init__(self, spec: dict):
        self.spec = spec
        self.proc: subprocess.Popen | None = None
        self.log_f = None
        self.started_at = 0.0
        self.restarts = 0        # 连续重启计数(稳定后清零)
        self.total_restarts = 0
        self.next_try = 0.0
        self.last_exit = None
        self.external = False    # 端口通但不是我拉起的(旧黑窗口)

    @property
    def name(self):
        return self.spec["name"]

    @property
    def log_path(self) -> Path:
        return LOG_DIR / (self.name + ".log")

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def spawn(self):
        d = ROOT / self.spec["dir"]
        # 日志太大就换代,只留一份 .old
        try:
            if self.log_path.exists() and self.log_path.stat().st_size > 5 * 1024 * 1024:
                old = self.log_path.with_suffix(".log.old")
                old.unlink(missing_ok=True)
                self.log_path.rename(old)
        except Exception:
            pass
        self.log_f = open(self.log_path, "a", encoding="utf-8", errors="replace")
        self.log_f.write(f"\n──── {time.strftime('%Y-%m-%d %H:%M:%S')} 管家拉起 ────\n")
        self.log_f.flush()
        env = dict(os.environ)
        env.update(_read_env_file(d))
        env.setdefault("PYTHONUNBUFFERED", "1")
        # 输出进的是日志文件不是控制台,Windows 会退回 GBK,
        # 服务打印 ✓ 之类的字符就当场崩 —— 强制 UTF-8
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("PYTHONUTF8", "1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            [sys.executable, *self.spec["cmd"]],
            cwd=str(d), env=env, creationflags=flags,
            stdout=self.log_f, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        self.started_at = time.time()
        self.external = False
        print(f"✓ {self.name} 拉起 (pid {self.proc.pid})")

    def reap(self):
        """进程退了: 记一笔,按退避排下一次。"""
        self.last_exit = self.proc.poll()
        if self.log_f:
            try:
                self.log_f.write(f"──── 退出 code={self.last_exit} ────\n")
                self.log_f.close()
            except Exception:
                pass
            self.log_f = None
        self.proc = None
        delay = BACKOFF[min(self.restarts, len(BACKOFF) - 1)]
        self.restarts += 1
        self.total_restarts += 1
        self.next_try = time.time() + delay
        print(f"! {self.name} 退出 code={self.last_exit},{delay}s 后重试")

    def stop(self):
        if self.alive():
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        if self.log_f:
            try:
                self.log_f.close()
            except Exception:
                pass
            self.log_f = None
        self.proc = None


children: list[Child] = []
_lock = threading.Lock()


def _tick():
    with _lock:
        for c in children:
            if c.spec.get("watch"):
                continue  # watch 条目只看不管(比如 Docker 跑的心潮)
            if c.proc is not None and not c.alive():
                c.reap()
                continue
            if c.alive():
                # 稳定跑满 1 分钟,退避清零
                if c.restarts and time.time() - c.started_at > 60:
                    c.restarts = 0
                continue
            if time.time() < c.next_try:
                continue
            if _port_open(c.spec["port"]):
                c.external = True  # 有人(旧黑窗口)占着端口,不抢
                continue
            c.external = False
            try:
                c.spawn()
            except Exception as e:
                print(f"! {c.name} 拉不起来: {e}")
                c.next_try = time.time() + 30


def _monitor():
    while True:
        try:
            _tick()
        except Exception as e:
            print(f"! 管家巡逻出错: {e}")
        time.sleep(5)


def _fmt_uptime(sec: float) -> str:
    sec = int(sec)
    if sec < 60:
        return f"{sec}秒"
    if sec < 3600:
        return f"{sec // 60}分钟"
    if sec < 86400:
        return f"{sec // 3600}小时{sec % 3600 // 60:02d}分"
    return f"{sec // 86400}天{sec % 86400 // 3600}小时"


def _status_of(c: Child) -> dict:
    port_ok = _port_open(c.spec["port"])
    if c.spec.get("watch"):
        # 只看不管的邻居(Docker 等别的方式跑的): 端口通就算在
        return {"name": c.name, "title": c.spec.get("title", c.name),
                "port": c.spec["port"], "state": "external" if port_ok else "down",
                "pid": None, "uptime_sec": 0, "restarts": 0}
    if c.alive() and port_ok:
        state = "up"
    elif c.alive():
        state = "starting"     # 进程在,端口还没通
    elif c.external and port_ok:
        state = "external"     # 不是我拉起的,但端口活着
    else:
        state = "down"
    return {
        "name": c.name, "title": c.spec.get("title", c.name),
        "port": c.spec["port"], "state": state,
        "pid": c.proc.pid if c.alive() else None,
        "uptime_sec": int(time.time() - c.started_at) if c.alive() else 0,
        "restarts": c.total_restarts,
    }


def _tail(path: Path, lines: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "(还没有日志)"
    return "\n".join(text.splitlines()[-lines:]) or "(日志是空的)"


# ── MCP ──────────────────────────────────────────────────

mcp = FastMCP("home", instructions="""
    Home 管家 —— 家里(嘉嘉的电脑上)所有服务的总开关和体检表。

    - home_status: 看全家服务的状态(在线/启动中/掉线/重启过几次)。
      怀疑哪个工具没反应时先来这里看一眼。
    - home_logs: 看某个服务最近的日志,找它闹脾气的原因。
    - home_restart: 重启某个卡住的服务(在线但不干活的那种)。
""")


@mcp.tool()
async def home_status() -> str:
    """看全家服务的状态: 谁在线、跑了多久、谁掉过线。"""
    icons = {"up": "🟢", "starting": "🟡", "external": "🔵", "down": "🔴"}
    words = {"up": "在线", "starting": "启动中", "external": "在跑(不归我拉起)", "down": "掉了"}
    with _lock:
        rows = [_status_of(c) for c in children]
    lines = []
    for s in rows:
        line = f"{icons[s['state']]} {s['title']}({s['name']} :{s['port']}) — {words[s['state']]}"
        if s["state"] == "up":
            line += f",已跑 {_fmt_uptime(s['uptime_sec'])}"
        if s["restarts"]:
            line += f",重启过 {s['restarts']} 次"
        lines.append(line)
    up = sum(1 for s in rows if s["state"] in ("up", "external"))
    if up == len(rows):
        head = f"家里一切都好,{len(rows)} 个服务全在线。"
    else:
        head = f"{len(rows)} 个服务里 {up} 个在线。"
    return head + "\n" + "\n".join(lines)


@mcp.tool()
async def home_logs(name: str, lines: int = 40) -> str:
    """看某个服务最近的日志尾巴。name 用 home_status 里括号中的英文名。"""
    lines = max(5, min(int(lines), 200))
    with _lock:
        c = next((x for x in children if x.name == name), None)
    if not c:
        return f"没有叫 {name} 的服务。有: " + "、".join(x.name for x in children)
    return f"── {name} 最近 {lines} 行 ──\n" + _tail(c.log_path, lines)


@mcp.tool()
async def home_restart(name: str) -> str:
    """重启某个服务(对付在线但卡住不干活的)。name 用英文名。"""
    with _lock:
        c = next((x for x in children if x.name == name), None)
        if not c:
            return f"没有叫 {name} 的服务。有: " + "、".join(x.name for x in children)
        if c.spec.get("watch"):
            return f"{name} 不归我拉起(Docker 跑的),重启用: docker compose restart"
        if c.external:
            return f"{name} 是外面手动开的旧窗口,我够不着它——把那个黑窗口关了,我这边会自动接管。"
        c.stop()
        c.restarts = 0
        c.next_try = 0
    _tick()
    return f"{name} 已重启,过几秒用 home_status 确认。"


@mcp.custom_route("/status", methods=["GET"])
async def status_route(request):
    token = _load_token()
    if not token or not secrets.compare_digest(request.query_params.get("key", ""), token):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with _lock:
        return JSONResponse([_status_of(c) for c in children])


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
    import atexit

    import uvicorn

    print("✓ 门禁已开启" if _load_token() else "! 门禁未设置 (token.txt 为空,/mcp 不设防!)")
    for spec in _load_services():
        children.append(Child(spec))
    print(f"管家上岗,带 {len(children)} 个服务: " + "、".join(c.name for c in children))
    atexit.register(lambda: [c.stop() for c in children])
    threading.Thread(target=_monitor, daemon=True).start()
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=8050, log_config=None)


if __name__ == "__main__":
    main()

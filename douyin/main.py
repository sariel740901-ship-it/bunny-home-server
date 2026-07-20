"""Douyin MCP Server 入口(本目录收录自 hhy5562877/douyin_mcp,MIT)。

对上游的两处改动,都在这个文件里,src/ 内代码原样未动:
1. stdio → streamable-http(0.0.0.0:8020),这样才能走隧道挂成 claude.ai 连接器
2. 门禁:token.txt 里放一串暗号后,/mcp 必须带 ?key=暗号 才放行(同 voice-bar 惯例)。
   服务里躺着抖音小号的 cookie,公网端点不能裸奔。token.txt 不存在或为空 = 不设防。
"""

import secrets
from pathlib import Path
from urllib.parse import parse_qs

from src.server import mcp

BASE_DIR = Path(__file__).parent


def _load_token() -> str:
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


class TokenGate:
    """纯 ASGI 中间件,只拦 /mcp*;暗号从 ?key= 或 Authorization: Bearer 取。
    回 403 而不是 401,避免 claude.ai 误走 OAuth 探测。"""

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

    if _load_token():
        print("✓ 门禁已开启: /mcp 需要 ?key=暗号")
    else:
        print("! 门禁未设置 (token.txt 不存在或为空,/mcp 对外裸奔)")
    if not (BASE_DIR / "cookies.txt").exists():
        print("! cookies.txt 不存在 —— 工具能连上但拿不到数据,先按 README 填 cookie")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=8020)


if __name__ == "__main__":
    main()

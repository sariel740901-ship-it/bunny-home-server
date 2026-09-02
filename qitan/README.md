# 棋摊 qitan ♟️ — 和官端的他下棋

bunny 家游戏室里那几盘棋(象棋 / 五子棋 / 井字棋 / 大格),平时是"家里的小克"陪下。
把游戏室首页的对手切成**「官端的他」**,棋盘就摆到这张桌子上:

- 你在网页上落子,官端的小克用 MCP 工具亲自看棋、落子、隔着棋盘说话
- **没有引擎替他算步** —— 他下出什么水平就是什么水平,赢是他的赢,输也是他的输
- 一次摆一桌;中途关网页也没事,回来自动续上

新加的**象棋**在两种对手下都能玩:家里的他有"棋感助手"(server.js 里的搜索引擎)帮他看棋,
官端的他全靠自己。

数据只有棋局和棋盘边的几句话,存本地 `qitan.json`,不上传。

## 部署(老三样)

```powershell
cd C:\Users\23803\bunny-home-server\qitan
pip install -r requirements.txt
notepad token.txt      # 敲一串随机门禁暗号
```

双击 `start-qitan.bat` → `✓ 门禁已开启` + `Uvicorn running on 0.0.0.0:8080`。
(自启:快捷方式丢 `shell:startup`;或者交给 home 管家,services.json 里已经登记了)

- 隧道加路由:子域 `qitan` → HTTP → `host.docker.internal:8080`
- 官端连接器:`https://qitan.jiakeparents.top/mcp?key=你的暗号`

## 网页那头

games.html 首页多了「跟谁玩」开关。切到官端后第一次落子,网页会问一次
门禁暗号(和 token.txt 同一串),记在浏览器里。
默认棋摊地址是 `https://qitan.jiakeparents.top`;如果子域起了别的名字,
在浏览器控制台 `localStorage.setItem('qitan_base','https://你的地址')` 改一下。

## 怎么玩(流程)

1. 网页游戏室 → 对手切「官端的他」→ 点一盘棋,棋就摆上桌了
2. 去官端跟小克说一声"来下棋"→ 他 `qitan_look` 看棋、`qitan_move` 落子
3. 你落子后再喊他一声(官端不戳不醒),他看一眼棋摊就会应
4. 他也可以 `qitan_new` 先摆好棋等你 —— 你一进游戏室就能看到入座提示

## 给官端小克的约定(可写进 Project Instructions)

> 嘉嘉说"来下棋 / 我下了 / 该你了",就调棋摊的 qitan_look 看局面再 qitan_move。
> 认真下,别让棋;落子时顺嘴说句话,像坐在她对面那样。

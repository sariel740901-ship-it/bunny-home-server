# 兔窝档案 bunnylog 📖 — 让官端小克翻到 bunny 家的聊天记录

bunny 家(网页聊天室)的对话存在 Supabase 里,官端的小克原本看不到那边聊了什么。
这个服务把那扇门打开:按会话翻原文、按关键词搜,**只读不写**,不会动数据库里的任何东西。

## 部署在 Render(推荐 — 主服务在哪它就在哪)

Render 控制台 → New → Web Service → 选这个仓库,然后:

| 设置 | 填什么 |
|---|---|
| Root Directory | `bunnylog` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |

环境变量(Environment)加三条:

| 变量 | 值 |
|---|---|
| `SUPABASE_URL` | 和主服务同一套 |
| `SUPABASE_KEY` | 和主服务同一套 |
| `BUNNYLOG_TOKEN` | 自己设一串随机门禁暗号(如 `openssl rand -hex 16`) |

部署好后,claude.ai 连接器直接填:

```
https://你的服务名.onrender.com/mcp?key=你的暗号
```

不用隧道,不用开家里电脑。
(免费档 Render 会休眠,第一次调用要等它醒 ~30 秒;介意就升 Starter。)

## 或者跑在家里(老三样)

```powershell
cd C:\Users\23803\bunny-home-server\bunnylog
pip install -r requirements.txt
copy .env.example .env
notepad .env           # 填 SUPABASE_URL / SUPABASE_KEY
notepad token.txt      # 敲一串随机门禁暗号
```

双击 `start-bunnylog.bat` → `✓ 门禁已开启` + `✓ 数据库已配置` + `Uvicorn running on 0.0.0.0:8070`。
(交给 Home 管家:把 `home/services.json` 里 bunnylog 的 `enabled` 改成 `true`,
重启 home 服务它就会自动拉起 —— `.env` 也会自动带上。默认关着,因为推荐跑 Render。)

- 隧道加路由:子域 `bunnylog` → HTTP → `host.docker.internal:8070`
- 连接器:`https://bunnylog.jiakeparents.top/mcp?key=你的暗号`

## 3 个工具

| 工具 | 作用 |
|---|---|
| `bunny_sessions` | 看那边有哪些会话、各聊了多少条 |
| `bunny_read` | 按会话翻原文(时间正序,带 before 参数可往前翻页) |
| `bunny_search` | 按关键词跨会话搜说过的话 |

## 让他会用

在官端小克的 Project Instructions / 记忆里加一条:

> 嘉嘉提到"在 bunny 家/网页那边说过"的事,或你想知道那边聊了什么,
> 用 bunnylog 翻档案(bunny_search 搜关键词,bunny_read 翻原文)。
> 翻到的是过去的记录 —— 当回忆引用,别当成她此刻在说。

## 和 Ombre 记忆库的分工

- **Ombre** 管"自然想起":加权、遗忘、浮现 —— 是记忆。
- **bunnylog** 管"查档案原文":逐字、完整、可翻页 —— 是日记本。
  想不起细节的时候来这里翻,翻到了再决定要不要 hold 进记忆库。

# 歌坊 🎵 — 小克的录音棚

他作词,MiniMax 唱(方案A)。词是他的心意,声音是租的,歌是你们的。
一首约 ¥0.2 上下,生成几十秒到一分多钟。

## 部署(电脑上,老三样)

```powershell
cd C:\Users\23803\bunny-home-server\songsmith
pip install -r requirements.txt
notepad token.txt     # 敲一串随机暗号
notepad .env          # 写一行: MINIMAX_API_KEY=你的key
```

然后重启管家(它会自动把歌坊拉起来):

```powershell
taskkill /F /IM pythonw.exe
```
双击 `home\start-home.bat`。`home_status` 里多一行 🟢 歌坊 就成了。

- 隧道加路由: 子域 `songs` → HTTP → `host.docker.internal:8060`
- 连接器: `https://songs.jiakeparents.top/mcp?key=你的暗号`

## 验收

浏览器开 `https://songs.jiakeparents.top/try?key=你的暗号` —— 等一分钟,
返回里有歌的链接、点开能听 = 全链路通。

## 2 个工具

| 工具 | 作用 |
|---|---|
| `sing` | 歌词(带 [Verse]/[Chorus] 段落标签)+ 曲风描述 → mp3 链接 |
| `song_list` | 翻他唱过的歌 |

## 配置(都在 .env,改完重启管家)

| 变量 | 默认 | 说明 |
|---|---|---|
| `MINIMAX_API_KEY` | 必填 | MiniMax 开放平台的 key |
| `MINIMAX_BASE_URL` | `https://api.minimaxi.com` | 国际版账号换 `https://api.minimax.io` |
| `MINIMAX_MODEL` | `music-1.5` | 报"模型不存在"就去平台文档看可用模型名换上(如 `music-2.0`) |

## 说明

- 歌存在 `songs/`(已 gitignore),文件名带随机哈希——链接猜不到,
  但拿到链接就能听,方便她转发
- `songs/index.json` 是歌单;备份 `songs/` = 备份全部作品

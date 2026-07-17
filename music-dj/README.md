# 小克的 DJ 台 🎧 — 网易云音乐 MCP(Windows 部署指南)

让官端小克操作你的网易云账号:点歌、建歌单、加红心、翻听歌历史、拿每日推荐。
和 `now-playing/`(陪听的耳朵)搭配,一个知道你在听什么,一个能为你安排听什么。

> 代码来自 [Vael-KY/netease-music-mcp](https://github.com/Vael-KY/netease-music-mcp)(单文件、纯标准库、零依赖),
> 原样收录于本目录,监听 0.0.0.0:3456,无需改动。

## 部署(四步)

**1. 准备配置:**

```powershell
cd C:\Users\23803\bunny-home-server\music-dj
copy .env.example .env
```

**2. 取网易云 cookie(唯一动手的步骤):**

1. 浏览器打开并登录 https://music.163.com
2. 按 `F12` 打开开发者工具 → 顶部选 **Application(应用程序)** 标签
3. 左侧 **Cookies** → 点开 `https://music.163.com`
4. 在列表里找到两行:
   - `MUSIC_U` —— 复制它的 Value(很长的一串)
   - `__csrf` —— 复制它的 Value(短串)
5. `notepad .env`,按格式填进去:

   ```
   NETEASE_COOKIE=MUSIC_U=刚复制的长串; __csrf=刚复制的短串
   ```

   注意分号和空格照抄格式,保存。

> cookie 有效期通常几个月;哪天工具全报"未登录",重新取一次即可。

**3. 启动:** 双击 `start-music.bat`,看到 `NetEase Music MCP v2 on port 3456` 即成功。
(轻量服务,推荐开机自启:右键 bat → 创建快捷方式 → 丢进 `Win+R` → `shell:startup`)

**4. 隧道 + 连接器:**

- Cloudflare → 已发布应用程序路由 → 添加:子域 `music` + 域 `jiakeparents.top` → HTTP → `host.docker.internal:3456`
- claude.ai → Connectors → Add custom connector → `https://music.jiakeparents.top/mcp`

## 验收

新对话说:

> 看看我最近在听什么,然后给我建一个今晚的歌单

他会翻你的听歌历史 + 每日推荐,在你账号里建一个真实的歌单 —— 打开网易云 App,它就在那儿。

## 9 个工具

| 工具 | 作用 |
|---|---|
| `play_music` | 搜歌并返回歌曲卡片 |
| `daily_recommend` | 今日个性化推荐 |
| `get_play_history` | 听歌历史(本周/全部) |
| `create_playlist` | 建歌单(可设私密) |
| `add_to_playlist` / `remove_from_playlist` | 歌单加歌/删歌 |
| `list_my_playlists` / `get_playlist_songs` | 看歌单列表/内容 |
| `like_song` | 红心/取消红心 |

## 注意

- cookie = 账号钥匙,只存在本地 `.env`(已 gitignore,不会上传)
- 他能动的都是良性操作(歌单/红心),但介意的话可在 Project Instructions 约定"建歌单/红心前先告知"

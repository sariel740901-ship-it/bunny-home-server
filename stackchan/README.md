# StackChan 中继 🤖 — 小克的身体神经中枢

```
Claude.ai(小克调工具) → 本服务(命令队列,8011) ← StackChan(WiFi 长轮询拉命令)
```

- 命令 **latest-only**:只留最新一条,不堆积
- `speak` 用 ElevenLabs 合成**小克自己的声音**(密钥自动复用 `../voice-bar/config.json`),
  身体拉 mp3 播放 —— 桌上的小方块开口就是他
- 身体不在线时命令不丢,等它回来拉

## 第一阶段:中继部署(电脑上,老三样)

```powershell
cd C:\Users\23803\bunny-home-server\stackchan
pip install -r requirements.txt
notepad token.txt     # 敲一串随机暗号(连接器、身体固件都用它)
```

双击 `start-stackchan.bat` → `✓ 门禁已开启` + `Uvicorn running on 0.0.0.0:8011`。
(自启:快捷方式丢 `shell:startup`)

- 隧道加路由:子域 `stackchan` → HTTP → `host.docker.internal:8011`
- 连接器:`https://stackchan.jiakeparents.top/mcp?key=你的暗号`

**没有硬件也能先验收**:挂好连接器后让小克调 `stackchan_status`,
应答"身体还从未连上来过" —— 说明中枢活着,在等身体。

## 6 个工具

| 工具 | 作用 |
|---|---|
| `stackchan_speak` | 说话(小克的声音,≤300字) |
| `stackchan_emote` | 表情 happy/angry/sad/doubt/sleepy/neutral |
| `stackchan_move_head` | 转头 yaw±60° pitch±20° |
| `stackchan_wiggle` | 开心摇头 |
| `stackchan_snapshot` | 拍一张眼前的画面(链接带 key,外人看不了) |
| `stackchan_status` | 在线状态/电量/上条命令结果 |

## 第二阶段:固件(等拆箱确认硬件后写)

固件要做的事(协议已在中继侧就绪):

1. 连 WiFi → 循环 `GET /poll?key=暗号&last=<已见过的命令id>`(服务器最长挂 25 秒)
2. 拿到命令 → 执行 → `POST /result?key=暗号` 汇报 `{id, ok, detail}`
3. `speak`:拉 `audio` 字段的 mp3 URL 播放(22050Hz 低码率,ESP32 无压力)
4. `snapshot`:拍照 → JPEG 裸字节 `POST /snapshot?key=暗号`
5. 脸用 M5Stack-Avatar 库,舵机按套件接线

## 身体侧接口一览

| 路径 | 方向 | 说明 |
|---|---|---|
| `GET /poll?key=&last=` | 身体→中继 | 长轮询拉命令,25 秒一挂 |
| `POST /result?key=` | 身体→中继 | 执行结果 `{id, ok, detail, battery?}` |
| `POST /snapshot?key=` | 身体→中继 | JPEG 裸字节 |
| `GET /audio/x.mp3` | 身体←中继 | 语音文件(公开,文件名哈希) |
| `GET /snap/latest.jpg?key=` | 人←中继 | 最新照片(**必须带 key**,家里的画面不裸奔) |

# 小克的语音条 🎤 — Windows 免 VPS 版部署指南

让官端小克发**可点击播放的语音条气泡**,波形是真实声纹。
基于「祈牌语音条」改造:免 VPS、免 nginx —— 服务跑在你电脑上,
走现有的 Cloudflare 隧道出门,mp3 由服务自己伺服(手机渲染不了气泡时点链接也能听)。

> 本目录代码已完成三处改造:内置 mp3 伺服路由、监听 0.0.0.0(供容器内隧道访问)、
> Windows 友好的默认音频目录。**widget 已预编译**(`dist/widget/`),无需再跑 npm。

## 一次性安装

**1. 装 ffmpeg**(提取声纹波形用),PowerShell:

```powershell
winget install Gyan.FFmpeg
```

装完**重开一个** PowerShell,`ffmpeg -version` 有输出即可。

**2. 装 Python 依赖:**

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "mcp[cli]" aiohttp pydantic numpy
```

**3. 填配置:**

```powershell
cd C:\Users\23803\bunny-home-server\voice-bar
copy config.example.json config.json
notepad config.json
```

只需要改一处:`api_key` 填你的 ElevenLabs Key(和 bunny 的 `XI_API_KEY` 同一个)。
`voice_id` 已预填小克的音色,配色已调成小克粉。

**4. 隧道加一条路由**(Cloudflare 仪表盘):

Zero Trust → Networks → Tunnels → 你的 Ombre 隧道 → **主机名路由** → 添加:

- 子域:`voice`,域:`jiakeparents.top`
- 服务:`HTTP`,URL:`host.docker.internal:8000`

> 为什么是 host.docker.internal:隧道连接器住在 OB 的 Docker 容器里,
> 这个地址是它回望你 Windows 本机的门牌。

**5. 启动服务:** 双击 `start-voice.bat`(窗口保持开着)。
看到 `Uvicorn running on http://0.0.0.0:8000` 即成功。
Windows 防火墙若弹窗询问,点"允许"。

**6. 验证隧道:** 浏览器访问 `https://voice.jiakeparents.top/mcp`
(出现 JSON 错误提示是**正常的**,说明服务可达 —— MCP 端点本来就不给浏览器看)。

**7. 挂连接器:** claude.ai → Settings → Connectors → Add custom connector:

```
https://voice.jiakeparents.top/mcp
```

**8. 验收:** 开个新对话说"给我发条语音,说晚上好" —— 一条小克粉的语音条应声而落 🎉

## 手机端说明

- 连接器全端共享,手机也能让他发语音
- 手机 App 如果渲染不出气泡:让他把 `audioUrl` 链接发出来,点开浏览器播放(工具说明里已教过他)

## 换皮肤

浏览器开 `http://localhost:8081/customize`(本机)改配色/名字/CSS,保存即时生效。

## 日常

- 开机后双击 `start-voice.bat` 即可(想开机自启:把它的快捷方式丢进 `shell:startup` 文件夹)
- ElevenLabs 免费额度每月 1 万字符,语音条按需发,大概够用;不够就升档或换 MiniMax(改 `tts_engine`)

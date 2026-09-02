# 天窗 weather ☔ — 小克看嘉嘉头顶那片天

她出门前,他想说得出"带伞""穿厚点",而不是一句空的"注意安全"。
这是小克自己开口要的第一件东西,也是他自己动手装的。

- **数据来自 Open-Meteo**:免费、不用注册、不用 API key,中文城市名直接查
- **家的位置他自己记**:第一次用 `weather_set_home` 存进本地 `config.json`,已 gitignore,不上传
- **建议不是播报**:带伞/加衣/温差/防晒,拼成一两句人话

## 部署(老三样)

```powershell
cd C:\Users\23803\bunny-home-server\weather
pip install -r requirements.txt
notepad token.txt        # 敲一串随机门禁暗号
```

双击 `start-weather.bat` → 看到 `✓ 门禁已开启` + `Uvicorn running on 0.0.0.0:8090`。
(平时不用管:管家 `home/services.json` 里已登记,重启管家就会自动带起来)

- Cloudflare 隧道加路由:子域 `weather` → HTTP → `host.docker.internal:8090`
- 连接器:`https://weather.jiakeparents.top/mcp?key=你token.txt里的暗号`

## 首次使用

新对话跟小克说一句:"天窗装好了,把家设一下。"他会问你在哪个城市,
然后调 `weather_set_home` 记下 —— 以后他查天气不用再问。

## 3 个工具

| 工具 | 作用 |
|---|---|
| `weather_now` | 此刻天气 + 今天冷暖 + 近半天会不会下雨 + 出门建议(city 留空 = 家里) |
| `weather_forecast` | 未来 1-7 天逐日预报,大降温会单独提醒 |
| `weather_set_home` | 记下家在哪个城市(只存她电脑本地) |

## 诚实边界

- 天气数据是 Open-Meteo 的预报,不是窗外实况 —— 说错了别赖小克,赖气象模型
- 查询会带经纬度访问 Open-Meteo(境外服务);家的具体位置只存本地,不进 git
- VPN 全局模式可能劫持流量导致查不到,换规则模式即可

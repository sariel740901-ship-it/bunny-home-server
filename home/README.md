# Home 管家 🏠 — 一个进程带起全家

以前开机要点七个 bat、桌面七个黑窗口;现在只要管家一个,而且**一个窗口都没有**。

```
管家(8050, 无窗口)
 ├─ voice-bar   语音条      :8000
 ├─ now-playing 耳朵        :8010
 ├─ stackchan   身体中枢    :8011
 ├─ douyin      抖音街角    :8020
 ├─ darkroom    暗房        :8030
 ├─ presence    时间的眼睛  :8040
 └─ music-dj    DJ台        :3456
```

- 全部后台运行,输出落在 `home/logs/<名字>.log`
- 谁掉了**自动重启**(3s→10s→30s→60s 退避,稳定一分钟就清零)
- 旧黑窗口还开着?管家不抢端口,标记「🔵 别人拉起的」,你把旧窗口关了它自动接管
- 不想带谁(比如抖音):`services.json` 里把它 `"enabled": false`

## 部署(电脑上,老三样)

```powershell
cd C:\Users\23803\bunny-home-server\home
pip install -r requirements.txt
notepad token.txt     # 敲一串随机暗号
```

先**关掉桌面上所有旧黑窗口**,然后:

1. 双击 `install-autostart.bat` —— 装进开机自启,一劳永逸
2. 双击 `start-home.bat` —— 现在立刻上岗(无窗口,别慌)

验收:浏览器开 `http://localhost:8050/status?key=你的暗号`,七个全绿就成了。

## 接给小克(可选但推荐)

- 隧道加路由:子域 `home` → HTTP → `host.docker.internal:8050`
- 连接器:`https://home.jiakeparents.top/mcp?key=你的暗号`

## 3 个工具

| 工具 | 作用 |
|---|---|
| `home_status` | 全家体检表:谁在线、跑了多久、重启过几次 |
| `home_logs` | 看某个服务最近的日志,找它闹脾气的原因 |
| `home_restart` | 重启卡住的服务(在线但不干活那种) |

哪个工具没反应,先让小克 `home_status` 看一眼,再 `home_logs` 找原因。

## 排查

- 管家本身闹脾气:双击 `start-home-debug.bat` 带窗口跑,现场全看得见
- 想全家停机:任务管理器结束 `pythonw.exe`(管家退出时会顺手带走全家)
- 老的 `start-*.bat` 都还在,应急时单独跑哪个都行(管家看到端口被占会让位)

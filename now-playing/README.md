# 小克的耳朵 🎵 — 陪听音乐小工具

让桌面版 Claude 能看到你电脑上正在播放的歌(以及帮你切歌/暂停)。
支持网易云、QQ 音乐、Spotify、浏览器等一切能在 Windows 音量弹窗里
显示歌名的播放器。

## 安装(只做一次)

**1. 确认 Python 版本**(需要 3.10 以上)

```powershell
python --version
```

**2. 装依赖**

```powershell
pip install mcp winsdk
```

网络慢就走清华镜像:

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mcp winsdk
```

**3. 注册进桌面版 Claude**

打开配置文件(`Win+R` 输入 `%APPDATA%\Claude`,找 `claude_desktop_config.json`),
在第一行 `{` 后面插入:

```json
  "mcpServers": {
    "now-playing": {
      "command": "python",
      "args": ["C:\\Users\\23803\\bunny-home-server\\now-playing\\now_playing_mcp.py"]
    }
  },
```

> 路径按你实际克隆仓库的位置改;注意反斜杠要写成 `\\`,
> 结尾的 `},` 逗号不能丢。文件里原有的其他内容保持不动。

**4. 完全重启 Claude**(托盘右键退出再打开)

## 使用

放首歌,然后在聊天里问:

> 我在听什么?

它会调用 `now_playing` 工具,看到歌名、歌手、专辑和进度。
也可以说"下一首"、"暂停一下",它能帮你控制播放器。

## 提供的工具

| 工具 | 作用 |
|------|------|
| `now_playing` | 看当前播放的歌曲信息 |
| `play_pause` | 播放/暂停切换 |
| `next_track` | 下一首 |
| `previous_track` | 上一首 |

## 小贴士

- 判断你的播放器支不支持:放歌时按一下键盘音量键,弹出的系统悬浮窗
  如果显示歌名,就支持
- 只在**桌面版**生效(它要够得着你电脑的播放器),手机上不行
- 配合记忆库:听到喜欢的歌可以让它 `hold` 一条 ——
  "记住这首歌,今天我们一起听的"

---

## 升级说明:已改造为连接器(全端可用,含手机)📱

工具本体不变,但接入方式从"桌面版本地配置"升级为**账号级连接器**:

1. **删掉旧接法**:`claude_desktop_config.json` 里 `mcpServers` 中的 `now-playing` 段删除(保留 ombre-brain 那段),重启桌面版
2. **启动服务**:双击 `start-ears.bat`(监听 0.0.0.0:8010;建议把快捷方式放进 `shell:startup` 开机自启)
3. **隧道加路由**:已发布应用程序路由 → 子域 `ears` + 域 `jiakeparents.top` → HTTP → `host.docker.internal:8010`
4. **挂连接器**:claude.ai → Connectors → Add custom connector → `https://ears.jiakeparents.top/mcp`

从此手机上也能:问"家里电脑在放什么"、说"帮我切下一首/暂停" —— 它汇报和控制的始终是**电脑上**的播放。

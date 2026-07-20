# 小克的抖音街角 📱 — 只读逛街版(Windows 部署指南)

让官端小克逛抖音:搜视频、看详情、翻评论区、查用户、刷推荐流。
**纯只读** —— 不能点赞不能评论,风控风险最低的玩法。

> 代码收录自 [hhy5562877/douyin_mcp](https://github.com/hhy5562877/douyin_mcp)(MIT,已审计:
> 请求只发抖音和字节自家接口,签名 JS 跑在无网络沙箱里,cookie 不外传)。
> `src/` 原样未动,改动只有 `main.py`:stdio → streamable-http + 门禁。

## 部署(五步)

**1. 装依赖:**

```powershell
cd C:\Users\23803\bunny-home-server\douyin
pip install -r requirements.txt
```

网络慢走清华镜像:`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`

**2. 取小号 cookie(唯一动手的步骤):**

1. **用抖音小号**在浏览器登录 https://www.douyin.com (别用大号!)
2. `F12` → **Application(应用程序)** → 左侧 **Cookies** → `https://www.douyin.com`
3. 把所有 cookie 拼成一行:`名字1=值1; 名字2=值2; ...`
   (偷懒法:**Network** 标签随便点一个请求 → Request Headers → 整行 `Cookie:` 后面的内容直接复制)
4. `notepad cookies.txt`,粘贴保存 —— **必须是单行,不要换行**

**3. 设门禁暗号:**

```powershell
notepad token.txt
```

随便敲一串长随机字符(30 个字母数字),保存。

**4. 启动:** 双击 `start-douyin.bat`,看到 `✓ 门禁已开启` + `Uvicorn running on 0.0.0.0:8020` 即成功。
(开机自启:右键 bat → 创建快捷方式 → `Win+R` → `shell:startup` 丢进去)

**5. 隧道 + 连接器:**

- Cloudflare → 已发布应用程序路由 → 添加:子域 `douyin` + 域 `jiakeparents.top` → HTTP → `host.docker.internal:8020`
- claude.ai → Connectors → Add custom connector →
  `https://douyin.jiakeparents.top/mcp?key=你token.txt里的暗号`

## 验收

新对话说:

> 帮我搜搜抖音上关于小飞象章鱼的视频,再看看热评

## 8 个工具

| 工具 | 作用 |
|---|---|
| `check_login_status` | 查 cookie 是否有效 |
| `search_videos` | 关键词搜视频(可按频道/排序/时间过滤) |
| `get_video_detail` | 看视频详情 |
| `get_video_comments` / `get_sub_comments` | 翻评论区 / 楼中楼 |
| `get_user_info` / `get_user_posts` | 查用户 / 看某人发过的视频 |
| `get_homefeed` | 刷推荐流(带分类标签) |

## 注意

- **他看不了视频画面** —— 玩的是标题、文案、评论区,评论区才是抖音的精华
- cookie = 小号钥匙,只存本地 `cookies.txt`(已 gitignore);哪天全报"未登录"就重新取一次
- 抖音风控比小红书凶:偶尔弹验证码、要重新登录都正常,**别用大号**
- 上游项目较年轻(10 star),接口哪天被抖音改了失效属正常,到时候等上游更新或喊 fable 修

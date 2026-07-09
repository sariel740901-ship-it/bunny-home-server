# Ombre Brain 记忆库 — 部署与连接指南

[Ombre Brain](https://github.com/P0luz/Ombre-Brain) 是一个带情绪坐标和遗忘曲线的长期记忆系统，
通过 MCP 协议连接 Claude。这个目录是它的部署配置，在你自己的电脑上运行
（Vercel 跑不了它——它需要 Docker 和持久磁盘）。

## 第一步：启动记忆库（在你的电脑上）

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows/Mac 都有）。
2. 把这个 `ombre-brain/` 文件夹放到你电脑上（克隆本仓库即可）。
3. 在这个文件夹里打开终端，执行：

   ```bash
   cp .env.example .env
   ```

4. 编辑 `.env`，填两个必填项：
   - `OMBRE_COMPRESS_API_KEY` — 去 [Google AI Studio](https://aistudio.google.com/apikey) 免费申请一个 key
   - `OMBRE_DASHBOARD_PASSWORD` — 自己设一个密码（后面连 claude.ai 时也用它）
5. 启动：

   ```bash
   docker compose up -d
   ```

6. 验证：浏览器打开 <http://localhost:18001> 能看到 Dashboard，
   或者 `curl http://localhost:18001/health` 返回正常即成功。

记忆数据保存在 `./buckets/` 文件夹里（已加入 .gitignore，不会被提交）。
**备份这个文件夹 = 备份全部记忆。**

## 第二步：连接 Claude Desktop（桌面版，最简单）

编辑配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

加入：

```json
{
  "mcpServers": {
    "ombre-brain": {
      "type": "streamable-http",
      "url": "http://localhost:18001/mcp"
    }
  }
}
```

重启 Claude Desktop，对话里就能看到 ombre-brain 的工具了。

## 第三步：连接 Claude.ai 网页版（可选，需要公网 HTTPS）

网页版无法访问 `localhost`，需要先用 Cloudflare Tunnel 把服务暴露到公网：

1. 打开 [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → Networks → Tunnels，
   创建一个 tunnel，复制 token（以 `eyJ` 开头）。
2. 打开 Ombre Brain 的 Dashboard（<http://localhost:18001>）→ 设置 → Cloudflare Tunnel →
   粘贴 token → 启动。状态点变绿后，在 Cloudflare 里给 tunnel 配一个公网域名，
   指向 `http://localhost:18001`。
3. 打开 [claude.ai](https://claude.ai) → Settings → Connectors → Add custom connector，
   填入 `https://你的域名/mcp`。
4. 会自动弹出 OAuth 授权，输入你的 Dashboard 密码即可。

> 注意：claude.ai 网页版的自定义连接器需要 Pro/Max 等付费订阅。

## 日常操作

```bash
docker compose up -d        # 启动
docker compose down         # 停止（记忆不会丢，都在 ./buckets）
docker compose pull && docker compose up -d   # 升级到最新版
docker compose logs -f      # 看日志
```

## 常用工具速查

连接成功后 Claude 会多出 12 个记忆工具，高频的几个：

| 工具 | 作用 |
|------|------|
| `breath` | 浮现相关记忆 |
| `hold` | 记录一件事 |
| `grow` | 整理长内容存入记忆 |
| `trace` | 修改记忆的元数据 |
| `dream` | 消化、沉淀记忆 |

require('dotenv').config();
const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

// 健康检查 — Render 部署后验证服务在跑
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'Bunny Home', timestamp: new Date().toISOString() });
});

// 占位 — 后续接 Supabase + Claude API
app.get('/', (req, res) => {
  res.json({ message: 'Bunny Home 后端已启动' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Bunny Home 后端运行在端口 ${PORT}`);
});

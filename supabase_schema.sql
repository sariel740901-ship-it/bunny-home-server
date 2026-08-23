-- Bunny Home 数据库建表 SQL — 在 Supabase SQL Editor 中粘贴并执行

-- 1. 会话管理
CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '新对话',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 聊天消息
CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  visible BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 记忆摘要 — 全局，被压缩后供所有会话使用
CREATE TABLE IF NOT EXISTS memories (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  conversation_id TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- (曾经还有一张 settings 表存 system_prompt/温度/上下文轮数,已废弃删除 ——
--  人设在 server.js 的 PERSONAS 里,上下文用环境变量 CONTEXT_BUDGET_TOKENS 控制)

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

-- 4. 动态 — 你们共用的朋友圈(她发文字+图,他只发文字;likes 是 ['her','him'] 这样的数组)
CREATE TABLE IF NOT EXISTS moments (
  id SERIAL PRIMARY KEY,
  author TEXT NOT NULL CHECK (author IN ('her', 'him')),
  content TEXT NOT NULL DEFAULT '',
  images JSONB DEFAULT '[]',
  seen JSONB DEFAULT '[]',      -- 配图的识图描述(发图后后台自动生成,官端靠它"看到"图)
  likes JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
-- 老库补列用这句:
-- ALTER TABLE moments ADD COLUMN IF NOT EXISTS seen JSONB DEFAULT '[]';

-- 5. 动态的评论楼
CREATE TABLE IF NOT EXISTS moment_comments (
  id SERIAL PRIMARY KEY,
  moment_id INTEGER REFERENCES moments(id) ON DELETE CASCADE,
  author TEXT NOT NULL CHECK (author IN ('her', 'him')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 开关旗标 — 需要"从服务端真正拦住"的开关放这里(目前只有自发醒来 wake_enabled)
CREATE TABLE IF NOT EXISTS flags (
  key TEXT PRIMARY KEY,
  value JSONB,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- (曾经还有一张 settings 表存 system_prompt/温度/上下文轮数,已废弃删除 ——
--  人设在 server.js 的 PERSONAS 里,上下文用环境变量 CONTEXT_BUDGET_TOKENS 控制)

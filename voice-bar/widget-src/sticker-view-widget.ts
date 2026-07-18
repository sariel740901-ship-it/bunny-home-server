import { App } from "@modelcontextprotocol/ext-apps";

/**
 * 表情包 widget — renders the sticker image inline in chat (instead of it being
 * buried inside the collapsed tool-result block). Minimal by design: transparent
 * background, one rounded image, WeChat-style.
 * Data arrives via structuredContent (Claude: `toolresult` / ChatGPT: window.openai.toolOutput).
 */

interface StickerData {
  imageUrl: string; // https URL or data: URI
  name: string;
  senderName: string;
  colorPrimary: string;
  colorSecondary: string;
  colorBg: string;
  colorBgEnd: string;
}

declare global {
  interface Window {
    openai?: { toolOutput?: unknown; [k: string]: unknown };
  }
}

function coerce(data: unknown): StickerData | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (typeof d.imageUrl !== "string" || !d.imageUrl) return null;
  const str = (v: unknown, fb: string) => (typeof v === "string" && v ? v : fb);
  return {
    imageUrl: d.imageUrl,
    name: str(d.name, ""),
    senderName: str(d.senderName, ""),
    colorPrimary: str(d.colorPrimary, "#e898a4"),
    colorSecondary: str(d.colorSecondary, "#d97f8e"),
    colorBg: str(d.colorBg, "#2b1f26"),
    colorBgEnd: str(d.colorBgEnd, "#241a20")
  };
}

let appRef: App | null = null;
let rendered = false;

function render(data: StickerData, platform: "chatgpt" | "claude") {
  rendered = true;
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = "";

  // Full-width skin card, same visual family as the voice bubble — so if the host
  // keeps the widget at full row width there's no bare gap, and if it honors our
  // reported width the card simply shrinks around the sticker.
  const card = document.createElement("div");
  card.id = "stk-card";
  card.style.cssText = `
    position:relative; box-sizing:border-box; width:100%;
    display:flex; align-items:center; padding:14px 18px 24px;
    background:radial-gradient(140px 90px at 20% 40%, ${data.colorPrimary}30, transparent 72%),
      radial-gradient(160px 120px at 88% 120%, ${data.colorSecondary}22, transparent 70%),
      linear-gradient(135deg, ${data.colorBg}, ${data.colorBgEnd});
    overflow:hidden;
    font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei UI",sans-serif;`;

  const deco = document.createElement("div");
  deco.id = "stk-deco";
  deco.textContent = "✦";
  deco.style.cssText = `position:absolute; right:20px; top:12px; font-size:14px;
    color:${data.colorPrimary}; opacity:0.35; pointer-events:none;`;
  card.appendChild(deco);

  const img = document.createElement("img");
  img.id = "stk-img";
  img.src = data.imageUrl;
  img.alt = data.name;
  img.title = data.name;
  img.style.cssText =
    "max-width:170px; max-height:170px; border-radius:12px; display:block; position:relative; z-index:1;";
  card.appendChild(img);

  if (data.senderName) {
    const nameEl = document.createElement("div");
    nameEl.id = "stk-name";
    nameEl.textContent = data.senderName + " · 表情";
    nameEl.style.cssText = `position:absolute; left:20px; bottom:8px; font-size:9px;
      color:rgba(255,255,255,0.4); pointer-events:none;`;
    card.appendChild(nameEl);
  }
  root.appendChild(card);

  // Report height, plus the CONTENT width (sticker + padding) — hosts that honor
  // width shrink the frame to sticker size; hosts that don't still get the skin.
  if (platform === "claude") {
    const reportSize = () => {
      const h = Math.ceil(card.getBoundingClientRect().height);
      if (h <= 0) return;
      const w = Math.min(
        Math.ceil(window.innerWidth),
        Math.ceil(img.getBoundingClientRect().width) + 36 + 4
      );
      document.documentElement.style.height = h + "px";
      document.body.style.height = h + "px";
      if (appRef) {
        try {
          appRef.sendSizeChanged({ width: w, height: h });
        } catch {
          /* ignore */
        }
      }
    };
    img.addEventListener("load", () => {
      reportSize();
      requestAnimationFrame(reportSize);
      setTimeout(reportSize, 200);
    });
    img.addEventListener("error", () => {
      card.innerHTML =
        `<div style="color:#e8dee2;font-size:13px;padding:8px;">图片加载失败: ${data.name}</div>`;
      reportSize();
    });
  }
}

function showError(msg: string) {
  if (rendered) return;
  const root = document.getElementById("root");
  if (root) root.innerHTML = `<div style="color:#b8aabb;font-size:13px;padding:10px;">${msg}</div>`;
}

function renderToolResult(
  params: { structuredContent?: unknown; content?: Array<{ type: string; text?: string }> },
  platform: "chatgpt" | "claude"
) {
  let data = coerce(params?.structuredContent);
  if (!data && Array.isArray(params?.content)) {
    for (const block of params.content) {
      if (block.type === "text" && block.text) {
        try {
          data = coerce(JSON.parse(block.text));
        } catch {
          /* not json */
        }
        if (data) break;
      }
    }
  }
  if (data) render(data, platform);
}

function tryChatGpt() {
  if (!window.openai) return;
  const apply = () => {
    const data = coerce(window.openai?.toolOutput);
    if (data) render(data, "chatgpt");
  };
  apply();
  window.addEventListener("openai:set_globals", apply as EventListener);
  window.addEventListener(
    "message",
    (event) => {
      if (event.source !== window.parent) return;
      const message = (event as MessageEvent).data;
      if (!message || message.jsonrpc !== "2.0") return;
      if (message.method !== "ui/notifications/tool-result") return;
      renderToolResult(message.params, "chatgpt");
    },
    { passive: true }
  );
}

async function tryMcpApps() {
  try {
    const app = new App({ name: "voice-mcp", version: "1.0.0" }, {}, { autoResize: false });
    appRef = app;
    app.addEventListener("toolresult", (params: { structuredContent?: unknown; content?: Array<{ type: string; text?: string }> }) => {
      renderToolResult(params, "claude");
    });
    await app.connect();
  } catch (e) {
    console.debug("[sticker] MCP Apps connect skipped:", e);
  }
}

function boot() {
  tryChatGpt();
  void tryMcpApps();
  setTimeout(() => showError("等待表情数据…"), 4000);
}

boot();

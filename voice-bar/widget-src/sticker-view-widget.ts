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
  return { imageUrl: d.imageUrl, name: typeof d.name === "string" ? d.name : "" };
}

let appRef: App | null = null;
let rendered = false;

function render(data: StickerData, platform: "chatgpt" | "claude") {
  rendered = true;
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.id = "stk-wrap";
  wrap.style.cssText =
    "display:flex; padding:4px 2px; background:transparent; " +
    'font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei UI",sans-serif;';

  const img = document.createElement("img");
  img.id = "stk-img";
  img.src = data.imageUrl;
  img.alt = data.name;
  img.title = data.name;
  img.style.cssText =
    "max-width:180px; max-height:180px; border-radius:12px; display:block;";
  wrap.appendChild(img);
  root.appendChild(wrap);

  // Report only HEIGHT to the host (same contract as the voice widget).
  if (platform === "claude") {
    const reportH = () => {
      const h = Math.ceil(wrap.getBoundingClientRect().height) + 8;
      if (h <= 8) return;
      document.documentElement.style.height = h + "px";
      document.body.style.height = h + "px";
      if (appRef) {
        try {
          appRef.sendSizeChanged({ width: Math.ceil(window.innerWidth), height: h });
        } catch {
          /* ignore */
        }
      }
    };
    img.addEventListener("load", () => {
      reportH();
      requestAnimationFrame(reportH);
      setTimeout(reportH, 200);
    });
    img.addEventListener("error", () => {
      wrap.innerHTML =
        `<div style="color:#b8aabb;font-size:13px;padding:8px;">图片加载失败: ${data.name}</div>`;
      reportH();
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

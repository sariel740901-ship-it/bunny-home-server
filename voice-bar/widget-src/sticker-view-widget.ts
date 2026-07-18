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

  // Chameleon card: the host keeps the widget at full row width and paints a bare
  // frame around transparent content, so instead of a decorated skin we blend in —
  // paint the same background as the claude.ai chat page (light/dark follows the
  // device color scheme) and let the sticker sit on it like a plain image.
  const dark = typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const pageBg = dark ? "#262624" : "#faf9f5";

  const card = document.createElement("div");
  card.id = "stk-card";
  card.style.cssText = `
    position:relative; box-sizing:border-box; width:100%;
    display:flex; align-items:center; padding:8px 10px;
    background:${pageBg}; overflow:hidden;
    font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei UI",sans-serif;`;

  const img = document.createElement("img");
  img.id = "stk-img";
  img.src = data.imageUrl;
  img.alt = data.name;
  img.title = data.name;
  img.style.cssText =
    "max-width:170px; max-height:170px; border-radius:12px; display:block;";
  card.appendChild(img);
  root.appendChild(card);

  // follow live theme switches too
  if (typeof window.matchMedia === "function") {
    try {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
        card.style.background = e.matches ? "#262624" : "#faf9f5";
      });
    } catch {
      /* older engines */
    }
  }

  // Report height, plus the CONTENT width (sticker + padding) — hosts that honor
  // width shrink the frame to sticker size; hosts that don't still get the skin.
  if (platform === "claude") {
    const reportSize = () => {
      const h = Math.ceil(card.getBoundingClientRect().height);
      if (h <= 0) return;
      const w = Math.min(
        Math.ceil(window.innerWidth),
        Math.ceil(img.getBoundingClientRect().width) + 24
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
        `<div style="color:#8a8580;font-size:13px;padding:8px;">图片加载失败: ${data.name}</div>`;
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

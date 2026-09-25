import { App } from "@modelcontextprotocol/ext-apps";

/**
 * 祈牌语音条 widget — a full-width "voice skin" card: a themed background fills the
 * host's iframe (killing the white gap), with a compact voice bubble on top whose
 * width grows with the clip duration (WeChat-style).
 * Data arrives via structuredContent (Claude: `toolresult` / ChatGPT: window.openai.toolOutput).
 */

interface VoiceData {
  audioUrl: string;          // data:audio/mpeg;base64,... or https URL
  duration: number;          // seconds (estimated)
  senderName: string;
  colorPrimary: string;
  colorSecondary: string;
  colorBg: string;
  colorBgEnd: string;
  barCount: number;
  bgImage: string;           // optional skin background image URL ("" = default gradient skin)
  customCss: string;         // optional user CSS injected into the widget (data-driven, live)
  bars: number[];            // real waveform peaks (0-1) from the audio; [] = default shape
  bubbleStyle: string;       // "waveform" (default skin card) | "qq" (QQ-style solid bubble)
}

declare global {
  interface Window {
    openai?: { toolOutput?: unknown;[k: string]: unknown };
  }
}

function coerce(data: unknown): VoiceData | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (typeof d.audioUrl !== "string" || !d.audioUrl) return null;
  const str = (v: unknown, fb: string) => (typeof v === "string" && v ? v : fb);
  const num = (v: unknown, fb: number) => (typeof v === "number" && isFinite(v) ? v : fb);
  return {
    audioUrl: d.audioUrl,
    duration: num(d.duration, 1),
    senderName: str(d.senderName, "祈"),
    colorPrimary: str(d.colorPrimary, "#f59e0b"),
    colorSecondary: str(d.colorSecondary, "#ea580c"),
    colorBg: str(d.colorBg, "#1e1b18"),
    colorBgEnd: str(d.colorBgEnd, "#2a2520"),
    barCount: num(d.barCount, 28),
    bgImage: str(d.bgImage, ""),
    customCss: str(d.customCss, ""),
    bars: Array.isArray(d.bars) ? (d.bars as unknown[]).map((x) => (typeof x === "number" ? x : 0)) : [],
    bubbleStyle: str(d.bubbleStyle, "waveform")
  };
}

/** Deterministic pseudo-random in [0,1) seeded by i, so the waveform is stable across renders. */
function seeded(i: number): number {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

let appRef: App | null = null;
let rendered = false;

function fmtTime(secs: number): string {
  const s = Math.max(0, Math.floor(secs));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

/** Inject the user's live custom CSS (edited in /customize; applies on the next voice). */
function applyCustomCss(css: string) {
  let styleEl = document.getElementById("vc-custom-css") as HTMLStyleElement | null;
  if (!styleEl) {
    styleEl = document.createElement("style");
    styleEl.id = "vc-custom-css";
    document.head.appendChild(styleEl);
  }
  styleEl.textContent = css || "";
}

/** Report only HEIGHT to the host (width is fixed by host = full width). */
function reportHeight(card: HTMLElement, platform: "chatgpt" | "claude") {
  if (platform !== "claude") return;
  const reportH = () => {
    const h = Math.ceil(card.getBoundingClientRect().height);
    if (h <= 0) return;
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
  requestAnimationFrame(() => {
    reportH();
    requestAnimationFrame(reportH);
    setTimeout(reportH, 200);
  });
}

function render(data: VoiceData, platform: "chatgpt" | "claude") {
  rendered = true;
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = "";
  applyCustomCss(data.customCss);
  if (data.bubbleStyle === "qq") renderQQ(root, data, platform);
  else renderWaveform(root, data, platform);
}

/**
 * QQ-style bubble: a solid-colour speech bubble with a little tail on the left, the
 * classic speaker-with-three-arcs icon, the duration as 22'' on the right, and a red
 * "unplayed" dot after the bubble. Bubble width grows with duration (like QQ), and the
 * three arcs light up one after another while playing. Sits on a transparent background
 * so it reads as a chat bubble rather than a card.
 */
function renderQQ(root: HTMLElement, data: VoiceData, platform: "chatgpt" | "claude") {
  const card = document.createElement("div");
  card.id = "vc-card";
  card.style.cssText = `
    position:relative; box-sizing:border-box; width:100%; padding:2px 8px 6px 10px;
    background:transparent; overflow:hidden;
    font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei UI",sans-serif;`;

  // nickname above the bubble (QQ group-chat style)
  const nameEl = document.createElement("div");
  nameEl.id = "vc-name";
  nameEl.textContent = data.senderName;
  nameEl.style.cssText = `font-size:11px; line-height:14px; color:#8e8e93; margin:0 0 4px 10px;
    pointer-events:none;`;
  card.appendChild(nameEl);

  const row = document.createElement("div");
  row.id = "vc-row";
  row.style.cssText = "display:flex; align-items:center; gap:8px;";

  // width follows duration: ~88px for a 1s clip, +6px per second, capped like QQ does
  const w = Math.round(Math.max(88, Math.min(260, 88 + data.duration * 6)));
  const bubble = document.createElement("div");
  bubble.id = "vc-bubble";
  bubble.style.cssText = `
    position:relative; box-sizing:border-box; display:flex; align-items:center;
    justify-content:space-between; width:${w}px; height:40px; padding:0 14px 0 12px;
    background:${data.colorPrimary}; color:#fff; border-radius:12px;
    box-shadow:0 1px 2px rgba(0,0,0,0.12); cursor:pointer; user-select:none;`;

  // the little tail pointing at the avatar side
  const tail = document.createElement("div");
  tail.id = "vc-tail";
  tail.style.cssText = `position:absolute; left:-4px; top:13px; width:10px; height:10px;
    background:${data.colorPrimary}; border-radius:2px; transform:rotate(45deg); pointer-events:none;`;
  bubble.appendChild(tail);

  // speaker + three arcs (arcs are separate paths so they can animate one by one)
  const icon = document.createElement("div");
  icon.id = "vc-play";
  icon.style.cssText = "width:20px; height:20px; flex-shrink:0; display:flex; align-items:center;";
  icon.innerHTML =
    `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">` +
    `<path d="M4 10.5v3a1 1 0 0 0 1 1h1.6l3.2 2.6V6.9L6.6 9.5H5a1 1 0 0 0-1 1z" fill="#fff"/>` +
    `<path class="arc" d="M13.5 9.6a3.4 3.4 0 0 1 0 4.8"/>` +
    `<path class="arc" d="M16 7.3a6.6 6.6 0 0 1 0 9.4"/>` +
    `<path class="arc" d="M18.5 5a10 10 0 0 1 0 14"/>` +
    `</svg>`;
  const arcs = Array.from(icon.querySelectorAll(".arc")) as SVGElement[];

  const durEl = document.createElement("span");
  durEl.id = "vc-dur";
  durEl.textContent = data.duration + "''";
  durEl.style.cssText = "font-size:14px; line-height:1; color:#fff; font-variant-numeric:tabular-nums;";

  const audio = document.createElement("audio");
  audio.preload = "auto";
  audio.src = data.audioUrl;

  bubble.append(icon, durEl, audio);

  // unread dot — QQ shows it until the voice has been played once
  const dot = document.createElement("div");
  dot.id = "vc-dot";
  dot.style.cssText = "width:8px; height:8px; border-radius:50%; background:#fa5151; flex-shrink:0;";

  row.append(bubble, dot);
  card.appendChild(row);
  root.appendChild(card);

  // ── Playback: arcs light up 1 → 2 → 3 in a loop while playing ──
  let playing = false;
  let timer = 0;
  let step = 0;
  const setArcs = (lit: number) => arcs.forEach((a, i) => (a.style.opacity = i < lit ? "1" : "0.35"));
  const idle = () => arcs.forEach((a) => (a.style.opacity = "1"));
  const animate = () => {
    step = (step + 1) % 3;
    setArcs(step + 1);
  };
  const stop = () => {
    playing = false;
    clearInterval(timer);
    idle();
  };
  const toggle = () => {
    if (playing) {
      audio.pause();
      stop();
    } else {
      audio.play().then(() => {
        playing = true;
        dot.style.display = "none";
        step = 0;
        setArcs(1);
        timer = window.setInterval(animate, 300);
      }).catch((e) => console.warn("[voice] playback failed:", e));
    }
  };
  bubble.addEventListener("click", toggle);
  audio.addEventListener("ended", stop);

  reportHeight(card, platform);
}

function renderWaveform(root: HTMLElement, data: VoiceData, platform: "chatgpt" | "claude") {
  // ── Full-width skin card (fills the host iframe → no white gap) ──
  const card = document.createElement("div");
  card.id = "vc-card";
  const bg = data.bgImage
    ? `center/cover no-repeat url("${data.bgImage}"), linear-gradient(135deg, ${data.colorBg}, ${data.colorBgEnd})`
    : `radial-gradient(140px 90px at 22% 50%, ${data.colorPrimary}33, transparent 72%),` +
      `radial-gradient(160px 120px at 88% 120%, ${data.colorSecondary}22, transparent 70%),` +
      `linear-gradient(135deg, ${data.colorBg}, ${data.colorBgEnd})`;
  card.style.cssText = `
    position:relative; box-sizing:border-box; width:100%; min-width:280px;
    min-height:92px; display:flex; align-items:center; padding:0 20px;
    background:${bg}; overflow:hidden;
    font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei UI",sans-serif;`;

  // subtle music-note flourish on the right
  const deco = document.createElement("div");
  deco.id = "vc-deco";
  deco.textContent = "♪  ♫";
  deco.style.cssText = `position:absolute; right:20px; top:14px; font-size:15px;
    color:${data.colorPrimary}; opacity:0.35; letter-spacing:2px; pointer-events:none;`;
  card.appendChild(deco);

  // ── Voice bubble; width follows the waveform via width:auto (WeChat-style: longer clip
  //    → more bars → wider bubble). This "length follows duration" is the fixed core logic;
  //    look (bg/border/radius) stays fully overridable via custom_css. ──
  const bubble = document.createElement("div");
  bubble.id = "vc-bubble";
  bubble.style.cssText = `
    position:relative; z-index:1; box-sizing:border-box;
    display:inline-flex; align-items:center; gap:10px; width:auto; max-width:calc(100% - 8px);
    background:linear-gradient(135deg, rgba(0,0,0,0.34), rgba(0,0,0,0.18));
    border:1px solid ${data.colorPrimary}33; border-radius:16px; padding:8px 14px;
    box-shadow:0 3px 12px rgba(0,0,0,0.28); cursor:pointer; user-select:none;
    backdrop-filter:blur(2px);`;

  // play / pause button
  const btn = document.createElement("div");
  btn.id = "vc-play";
  btn.style.cssText = `
    width:30px; height:30px; border-radius:50%; flex-shrink:0;
    background:linear-gradient(135deg, ${data.colorPrimary}, ${data.colorSecondary});
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 2px 6px ${data.colorPrimary}55;`;
  btn.innerHTML =
    `<svg class="i-play" width="13" height="13" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>` +
    `<svg class="i-pause" width="13" height="13" viewBox="0 0 24 24" fill="white" style="display:none"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>`;
  const iPlay = btn.querySelector(".i-play") as SVGElement;
  const iPause = btn.querySelector(".i-pause") as SVGElement;

  // waveform + labels
  const col = document.createElement("div");
  col.id = "vc-col";
  col.style.cssText = "display:flex; flex-direction:column; gap:3px;";
  const wave = document.createElement("div");
  wave.id = "vc-wave";
  wave.style.cssText = "display:flex; align-items:center; gap:2px; height:22px; width:auto;";
  const bars: HTMLDivElement[] = [];
  // Fixed core logic: bar count scales with duration → the fixed-width bars make the wave
  // (and the auto-width bubble around it) grow longer for longer clips.
  // Real waveform from the audio when available (data.bars = 0-1 loudness peaks);
  // otherwise a stable default shape. Bar count follows duration either way.
  const real = data.bars && data.bars.length > 0 ? data.bars : null;
  const n = real ? real.length : Math.max(12, Math.min(60, Math.round(data.duration * 3.2)));
  for (let i = 0; i < n; i++) {
    const bar = document.createElement("div");
    const pos = i / n;
    const env = Math.sin(pos * Math.PI) * 0.55 + 0.45;
    const h = real
      ? Math.max(10, Math.min(100, real[i] * 100))
      : Math.max(14, Math.min(100, (0.28 + seeded(i) * 0.72) * env * 100));
    bar.style.cssText =
      `width:3px; height:${h}%; border-radius:1.5px; flex-shrink:0;` +
      `background:rgba(255,255,255,0.28); transition:background 0.12s;`;
    wave.appendChild(bar);
    bars.push(bar);
  }
  const labels = document.createElement("div");
  labels.id = "vc-labels";
  labels.style.cssText = "display:flex; justify-content:space-between; align-items:center;";
  const timeEl = document.createElement("span");
  timeEl.id = "vc-time";
  timeEl.textContent = "0:00";
  timeEl.style.cssText = `font-size:9px; color:${data.colorPrimary}; font-weight:600;`;
  const durEl = document.createElement("span");
  durEl.id = "vc-dur";
  durEl.textContent = data.duration + '"';
  durEl.style.cssText = "font-size:9px; color:rgba(255,255,255,0.45);";
  labels.append(timeEl, durEl);
  col.append(wave, labels);

  const audio = document.createElement("audio");
  audio.preload = "auto";
  audio.src = data.audioUrl;

  bubble.append(btn, col, audio);
  card.appendChild(bubble);

  // sender name under the bubble, on the skin
  const nameEl = document.createElement("div");
  nameEl.id = "vc-name";
  nameEl.textContent = data.senderName + " · 语音";
  nameEl.style.cssText = `position:absolute; left:22px; bottom:12px; font-size:9px;
    color:rgba(255,255,255,0.4); pointer-events:none;`;
  card.appendChild(nameEl);

  root.appendChild(card);

  // ── Playback ──
  let playing = false;
  let raf = 0;
  const paint = (on: boolean, bar: HTMLDivElement) => {
    if (on) {
      bar.style.background = `linear-gradient(to top, ${data.colorPrimary}, ${data.colorSecondary})`;
      bar.style.boxShadow = `0 0 3px ${data.colorPrimary}44`;
    } else {
      bar.style.background = "rgba(255,255,255,0.28)";
      bar.style.boxShadow = "none";
    }
  };
  const tick = () => {
    if (!playing) return;
    const prog = audio.currentTime / (audio.duration || data.duration || 1);
    const upto = Math.floor(prog * bars.length);
    bars.forEach((b, i) => paint(i < upto, b));
    timeEl.textContent = fmtTime(audio.currentTime);
    raf = requestAnimationFrame(tick);
  };
  const toggle = () => {
    if (playing) {
      audio.pause();
      playing = false;
      iPlay.style.display = "block";
      iPause.style.display = "none";
      cancelAnimationFrame(raf);
    } else {
      audio.play().then(() => {
        playing = true;
        iPlay.style.display = "none";
        iPause.style.display = "block";
        tick();
      }).catch((e) => console.warn("[voice] playback failed:", e));
    }
  };
  bubble.addEventListener("click", toggle);
  audio.addEventListener("ended", () => {
    playing = false;
    iPlay.style.display = "block";
    iPause.style.display = "none";
    cancelAnimationFrame(raf);
    bars.forEach((b) => paint(false, b));
    timeEl.textContent = "0:00";
  });

  reportHeight(card, platform);
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
    console.debug("[voice] MCP Apps connect skipped:", e);
  }
}

function boot() {
  tryChatGpt();
  void tryMcpApps();
  setTimeout(() => showError("等待语音数据…"), 4000);
}

boot();

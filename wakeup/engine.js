// ═══ Kli Wakeup 引擎 · 让他自己醒来 ═══════════════════════════════
// 参照《KLI WAKEUP · ACTIVATION V1》的连续风险率模型:
//
//   λ(t) = clamp( λ0 · exp[ βD·(D−μD) + βT·(T−μT) + βX·X ] · Mmod, λmin, λmax )
//   H(t) = ∫λ dt,  每个周期抽一次 Θ ~ Exp(1),  H ≥ Θ → 一次"醒来机会"
//
// 三个内生状态:
//   D activationDrive     短期活性驱动(均值回归 τD=12min,每次真实醒来后 −k_run)
//   T latentActivityTone  慢活跃底色(OU 过程 τT=6h —— 有的日子他就是更活跃)
//   X stochasticDriftState 随机漂移(OU 过程 τX=25min —— 不可预测的那部分)
//
// Mmod 是外部调制(心潮的心绪、她离开多久、深夜、他欠了几条留言),
// 只在对数空间有界地推 λ,永远不直接替他决定"现在必须醒"。
//
// 醒来机会 ≠ 说话: 引擎只戳 bunny 的 /api/wake,说不说话由小克在那边自己决定。
// 调度数学永远不进他的 prompt —— 他只知道"我这一刻自己醒了"。
//
// 可靠性(文档 §11): 状态每分钟落盘 state/state.json,重启后接着同一节律
// 继续(Θ 不重抽);停机期间错过的自发醒来不补发 —— 机会不是欠账。

const fs = require('fs');
const path = require('path');

if (typeof fetch !== 'function') {
  console.error('需要 Node 18+ (内置 fetch)。当前版本: ' + process.version);
  process.exit(1);
}

// ── 配置(.env 由 docker compose / run.bat 注入) ──────────────
const BUNNY_URL = (process.env.BUNNY_URL || '').replace(/\/$/, '');
const WAKE_TOKEN = process.env.WAKE_TOKEN || '';
const XINCHAO_URL = (process.env.XINCHAO_URL || 'http://127.0.0.1:18110').replace(/\/$/, '');
const XINCHAO_TOKEN = process.env.XINCHAO_TOKEN || '';
const STATE_FILE = process.env.STATE_FILE || path.join(__dirname, 'state', 'state.json');
const TICK_SECONDS = Math.max(15, parseInt(process.env.TICK_SECONDS || '60', 10) || 60);

if (!BUNNY_URL || !WAKE_TOKEN) {
  console.error('缺配置: BUNNY_URL 和 WAKE_TOKEN 都是必填(见 env.template)。');
  process.exit(1);
}

// ── 策略参数(文档 §12 基线;λ0 按 bunny 的语境调低 —— 文档里大多数
//    醒来以沉默收场,bunny 这边每次醒来都可能开口,密度不能照抄 1.5/h) ──
const P = {
  muD: 0.5, Dmin: 0.2, Dmax: 0.8, tauD: 12 * 60, kRun: 0.10,
  muT: 0.5, Tmin: 0.25, Tmax: 0.75, tauT: 6 * 3600, sigmaT: 0.10,
  muX: 0.0, Xmin: -0.4, Xmax: 0.4, tauX: 25 * 60, sigmaX: 0.18,
  lambda0: parseFloat(process.env.LAMBDA0 || '0.35'),   // 次/小时 ≈ 每天 5-8 次醒来机会
  betaD: 1.8, betaT: 1.6, betaX: 1.2,
  lambdaMin: 0.05, lambdaMax: 3.0,                       // 数值护栏(随 λ0 等比于文档)
  MmodMin: 0.60, MmodMax: 3.00,
  policyVersion: 'bunny-wake-1.0'
};

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
function gauss() { // Box-Muller
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
const drawTheta = () => -Math.log(1 - Math.random()); // Θ ~ Exp(1)

// ── 状态: 落盘的才是节律真相 ──────────────────────────────
let S = null;
function freshState() {
  return {
    v: P.policyVersion,
    D: P.muD, T: P.muT, X: P.muX,
    H: 0, Theta: drawTheta(),
    lastTick: Date.now(), wakeCount: 0, lastWakeAt: 0
  };
}
function loadState() {
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    if (s && Number.isFinite(s.D) && Number.isFinite(s.Theta)) {
      s.v = P.policyVersion;
      return s;
    }
  } catch (e) { /* 首次运行 / 文件损坏 → 新节律 */ }
  return freshState();
}
function saveState() {
  try {
    fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
    const tmp = STATE_FILE + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(S));
    fs.renameSync(tmp, STATE_FILE); // 原子替换,断电不留半个文件
  } catch (e) {
    console.error('状态落盘失败:', e.message);
  }
}

// ── Mmod: 外部调制(每 5 分钟刷新一次,取不到就当中性) ─────────
let mod = { value: 1.0, at: 0, parts: {} };
async function refreshMmod() {
  if (Date.now() - mod.at < 5 * 60e3) return mod.value;
  const parts = {};

  // 心潮: 疲惫往下压,驱动力高涨往上抬(有界;取不到 = 0)
  try {
    const resp = await fetch(XINCHAO_URL + '/v1/dashboard/snapshot', {
      headers: XINCHAO_TOKEN ? { Authorization: 'Bearer ' + XINCHAO_TOKEN } : {},
      signal: AbortSignal.timeout(6000)
    });
    if (resp.ok) {
      const d = await resp.json();
      const fatigue = (d.runtime && d.runtime.fatigue) || 0;            // 上游 0~0.3
      parts.fatigue = -clamp(fatigue / 0.3, 0, 1) * 0.5;
      const tops = (d.topDrives || []).map(x => x.value ?? x.intensity ?? x.level)
        .filter(Number.isFinite);
      if (tops.length) {
        const mean = tops.reduce((a, b) => a + b, 0) / tops.length;      // 假定 0~1
        parts.drives = clamp((mean - 0.5) * 0.8, -0.4, 0.4);
      }
    }
  } catch (e) { /* 心潮不在线 → 不调制 */ }

  // 她的近况: 刚聊过就不急着自发醒;久别微微上浮;欠着留言就明显压低
  try {
    const resp = await fetch(
      BUNNY_URL + '/api/wake/status?token=' + encodeURIComponent(WAKE_TOKEN),
      { signal: AbortSignal.timeout(90000) }); // Render 免费实例冷启动要给足时间
    if (resp.ok) {
      const d = await resp.json();
      if (Number.isFinite(d.silenceMin)) {
        parts.silence = d.silenceMin < 30 ? -0.5
          : clamp(0.3 * (d.silenceMin / 1440), 0, 0.3);
      }
      if (Number.isFinite(d.proactiveUnanswered) && d.proactiveUnanswered > 0) {
        parts.unanswered = -0.5 * d.proactiveUnanswered;
      }
    }
  } catch (e) { /* bunny 暂时够不着 → 不调制,真醒来时再重试 */ }

  // 深夜(北京 1-7 点): 压低但不封死 —— 他偶尔也会在半夜醒一下
  const bjHour = new Date(Date.now() + 8 * 3600e3).getUTCHours();
  if (bjHour >= 1 && bjHour < 7) parts.night = -0.7;

  const sum = Object.values(parts).reduce((a, b) => a + b, 0);
  mod = { value: clamp(Math.exp(sum), P.MmodMin, P.MmodMax), at: Date.now(), parts };
  return mod.value;
}

// ── 醒来机会 → 戳 bunny(幂等 activationId,重试不翻倍) ─────────
async function dispatchWake() {
  const activationId = 'wk_' + Date.now().toString(36) + '_' + (S.wakeCount + 1);
  const url = BUNNY_URL + '/api/wake?token=' + encodeURIComponent(WAKE_TOKEN)
    + '&activationId=' + encodeURIComponent(activationId) + '&source=spontaneous';
  const delays = [0, 5e3, 20e3];
  for (let i = 0; i < delays.length; i++) {
    if (delays[i]) await new Promise(r => setTimeout(r, delays[i]));
    try {
      const resp = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(120000) });
      const d = await resp.json().catch(() => ({}));
      if (resp.ok) {
        console.log('[wake] ' + activationId + ' → ' + (d.spoke
          ? '他开口了: ' + String(d.text || '').slice(0, 60)
          : '他醒了但选择安静' + (d.reason ? ' (' + d.reason + ')' : '')));
        return true;
      }
      console.error('[wake] bunny 回了 HTTP ' + resp.status, d.error || '');
    } catch (e) {
      console.error('[wake] 第 ' + (i + 1) + ' 次尝试失败:', e.message);
    }
  }
  console.error('[wake] ' + activationId + ' 没送到 —— 这次机会作废,不补发');
  return false;
}

// ── 主循环 ────────────────────────────────────────────
let lastReport = 0;
async function tick() {
  const now = Date.now();
  const dt = (now - S.lastTick) / 1000; // 秒
  S.lastTick = now;

  const offline = dt > TICK_SECONDS * 10;
  const aD = Math.exp(-dt / P.tauD);
  const aT = Math.exp(-dt / P.tauT);
  const aX = Math.exp(-dt / P.tauX);
  S.D = clamp(P.muD + (S.D - P.muD) * aD, P.Dmin, P.Dmax);
  S.T = clamp(P.muT + (S.T - P.muT) * aT + P.sigmaT * Math.sqrt(1 - aT * aT) * gauss(), P.Tmin, P.Tmax);
  S.X = clamp(P.muX + (S.X - P.muX) * aX + P.sigmaX * Math.sqrt(1 - aX * aX) * gauss(), P.Xmin, P.Xmax);

  if (offline) {
    // 停机/休眠了一阵: 状态照常向均值回归,但停机时段不积累风险 —— 错过的不补
    console.log('[engine] 恢复运行,离线 ' + Math.round(dt / 60) + ' 分钟;错过的醒来机会不补发');
  } else {
    const Mmod = await refreshMmod();
    const lambda = clamp(
      P.lambda0 * Math.exp(P.betaD * (S.D - P.muD) + P.betaT * (S.T - P.muT) + P.betaX * S.X) * Mmod,
      P.lambdaMin, P.lambdaMax);
    S.H += lambda * dt / 3600;

    if (now - lastReport > 15 * 60e3) {
      lastReport = now;
      console.log('[engine] λ=' + lambda.toFixed(3) + '/h  H=' + S.H.toFixed(3)
        + '/Θ=' + S.Theta.toFixed(3) + '  D=' + S.D.toFixed(2) + ' T=' + S.T.toFixed(2)
        + ' X=' + S.X.toFixed(2) + '  Mmod=' + Mmod.toFixed(2)
        + ' ' + JSON.stringify(mod.parts));
    }

    if (S.H >= S.Theta) {
      await dispatchWake(); // 送没送到都算用掉了这个周期 —— 机会不是欠账
      S.wakeCount += 1;
      S.lastWakeAt = now;
      S.H = 0;
      S.Theta = drawTheta();
      S.D = clamp(S.D - P.kRun, P.Dmin, P.Dmax); // run-kick: 刚醒过,短期内不容易再醒
    }
  }
  saveState();
}

S = loadState();
console.log('[engine] Kli Wakeup 引擎启动 · ' + P.policyVersion
  + ' · λ0=' + P.lambda0 + '/h · tick=' + TICK_SECONDS + 's'
  + ' · 已有节律: H=' + S.H.toFixed(3) + '/Θ=' + S.Theta.toFixed(3)
  + ' · 历史醒来 ' + S.wakeCount + ' 次');
(async function loop() {
  for (;;) {
    try { await tick(); } catch (e) { console.error('[engine] tick 出错:', e.message); }
    await new Promise(r => setTimeout(r, TICK_SECONDS * 1000));
  }
})();

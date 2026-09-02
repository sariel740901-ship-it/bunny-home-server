// 中国象棋规则引擎 —— 浏览器(games.html)和 server.js 共用同一份,规则只写一遍。
// 棋盘: 长度 90 的数组, idx = row*9+col; row0 = 黑方底线(画在上面), row9 = 红方底线(下面)。
// 红方大写: K帅 A仕 B相 N马 R车 C炮 P兵 ; 黑方小写: k将 a士 b象 n马 c炮 p卒。空格 ''。
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.XQ = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const RED = 'r', BLACK = 'b';
  const row = i => (i / 9) | 0, col = i => i % 9, at = (r, c) => r * 9 + c;
  const isRed = p => p >= 'A' && p <= 'Z';
  const sideOf = p => p ? (isRed(p) ? RED : BLACK) : '';
  const inBoard = (r, c) => r >= 0 && r <= 9 && c >= 0 && c <= 8;
  const inPalace = (r, c, s) => c >= 3 && c <= 5 && (s === RED ? r >= 7 : r <= 2);
  const crossedRiver = (r, s) => s === RED ? r <= 4 : r >= 5;

  function initBoard() {
    const b = Array(90).fill('');
    const back = 'rnbakabnr';
    for (let c = 0; c < 9; c++) { b[c] = back[c]; b[81 + c] = back[c].toUpperCase(); }
    b[at(2, 1)] = 'c'; b[at(2, 7)] = 'c'; b[at(7, 1)] = 'C'; b[at(7, 7)] = 'C';
    for (let c = 0; c < 9; c += 2) { b[at(3, c)] = 'p'; b[at(6, c)] = 'P'; }
    return b;
  }
  function sanitize(arr) {
    const ok = 'KABNRCPkabnrcp';
    return Array.from({ length: 90 }, (_, i) => (ok.includes(arr[i]) ? arr[i] : ''));
  }
  function findKing(b, s) {
    const k = s === RED ? 'K' : 'k';
    for (let i = 0; i < 90; i++) if (b[i] === k) return i;
    return -1;
  }

  // 伪合法着法(不滤送将)。king 的"白脸将飞吃"也生成,让搜索自己惩罚对脸。
  function genPseudo(b, s) {
    const ms = [];
    const push = (f, r, c) => {
      if (!inBoard(r, c)) return false;
      const t = at(r, c), q = b[t];
      if (!q) { ms.push([f, t]); return true; }        // 空位,可继续延伸
      if (sideOf(q) !== s) ms.push([f, t]);            // 吃子
      return false;                                     // 撞到子,停
    };
    for (let i = 0; i < 90; i++) {
      const p = b[i];
      if (!p || sideOf(p) !== s) continue;
      const r = row(i), c = col(i), u = p.toUpperCase();
      if (u === 'R') {
        for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          let rr = r + dr, cc = c + dc;
          while (push(i, rr, cc)) { rr += dr; cc += dc; }
        }
      } else if (u === 'C') { // 炮: 平走不吃,隔一子吃
        for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          let rr = r + dr, cc = c + dc;
          while (inBoard(rr, cc) && !b[at(rr, cc)]) { ms.push([i, at(rr, cc)]); rr += dr; cc += dc; }
          rr += dr; cc += dc; // 跳过炮架
          while (inBoard(rr, cc)) {
            const q = b[at(rr, cc)];
            if (q) { if (sideOf(q) !== s) ms.push([i, at(rr, cc)]); break; }
            rr += dr; cc += dc;
          }
        }
      } else if (u === 'N') { // 马: 蹩马腿
        for (const [dr, dc, lr, lc] of [[-2, -1, -1, 0], [-2, 1, -1, 0], [2, -1, 1, 0], [2, 1, 1, 0],
                                         [-1, -2, 0, -1], [1, -2, 0, -1], [-1, 2, 0, 1], [1, 2, 0, 1]]) {
          if (inBoard(r + lr, c + lc) && !b[at(r + lr, c + lc)]) push(i, r + dr, c + dc);
        }
      } else if (u === 'B') { // 相/象: 田字,塞象眼,不过河
        for (const [dr, dc] of [[-2, -2], [-2, 2], [2, -2], [2, 2]]) {
          const rr = r + dr, cc = c + dc;
          if (!inBoard(rr, cc) || crossedRiver(rr, s)) continue;
          if (!b[at(r + dr / 2, c + dc / 2)]) push(i, rr, cc);
        }
      } else if (u === 'A') { // 士: 斜一步,不出九宫
        for (const [dr, dc] of [[-1, -1], [-1, 1], [1, -1], [1, 1]]) {
          if (inPalace(r + dr, c + dc, s)) push(i, r + dr, c + dc);
        }
      } else if (u === 'K') {
        for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
          if (inPalace(r + dr, c + dc, s)) push(i, r + dr, c + dc);
        }
        // 白脸将: 两帅同列无遮挡时可"飞吃"(用于搜索惩罚,真实走法会被合法性过滤挡下双方对脸)
        const ek = findKing(b, s === RED ? BLACK : RED);
        if (ek >= 0 && col(ek) === c) {
          let clear = true;
          for (let rr = Math.min(r, row(ek)) + 1; rr < Math.max(r, row(ek)); rr++) if (b[at(rr, c)]) { clear = false; break; }
          if (clear) ms.push([i, ek]);
        }
      } else if (u === 'P') { // 兵: 过河前只进,过河后可横
        const dr = s === RED ? -1 : 1;
        push(i, r + dr, c);
        if (crossedRiver(r, s)) { push(i, r, c - 1); push(i, r, c + 1); }
      }
    }
    return ms;
  }

  function kingsFacing(b) {
    const rk = findKing(b, RED), bk = findKing(b, BLACK);
    if (rk < 0 || bk < 0 || col(rk) !== col(bk)) return false;
    const c = col(rk);
    for (let r = row(bk) + 1; r < row(rk); r++) if (b[at(r, c)]) return false;
    return true;
  }
  function inCheck(b, s) {
    const k = findKing(b, s);
    if (k < 0) return true;
    const em = genPseudo(b, s === RED ? BLACK : RED);
    for (const [, t] of em) if (t === k) return true;
    return false;
  }
  // 走一步(原地改),返回被吃的子;undo 用 unmake
  function doMove(b, f, t) { const cap = b[t]; b[t] = b[f]; b[f] = ''; return cap; }
  function unMove(b, f, t, cap) { b[f] = b[t]; b[t] = cap; }
  function makeMove(b, f, t) { const nb = b.slice(); nb[t] = nb[f]; nb[f] = ''; return nb; }

  function legalMoves(b, s) {
    const out = [];
    for (const [f, t] of genPseudo(b, s)) {
      if (b[t] && b[t].toUpperCase() === 'K') { out.push([f, t]); continue; } // 对方已对脸露将
      const cap = doMove(b, f, t);
      const bad = inCheck(b, s) || kingsFacing(b);
      unMove(b, f, t, cap);
      if (!bad) out.push([f, t]);
    }
    return out;
  }
  const movesFrom = (b, s, f) => legalMoves(b, s).filter(m => m[0] === f);

  // ── 估值 + 浅层搜索(给家里的小克当"棋感助手") ──
  const VAL = { K: 100000, R: 1000, N: 450, C: 480, B: 210, A: 210, P: 100 };
  function evaluate(b) { // 红方视角
    let s = 0;
    for (let i = 0; i < 90; i++) {
      const p = b[i];
      if (!p) continue;
      const u = p.toUpperCase(), red = isRed(p), r = row(i), c = col(i);
      let v = VAL[u];
      if (u === 'P') {
        if (crossedRiver(r, red ? RED : BLACK)) v += 80 + (red ? (4 - r) : (r - 5)) * 15;
        if (c >= 2 && c <= 6) v += 8;
      } else if (u === 'N' || u === 'C') {
        v += 6 - (Math.abs(c - 4) + Math.abs(r - 4.5)) | 0; // 略偏爱中路
      } else if (u === 'R') {
        v += 8;
      }
      s += red ? v : -v;
    }
    return s;
  }
  // 静态搜索: 到叶子后只延伸吃子,把兑子算完再估值(不然最后一吃没人反吃,搜索会馋到乱吃)
  function qsearch(b, s, alpha, beta, qd) {
    if (findKing(b, s) < 0) return -VAL.K;
    const stand = s === RED ? evaluate(b) : -evaluate(b);
    if (qd === 0 || stand >= beta) return stand;
    if (stand > alpha) alpha = stand;
    const caps = genPseudo(b, s).filter(m => b[m[1]]);
    caps.sort((m, n) => VAL[b[n[1]].toUpperCase()] - VAL[b[m[1]].toUpperCase()]);
    let best = stand;
    for (const [f, t] of caps) {
      const cap = doMove(b, f, t);
      const v = -qsearch(b, s === RED ? BLACK : RED, -beta, -alpha, qd - 1);
      unMove(b, f, t, cap);
      if (v > best) best = v;
      if (v > alpha) alpha = v;
      if (alpha >= beta) break;
    }
    return best;
  }
  function negamax(b, s, depth, alpha, beta) {
    if (findKing(b, s) < 0) return -VAL.K - depth; // 越早丢帅越糟
    if (depth === 0) return qsearch(b, s, alpha, beta, 6);
    const ms = genPseudo(b, s);
    ms.sort((m, n) => (VAL[(b[n[1]] || 'x').toUpperCase()] || 0) - (VAL[(b[m[1]] || 'x').toUpperCase()] || 0));
    let best = -Infinity;
    for (const [f, t] of ms) {
      const cap = doMove(b, f, t);
      const v = -negamax(b, s === RED ? BLACK : RED, depth - 1, -beta, -alpha);
      unMove(b, f, t, cap);
      if (v > best) best = v;
      if (v > alpha) alpha = v;
      if (alpha >= beta) break;
    }
    return best === -Infinity ? -VAL.K : best;
  }
  const PIECE_CN = { K: '帅', A: '仕', B: '相', N: '马', R: '车', C: '炮', P: '兵',
                     k: '将', a: '士', b: '象', n: '马', r: '车', c: '炮', p: '卒' };
  const CNUM = '一二三四五六七八九';
  // 传统纵线记法: 炮二平五 / 马8进7 之类(红中文数,黑阿拉伯数)
  function moveName(b, f, t) {
    const p = b[f];
    if (!p) return '';
    const s = sideOf(p), u = p.toUpperCase();
    const fr = row(f), fc = col(f), tr = row(t), tc = col(t);
    const fileN = c => s === RED ? 9 - c : c + 1;
    const fx = n => s === RED ? CNUM[n - 1] : String(n);
    const forward = s === RED ? tr < fr : tr > fr;
    let act;
    if (tr === fr) act = '平' + fx(fileN(tc));
    else if (u === 'R' || u === 'C' || u === 'P' || u === 'K') act = (forward ? '进' : '退') + fx(Math.abs(tr - fr));
    else act = (forward ? '进' : '退') + fx(fileN(tc));
    // 同线有同名子 → 前/后
    const twins = [];
    for (let r = 0; r <= 9; r++) if (b[at(r, fc)] === p) twins.push(r);
    if (twins.length > 1 && u !== 'K') {
      const sorted = s === RED ? twins.slice().sort((a2, b2) => a2 - b2) : twins.slice().sort((a2, b2) => b2 - a2);
      const pos = sorted.indexOf(fr);
      const tag = twins.length === 2 ? (pos === 0 ? '前' : '后') : (pos === 0 ? '前' : pos === twins.length - 1 ? '后' : '中');
      return tag + PIECE_CN[p] + act;
    }
    return PIECE_CN[p] + fx(fileN(fc)) + act;
  }
  // ICCS 坐标: 列 a-i(红方左手边=a), 行 0-9(红方底线=0)。如 h2e2 = 炮二平五
  const iccs = i => String.fromCharCode(97 + col(i)) + (9 - row(i));
  function parseIccs(str) {
    const m = /^([a-i])([0-9])([a-i])([0-9])$/.exec(String(str || '').trim().toLowerCase());
    if (!m) return null;
    return [at(9 - +m[2], m[1].charCodeAt(0) - 97), at(9 - +m[4], m[3].charCodeAt(0) - 97)];
  }
  function boardText(b) {
    const lines = ['  a b c d e f g h i'];
    for (let r = 0; r <= 9; r++) {
      lines.push((9 - r) + ' ' + Array.from({ length: 9 }, (_, c) => b[at(r, c)] || '.').join(' ')
        + (r === 0 ? '  ← 黑方底线' : r === 4 ? '  ~楚河' : r === 5 ? '  ~汉界' : r === 9 ? '  ← 红方底线' : ''));
    }
    lines.push('(大写=红: K帅 A仕 B相 N马 R车 C炮 P兵; 小写=黑: k将 a士 b象 n马 c炮 p卒)');
    return lines.join('\n');
  }

  // 候选步: 3 层搜索打分,前 k 个给小克挑
  function bestMoves(b, s, k) {
    const legal = legalMoves(b, s);
    const opp = s === RED ? BLACK : RED;
    const scored = legal.map(([f, t]) => {
      const name = moveName(b, f, t);
      const capd = b[t];
      const cap = doMove(b, f, t);
      const score = -negamax(b, opp, 2, -Infinity, Infinity);
      const check = inCheck(b, opp);
      unMove(b, f, t, cap);
      let why = [];
      if (score > VAL.K / 2) why.push('杀招,走这步基本赢了');
      if (capd) why.push('吃掉对方的' + PIECE_CN[capd]);
      if (check) why.push('将军');
      if (!why.length) why.push(score < -VAL.K / 2 ? '败着(其他都更糟)' : '调整阵形');
      return { from: f, to: t, name, score, why: why.join(',') };
    });
    scored.sort((a, b2) => b2.score - a.score);
    return scored.slice(0, k);
  }

  return { RED, BLACK, initBoard, sanitize, sideOf, isRed, row, col,
           genPseudo, legalMoves, movesFrom, makeMove, inCheck, kingsFacing,
           evaluate, bestMoves, moveName, boardText, iccs, parseIccs, PIECE_CN };
});

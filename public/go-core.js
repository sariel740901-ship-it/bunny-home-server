// 围棋规则引擎 —— 浏览器(games.html)和 server.js 共用一份。
// 棋盘: 长度 n*n 的数组, idx = row*n+col, row0 在上。黑 'X'(她默认), 白 'O'。
// 规则: 提子、禁自杀、打劫(单劫)、两次连续停一手终局、数子法(中国规则)贴 7.5 目。
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GO = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  const B = 'X', W = 'O', KOMI = 7.5;
  const SIZES = [9, 13, 19];
  const LET = 'ABCDEFGHJKLMNOPQRST'; // 标准记法跳过 I

  const init = n => Array(n * n).fill('');
  function neighbors(n, i) {
    const r = (i / n) | 0, c = i % n, out = [];
    if (r > 0) out.push(i - n);
    if (r < n - 1) out.push(i + n);
    if (c > 0) out.push(i - 1);
    if (c < n - 1) out.push(i + 1);
    return out;
  }
  // 一块棋: 所有子 + 气
  function group(board, n, i) {
    const color = board[i], stack = [i], seen = new Set([i]), libs = new Set();
    while (stack.length) {
      const x = stack.pop();
      for (const y of neighbors(n, x)) {
        if (board[y] === '') libs.add(y);
        else if (board[y] === color && !seen.has(y)) { seen.add(y); stack.push(y); }
      }
    }
    return { stones: [...seen], libs };
  }
  // 落子: 返回 {ok, board, captured, ko, reason}
  function play(board, n, i, color, ko) {
    if (i < 0 || i >= n * n || board[i] !== '') return { ok: false, reason: '那里已经有子了' };
    if (i === ko) return { ok: false, reason: '打劫 —— 这手不能马上提回去,先找个劫材' };
    const nb = board.slice(); nb[i] = color;
    const opp = color === B ? W : B, captured = [];
    for (const y of neighbors(n, i)) {
      if (nb[y] === opp) {
        const g = group(nb, n, y);
        if (g.libs.size === 0) for (const s of g.stones) { nb[s] = ''; captured.push(s); }
      }
    }
    const own = group(nb, n, i);
    if (own.libs.size === 0) return { ok: false, reason: '自杀手,不能下' };
    let newKo = -1;
    if (captured.length === 1 && own.stones.length === 1 && own.libs.size === 1) newKo = captured[0];
    return { ok: true, board: nb, captured, ko: newKo };
  }
  function legalMoves(board, n, color, ko) {
    const out = [];
    for (let i = 0; i < n * n; i++) if (!board[i] && play(board, n, i, color, ko).ok) out.push(i);
    return out;
  }
  // 数子法: 子 + 只挨一方的空(不判死活,终局前把死子提干净是双方的事)
  function score(board, n, komi) {
    komi = komi == null ? KOMI : komi;
    let b = 0, w = 0; const seen = new Set();
    for (let i = 0; i < n * n; i++) {
      if (board[i] === B) b++;
      else if (board[i] === W) w++;
      else if (!seen.has(i)) {
        const stack = [i], region = [i]; seen.add(i);
        let tb = false, tw = false;
        while (stack.length) {
          const x = stack.pop();
          for (const y of neighbors(n, x)) {
            if (board[y] === '') { if (!seen.has(y)) { seen.add(y); stack.push(y); region.push(y); } }
            else if (board[y] === B) tb = true; else tw = true;
          }
        }
        if (tb && !tw) b += region.length; else if (tw && !tb) w += region.length;
      }
    }
    return { black: b, white: w + komi, komi, diff: b - (w + komi) };
  }
  const coord = (n, i) => LET[i % n] + (n - ((i / n) | 0));
  function parseCoord(n, s) {
    const m = /^([A-HJ-T])(\d{1,2})$/.exec(String(s || '').trim().toUpperCase());
    if (!m) return -1;
    const c = LET.indexOf(m[1]), r = n - parseInt(m[2], 10);
    return (c < 0 || c >= n || r < 0 || r >= n) ? -1 : r * n + c;
  }
  function boardText(board, n) {
    const lines = ['   ' + LET.slice(0, n).split('').join(' ')];
    for (let r = 0; r < n; r++) {
      lines.push(String(n - r).padStart(2, ' ') + ' ' + Array.from({ length: n }, (_, c) => board[r * n + c] === B ? 'X' : board[r * n + c] === W ? 'O' : '.').join(' '));
    }
    return lines.join('\n');
  }
  const starPoints = n => n === 9 ? [[2, 2], [2, 6], [6, 2], [6, 6], [4, 4]]
    : n === 13 ? [[3, 3], [3, 9], [9, 3], [9, 9], [6, 6], [3, 6], [6, 3], [9, 6], [6, 9]]
    : [[3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15]];

  // 候选步(给家里的小克当棋感): 提子/逃叫吃/叫吃/别自填气/别填眼/开局占三四线/贴着战场。弱,但不瞎。
  function bestMoves(board, n, color, ko, k) {
    const opp = color === B ? W : B, stones = board.filter(Boolean).length;
    const line = i => { const r = (i / n) | 0, c = i % n; return Math.min(r, c, n - 1 - r, n - 1 - c) + 1; };
    const cands = [];
    for (const i of legalMoves(board, n, color, ko)) {
      const res = play(board, n, i, color, ko), nb = res.board, own = group(nb, n, i);
      let s = 0; const why = [];
      if (res.captured.length) { s += 12 * res.captured.length; why.push('提掉对方 ' + res.captured.length + ' 子'); }
      let saved = false;
      for (const y of neighbors(n, i)) if (board[y] === color && group(board, n, y).libs.size === 1 && own.libs.size >= 2) saved = true;
      if (saved) { s += 8; why.push('把自己被叫吃的棋救出来'); }
      const atariSeen = new Set(); let atari = 0;
      for (const y of neighbors(n, i)) if (nb[y] === opp) {
        const g = group(nb, n, y);
        if (g.libs.size === 1 && !atariSeen.has(g.stones[0])) { atariSeen.add(g.stones[0]); atari++; }
      }
      if (atari) { s += 4 * atari; why.push('叫吃对方'); }
      if (own.libs.size === 1 && !res.captured.length) { s -= 10; why.push('自填气,会被提'); }
      else s += Math.min(own.libs.size, 4) * 0.8;
      const nbs = neighbors(n, i);
      if (nbs.every(y => board[y] === color)) { s -= 15; why.push('这是自己的眼,别填'); }
      const ln = line(i);
      if (stones < n * n / 4) { s += ln === 1 ? -4 : ln === 2 ? -1 : (ln === 3 || ln === 4) ? 3 : 1; }
      else if (ln === 1) s -= 1.5;
      const r0 = (i / n) | 0, c0 = i % n; let near = false;
      for (let dr = -1; dr <= 1 && !near; dr++) for (let dc = -1; dc <= 1; dc++) {
        const rr = r0 + dr, cc = c0 + dc;
        if ((dr || dc) && rr >= 0 && cc >= 0 && rr < n && cc < n && board[rr * n + cc]) { near = true; break; }
      }
      if (near) s += 1.5;
      s += Math.random() * 0.5;
      cands.push({ i, score: s, why: why.join(',') || (stones < n * n / 4 ? '布子占地' : '收官') });
    }
    cands.sort((a, b) => b.score - a.score);
    const top = cands.slice(0, k);
    if (!top.length || (top[0].score < 0 && stones > n * n * 0.5)) top.unshift({ i: -1, score: 0, why: '没有好点了,停一手' });
    return top;
  }

  return { B, W, KOMI, SIZES, init, neighbors, group, play, legalMoves, score, coord, parseCoord, boardText, starPoints, bestMoves };
});

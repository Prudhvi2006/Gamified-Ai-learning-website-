/**
 * static/js/gal-charts.js — GAL Canvas Chart Library
 * ====================================================
 * Zero-dependency charts that match the GAL dark-mode design.
 * All charts read CSS variables so they auto-adapt to theme changes.
 *
 * API
 * ---
 *   GALCharts.radar(canvasId, labels, data, options?)
 *   GALCharts.line(canvasId,  labels, data, options?)
 *   GALCharts.bar(canvasId,   labels, data, options?)
 *   GALCharts.ring(canvasId,  value,  max,  label, options?)
 */

const GALCharts = (() => {
  // ── Theme helpers ──────────────────────────────────────────────
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const accent  = () => css('--r')  || '#ff1a1a';
  const accent2 = () => css('--r2') || '#fd9800';
  const muted   = () => 'rgba(255,255,255,0.25)';
  const bg      = () => 'rgba(255,255,255,0.04)';

  // ── Canvas setup helper ────────────────────────────────────────
  function _setup(canvasId) {
    const el  = document.getElementById(canvasId);
    if (!el) { console.warn(`[GALCharts] #${canvasId} not found`); return null; }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.width  = el.offsetWidth  * dpr;
    el.height = el.offsetHeight * dpr;
    const ctx = el.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, el.offsetWidth, el.offsetHeight);
    return { el, ctx, w: el.offsetWidth, h: el.offsetHeight };
  }

  // ── No-data placeholder ────────────────────────────────────────
  function _noData(ctx, w, h, label = 'No data yet') {
    ctx.fillStyle = muted();
    ctx.font      = '11px Rajdhani, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, w / 2, h / 2);
  }


  // ────────────────────────────────────────────────────────────────
  // Radar / Spider chart
  // labels : string[]     — axis labels
  // data   : number[0-1]  — normalised values
  // ────────────────────────────────────────────────────────────────
  function radar(canvasId, labels = [], data = [], opts = {}) {
    const s = _setup(canvasId);
    if (!s) return;
    const { ctx, w, h } = s;
    const n = labels.length;
    if (!n) return _noData(ctx, w, h);

    const cx   = w / 2;
    const cy   = h / 2;
    const R    = Math.min(cx, cy) * 0.72;
    const step = (Math.PI * 2) / n;
    const col  = opts.color || accent();

    // Grid rings
    for (let ring = 1; ring <= 4; ring++) {
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const a = step * i - Math.PI / 2;
        const r = R * (ring / 4);
        i === 0 ? ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
                : ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
      }
      ctx.closePath();
      ctx.strokeStyle = bg();
      ctx.lineWidth   = 1;
      ctx.stroke();
    }

    // Axis lines
    for (let i = 0; i < n; i++) {
      const a = step * i - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
      ctx.strokeStyle = bg();
      ctx.stroke();
    }

    // Data polygon
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const a = step * i - Math.PI / 2;
      const r = R * Math.max(0, Math.min(1, data[i] ?? 0));
      i === 0 ? ctx.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
              : ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
    }
    ctx.closePath();
    ctx.fillStyle   = col.replace(')', ', 0.15)').replace('rgb', 'rgba');
    ctx.fill();
    ctx.strokeStyle = col;
    ctx.lineWidth   = 2;
    ctx.stroke();

    // Labels
    ctx.fillStyle  = 'rgba(255,255,255,0.7)';
    ctx.font       = '9px Orbitron, monospace';
    ctx.textAlign  = 'center';
    for (let i = 0; i < n; i++) {
      const a   = step * i - Math.PI / 2;
      const lx  = cx + (R + 18) * Math.cos(a);
      const ly  = cy + (R + 18) * Math.sin(a) + 4;
      ctx.fillText(labels[i], lx, ly);
    }
  }


  // ────────────────────────────────────────────────────────────────
  // Line chart (XP Trend)
  // ────────────────────────────────────────────────────────────────
  function line(canvasId, labels = [], data = [], opts = {}) {
    const s = _setup(canvasId);
    if (!s) return;
    const { ctx, w, h } = s;
    if (!data.length) return _noData(ctx, w, h);

    const pad   = { top: 12, right: 12, bottom: 24, left: 30 };
    const cw    = w - pad.left - pad.right;
    const ch    = h - pad.top  - pad.bottom;
    const max   = Math.max(...data, 1);
    const col   = opts.color || accent();
    const col2  = opts.color2 || accent2();
    const xs    = data.map((_, i) => pad.left + (i / (data.length - 1 || 1)) * cw);
    const ys    = data.map(v  => pad.top  + (1 - v / max) * ch);

    // Grid lines
    for (let g = 0; g <= 4; g++) {
      const y = pad.top + (g / 4) * ch;
      ctx.strokeStyle = bg();
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + cw, y);
      ctx.stroke();
    }

    // Gradient fill under line
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + ch);
    grad.addColorStop(0, col.replace(')', ', 0.25)').replace('rgb', 'rgba'));
    grad.addColorStop(1, col.replace(')', ', 0)').replace('rgb', 'rgba'));
    ctx.beginPath();
    xs.forEach((x, i) => i === 0 ? ctx.moveTo(x, ys[i]) : ctx.lineTo(x, ys[i]));
    ctx.lineTo(xs[xs.length - 1], pad.top + ch);
    ctx.lineTo(xs[0], pad.top + ch);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    xs.forEach((x, i) => i === 0 ? ctx.moveTo(x, ys[i]) : ctx.lineTo(x, ys[i]));
    ctx.strokeStyle = col;
    ctx.lineWidth   = 2;
    ctx.lineJoin    = 'round';
    ctx.stroke();

    // Data points
    xs.forEach((x, i) => {
      ctx.beginPath();
      ctx.arc(x, ys[i], 3, 0, Math.PI * 2);
      ctx.fillStyle = col2;
      ctx.fill();
    });

    // X labels
    ctx.fillStyle  = muted();
    ctx.font       = '7px Orbitron, monospace';
    ctx.textAlign  = 'center';
    labels.forEach((lbl, i) => ctx.fillText(lbl, xs[i], h - 6));
  }


  // ────────────────────────────────────────────────────────────────
  // Bar chart
  // ────────────────────────────────────────────────────────────────
  function bar(canvasId, labels = [], data = [], opts = {}) {
    const s = _setup(canvasId);
    if (!s) return;
    const { ctx, w, h } = s;
    if (!data.length) return _noData(ctx, w, h);

    const pad    = { top: 8, right: 6, bottom: 20, left: 6 };
    const cw     = w - pad.left - pad.right;
    const ch     = h - pad.top  - pad.bottom;
    const max    = Math.max(...data, 1);
    const barW   = cw / data.length * 0.65;
    const gap    = cw / data.length;
    const col1   = opts.color  || accent();
    const col2   = opts.color2 || accent2();

    data.forEach((val, i) => {
      const bh  = Math.max(4, (val / max) * ch);
      const x   = pad.left + i * gap + gap * 0.175;
      const y   = pad.top  + ch - bh;
      const g   = ctx.createLinearGradient(0, y, 0, y + bh);
      g.addColorStop(0, col2);
      g.addColorStop(1, col1);
      ctx.fillStyle = g;
      ctx.fillRect(x, y, barW, bh);
    });

    // X labels
    ctx.fillStyle  = muted();
    ctx.font       = '7px Orbitron, monospace';
    ctx.textAlign  = 'center';
    labels.forEach((lbl, i) => {
      const cx = pad.left + i * gap + gap / 2;
      ctx.fillText(lbl, cx, h - 5);
    });
  }


  // ────────────────────────────────────────────────────────────────
  // Ring / Donut chart (accuracy / progress)
  // ────────────────────────────────────────────────────────────────
  function ring(canvasId, value = 0, max = 100, label = '', opts = {}) {
    const s = _setup(canvasId);
    if (!s) return;
    const { ctx, w, h } = s;

    const cx     = w / 2;
    const cy     = h / 2;
    const r      = Math.min(cx, cy) * 0.78;
    const thick  = r * 0.22;
    const pct    = Math.max(0, Math.min(1, value / (max || 1)));
    const start  = -Math.PI / 2;
    const end    = start + pct * Math.PI * 2;
    const col    = opts.color  || accent();
    const col2   = opts.color2 || accent2();

    // Background ring
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = bg();
    ctx.lineWidth   = thick;
    ctx.stroke();

    // Value arc
    if (pct > 0) {
      const grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
      grad.addColorStop(0, col);
      grad.addColorStop(1, col2);
      ctx.beginPath();
      ctx.arc(cx, cy, r, start, end);
      ctx.strokeStyle = grad;
      ctx.lineWidth   = thick;
      ctx.lineCap     = 'round';
      ctx.stroke();
    }

    // Centre text
    ctx.textAlign    = 'center';
    ctx.fillStyle    = '#fff';
    ctx.font         = `bold ${Math.round(r * 0.44)}px Orbitron, monospace`;
    ctx.fillText(`${Math.round(pct * 100)}%`, cx, cy + r * 0.15);
    if (label) {
      ctx.fillStyle  = muted();
      ctx.font       = `${Math.round(r * 0.2)}px Rajdhani, sans-serif`;
      ctx.fillText(label, cx, cy + r * 0.42);
    }
  }

  return { radar, line, bar, ring };
})();

// Export for ES module usage
if (typeof module !== 'undefined') module.exports = { GALCharts };

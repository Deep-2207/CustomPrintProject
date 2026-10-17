// Text styles: ready-made looks for the customer's own words (the "World's Best Dad" idea).
// The customer types "Deep" and "Patel"; a style decides the fonts, colours, outline, shapes and layout.
//
// A style is { font(px, lineIndex), caps, weights(lines), lh, fw, fh, inner(box), draw(ctx, L, o) }.
//   layoutLines() fits the lines into the print area first (never cutting any text), then draw() paints.
//   o.ink  = the colour the customer picked (replaces the style's main colour), or ''.
//   o.mono = a single colour for the relief (bump) map of embossed/debossed products; shapes are
//            drawn solid in that colour so they feel raised or engraved. Null for the normal colour pass.
//
// To add a style: add one entry here, and its id and label to text-styles.json (the server reads that file too).

const SANS = '"Arial Rounded MT Bold","Arial Black",Impact,sans-serif';
const IMPACT = 'Impact,"Arial Black",sans-serif';
const SERIF = 'Georgia,"Times New Roman",serif';
const SCRIPT = '"Brush Script MT","Segoe Script","Lucida Handwriting",cursive';

// Fit the lines into the area. The font shrinks until the widest line fits the width and all lines
// fit the height; the text-size slider can only make it smaller than that fit.
export function layoutLines(ctx, lines, box, s, spec) {
  const wts = spec.weights ? spec.weights(lines) : lines.map(() => 1);
  const txt = lines.map((l, i) => ((typeof spec.caps === 'function' ? spec.caps(i) : spec.caps) ? l.toUpperCase() : l));
  const LH = spec.lh || 1.12;
  const inner = spec.inner ? spec.inner(box) : box;
  const cx = box.x + s.x * box.w, cy = box.y + s.y * box.h;
  ctx.save();
  const w100 = txt.map((t, i) => { ctx.font = spec.font(100 * wts[i], i); return Math.max(1, ctx.measureText(t).width); });
  ctx.restore();
  const totalH100 = wts.reduce((a, w) => a + w * 100 * LH, 0);
  let k = Math.min((inner.w * (spec.fw || 0.9)) / Math.max(...w100), (inner.h * (spec.fh || 0.86)) / totalH100);
  k *= Math.min(1, Math.max(0.2, s.size / 0.6));
  const items = [];
  let y = cy - (totalH100 * k) / 2;
  txt.forEach((t, i) => {
    const px = 100 * wts[i] * k, h = px * LH;
    items.push({ t, px, x: cx, y: y + h / 2, font: spec.font(px, i) });
    y += h;
  });
  return { cx, cy, items, w: Math.max(...w100.map((w, i) => w * k)), h: totalH100 * k, inner };
}

function line(c, it, { fill, stroke, lw = 0, dx = 0, dy = 0 }) {
  c.font = it.font; c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.miterLimit = 2;
  if (stroke) { c.strokeStyle = stroke; c.lineWidth = lw; c.strokeText(it.t, it.x + dx, it.y + dy); }
  if (fill) { c.fillStyle = fill; c.fillText(it.t, it.x + dx, it.y + dy); }
}
const tilt = (c, L, a) => { c.translate(L.cx, L.cy); c.rotate(a); c.translate(-L.cx, -L.cy); };
function rrect(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
function star(c, cx, cy, R) {
  c.beginPath();
  for (let i = 0; i < 10; i++) { const r = i % 2 ? R * 0.45 : R, a = -Math.PI / 2 + (i * Math.PI) / 5; c.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a)); }
  c.closePath();
}

export const TEXT_STYLES = {
  // Chunky yellow letters with a dark outline and a white die-cut border, like a sticker.
  bubble: {
    font: px => `900 ${px}px ${SANS}`, caps: true, lh: 1.0,
    weights: ls => ls.map((_, i) => (ls.length > 2 && i === 0 ? 0.62 : 1)),
    draw(c, L, o) {
      c.save(); tilt(c, L, -0.05);
      L.items.forEach(it => line(c, it, { stroke: o.mono || '#ffffff', lw: it.px * 0.5 }));
      L.items.forEach(it => line(c, it, { stroke: o.mono || '#4a2e00', lw: it.px * 0.22 }));
      L.items.forEach(it => line(c, it, { fill: o.mono || o.ink || '#ffd400' }));
      c.restore();
    },
  },

  // Text on a swallow-tail ribbon.
  banner: {
    font: px => `900 ${px}px ${SANS}`, caps: true, lh: 1.05, fw: 0.78, fh: 0.62,
    draw(c, L, o) {
      const pad = Math.max(L.items[0].px * 0.35, 14), x = L.cx - L.w / 2 - pad * 1.2, y = L.cy - L.h / 2 - pad * 0.7;
      const w = L.w + pad * 2.4, h = L.h + pad * 1.4, t = h * 0.3;
      const main = o.mono || o.ink || '#d62828', dark = o.mono || '#8f1a1a';
      c.save();
      c.fillStyle = dark;
      c.beginPath(); c.moveTo(x, y + h * 0.12); c.lineTo(x - t, y + h * 0.12); c.lineTo(x - t * 0.6, y + h * 0.5); c.lineTo(x - t, y + h * 0.88); c.lineTo(x, y + h * 0.88); c.closePath(); c.fill();
      c.beginPath(); c.moveTo(x + w, y + h * 0.12); c.lineTo(x + w + t, y + h * 0.12); c.lineTo(x + w + t * 0.6, y + h * 0.5); c.lineTo(x + w + t, y + h * 0.88); c.lineTo(x + w, y + h * 0.88); c.closePath(); c.fill();
      c.fillStyle = main; c.fillRect(x, y, w, h);
      if (!o.mono) { c.strokeStyle = '#ffffff'; c.lineWidth = Math.max(2, h * 0.03); c.setLineDash([h * 0.1, h * 0.07]); c.strokeRect(x + h * 0.08, y + h * 0.08, w - h * 0.16, h - h * 0.16); c.setLineDash([]); }
      if (!o.mono) L.items.forEach(it => line(c, it, { fill: '#ffffff' }));
      c.restore();
    },
  },

  // Words inside a round badge with a gold ring and a star.
  badge: {
    font: px => `800 ${px}px ${SANS}`, caps: true, lh: 1.05, fw: 1, fh: 1,
    inner: box => { const d = Math.min(box.w, box.h) * 0.62; return { x: box.x, y: box.y, w: d, h: d * 0.62 }; },
    draw(c, L, o) {
      const r = L.inner.w * 0.74, main = o.mono || o.ink || '#1d3557', gold = o.mono || '#e9c46a';
      c.save();
      c.beginPath(); c.arc(L.cx, L.cy, r, 0, Math.PI * 2); c.fillStyle = main; c.fill();
      c.strokeStyle = gold; c.lineWidth = r * 0.07; c.stroke();
      if (!o.mono) {
        c.beginPath(); c.arc(L.cx, L.cy, r * 0.84, 0, Math.PI * 2); c.strokeStyle = '#f1faee'; c.lineWidth = r * 0.025; c.setLineDash([r * 0.05, r * 0.05]); c.stroke(); c.setLineDash([]);
        if (L.items.length <= 2) { star(c, L.cx, L.cy - r * 0.6, r * 0.1); c.fillStyle = gold; c.fill(); star(c, L.cx, L.cy + r * 0.6, r * 0.1); c.fill(); }
        L.items.forEach(it => line(c, it, { fill: '#fff4d6' }));
      }
      c.restore();
    },
  },

  // Cream letters, dark outline and a hard pink shadow.
  shadow: {
    font: px => `400 ${px}px ${IMPACT}`, caps: true, lh: 1.02,
    draw(c, L, o) {
      c.save(); tilt(c, L, -0.03);
      const d = L.items[0].px * 0.11;
      L.items.forEach(it => line(c, it, { fill: o.mono || '#ff5d8f', stroke: o.mono || '#ff5d8f', lw: it.px * 0.14, dx: d, dy: d }));
      L.items.forEach(it => line(c, it, { stroke: o.mono || '#1b1b1b', lw: it.px * 0.14 }));
      L.items.forEach(it => line(c, it, { fill: o.mono || o.ink || '#fff3b0' }));
      c.restore();
    },
  },

  // First line in handwriting, the rest in small spaced capitals, with a small flourish between.
  script: {
    font: (px, i) => (i === 0 ? `400 ${px}px ${SCRIPT}` : `700 ${px}px ${SERIF}`), lh: 1.05,
    caps: i => i > 0, weights: ls => ls.map((_, i) => (i === 0 ? 1 : 0.38)),
    draw(c, L, o) {
      const col = o.mono || o.ink || '#7a1f3d';
      L.items.forEach((it, i) => line(c, it, i === 0 ? { fill: col, stroke: col, lw: it.px * 0.012 } : { fill: col }));
      if (L.items.length > 1) {
        const a = L.items[0], b = L.items[1], y = (a.y + a.px * 0.42 + b.y - b.px * 0.5) / 2, half = Math.max(L.w * 0.3, 20);
        c.save(); c.strokeStyle = col; c.fillStyle = col; c.lineWidth = Math.max(2, b.px * 0.07);
        c.beginPath(); c.moveTo(L.cx - half, y); c.lineTo(L.cx - half * 0.15, y); c.moveTo(L.cx + half * 0.15, y); c.lineTo(L.cx + half, y); c.stroke();
        c.beginPath(); c.moveTo(L.cx, y - b.px * 0.14); c.lineTo(L.cx + b.px * 0.14, y); c.lineTo(L.cx, y + b.px * 0.14); c.lineTo(L.cx - b.px * 0.14, y); c.closePath(); c.fill();
        c.restore();
      }
    },
  },

  // Rubber-stamp look: double border, slight tilt.
  stamp: {
    font: px => `400 ${px}px ${IMPACT}`, caps: true, lh: 1.05, fw: 0.8, fh: 0.7,
    draw(c, L, o) {
      c.save(); tilt(c, L, -0.09);
      const col = o.mono || o.ink || '#c1121f', u = L.items[0].px, pad = Math.max(u * 0.4, 12);
      const x = L.cx - L.w / 2 - pad, y = L.cy - L.h / 2 - pad * 0.8, w = L.w + pad * 2, h = L.h + pad * 1.6;
      c.strokeStyle = col; c.lineWidth = u * 0.1; rrect(c, x, y, w, h, pad * 0.6); c.stroke();
      c.lineWidth = u * 0.04; rrect(c, x + pad * 0.35, y + pad * 0.35, w - pad * 0.7, h - pad * 0.7, pad * 0.4); c.stroke();
      L.items.forEach(it => line(c, it, { fill: col }));
      c.restore();
    },
  },

  // Orange to pink gradient letters with outline and white border.
  pop: {
    font: px => `900 ${px}px ${SANS}`, caps: true, lh: 1.0,
    draw(c, L, o) {
      c.save(); tilt(c, L, -0.04);
      const g = c.createLinearGradient(0, L.cy - L.h / 2, 0, L.cy + L.h / 2);
      g.addColorStop(0, '#ffb703'); g.addColorStop(0.5, '#fb5607'); g.addColorStop(1, '#ff006e');
      L.items.forEach(it => line(c, it, { stroke: o.mono || '#ffffff', lw: it.px * 0.48 }));
      L.items.forEach(it => line(c, it, { stroke: o.mono || '#2b2d42', lw: it.px * 0.2, dx: it.px * 0.03, dy: it.px * 0.05 }));
      L.items.forEach(it => line(c, it, { fill: o.mono || o.ink || g }));
      c.restore();
    },
  },
};

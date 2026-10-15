/*!
 * Wristband Customizer — dependency-free live preview + message editor.
 * Drop-in for "Customize Your Message" on wrist-band.in product pages.
 *
 *   WBCustomizer.mount('#wb-customizer', {
 *     style: 'embossed',          // embossed | debossed | printed ...
 *     size: '1/2',                // 1/4 | 1/2 | 3/4 | 1 | 1.5 | 2
 *     productImage: 'https://.../file-1771738969.png', // optional real artwork
 *     onChange: cfg => { ... },   // fires on every valid/invalid change
 *   });
 *   WBCustomizer.getConfig()      // -> JSON for cart (messages, colors, font...)
 *   WBCustomizer.setSize('3/4')   // call when the page's size variant changes
 *   WBCustomizer.setConfig(cfg)   // restore from cart "edit"
 */
(function (global) {
  'use strict';

  // ---- Production rules (edit these to match manufacturing) -------------
  // Max characters per message area, per band width. Continuous = front+back run together.
  const LIMITS = {
    '1/4': { front: 20, back: 20, inside: 20, continuous: 40 },
    '1/2': { front: 28, back: 28, inside: 28, continuous: 56 },
    '3/4': { front: 32, back: 32, inside: 32, continuous: 64 },
    '1':   { front: 34, back: 34, inside: 34, continuous: 68 },
    '1.5': { front: 36, back: 36, inside: 36, continuous: 72 },
    '2':   { front: 38, back: 38, inside: 38, continuous: 76 },
  };
  // 'Inside message' only for styles that support it.
  const INSIDE_STYLES = ['embossed', 'debossed', 'printed', 'debossed-filled', 'embossed-printed'];
  // Band thickness in the preview (fraction of the base) by size.
  const BAND_H = { '1/4': 34, '1/2': 56, '3/4': 74, '1': 92, '1.5': 118, '2': 144 };

  const COLORS = [
    ['Black', '#1b1b1b'], ['White', '#f4f4f4'], ['Red', '#d62828'], ['Blue', '#1d4ed8'],
    ['Navy', '#14213d'], ['Green', '#2a9d3f'], ['Yellow', '#facc15'], ['Orange', '#f97316'],
    ['Purple', '#7e3ff2'], ['Pink', '#ec4899'], ['Teal', '#0d9488'], ['Grey', '#8d99ae'],
  ];
  const IMPRINTS = [['None', ''], ['White', '#ffffff'], ['Black', '#111111'], ['Gold', '#d4a017'],
    ['Silver', '#c0c6cc'], ['Red', '#e11d2e'], ['Blue', '#2563eb'], ['Green', '#16a34a']];
  const FONTS = [
    ['Arial Bold', 'Arial, Helvetica, sans-serif', 700], ['Impact', 'Impact, "Arial Black", sans-serif', 400],
    ['Georgia', 'Georgia, serif', 700], ['Courier', '"Courier New", monospace', 700],
    ['Script', '"Brush Script MT", "Segoe Script", cursive', 400], ['Trebuchet', '"Trebuchet MS", sans-serif', 700],
  ];
  const ICONS = [['None', ''], ['Star', '★'], ['Heart', '♥'], ['Cross', '✚'], ['Dot', '●'], ['Arrow', '➜'], ['Ribbon', '🎗'], ['Smile', '☺']];
  const STORE_KEY = 'wbc:draft:v1';
  const CART_KEY = 'wbc:cart:v1';

  const DEFAULTS = {
    size: '1/2', view: 'front', bandColor: '#1d4ed8', imprintColor: '', font: 0, textSize: 100, align: 'middle', offset: 0, hpos: 0,
    front: { text: '', continuous: false, start: '', end: '' },
    back:  { text: '', start: '', end: '' },
    inside: { text: '', mode: 'embossed' },
  };

  // ---- helpers -----------------------------------------------------------
  const clone = o => JSON.parse(JSON.stringify(o));
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Allow letters/digits (any language), spaces and common punctuation. Strip everything else (HTML, control chars).
  const sanitize = s => String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f<>`\\{}]/g, '').replace(/\s+/g, ' ').replace(/^\s+/, '');
  const safeColor = (c, fb) => /^#[0-9a-f]{6}$/i.test(c) ? c : fb;
  const shade = (hex, amt) => {
    const n = parseInt(hex.slice(1), 16);
    const f = v => Math.max(0, Math.min(255, v + amt));
    return '#' + [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(f).map(v => v.toString(16).padStart(2, '0')).join('');
  };
  const lum = hex => { const n = parseInt(hex.slice(1), 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; };

  let uid = 0;
  function mount(target, opts) {
    const root = typeof target === 'string' ? document.querySelector(target) : target;
    if (!root) throw new Error('WBCustomizer: mount target not found');
    opts = opts || {};
    const id = 'wbc' + (++uid);
    const style = opts.style || 'embossed';
    const hasInside = INSIDE_STYLES.indexOf(style) > -1;
    let st = clone(DEFAULTS);
    st.size = opts.size || st.size;
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null'); } catch (e) {}
    if (opts.initial) st = merge(st, opts.initial);
    else if (saved && saved.style === style) st = merge(st, saved.config);
    if (opts.size) st.size = opts.size;

    function merge(base, src) {
      const out = clone(base);
      Object.keys(src || {}).forEach(k => {
        if (src[k] && typeof src[k] === 'object' && out[k] && typeof out[k] === 'object') Object.assign(out[k], src[k]);
        else if (k in out) out[k] = src[k];
      });
      return out;
    }

    root.classList.add('wbc');
    root.innerHTML = template();
    const $ = s => root.querySelector(s);
    const $$ = s => Array.prototype.slice.call(root.querySelectorAll(s));
    const svg = $('.wbc-svg');
    const modal = $('.wbc-modal');
    const limit = k => LIMITS[st.size][k];

    // ---- template ----
    function swatches(name, list, cur) {
      return list.map(c => `<label class="wbc-sw" title="${c[0]}"><input type="radio" name="${id}-${name}" value="${c[1]}"${cur === c[1] ? ' checked' : ''}>
        <span style="background:${c[1] || 'repeating-linear-gradient(45deg,#fff,#fff 4px,#ddd 4px,#ddd 8px)'}"></span><i>${c[0]}</i></label>`).join('');
    }
    function iconSel(name) { return `<select data-k="${name}" aria-label="${name.includes('start') ? 'Start' : 'End'} icon">${ICONS.map(i => `<option value="${i[1]}">${i[0]} ${i[1]}</option>`).join('')}</select>`; }
    function field(key, label, ph, extra) {
      return `<div class="wbc-field" data-area="${key}">
        <div class="wbc-lr"><label for="${id}-${key}">${label}</label><span class="wbc-count" id="${id}-${key}-c" aria-live="polite"></span></div>
        <input id="${id}-${key}" type="text" data-text="${key}" placeholder="${ph}" autocomplete="off" maxlength="200" aria-describedby="${id}-${key}-e">
        <div class="wbc-err" id="${id}-${key}-e" role="alert"></div>${extra || ''}</div>`;
    }
    function template() {
      return `
<div class="wbc-grid">
 <div class="wbc-prev">
  <div class="wbc-tabs" role="tablist" aria-label="Preview side">
    <button type="button" role="tab" data-view="front">Front</button><button type="button" role="tab" data-view="back">Back</button>
  </div>
  <div class="wbc-stage"><svg class="wbc-svg" viewBox="0 0 800 340" role="img" aria-label="Live wristband preview"></svg></div>
  <div class="wbc-strip" tabindex="0" role="slider" aria-label="Text position. Drag, or use arrow keys, to move the message" aria-valuemin="-50" aria-valuemax="50"><span class="wbc-strip-t"></span></div>
  <p class="wbc-hint">&#10021; Drag the text above (or use arrow keys) to adjust its position on the band.</p>
  <p class="wbc-note">Preview is an illustration. Final spacing is set by our production team; a free digital proof is available.</p>
  <div class="wbc-actions"><button type="button" class="wbc-btn" data-act="zoom">Preview My Design</button>
  <button type="button" class="wbc-btn wbc-ghost" data-act="reset">Reset Design</button></div>
 </div>
 <form class="wbc-form" novalidate onsubmit="return false">
  <h3>Enter Your Custom Message</h3>
  ${field('front', 'Front Message', 'e.g. TEAM SPIRIT 2026')}
  <div class="wbc-row"><label>Start icon ${iconSel('front.start')}</label><label>End icon ${iconSel('front.end')}</label></div>
  <label class="wbc-chk"><input type="checkbox" data-k="front.continuous"> Continuous message (runs around the whole band)</label>
  <div data-hide-cont>${field('back', 'Back Message', 'e.g. NEVER GIVE UP')}
  <div class="wbc-row"><label>Start icon ${iconSel('back.start')}</label><label>End icon ${iconSel('back.end')}</label></div></div>
  ${hasInside ? `${field('inside', 'Inside Message', 'Optional — printed inside the band')}
  <div class="wbc-row"><label>Inside style <select data-k="inside.mode"><option value="embossed">Embossed – no fill</option><option value="printed">Printed – same colour as outside</option></select></label></div>` : ''}
  <fieldset><legend>Wristband colour</legend><div class="wbc-sws">${swatches('band', COLORS, st.bandColor)}
   <label class="wbc-custom">Custom <input type="color" data-k="bandColor" value="${st.bandColor}" aria-label="Custom band colour"></label></div></fieldset>
  <fieldset><legend>Text / imprint colour</legend><div class="wbc-sws">${swatches('imp', IMPRINTS, st.imprintColor)}</div></fieldset>
  <div class="wbc-row">
   <label>Font <select data-k="font">${FONTS.map((f, i) => `<option value="${i}">${f[0]}</option>`).join('')}</select></label>
   <label>Alignment <select data-k="align"><option value="start">Left</option><option value="middle">Centre</option><option value="end">Right</option></select></label></div>
  <div class="wbc-row">
   <label>Text size <output></output><input type="range" min="70" max="130" step="5" data-k="textSize"></label>
   <label>Position <output></output><input type="range" min="-30" max="30" step="1" data-k="offset"></label></div>
  <div class="wbc-sum" aria-live="polite"></div>
 </form>
</div>
<div class="wbc-modal" hidden role="dialog" aria-modal="true" aria-label="Large design preview"><div class="wbc-mbox">
 <button type="button" class="wbc-x" data-act="close" aria-label="Close preview">×</button>
 <div class="wbc-mbig"></div>
 <div class="wbc-actions"><button type="button" class="wbc-btn wbc-ghost" data-act="flip">Flip front / back</button></div></div></div>`;
    }

    // ---- state <-> form ----
    function get(path) { return path.split('.').reduce((o, k) => o[k], st); }
    function set(path, v) { const p = path.split('.'), l = p.pop(); p.reduce((o, k) => o[k], st)[l] = v; }

    function syncForm() {
      $$('[data-text]').forEach(i => { const k = i.dataset.text; if (i.value !== st[k].text) i.value = st[k].text; });
      $$('[data-k]').forEach(i => {
        const v = get(i.dataset.k);
        if (i.type === 'checkbox') i.checked = !!v; else i.value = v;
      });
      $$('input[type=radio]').forEach(r => { r.checked = r.value === (r.name.endsWith('band') ? st.bandColor : st.imprintColor); });
      $$('.wbc-tabs button').forEach(b => { b.setAttribute('aria-selected', b.dataset.view === st.view); b.classList.toggle('on', b.dataset.view === st.view); });
      const hide = $('[data-hide-cont]'); hide.hidden = st.front.continuous;
      $$('input[type=range]').forEach(r => { r.previousElementSibling.textContent = r.dataset.k === 'textSize' ? r.value + '%' : (r.value > 0 ? '+' : '') + r.value; });
    }

    // ---- validation ----
    function validate() {
      const errs = {};
      const areas = [['front', st.front.continuous ? 'continuous' : 'front'], ['back', 'back']];
      if (hasInside) areas.push(['inside', 'inside']);
      areas.forEach(a => {
        const key = a[0], max = limit(a[1]), len = st[key].text.length;
        const c = $(`#${id}-${key}-c`);
        c.textContent = len + ' / ' + max;
        c.classList.toggle('bad', len > max);
        const f = $(`[data-area="${key}"]`);
        if (len > max) errs[key] = `Too long for a ${st.size}" band: ${len - max} character${len - max > 1 ? 's' : ''} over the ${max} limit. Shorten it or choose a wider band.`;
        $(`#${id}-${key}-e`).textContent = errs[key] || '';
        f.classList.toggle('invalid', !!errs[key]);
        $(`#${id}-${key}`).setAttribute('aria-invalid', !!errs[key]);
      });
      const label = $(`[data-area="front"] label`);
      label.textContent = st.front.continuous ? 'Continuous Message' : 'Front Message';
      return errs;
    }

    // ---- SVG rendering ----
    const CX = 400, RX = 335, RY = 46, CY = 150;
    function bandPaths(h) {
      // 3/4 perspective ring: front face = lower half of the top/bottom ellipses.
      const t = CY - h / 2, b = CY + h / 2, l = CX - RX, r = CX + RX;
      const m = CY; // centre line of the front face
      return {
        front: `M${l},${t} A${RX},${RY} 0 0 0 ${r},${t} L${r},${b} A${RX},${RY} 0 0 1 ${l},${b} Z`,
        topEll: `M${l},${t} A${RX},${RY} 0 1 1 ${r},${t} A${RX},${RY} 0 1 1 ${l},${t} Z`,
        inner: `M${l + 20},${t + 2} A${RX - 20},${RY - 12} 0 1 1 ${r - 20},${t + 2} A${RX - 20},${RY - 12} 0 1 1 ${l + 20},${t + 2} Z`,
        center: `M${l + 6},${m} A${RX - 6},${RY} 0 0 0 ${r - 6},${m}`,
        t: t, b: b, l: l, r: r, h: h,
      };
    }

    function textFor(area) {
      const a = st[area];
      return [a.start, a.text, a.end].filter(Boolean).join(' ').trim();
    }

    function render() {
      const errs = validate();
      const h = BAND_H[st.size] * 1.25, p = bandPaths(h), font = FONTS[st.font];
      const base = safeColor(st.bandColor, '#1d4ed8'), dark = lum(base) < 0.5;
      const imp = st.imprintColor ? safeColor(st.imprintColor, '') : '';
      const isPrinted = style === 'printed' || style === 'embossed-printed';
      const face = imp || (isPrinted ? '#fff' : shade(base, dark ? 8 : -6));
      // Which message is on the visible face
      let msg, cont = st.front.continuous;
      if (cont) {
        const full = textFor('front'), half = Math.ceil(full.length / 2);
        // Split at nearest space around the middle so words aren't broken between faces.
        let cut = full.lastIndexOf(' ', half); if (cut < 1) cut = half;
        msg = st.view === 'front' ? full.slice(0, cut) : full.slice(cut).trim();
      } else msg = textFor(st.view);
      const placeholder = !msg;
      if (placeholder) msg = st.view === 'front' ? 'YOUR FRONT MESSAGE' : 'YOUR BACK MESSAGE';
      const avail = 560 * (0.9 + 0.1 * (h / 144));
      const baseSize = Math.min(h * 0.5, 48) * st.textSize / 100;
      const body = esc(msg);
      const gid = id + 'g';
      const shadowOff = Math.max(1.5, baseSize / 14);
      const off = (st.offset / 100) * h; // vertical position nudge
      const anchor = st.align;
      const startOff = ((anchor === 'start' ? 18 : anchor === 'end' ? 82 : 50) + st.hpos) + '%';
      const emb = style.indexOf('emboss') === 0, deb = style.indexOf('debossed') === 0;
      const txt = (dx, dy, fill, extra) => `<text font-family='${font[1].replace(/'/g, '')}' font-weight="${font[2]}" font-size="${baseSize}" fill="${fill}" ${extra || ''} text-anchor="${anchor}" dy="${dy}" transform="translate(${dx},${off})"><textPath href="#${gid}-c" startOffset="${startOff}">${body}</textPath></text>`;
      let layers = '';
      if (emb) layers = txt(shadowOff, baseSize * .35 + shadowOff, 'rgba(0,0,0,.5)') + txt(-shadowOff * .6, baseSize * .35 - shadowOff * .6, 'rgba(255,255,255,.45)') + txt(0, baseSize * .35, face);
      else if (deb) layers = txt(0, baseSize * .35 + shadowOff * .6, 'rgba(255,255,255,.35)') + txt(0, baseSize * .35, imp || shade(base, -60), 'opacity=".95"');
      else layers = txt(0, baseSize * .35, face);
      if (placeholder) layers = `<g opacity=".45">${layers}</g>`;

      const real = '';
      svg.innerHTML = `
<defs>
 <linearGradient id="${gid}-fv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".30"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".32"/></linearGradient>
 <linearGradient id="${gid}-ed" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset=".16" stop-color="#000" stop-opacity="0"/><stop offset=".78" stop-color="#fff" stop-opacity="0"/><stop offset=".92" stop-color="#fff" stop-opacity=".18"/><stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient>
 <linearGradient id="${gid}-iw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${shade(base, -70)}"/><stop offset="1" stop-color="${shade(base, 25)}"/></linearGradient>
 <filter id="${gid}-b" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
 <clipPath id="${gid}-cp"><path d="${p.front}"/></clipPath>
 <path id="${gid}-c" d="${p.center}"/>
</defs>
<ellipse cx="${CX}" cy="${p.b + RY - 8}" rx="${RX - 20}" ry="12" fill="#000" opacity=".2" filter="url(#${gid}-b)"/>
<path d="${p.topEll}" fill="${shade(base, 30)}" stroke="#000" stroke-opacity=".2"/>
<path d="${p.inner}" fill="url(#${gid}-iw)"/>
<path d="${p.front}" fill="${base}"/>
<g clip-path="url(#${gid}-cp)"><rect width="800" height="340" fill="url(#${gid}-fv)"/><rect width="800" height="340" fill="url(#${gid}-ed)"/>
 <g class="wbc-text">${layers}</g></g>
<path d="${p.front}" fill="none" stroke="#000" stroke-opacity=".22" stroke-width="1.5"/>`;

      // Fit: shrink font if measured text overflows the face. Never drop characters.
      const tp = svg.querySelectorAll('.wbc-text > text, .wbc-text > g > text');
      if (tp.length && tp[0].getComputedTextLength) {
        let len = 0; try { len = tp[tp.length - 1].getComputedTextLength(); } catch (e) {}
        if (len > avail) {
          const k = Math.max(0.35, avail / len), ns = baseSize * k;
          tp.forEach(t => t.setAttribute('font-size', ns));
        }
      }
      strip(msg, placeholder, font, face, dark, base);
      summary(errs);
      const clean = Object.keys(errs).length === 0;
      persist();
      if (opts.onChange) try { opts.onChange(api.getConfig(), clean); } catch (e) {}
      root.dispatchEvent(new CustomEvent('wbc:change', { bubbles: true, detail: { config: api.getConfig(), valid: clean } }));
      if (!modal.hidden) $('.wbc-mbig').innerHTML = svg.outerHTML.replace(new RegExp(id + 'g', 'g'), id + 'm');
    }

    // Draggable overlay strip: shows the text on a transparent (checkerboard) layer.
    function strip(msg, ph, font, face, dark, base) {
      const el = $('.wbc-strip'), t = $('.wbc-strip-t');
      t.textContent = msg;
      t.style.fontFamily = font[1]; t.style.fontWeight = font[2];
      t.style.fontSize = (34 * st.textSize / 100) + 'px';
      t.style.color = face; t.style.opacity = ph ? .5 : 1;
      t.style.textShadow = style.indexOf('emboss') === 0 ? '1px 1px 1px rgba(0,0,0,.55), -1px -1px 1px rgba(255,255,255,.7)' : '0 1px 0 rgba(255,255,255,.5)';
      const w = el.clientWidth || 600;
      t.style.transform = `translate(calc(-50% + ${st.hpos / 100 * w}px), calc(-50% + ${st.offset / 100 * 60}px))`;
      el.setAttribute('aria-valuenow', st.hpos);
    }
    (function dragSetup() {
      const el = $('.wbc-strip'); let d = null;
      el.addEventListener('pointerdown', e => { d = { x: e.clientX, y: e.clientY, h: st.hpos, o: st.offset }; el.setPointerCapture(e.pointerId); el.classList.add('drag'); });
      el.addEventListener('pointermove', e => {
        if (!d) return; const w = el.clientWidth || 600;
        st.hpos = Math.max(-50, Math.min(50, Math.round((d.h + (e.clientX - d.x) / w * 100) * 2) / 2));
        st.offset = Math.max(-30, Math.min(30, Math.round(d.o + (e.clientY - d.y) / 60 * 100)));
        syncForm(); render();
      });
      const end = () => { d = null; el.classList.remove('drag'); };
      el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
      el.addEventListener('keydown', e => {
        const k = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -2], ArrowDown: [0, 2] }[e.key]; if (!k) return;
        e.preventDefault(); st.hpos = Math.max(-50, Math.min(50, st.hpos + k[0])); st.offset = Math.max(-30, Math.min(30, st.offset + k[1])); syncForm(); render();
      });
    })();

    function summary(errs) {
      const c = st.front.continuous;
      const rows = [['Size', st.size + '"'], c ? ['Continuous', st.front.text] : ['Front', st.front.text], !c && ['Back', st.back.text], hasInside && ['Inside', st.inside.text]]
        .filter(r => r && r[1]).map(r => `<b>${r[0]}:</b> ${esc(r[1])}`);
      $('.wbc-sum').innerHTML = (rows.length ? rows.join(' · ') : 'Type a message to see it on the band.') +
        (Object.keys(errs).length ? '<div class="wbc-err on">Fix the highlighted fields before adding to cart.</div>' : '');
    }

    function persist() { try { localStorage.setItem(STORE_KEY, JSON.stringify({ style: style, config: st })); } catch (e) {} }

    // ---- events ----
    root.addEventListener('input', e => {
      const t = e.target;
      if (t.dataset.text) { const v = sanitize(t.value); st[t.dataset.text].text = v; if (v !== t.value) t.value = v; }
      else if (t.dataset.k) {
        let v = t.type === 'checkbox' ? t.checked : t.value;
        if (['font', 'textSize', 'offset'].indexOf(t.dataset.k) > -1) v = Number(v);
        if (t.dataset.k === 'bandColor') v = safeColor(v, st.bandColor);
        set(t.dataset.k, v);
      } else if (t.type === 'radio') {
        if (t.name.endsWith('band')) st.bandColor = t.value; else st.imprintColor = t.value;
      }
      syncForm(); render();
    });
    root.addEventListener('click', e => {
      const b = e.target.closest('[data-view],[data-act]'); if (!b) return;
      if (b.dataset.view) { st.view = b.dataset.view; }
      else if (b.dataset.act === 'reset') { const s = st.size; st = clone(DEFAULTS); st.size = s; }
      else if (b.dataset.act === 'zoom') { modal.hidden = false; document.body.style.overflow = 'hidden'; $('.wbc-x').focus(); }
      else if (b.dataset.act === 'close') closeModal();
      else if (b.dataset.act === 'flip') st.view = st.view === 'front' ? 'back' : 'front';
      syncForm(); render();
    });
    function closeModal() { modal.hidden = true; document.body.style.overflow = ''; }
    root.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) closeModal(); });
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

    const api = {
      getConfig() {
        const c = st.front.continuous;
        return {
          version: 1, style: style, size: st.size, bandColor: st.bandColor, imprintColor: st.imprintColor || null,
          font: FONTS[st.font][0], fontIndex: st.font, textSize: st.textSize, align: st.align, offset: st.offset, hpos: st.hpos,
          messages: {
            front: { text: sanitize(st.front.text), startIcon: st.front.start, endIcon: st.front.end, continuous: c },
            back: c ? null : { text: sanitize(st.back.text), startIcon: st.back.start, endIcon: st.back.end },
            inside: hasInside && st.inside.text ? { text: sanitize(st.inside.text), mode: st.inside.mode } : null,
          },
          _state: clone(st),
        };
      },
      isValid() { return Object.keys(validate()).length === 0; },
      setSize(s) { if (LIMITS[s]) { st.size = s; render(); } },
      setConfig(cfg) { st = merge(clone(DEFAULTS), cfg && cfg._state ? cfg._state : cfg); syncForm(); render(); },
      reset() { const s = st.size; st = clone(DEFAULTS); st.size = s; syncForm(); render(); },
    };
    syncForm(); render();
    return api;
  }

  // ---- Cart (localStorage demo; replace with your cart API) ---------------
  const Cart = {
    all() { try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch (e) { return []; } },
    add(item) { const a = this.all(); item.id = 'ci' + Date.now(); a.push(item); localStorage.setItem(CART_KEY, JSON.stringify(a)); return item; },
    update(id, item) { const a = this.all().map(x => x.id === id ? Object.assign(x, item) : x); localStorage.setItem(CART_KEY, JSON.stringify(a)); },
    remove(id) { localStorage.setItem(CART_KEY, JSON.stringify(this.all().filter(x => x.id !== id))); },
    describe(cfg) {
      const m = cfg.messages, l = [`Style: ${cfg.style}`, `Size: ${cfg.size}"`, `Band colour: ${cfg.bandColor}`, `Imprint: ${cfg.imprintColor || 'none'}`, `Font: ${cfg.font}`];
      const w = x => [x.startIcon, x.text, x.endIcon].filter(Boolean).join(' ');
      if (m.front.continuous) l.push('Continuous: ' + w(m.front)); else { l.push('Front: ' + w(m.front)); if (m.back) l.push('Back: ' + w(m.back)); }
      if (m.inside) l.push(`Inside (${m.inside.mode}): ${m.inside.text}`);
      return l;
    },
  };

  global.WBCustomizer = { mount: mount, Cart: Cart, LIMITS: LIMITS, sanitize: sanitize };
})(window);

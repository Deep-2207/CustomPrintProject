import { Customizer } from './customizer.js';

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const q = new URLSearchParams(location.search);
// Two ways in: the normal page (/?product=slug) and a seller's shareable link (/s/<seller>/<slug>).
const pathMatch = location.pathname.match(/^\/s\/([a-z0-9-]+)\/([a-z0-9-]+)/);
const seller = pathMatch ? pathMatch[1] : null;
// Third way in: a seller's own website shows the page in an iframe (/embed/<public key>/<product>), see static/embed.js.
const embedMatch = location.pathname.match(/^\/embed\/(pk_[A-Za-z0-9_-]+)\/([a-z0-9-]+)/);
const embedKey = embedMatch ? embedMatch[1] : null;
const slug = pathMatch ? pathMatch[2] : embedMatch ? embedMatch[2] : (q.get('product') || 'custom-embossed-wristband');
const pageUrl = design => (seller ? `/s/${seller}/${slug}` : `/?product=${encodeURIComponent(slug)}`) + (design ? (seller ? '?' : '&') + 'design=' + design : '');
const CART = 'plat:cart:v1';
// Keep letters, digits, punctuation and line breaks; drop control characters and anything that could be markup.
const clean = s => String(s).replace(/\r\n?/g, '\n').replace(/[\u0000-\u0009\u000b-\u001f\u007f<>`\\{}]/g, '').replace(/^\s+/, '');
const MAX_STICKERS = 6;                       // per print area (the server allows 10)
const SLOTS = [.2, .8, .5, .35, .65, .12];    // where new stickers land, so they do not stack
const stickerSvg = k => `<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true">${k.svg}</svg>`;

const stickers = await (await fetch('/stickers.json')).json();
const textStyles = await (await fetch('/text-styles.json')).json();   // ids + labels; the drawing lives in textstyles.js
const productRes = await fetch(embedKey ? `/api/embed/${embedKey}/products/${slug}` : seller ? `/api/t/${seller}/products/${slug}` : '/api/products/' + slug);
if (!productRes.ok) {
  document.body.innerHTML = '<main class="wrap"><h1>This product is not available</h1><p>The link may be wrong, or the seller has not published it yet.</p></main>';
  throw new Error('product not available');
}
const product = await productRes.json();
document.title = product.name; $('#title').textContent = product.name;
// Messages to the website that embeds us. Only sent to a website on the seller's allowed list.
let hostOrigin = null;
const tell = msg => { if (hostOrigin) parent.postMessage({ source: 'previewprint', version: 1, ...msg }, hostOrigin); };
if (embedKey) {
  document.body.classList.add('embed');
  const asked = q.get('host') || '';
  if (asked && window.self !== window.top) {
    const r = await fetch(`/api/embed/${embedKey}/host?origin=${encodeURIComponent(asked)}`).then(r => r.json()).catch(() => ({}));
    if (r.allowed) hostOrigin = asked;
  }
  new ResizeObserver(() => tell({ type: 'resize', height: document.documentElement.scrollHeight })).observe(document.body);
}
if (seller && $('#seller-line')) $('#seller-line').innerHTML = 'Ordering from <b>' + esc(seller.replace(/-/g, ' ').replace(/(^| )\w/g, c => c.toUpperCase())) + '</b>';
const cz = new Customizer($('#stage'), product);
cz.stickers = Object.fromEntries(stickers.map(k => [k.id, k]));

// Text carried over from the product the customer was just looking at (see the picker below).
const CARRY = 'plat:carry';
if (q.get('design')) {
  const r = await fetch('/api/designs/' + q.get('design'));
  if (r.ok) cz.fromDesign(await r.json());
} else {
  try {
    const carry = JSON.parse(sessionStorage.getItem(CARRY) || 'null');
    sessionStorage.removeItem(CARRY);
    if (carry) product.zones.forEach((z, i) => { if (carry.texts[i]) cz.state.zones[z.id].text = carry.texts[i]; });   // over-long text is flagged, never cut
  } catch { /* storage unavailable: start fresh */ }
}
await cz.load();
if (q.get('view') === 'back') cz.setView('back');   // handy for links and screenshots

// ---------- panel ----------
function sw(name, list, cur, cls) {
  return `<div class="sws">${list.map(c => `<label class="sw" title="${esc(c.name)}"><input type="radio" name="${name}" value="${c.hex}" ${c.hex === cur ? 'checked' : ''}>
  <span style="background:${c.hex || 'repeating-linear-gradient(45deg,#fff,#fff 4px,#ddd 4px,#ddd 8px)'}"></span></label>`).join('')}</div>`;
}
function buildPanel() {
  const st = cz.state;
  $('#panel').innerHTML = `
  ${product.sizes.length ? `<label class="lr" for="size">Size</label><select id="size">${product.sizes.map(s => `<option value="${s.id}" ${s.id === st.size ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select>` : ''}
  <fieldset><legend>Colour</legend>${sw('body', product.colors, st.bodyColor)}</fieldset>
  <fieldset><legend>Text / imprint colour</legend>${sw('imp', product.imprint_colors, st.imprintColor)}</fieldset>
  ${product.zones.map(z => `<div class="zone" data-z="${z.id}"><h4>${esc(z.label)}</h4>
    <div class="lr"><label for="t-${z.id}">Enter Your Custom Message</label><span class="cnt" id="c-${z.id}"></span></div>
    ${(z.max_lines || 1) > 1
      ? `<textarea id="t-${z.id}" data-f="text" rows="${Math.min(z.max_lines, 4)}" placeholder="${esc(product.placeholder || 'Type here. Press Enter for a new line')}" maxlength="500" aria-describedby="m-${z.id}"></textarea>`
      : `<input type="text" id="t-${z.id}" data-f="text" placeholder="${esc(product.placeholder || 'Type here…')}" autocomplete="off" maxlength="500" aria-describedby="m-${z.id}">`}
    <div class="msg" id="m-${z.id}"></div>
    <div class="tpl"><div class="lr"><span>Text style</span><span class="cnt">your text in each style</span></div>
      <div class="tpl-grid">${textStyles.map(t => `<button type="button" class="tpl-btn" data-tpl="${t.id}" aria-pressed="false" aria-label="${esc(t.label)} style"><canvas width="240" height="150"></canvas><span>${esc(t.label)}</span></button>`).join('')}</div></div>
    <div class="row"><label>Font<select data-f="font">${product.fonts.map(f => `<option>${esc(f)}</option>`).join('')}</select></label>
      <label>Text size<input type="range" min="20" max="80" data-f="size"></label></div>
    <div class="row"><label>Horizontal<input type="range" min="0" max="100" data-f="x"></label><label>Vertical<input type="range" min="10" max="90" data-f="y"></label></div>
    ${z.allow_images ? `<label>Add logo / photo<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" data-up="${z.id}"></label>
      <div class="warn" id="w-${z.id}"></div><div class="row img-row" id="ir-${z.id}" hidden><label>Image size<input type="range" min="10" max="100" data-i="scale"></label>
      <button type="button" class="btn ghost" data-rm="${z.id}">Remove image</button></div>` : ''}
    ${z.allow_stickers !== false ? `<div class="stk"><div class="lr"><span>Stickers</span><span class="cnt">tap one to add it</span></div>
      <div class="stk-grid">${stickers.map(k => `<button type="button" class="stk-btn" data-stk="${k.id}" title="${esc(k.label)}" aria-label="Add ${esc(k.label)} sticker">${stickerSvg(k)}</button>`).join('')}</div>
      <div class="stk-list" id="sl-${z.id}"></div></div>` : ''}
  </div>`).join('')}`;
  sync();
  const strips = $('#strips'); strips.innerHTML = '';
  product.zones.forEach(z => {
    const d = document.createElement('div'); d.className = 'strip'; d.dataset.z = z.id; d.innerHTML = '<canvas></canvas>'; strips.appendChild(d); dragStrip(d, z);
  });
}
function sync() {
  const st = cz.state;
  document.querySelectorAll('.zone').forEach(el => {
    const s = st.zones[el.dataset.z];
    el.querySelectorAll('[data-f]').forEach(i => {
      const v = i.dataset.f === 'size' ? s.size * 100 : i.dataset.f === 'x' ? s.x * 100 : i.dataset.f === 'y' ? s.y * 100 : s[i.dataset.f];
      if (i.value !== String(v)) i.value = v;
    });
    const ir = el.querySelector('.img-row'); if (ir) { ir.hidden = !s.image; if (s.image) ir.querySelector('[data-i=scale]').value = s.image.scale * 100; }
    syncStickers(el, s);
    el.querySelectorAll('.tpl-btn').forEach(bt => { const on = bt.dataset.tpl === s.tpl; bt.classList.toggle('on', on); bt.setAttribute('aria-pressed', on); });
  });
}
// The sticker rows are only rebuilt when the set of stickers changes, so a slider is not
// destroyed while it is being dragged.
function syncStickers(el, s) {
  const list = el.querySelector('.stk-list'); if (!list) return;
  const sig = s.stickers.map(k => k.id).join(',');
  if (list.dataset.sig !== sig) {
    list.dataset.sig = sig;
    list.innerHTML = s.stickers.map((k, i) => `<div class="stk-row"><span class="stk-ico">${stickerSvg(cz.stickers[k.id])}</span>
      <input type="range" min="10" max="100" data-sk="${i}" aria-label="${esc(cz.stickers[k.id].label)} sticker size">
      <button type="button" class="stk-x" data-rm-stk="${i}" aria-label="Remove ${esc(cz.stickers[k.id].label)} sticker">&times;</button></div>`).join('');
  }
  list.querySelectorAll('[data-sk]').forEach(r => { const v = String(Math.round(s.stickers[+r.dataset.sk].scale * 100)); if (r.value !== v) r.value = v; });
}

$('#panel').addEventListener('input', async e => {
  const t = e.target, st = cz.state;
  if (t.id === 'size') { st.size = t.value; await cz.load(); return update(); }
  if (t.name === 'body') st.bodyColor = t.value;
  else if (t.name === 'imp') st.imprintColor = t.value;
  else if (t.dataset.f) {
    const s = st.zones[t.closest('.zone').dataset.z], f = t.dataset.f;
    if (f === 'text') { s.text = clean(t.value); if (s.text !== t.value) t.value = s.text; }
    else if (f === 'font') s.font = t.value;
    else s[f] = Number(t.value) / (f === 'size' || f === 'x' || f === 'y' ? 100 : 1);
  } else if (t.dataset.sk !== undefined) st.zones[t.closest('.zone').dataset.z].stickers[+t.dataset.sk].scale = t.value / 100;
  else if (t.dataset.i) st.zones[t.closest('.zone').dataset.z].image.scale = t.value / 100;
  else if (t.dataset.up) return upload(t);
  update();
});
$('#panel').addEventListener('change', e => { if (e.target.dataset.up) upload(e.target); });
$('#panel').addEventListener('click', e => {
  const b = e.target.closest('[data-stk],[data-rm-stk],[data-rm],[data-tpl]'); if (!b) return;
  const zEl = b.closest('.zone'), zid = zEl ? zEl.dataset.z : null;
  if (b.dataset.tpl) cz.state.zones[zid].tpl = b.dataset.tpl;
  else if (b.dataset.rm) { cz.state.zones[b.dataset.rm].image = null; $('#w-' + b.dataset.rm).textContent = ''; }
  else if (b.dataset.stk) {
    const s = cz.state.zones[zid]; if (s.stickers.length >= MAX_STICKERS) return;
    s.stickers.push({ id: b.dataset.stk, x: SLOTS[s.stickers.length % SLOTS.length], y: .5, scale: .35, rot: 0 });
  } else if (b.dataset.rmStk !== undefined) cz.state.zones[zid].stickers.splice(+b.dataset.rmStk, 1);
  sync(); update();
});

async function upload(inp) {
  const f = inp.files[0]; if (!f) return; const z = inp.dataset.up, w = $('#w-' + z);
  w.textContent = 'Uploading…';
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/uploads', { method: 'POST', body: fd });
  const j = await r.json();
  if (!r.ok) { w.textContent = j.detail || 'Upload failed'; w.className = 'msg'; inp.value = ''; return; }
  w.className = 'warn'; w.textContent = j.warning || '';
  cz.state.zones[z].image = { upload_id: j.id, url: j.url, x: .5, y: .5, scale: .6, rot: 0 };
  inp.value = ''; sync(); update();
}

// ---------- validation + redraw ----------
function validate() {
  const errs = [];
  product.zones.forEach(z => {
    // Letters count towards the limit; line breaks are free but limited per area.
    const text = cz.state.zones[z.id].text, len = text.replace(/\n/g, '').length, lines = text ? text.split('\n').length : 0, maxL = z.max_lines || 1;
    const overC = len > z.max_chars, overL = lines > maxL, over = overC || overL;
    $('#c-' + z.id).textContent = `${len} / ${z.max_chars}` + (maxL > 1 ? ` · ${lines} / ${maxL} lines` : ''); $('#c-' + z.id).classList.toggle('bad', over);
    $('#t-' + z.id).classList.toggle('invalid', over);
    $('#m-' + z.id).textContent = overC ? `Too long: ${len - z.max_chars} character(s) over the ${z.max_chars} limit. Shorten it, or choose a wider size.`
      : overL ? `Too many lines: ${lines}, and this area allows ${maxL}. Remove a line break.` : '';
    if (over) errs.push(z.label);
  });
  return errs;
}
function update() { cz.redraw(); }
// The style gallery shows the customer's own text; redraw it at most once per frame.
let thumbTimer = 0;
function drawThumbs() {
  thumbTimer = 0;
  document.querySelectorAll('.zone').forEach(el => {
    const z = product.zones.find(z => z.id === el.dataset.z);
    el.querySelectorAll('.tpl-btn').forEach(bt => cz.renderThumb(bt.querySelector('canvas'), z, bt.dataset.tpl));
  });
}
cz.addEventListener('redraw', () => {
  if (!thumbTimer) thumbTimer = requestAnimationFrame(drawThumbs);
  const bad = validate();
  $('#errs').textContent = bad.length ? 'Fix the highlighted messages before adding to cart.' : '';
  $('#add').disabled = bad.length > 0;
  document.querySelectorAll('.strip').forEach(d => {
    const z = product.zones.find(z => z.id === d.dataset.z), r = cz.zoneRect(z); if (!r) return;
    const c = d.querySelector('canvas'); c.width = 1400; c.height = Math.max(40, Math.round(1400 * r.sh / r.sw));
    const x = c.getContext('2d'); x.drawImage(r.src, r.sx, r.sy, r.sw, r.sh, 0, 0, c.width, c.height);
  });
});

function dragStrip(el, z) {
  let d = null;
  // Everything placed in the area has x and y (0 to 1). Grab whichever is closest to the pointer.
  const items = () => { const s = cz.state.zones[z.id], t = []; if (s.text) t.push(s); if (s.image) t.push(s.image); s.stickers.forEach(k => t.push(k)); return t; };
  el.addEventListener('pointerdown', e => {
    const r = el.getBoundingClientRect(), px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height, list = items();
    if (!list.length) return;
    let best = list[0], bd = Infinity;
    list.forEach(t => { const dist = Math.hypot(t.x - px, (t.y - py) * r.height / r.width); if (dist < bd) { bd = dist; best = t; } });
    d = { x: e.clientX, y: e.clientY, t: best, tx: best.x, ty: best.y };
    el.setPointerCapture(e.pointerId); el.classList.add('drag');
  });
  el.addEventListener('pointermove', e => {
    if (!d) return; const r = el.getBoundingClientRect();
    d.t.x = Math.max(0, Math.min(1, d.tx + (e.clientX - d.x) / r.width));
    d.t.y = Math.max(.05, Math.min(.95, d.ty + (e.clientY - d.y) / r.height));
    sync(); update();
  });
  const end = () => { d = null; el.classList.remove('drag'); };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
}

// ---------- actions ----------
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => cz.setView(b.dataset.view));
$('#reset').onclick = async () => { cz.state = cz.defaults(); await cz.load(); buildPanel(); update(); };
$('#add').onclick = async () => {
  const btn = $('#add'); btn.disabled = true; $('#errs').textContent = '';
  const body = cz.toDesign(); body.preview_png = cz.snapshot();
  if (seller) body.seller = seller;
  if (embedKey && q.get('ref')) body.ref = q.get('ref').slice(0, 80);
  const r = await fetch(embedKey ? `/api/embed/${embedKey}/designs` : '/api/designs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) { $('#errs').textContent = (j.detail && j.detail.errors ? j.detail.errors : [j.detail || 'Could not save']).join(' · '); btn.disabled = false; return; }
  if (embedKey) {            // inside the seller's website: hand the design to the page, no cart of our own
    btn.disabled = false;
    $('#errs').textContent = '';
    $('#saved-note').hidden = false;
    tell({ type: 'design.saved', designId: j.id, product: slug, previewUrl: location.origin + j.preview,
           text: body.layers.filter(l => l.type === 'text').map(l => l.text.split(String.fromCharCode(10)).join(' / ')).join(' | ') });
    return;
  }
  const cart = JSON.parse(localStorage.getItem(CART) || '[]');
  cart.push({ design: j.id, preview: j.preview, name: product.name, size: cz.state.size, layers: body.layers });
  localStorage.setItem(CART, JSON.stringify(cart)); btn.disabled = false; renderCart();
  if (seller) showShare(j.id);
};
function renderCart() {
  if (!$('#cart')) return;
  const cart = JSON.parse(localStorage.getItem(CART) || '[]');
  $('#cart').innerHTML = cart.map((c, i) => `<li><img src="${esc(c.preview)}" alt=""><div><b>${esc(c.name)}</b>
    ${c.size ? `<small>Size: ${esc(c.size)}</small>` : ''}${c.layers.filter(l => l.type === 'text').map(l => `<small>${esc(l.zone)}: ${esc(l.text).replace(/\n/g, ' / ')}</small>`).join('')}
    ${c.layers.filter(l => l.type === 'image').map(l => `<small>${esc(l.zone)}: image</small>`).join('')}
    ${c.layers.filter(l => l.type === 'sticker').map(l => `<small>${esc(l.zone)}: sticker ${esc(l.sticker)}</small>`).join('')}
    <a href="${pageUrl(c.design)}">Edit design</a> · <a href="#" data-rm-cart="${i}">Remove</a></div></li>`).join('') || '<li>Cart is empty.</li>';
}
$('#cart')?.addEventListener('click', e => {
  if (e.target.dataset.rmCart === undefined) return; e.preventDefault();
  const c = JSON.parse(localStorage.getItem(CART) || '[]'); c.splice(+e.target.dataset.rmCart, 1); localStorage.setItem(CART, JSON.stringify(c)); renderCart();
});
renderCart();
buildPanel(); update();
window.cz = cz;

// ---------- product picker: switch products, keeping the text typed so far ----------
const all = embedKey ? [] : await (await fetch(seller ? `/api/t/${seller}/products` : '/api/products')).json();
if (all.length > 1 && $('#picker') && window.self === window.top) {   // inside the landing-page demo the tabs do this job
  const href = s => (seller ? `/s/${seller}/${s}` : `/?product=${encodeURIComponent(s)}`) + (q.get('demo') ? (seller ? '?' : '&') + 'demo=1' : '');
  $('#picker').hidden = false;
  $('#picker').innerHTML = all.map(p => `<a href="${href(p.slug)}" data-pick class="pick${p.slug === slug ? ' on' : ''}" ${p.slug === slug ? 'aria-current="page"' : ''}>${esc(p.name)}</a>`).join('');
  $('#picker').addEventListener('click', e => {
    if (!e.target.matches('[data-pick]')) return;
    try { sessionStorage.setItem(CARRY, JSON.stringify({ texts: product.zones.map(z => cz.state.zones[z.id].text) })); } catch { /* ignore */ }
  });
}

// ---------- demo bar (?demo=1): examples, auto-rotate, download a picture ----------
if (q.get('demo') && $('#demo') && (product.demos || []).length) {
  const bar = $('#demo'); bar.hidden = false;
  bar.innerHTML = `<span class="demo-l">Try an example:</span>${product.demos.map((d, i) => `<button type="button" class="chip" data-demo="${i}">${esc(d.name)}</button>`).join('')}
    <label class="demo-r"><input type="checkbox" id="spin"> Auto-rotate</label><button type="button" class="chip" id="shot">Download picture</button>`;
  bar.addEventListener('click', async e => {
    if (e.target.dataset.demo !== undefined) { cz.applyDemo(product.demos[+e.target.dataset.demo]); cz.setView('front'); buildPanel(); update(); }
    else if (e.target.id === 'shot') { const a = document.createElement('a'); a.href = cz.snapshot(); a.download = `${slug}-design.png`; a.click(); }
  });
  bar.addEventListener('input', e => { if (e.target.id === 'spin') cz.autoRotate = e.target.checked; });
}

// ---------- shareable link page: share the saved design ----------
function showShare(id) {
  const url = location.origin + pageUrl(id), box = $('#share');
  if (!box) return;
  const text = `My ${product.name} design: ${url}`;
  box.hidden = false;
  box.querySelector('input').value = url;
  box.querySelector('[data-wa]').href = 'https://wa.me/?text=' + encodeURIComponent(text);
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
$('#share')?.addEventListener('click', async e => {
  if (!e.target.matches('[data-copy]')) return;
  const inp = $('#share input'); inp.select();
  try { await navigator.clipboard.writeText(inp.value); e.target.textContent = 'Copied'; } catch { document.execCommand('copy'); e.target.textContent = 'Copied'; }
  setTimeout(() => e.target.textContent = 'Copy link', 1500);
});
if (seller) $('#add').textContent = 'Save and share design';
if (embedKey) {
  $('#add').textContent = (q.get('button') || 'Add to my order').slice(0, 40);
  tell({ type: 'ready', product: slug });
}

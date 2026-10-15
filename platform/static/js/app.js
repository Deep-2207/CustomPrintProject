import { Customizer } from './customizer.js';

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const q = new URLSearchParams(location.search);
const slug = q.get('product') || 'custom-embossed-wristband';
const CART = 'plat:cart:v1';
const clean = s => String(s).replace(/[\u0000-\u001f\u007f<>`\\{}]/g, '').replace(/^\s+/, '');

const product = await (await fetch('/api/products/' + slug)).json();
document.title = product.name; $('#title').textContent = product.name;
const cz = new Customizer($('#stage'), product);

if (q.get('design')) {
  const r = await fetch('/api/designs/' + q.get('design'));
  if (r.ok) cz.fromDesign(await r.json());
}
await cz.load();

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
    <input type="text" id="t-${z.id}" data-f="text" placeholder="Type here…" autocomplete="off" maxlength="500" aria-describedby="m-${z.id}">
    <div class="msg" id="m-${z.id}"></div>
    <div class="row"><label>Font<select data-f="font">${product.fonts.map(f => `<option>${esc(f)}</option>`).join('')}</select></label>
      <label>Text size<input type="range" min="20" max="80" data-f="size"></label></div>
    <div class="row"><label>Horizontal<input type="range" min="0" max="100" data-f="x"></label><label>Vertical<input type="range" min="10" max="90" data-f="y"></label></div>
    ${z.allow_images ? `<label>Add logo / photo<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" data-up="${z.id}"></label>
      <div class="warn" id="w-${z.id}"></div><div class="row img-row" id="ir-${z.id}" hidden><label>Image size<input type="range" min="10" max="100" data-i="scale"></label>
      <button type="button" class="btn ghost" data-rm="${z.id}">Remove image</button></div>` : ''}
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
  });
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
  } else if (t.dataset.i) st.zones[t.closest('.zone').dataset.z].image.scale = t.value / 100;
  else if (t.dataset.up) return upload(t);
  update();
});
$('#panel').addEventListener('change', e => { if (e.target.dataset.up) upload(e.target); });
$('#panel').addEventListener('click', e => {
  const z = e.target.dataset.rm; if (z) { cz.state.zones[z].image = null; $('#w-' + z).textContent = ''; sync(); update(); }
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
    const len = cz.state.zones[z.id].text.length, over = len > z.max_chars;
    $('#c-' + z.id).textContent = `${len} / ${z.max_chars}`; $('#c-' + z.id).classList.toggle('bad', over);
    $('#t-' + z.id).classList.toggle('invalid', over);
    $('#m-' + z.id).textContent = over ? `Too long: ${len - z.max_chars} character(s) over the ${z.max_chars} limit. Shorten it, or choose a wider size.` : '';
    if (over) errs.push(z.label);
  });
  return errs;
}
function update() { cz.redraw(); }
cz.addEventListener('redraw', () => {
  const bad = validate();
  $('#errs').textContent = bad.length ? 'Fix the highlighted messages before adding to cart.' : '';
  $('#add').disabled = bad.length > 0;
  document.querySelectorAll('.strip').forEach(d => {
    const z = product.zones.find(z => z.id === d.dataset.z), r = cz.zoneRect(z); if (!r) return;
    const c = d.querySelector('canvas'); c.width = 1400; c.height = Math.max(40, Math.round(1400 * r.sh / r.sw));
    const x = c.getContext('2d'); x.drawImage(r.src, r.sx, 0, r.sw, r.sh, 0, 0, c.width, c.height);
  });
});

function dragStrip(el, z) {
  let d = null;
  el.addEventListener('pointerdown', e => { d = { x: e.clientX, y: e.clientY, s: { ...cz.state.zones[z.id] } }; el.setPointerCapture(e.pointerId); el.classList.add('drag'); });
  el.addEventListener('pointermove', e => {
    if (!d) return; const r = el.getBoundingClientRect(), s = cz.state.zones[z.id], tgt = s.text || !s.image ? s : s.image;
    tgt.x = Math.max(0, Math.min(1, (tgt === s ? d.s.x : d.s.image.x) + (e.clientX - d.x) / r.width));
    tgt.y = Math.max(.1, Math.min(.9, (tgt === s ? d.s.y : d.s.image.y) + (e.clientY - d.y) / r.height));
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
  const r = await fetch('/api/designs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) { $('#errs').textContent = (j.detail && j.detail.errors ? j.detail.errors : [j.detail || 'Could not save']).join(' · '); btn.disabled = false; return; }
  const cart = JSON.parse(localStorage.getItem(CART) || '[]');
  cart.push({ design: j.id, preview: j.preview, name: product.name, size: cz.state.size, layers: body.layers });
  localStorage.setItem(CART, JSON.stringify(cart)); btn.disabled = false; renderCart();
};
function renderCart() {
  const cart = JSON.parse(localStorage.getItem(CART) || '[]');
  $('#cart').innerHTML = cart.map((c, i) => `<li><img src="${esc(c.preview)}" alt=""><div><b>${esc(c.name)}</b>
    ${c.size ? `<small>Size: ${esc(c.size)}</small>` : ''}${c.layers.filter(l => l.type === 'text').map(l => `<small>${esc(l.zone)}: ${esc(l.text)}</small>`).join('')}
    ${c.layers.filter(l => l.type === 'image').map(l => `<small>${esc(l.zone)}: image</small>`).join('')}
    <a href="?product=${encodeURIComponent(slug)}&design=${c.design}">Edit design</a> · <a href="#" data-rm-cart="${i}">Remove</a></div></li>`).join('') || '<li>Cart is empty.</li>';
}
$('#cart').addEventListener('click', e => {
  if (e.target.dataset.rmCart === undefined) return; e.preventDefault();
  const c = JSON.parse(localStorage.getItem(CART) || '[]'); c.splice(+e.target.dataset.rmCart, 1); localStorage.setItem(CART, JSON.stringify(c)); renderCart();
});
renderCart();
buildPanel(); update();
window.cz = cz;

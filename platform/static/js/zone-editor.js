// Print-area editor: pick a part of the 3D model, add a print area on it, and position it with live preview.
import * as THREE from '../vendor/three.module.js';
import { Customizer } from './customizer.js';
import { $, $$, esc, api, me, showErrors, clearErrors } from './api.js';

const id = Number(new URLSearchParams(location.search).get('product'));
const user = await me().catch(() => null);
if (!user) location.replace('/account.html');
else if (user.role === 'owner') location.replace('/owner.html');
const canEdit = user.tenant.status === 'active' && user.role === 'seller_admin';

const p = await api(`/api/seller/products/${id}`).catch(e => { document.body.innerHTML = `<main class="wrap"><div class="errs">${esc(e.message)}</div><p><a href="/dashboard.html">Back</a></p></main>`; throw e; });
const draft = structuredClone(p.config);
draft.zones = draft.zones || [];
$('#title').textContent = `Print areas: ${draft.name}`;
$('#back').href = `/dashboard.html#/product/${id}`;
if (!canEdit) { $('#save').disabled = true; $('#add').disabled = true; $('#add-note').textContent = 'Your account cannot change products right now.'; }

let selectedPart = null;     // three.js name of the selected part
let activeZone = null;       // id of the zone being adjusted
let dirty = false;
let cz = null;
let parts = [];              // [{name, mesh, tris, hasUv}]
const toast = msg => { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 2400); };
const setDirty = v => { dirty = v; $('#dirty').textContent = v ? 'Unsaved changes' : ''; };
window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

// ---------------------------------------------------------------- 3D view (the same Customizer the shoppers use)
async function rebuild() {
  // The customizer gets its own copy of the zones, always with the dashed outline switched on.
  const model = { ...draft, zones: draft.zones.map(z => ({ ...z, guide: true })), sizes: draft.sizes || [] };
  if (!cz) { cz = new Customizer($('#stage'), model); cz.stickers = {}; }
  cz.product = model;
  cz.state = cz.defaults();
  const text = $('#sample').value;
  draft.zones.forEach(z => { cz.state.zones[z.id].text = text; });
  await cz.load();
  collectParts();
  paintSelection();
  cz.redraw();
}

function collectParts() {
  parts = [];
  cz.root.traverse(o => {
    if (!o.isMesh || !o.name) return;
    const g = o.geometry, tris = (g.index ? g.index.count : g.attributes.position.count) / 3;
    parts.push({ name: o.name, mesh: o, tris, hasUv: !!g.attributes.uv });
  });
}

function paintSelection() {
  for (const part of parts) {
    const m = part.mesh.material;
    if (m && m.emissive) { m.emissive.set(part.name === selectedPart ? 0x0b5fff : 0x000000); m.emissiveIntensity = part.name === selectedPart ? 0.35 : 0; }
  }
}

// Click on the model to select a part (a drag is only a rotation).
(() => {
  const el = $('#stage'); let down = null;
  el.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY }; });
  el.addEventListener('pointerup', e => {
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
    const r = el.getBoundingClientRect(), ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, cz.camera);
    const hit = ray.intersectObjects(parts.map(x => x.mesh), false)[0];
    if (hit) selectPart(hit.object.name);
  });
})();
$$('[data-view]').forEach(b => b.onclick = () => cz.setView(b.dataset.view));

// ---------------------------------------------------------------- the parts list
function renderParts() {
  $('#parts').innerHTML = parts.map(x => {
    const n = draft.zones.filter(z => z.mesh === x.name).length;
    return `<button type="button" class="part ${x.name === selectedPart ? 'on' : ''}" data-part="${esc(x.name)}" ${x.hasUv ? '' : 'disabled title="This part has no UV map, so it cannot be printed on"'}>
      <span><b>${esc(x.name)}</b><br><small>${x.tris.toLocaleString()} triangles${x.hasUv ? '' : ', no UV map'}</small></span>
      <small>${n ? `${n} print area${n > 1 ? 's' : ''}` : (x.hasUv ? 'not printable yet' : '')}</small></button>`;
  }).join('') || '<p class="muted">Loading the model…</p>';
}
function selectPart(name) {
  selectedPart = name;
  const first = draft.zones.find(z => z.mesh === name);
  if (first) activeZone = first.id;
  paintSelection(); renderAll();
}
$('#parts').onclick = e => { const b = e.target.closest('[data-part]'); if (b && !b.disabled) selectPart(b.dataset.part); };

// ---------------------------------------------------------------- print areas
const uniqueId = () => { let n = 1; while (draft.zones.some(z => z.id === `area-${n}`)) n++; return `area-${n}`; };

$('#add').onclick = async () => {
  if (!selectedPart) return;
  const part = parts.find(x => x.name === selectedPart);
  const sameMesh = draft.zones.find(z => z.mesh === selectedPart);
  const n = draft.zones.length + 1;
  const z = { id: uniqueId(), label: `Print area ${n}`, mesh: selectedPart, style: 'print', max_chars: 30, max_lines: 3, allow_images: true, allow_stickers: true,
              u0: 0.25, u1: 0.75, y0: 0.25, y1: 0.75, aspect: sameMesh ? sameMesh.aspect : autoAspect(part.mesh), guide: true };
  draft.zones.push(z); activeZone = z.id; setDirty(true);
  await rebuild(); renderAll();
};

function renderZones() {
  $('#zones').innerHTML = draft.zones.map(z => `<button type="button" class="part ${z.id === activeZone ? 'on' : ''}" data-zone="${esc(z.id)}"><span><b>${esc(z.label)}</b><br><small>on ${esc(z.mesh)}</small></span><small>${Math.round(z.u0 * 100)}-${Math.round(z.u1 * 100)}% across</small></button>`).join('')
    || '<p class="muted" style="margin-top:0">None yet. Pick a part above, then add a print area on it.</p>';
  const part = parts.find(x => x.name === selectedPart);
  $('#add').textContent = selectedPart ? `Add a print area on "${selectedPart}"` : 'Add a print area';
  $('#add').disabled = !canEdit || !selectedPart || !(part && part.hasUv);
  $('#add-note').textContent = !canEdit ? $('#add-note').textContent : (selectedPart ? '' : 'Select a part first.');
}
$('#zones').onclick = e => { const b = e.target.closest('[data-zone]'); if (b) { activeZone = b.dataset.zone; const z = draft.zones.find(x => x.id === activeZone); selectedPart = z.mesh; paintSelection(); renderAll(); } };

// ---------------------------------------------------------------- adjusting the selected area
const zone = () => draft.zones.find(z => z.id === activeZone);
function renderAdjust() {
  const z = zone();
  $('#adjust').hidden = !z;
  if (!z) return;
  $('#z-label').value = z.label; $('#z-style').value = z.style; $('#z-chars').value = z.max_chars; $('#z-lines').value = z.max_lines || 1;
  for (const k of ['u0', 'u1', 'y0', 'y1']) { $('#z-' + k).value = Math.round(z[k] * 100); $('#v-' + k).textContent = Math.round(z[k] * 100) + '%'; }
  $('#z-aspect').value = (z.aspect || 0).toFixed(2);
  if (!canEdit) $$('#adjust input,#adjust select,#adjust button').forEach(x => x.disabled = true);
}

const MIN_GAP = 0.04;
$('#adjust').addEventListener('input', async e => {
  const z = zone(), t = e.target; if (!z) return;
  let reload = false;
  if (t.id === 'z-label') z.label = t.value.slice(0, 60);
  else if (t.id === 'z-style') z.style = t.value;
  else if (t.id === 'z-chars') z.max_chars = Math.min(500, Math.max(1, Number(t.value) || 1));
  else if (t.id === 'z-lines') z.max_lines = Math.min(10, Math.max(1, Number(t.value) || 1));
  else if (/^z-(u0|u1|y0|y1)$/.test(t.id)) {
    const k = t.id.slice(2), v = Number(t.value) / 100;
    z[k] = v;
    // keep the rectangle at least a little wide and tall
    if (k === 'u0' && z.u1 - z.u0 < MIN_GAP) z.u1 = Math.min(1, z.u0 + MIN_GAP), z.u0 = z.u1 - MIN_GAP;
    if (k === 'u1' && z.u1 - z.u0 < MIN_GAP) z.u0 = Math.max(0, z.u1 - MIN_GAP), z.u1 = z.u0 + MIN_GAP;
    if (k === 'y0' && z.y1 - z.y0 < MIN_GAP) z.y1 = Math.min(1, z.y0 + MIN_GAP), z.y0 = z.y1 - MIN_GAP;
    if (k === 'y1' && z.y1 - z.y0 < MIN_GAP) z.y0 = Math.max(0, z.y1 - MIN_GAP), z.y1 = z.y0 + MIN_GAP;
    for (const key of ['u0', 'u1', 'y0', 'y1']) { $('#z-' + key).value = Math.round(z[key] * 100); $('#v-' + key).textContent = Math.round(z[key] * 100) + '%'; }
  } else if (t.id === 'z-aspect') {
    const a = Number(t.value);
    if (!(a >= 0.05 && a <= 100)) return;
    draft.zones.filter(x => x.mesh === z.mesh).forEach(x => x.aspect = a);    // one surface shape per part
    reload = true;
  }
  setDirty(true);
  if (reload) await rebuild(); else { cz.product.zones = draft.zones.map(x => ({ ...x, guide: true })); cz.redraw(); }
  renderZones(); renderParts(); drawUv();
});
$('#auto').onclick = async () => {
  const z = zone(), part = z && parts.find(x => x.name === z.mesh); if (!part) return;
  const a = autoAspect(part.mesh);
  draft.zones.filter(x => x.mesh === z.mesh).forEach(x => x.aspect = a);
  $('#z-aspect').value = a.toFixed(2); setDirty(true); await rebuild(); drawUv();
  toast(`Surface shape set to ${a.toFixed(2)}`);
};
$('#del').onclick = async () => {
  draft.zones = draft.zones.filter(z => z.id !== activeZone);
  activeZone = (draft.zones[0] || {}).id || null; setDirty(true); await rebuild(); renderAll();
};
$('#sample').addEventListener('input', () => { draft.zones.forEach(z => { cz.state.zones[z.id].text = $('#sample').value; }); cz.redraw(); });

// ---------------------------------------------------------------- measuring the model
// Works out how many world units one step in u covers compared with one step in v, so text is not stretched.
function autoAspect(mesh) {
  const g = mesh.geometry, pos = g.attributes.position, uv = g.attributes.uv, idx = g.index;
  if (!uv) return 1;
  const s = new THREE.Vector3(); mesh.getWorldScale(s);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
  const pu = new THREE.Vector3(), pv = new THREE.Vector3(), tmp = new THREE.Vector3();
  const count = idx ? idx.count : pos.count, step = Math.max(1, Math.floor(count / 3 / 40000)) * 3;   // look at most ~40k triangles
  let wu = 0, wv = 0, wsum = 0;
  for (let i = 0; i + 2 < count; i += step) {
    const i0 = idx ? idx.getX(i) : i, i1 = idx ? idx.getX(i + 1) : i + 1, i2 = idx ? idx.getX(i + 2) : i + 2;
    a.fromBufferAttribute(pos, i0).multiply(s); b.fromBufferAttribute(pos, i1).multiply(s); c.fromBufferAttribute(pos, i2).multiply(s);
    e1.subVectors(b, a); e2.subVectors(c, a);
    const du1 = uv.getX(i1) - uv.getX(i0), dv1 = uv.getY(i1) - uv.getY(i0), du2 = uv.getX(i2) - uv.getX(i0), dv2 = uv.getY(i2) - uv.getY(i0);
    const det = du1 * dv2 - du2 * dv1;
    if (Math.abs(det) < 1e-9) continue;
    pu.copy(e1).multiplyScalar(dv2).addScaledVector(e2, -dv1).multiplyScalar(1 / det);
    pv.copy(e2).multiplyScalar(du1).addScaledVector(e1, -du2).multiplyScalar(1 / det);
    const area = tmp.crossVectors(e1, e2).length() / 2;
    wu += pu.length() * area; wv += pv.length() * area; wsum += area;
  }
  if (!wsum || !wv) return 1;
  return Math.min(100, Math.max(0.05, wu / wv));
}

// ---------------------------------------------------------------- the flat map of the selected part
function drawUv() {
  const cv = $('#uv'), c = cv.getContext('2d'), W = cv.width, H = cv.height;
  c.clearRect(0, 0, W, H); c.fillStyle = '#fff'; c.fillRect(0, 0, W, H);
  c.strokeStyle = '#e1e5ec'; c.lineWidth = 1; c.strokeRect(0.5, 0.5, W - 1, H - 1);
  const part = parts.find(x => x.name === selectedPart); if (!part || !part.hasUv) return;
  const g = part.mesh.geometry, uv = g.attributes.uv, idx = g.index, count = idx ? idx.count : uv.count;
  const step = Math.max(1, Math.floor(count / 3 / 15000)) * 3;
  c.strokeStyle = '#b9c1cf'; c.lineWidth = 1; c.beginPath();
  for (let i = 0; i + 2 < count; i += step) {
    const ids = [0, 1, 2].map(k => (idx ? idx.getX(i + k) : i + k));
    ids.forEach((v, k) => { const x = uv.getX(v) * W, y = (1 - uv.getY(v)) * H; k ? c.lineTo(x, y) : c.moveTo(x, y); });
    c.closePath();
  }
  c.stroke();
  for (const z of draft.zones.filter(x => x.mesh === selectedPart)) {
    c.fillStyle = z.id === activeZone ? 'rgba(11,95,255,.30)' : 'rgba(11,95,255,.12)';
    c.strokeStyle = '#0b5fff'; c.lineWidth = z.id === activeZone ? 3 : 1.5;
    c.fillRect(z.u0 * W, z.y0 * H, (z.u1 - z.u0) * W, (z.y1 - z.y0) * H); c.strokeRect(z.u0 * W, z.y0 * H, (z.u1 - z.u0) * W, (z.y1 - z.y0) * H);
  }
}

function renderAll() { renderParts(); renderZones(); renderAdjust(); drawUv(); }

// ---------------------------------------------------------------- save
$('#save').onclick = async () => {
  const err = $('#err'); clearErrors(err);
  const body = { name: draft.name, sizes: draft.sizes || [], colors: draft.colors, imprint_colors: draft.imprint_colors, fonts: draft.fonts,
                 zones: draft.zones, defaults: draft.defaults || {}, sample: draft.sample || '', placeholder: draft.placeholder || '', price: draft.price || {} };
  try { await api(`/api/seller/products/${id}`, { method: 'PUT', json: body }); setDirty(false); toast('Saved'); }
  catch (x) { showErrors(err, x); window.scrollTo(0, 0); }
};

await rebuild();
if (draft.zones[0]) { activeZone = draft.zones[0].id; selectedPart = draft.zones[0].mesh; paintSelection(); }
else if (parts.filter(x => x.hasUv).length === 1) selectedPart = parts.find(x => x.hasUv).name;
paintSelection();
renderAll();
window.ze = { draft, get cz() { return cz; }, get parts() { return parts; } };   // handy for tests

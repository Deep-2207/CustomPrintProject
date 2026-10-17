import * as THREE from '/vendor/three.module.js';
import { GLTFLoader } from '/vendor/addons/GLTFLoader.js';
const $ = s => document.querySelector(s), key = () => $('#key').value;
fetch('/api/products/custom-embossed-wristband').then(r => r.json()).then(p => $('#json').value = JSON.stringify(p, null, 2));

$('#glb').onchange = async e => {
  const f = e.target.files[0]; if (!f) return; $('#log').textContent = 'Uploading…';
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/models', { method: 'POST', headers: { 'x-admin-key': key() }, body: fd }), j = await r.json();
  if (!r.ok) return $('#log').textContent = j.detail || 'Upload failed';
  const gltf = await new GLTFLoader().loadAsync(j.url), meshes = [];
  gltf.scene.traverse(o => { if (o.isMesh) {
    const uv = o.geometry.attributes.uv, tris = (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
    meshes.push({ name: o.name || '(unnamed)', uv: !!uv, tris });
  }});
  $('#log').textContent = `Uploaded ${(j.bytes / 1048576).toFixed(1)} MB\n` + meshes.map(m => `• ${m.name}: ${m.tris} triangles, ${m.uv ? 'UVs ok' : 'NO UVs — cannot be printed on'}`).join('\n') +
    (meshes.reduce((a, m) => a + m.tris, 0) > 200000 ? '\n⚠ Very heavy model (>200k triangles): compress for mobile.' : '');
  const p = JSON.parse($('#json').value);
  p.model = { type: 'glb', url: j.url };
  p.sizes = []; p.body_meshes = meshes.map(m => m.name);
  p.zones = meshes.filter(m => m.uv && m.name !== '(unnamed)').slice(0, 4).map((m, i) => ({ id: 'zone' + (i + 1), label: 'Message ' + (i + 1), mesh: m.name, style: 'print', max_chars: 30, allow_images: true, u0: 0, u1: 1, aspect: 4 }));
  $('#json').value = JSON.stringify(p, null, 2);
};
// Sign-ups: shown as text only (textContent), because these values were typed by strangers.
$('#loadLeads').onclick = async () => {
  const r = await fetch('/api/leads', { headers: { 'x-admin-key': key() } });
  if (!r.ok) return $('#leadMsg').textContent = r.status === 401 ? 'Enter the admin key first.' : 'Could not load.';
  const rows = await r.json(), t = $('#leads'); t.textContent = '';
  $('#leadMsg').textContent = rows.length + ' sign-up(s)';
  const cols = ['created', 'business', 'name', 'phone', 'email', 'sells', 'website', 'city'];
  const add = (cells, tag) => { const tr = document.createElement('tr'); cells.forEach(v => { const c = document.createElement(tag); c.textContent = v || ''; c.style.cssText = 'border-bottom:1px solid #dcdfe4;padding:6px 8px;text-align:left;vertical-align:top'; tr.appendChild(c); }); t.appendChild(tr); };
  add(cols, 'th'); rows.forEach(r => add(cols.map(k => r[k]), 'td'));
};
$('#save').onclick = async () => {
  let p; try { p = JSON.parse($('#json').value); } catch (e) { return $('#res').textContent = 'Invalid JSON: ' + e.message; }
  const r = await fetch('/api/products/' + p.slug, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'x-admin-key': key() }, body: JSON.stringify(p) });
  const j = await r.json();
  if (!r.ok) return $('#res').textContent = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
  $('#res').textContent = ''; $('#open').href = '/?product=' + p.slug; $('#open').textContent = 'Saved — open product page';
};

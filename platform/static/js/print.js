// Print files for one saved design. The files are drawn in the browser with the same code that draws the 3D preview,
// so what is printed is exactly what the customer approved. Output: one transparent PNG per print area
// (plus a relief map for emboss / deboss), the customer's original pictures, and a design.json with the details.
import { $, esc, api, me, showErrors } from './api.js';
import { Customizer } from './customizer.js';
import { zipStore } from './zip.js';

const DPI = 300, MAX_PX = 6000, DEFAULT_PX = 2400;
const id = new URLSearchParams(location.search).get('design') || '';
const user = await me().catch(() => null);
if (!user) location.replace('/account.html');
else if (user.role === 'owner') location.replace('/owner.html');

const toBlob = cv => new Promise((ok, no) => cv.toBlob(b => b ? ok(b) : no(new Error('Could not make the picture')), 'image/png'));
const bytes = async blob => new Uint8Array(await blob.arrayBuffer());
const safe = s => String(s).replace(/[^a-z0-9_-]+/gi, '-').slice(0, 40) || 'area';

try {
  if (!/^[0-9a-f]{12}$/.test(id)) throw new Error('This page needs a design from the Designs list.');
  const d = await api(`/api/seller/designs/${id}`);
  if (!d.product_config) throw new Error('The product this design was made for has been deleted, so it cannot be redrawn.');
  const product = d.product_config, stickers = await (await fetch('/stickers.json')).json();
  const cz = new Customizer($('#stage'), product);
  if (cz.noGL) throw new Error('Your browser needs WebGL to draw print files. Try Chrome or Edge.');
  cz.stickers = Object.fromEntries(stickers.map(k => [k.id, k]));
  cz.fromDesign(d.design);
  await cz.load();

  const out = [];
  for (const z of product.zones) {
    const mm = z.print_w_mm && z.print_h_mm;
    const px = mm ? Math.min(MAX_PX, Math.round(z.print_w_mm / 25.4 * DPI)) : DEFAULT_PX;
    const r = await cz.renderZone(z, px);
    out.push({ z, r, mm, empty: !cz.state.zones[z.id].text && !cz.state.zones[z.id].image && !cz.state.zones[z.id].stickers.length });
  }

  $('#page').innerHTML = `<div class="head"><div><h1>${esc(d.product)}</h1>
      <p class="muted" style="margin:0">${d.text ? esc(d.text) + ' · ' : ''}${new Date(d.created_at).toLocaleString()}${d.ref ? ' · Order ' + esc(d.ref) : ''} · id ${esc(d.id)}</p></div>
      <button class="btn" id="dl">Download print files (.zip)</button></div>
    <div class="pgrid"><div><img class="shot" src="${esc(d.preview)}" alt="What the customer approved" id="shot"><p class="muted">What the customer approved.</p></div>
      <div>${out.map((o, i) => `<section class="card zfile"><h3>${esc(o.z.label)} <span class="pill">${esc(o.z.style === 'print' ? 'printed' : o.z.style === 'emboss' ? 'emboss' : 'deboss')}</span></h3>
        <div class="checker" id="zc${i}"></div>
        <p class="muted" style="margin:0">${o.r.width} &times; ${o.r.height} px${o.mm ? ` for ${o.z.print_w_mm} &times; ${o.z.print_h_mm} mm (${DPI} dpi)` : ''}${o.r.relief ? ' · with relief map' : ''}</p>
        ${o.mm ? '' : '<p class="notice" style="margin:0">The real size of this print area is not set, so the file is not tied to a print size. Set it in the product editor (Print areas) to get 300 dpi files.</p>'}
        ${o.empty ? '<p class="notice" style="margin:0">The customer put nothing in this area.</p>' : ''}</section>`).join('')}</div></div>`;
  out.forEach((o, i) => $('#zc' + i).appendChild(o.r.color));
  $('#shot').addEventListener('error', e => { e.target.style.visibility = 'hidden'; });

  $('#dl').onclick = async e => {
    const btn = e.target; btn.disabled = true; btn.textContent = 'Preparing…';
    try {
      const files = [], info = [];
      for (const o of out) {
        const base = safe(o.z.id);
        files.push({ name: `${base}.png`, data: await bytes(await toBlob(o.r.color)) });
        if (o.r.relief) files.push({ name: `${base}-relief.png`, data: await bytes(await toBlob(o.r.relief)) });
        info.push({ id: o.z.id, label: o.z.label, style: o.z.style, file: `${base}.png`, relief_file: o.r.relief ? `${base}-relief.png` : null,
                    pixels: [o.r.width, o.r.height], size_mm: o.mm ? [o.z.print_w_mm, o.z.print_h_mm] : null, dpi: o.mm ? DPI : null,
                    layers: d.design.layers.filter(l => l.zone === o.z.id).map(l => l.type === 'image' ? { ...l, url: undefined, original: `originals/${(l.url || '').split('/').pop()}` } : l) });
      }
      for (const l of d.design.layers.filter(l => l.type === 'image' && l.url)) {
        const r = await fetch(l.url);
        if (r.ok) files.push({ name: `originals/${l.url.split('/').pop()}`, data: new Uint8Array(await r.arrayBuffer()) });
      }
      const pv = await fetch(d.preview).catch(() => null);
      if (pv && pv.ok) files.push({ name: 'preview.png', data: new Uint8Array(await pv.arrayBuffer()) });
      files.push({ name: 'design.json', data: new TextEncoder().encode(JSON.stringify({
        design_id: d.id, product: d.product, created_at: d.created_at, order_reference: d.ref || null, product_colour: d.design.body_color,
        text_colour: d.design.imprint_color || null, size: d.design.size, areas: info }, null, 2)) });
      files.push({ name: 'README.txt', data: new TextEncoder().encode(
        'Print files for design ' + d.id + '\r\n\r\nEach .png is one print area on a transparent background: exactly what is printed, without the product colour.\r\n' +
        '*-relief.png is a grey height map for emboss / deboss areas (white = raised for emboss, black = cut for deboss).\r\n' +
        'originals/ holds the customer\'s own pictures, unchanged. design.json lists sizes, text, fonts and positions.\r\n') });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(zipStore(files)); a.download = `design-${d.id}.zip`; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
      await api(`/api/seller/designs/${d.id}/exported`, { method: 'POST' }).catch(() => {});
      btn.textContent = 'Downloaded. Download again';
    } catch (x) { showErrors($('#err'), x); btn.textContent = 'Download print files (.zip)'; }
    btn.disabled = false;
  };
} catch (x) {
  $('#page').innerHTML = '';
  showErrors($('#err'), x);
}

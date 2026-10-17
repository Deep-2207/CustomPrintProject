import { $, $$, esc, api, me, showErrors, clearErrors, slugify } from './api.js';

const FONTS = ['Arial', 'Impact', 'Georgia', 'Courier New', 'Trebuchet MS'];   // same list the server allows
const PRINT_STYLES = [['print', 'Print (flat colour)'], ['emboss', 'Emboss (raised)'], ['deboss', 'Deboss (engraved)']];

const textStyles = await (await fetch('/text-styles.json')).json();
const view = $('#view');
let user, tenant, active, canEdit;

// Who is logged in and what their shop may do. Checked again on every page change, so an approval
// (or suspension) takes effect without reloading the page.
async function refreshUser() {
  const u = await me().catch(() => null);
  if (!u || u.role === 'owner') { location.replace(u ? '/owner.html' : '/account.html'); throw new Error('redirecting'); }
  user = u; tenant = u.tenant; active = tenant.status === 'active'; canEdit = active && u.role === 'seller_admin';
  $('#who-shop').textContent = tenant.name;
  $('#who-name').textContent = user.name;
  $('#banner').innerHTML = tenant.status === 'pending'
    ? '<div class="banner pending"><b>Your account is waiting for approval.</b> You can look around now. Creating products unlocks as soon as our team approves your shop.</div>'
    : tenant.status === 'suspended' ? '<div class="banner bad"><b>Your account is suspended.</b> Please contact us.</div>' : '';
}
$('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); location.href = '/account.html'; };

const shareUrl = slug => `${location.origin}/s/${tenant.slug}/${slug}`;
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 2600); }
async function copy(text) { try { await navigator.clipboard.writeText(text); toast('Link copied'); } catch { toast('Copy failed. Select the link and copy it yourself.'); } }
const num = (v, d) => { const n = Number(v); return Number.isFinite(n) ? n : d; };

// ------------------------------------------------------------------ routing
async function route() {
  try { await refreshUser(); } catch { return; }
  const [page, arg] = (location.hash.replace(/^#\/?/, '') || 'products').split('/');
  $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === (page === 'new' || page === 'product' ? 'products' : page)));
  view.onclick = view.oninput = view.onchange = null;
  view.innerHTML = '<p class="muted">Loading…</p>';
  const pages = { products: viewProducts, new: viewNew, models: viewModels, designs: viewDesigns, embed: viewEmbed, usage: viewUsage, account: viewAccount, product: () => viewProduct(Number(arg)) };
  try { await (pages[page] || viewProducts)(); }
  catch (e) { view.innerHTML = `<div class="errs">${esc(e.message)}</div><p><a href="#/products">Back to products</a></p>`; }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);

// ------------------------------------------------------------------ products list
async function viewProducts() {
  const list = await api('/api/seller/products');
  view.innerHTML = `<div class="head"><div><h1>Products</h1><p class="muted">Each product has its own link you can share with customers.</p></div>
    ${canEdit ? '<a class="btn" href="#/new">New product</a>' : ''}</div>
    ${list.length ? `<div class="grid">${list.map(p => `<article class="card pc"><div class="row" style="justify-content:space-between"><h3>${esc(p.name)}</h3>
      <span class="pill ${p.published ? 'on' : ''}">${p.published ? 'Published' : 'Draft'}</span></div>
      <div class="url">${esc(shareUrl(p.slug))}</div>
      <p class="muted" style="margin:0 0 12px">${p.zones} print area${p.zones === 1 ? '' : 's'}${p.zones ? '' : ' (add one before publishing)'}</p>
      <div class="row"><a class="btn sm" href="#/product/${p.id}">${canEdit ? 'Edit' : 'View'}</a>
        <a class="btn sm ghost" href="/s/${esc(tenant.slug)}/${esc(p.slug)}" target="_blank" rel="noopener">Preview</a>
        <button class="btn sm ghost" data-copy="${esc(p.slug)}" ${p.published ? '' : 'disabled title="Publish the product to share its link"'}>Copy link</button></div></article>`).join('')}</div>`
      : `<div class="card"><h2>No products yet</h2><p class="muted">Start from a ready-made mug or wristband, or use your own 3D model.</p>${canEdit ? '<a class="btn" href="#/new">Create your first product</a>' : ''}</div>`}`;
  view.onclick = e => { const b = e.target.closest('[data-copy]'); if (b && !b.disabled) copy(shareUrl(b.dataset.copy)); };
}

// ------------------------------------------------------------------ new product
async function viewNew() {
  const [tpls, models] = await Promise.all([api('/api/seller/templates'), api('/api/seller/models')]);
  const usable = models.filter(m => m.report.valid);
  view.innerHTML = `<div class="head"><div><h1>New product</h1><p class="muted">Start from a ready-made shape, or use your own 3D model.</p></div></div>
    <form id="np" class="card" novalidate>
      <h2>1. Choose a starting point</h2>
      ${tpls.map((t, i) => `<label class="opt"><input type="radio" name="src" value="t:${esc(t.slug)}" ${i === 0 ? 'checked' : ''}><span><b>${esc(t.name)}</b><span class="muted">Ready-made shape with its print areas already set.</span></span></label>`).join('')}
      ${usable.map(m => `<label class="opt"><input type="radio" name="src" value="m:${m.id}"><span><b>My 3D model: ${esc(m.name)}</b><span class="muted">${m.report.meshes.length} part(s), ${m.report.total_triangles.toLocaleString()} triangles. You mark the print areas next.</span></span></label>`).join('')}
      <p class="muted">To use a different 3D model, <a href="#/models">upload it first</a>.</p>
      <h2 style="margin-top:18px">2. Name it</h2>
      <div class="two"><div class="f"><label for="np-name">Product name</label><input id="np-name" type="text" maxlength="120" required placeholder="e.g. Photo mug"></div>
        <div class="f"><label for="np-slug">Link name</label><input id="np-slug" type="text" maxlength="60" pattern="[a-z0-9\\-]{2,60}" required>
        <small>Customers open ${esc(location.origin)}/s/${esc(tenant.slug)}/<b id="slugv">…</b></small></div></div>
      <div class="errs" id="np-err" role="alert" hidden></div>
      <div class="row"><button class="btn" type="submit" ${canEdit ? '' : 'disabled'}>Create product</button><a class="btn ghost" href="#/products">Cancel</a></div>
      ${canEdit ? '' : '<p class="muted">Creating products is available once your account is approved.</p>'}
    </form>`;
  let edited = false;
  const sync = () => { $('#slugv').textContent = $('#np-slug').value || '…'; };
  view.oninput = e => {
    if (e.target.id === 'np-slug') edited = true;
    if (e.target.id === 'np-name' && !edited) $('#np-slug').value = slugify($('#np-name').value, 60);
    sync();
  };
  view.onsubmit = async e => {
    e.preventDefault();
    const err = $('#np-err'); clearErrors(err);
    const [kind, ref] = (new FormData($('#np')).get('src') || '').split(':');
    const body = { name: $('#np-name').value.trim(), slug: $('#np-slug').value.trim() };
    if (kind === 't') body.template = ref; else body.model_id = Number(ref);
    try { const p = await api('/api/seller/products', { method: 'POST', json: body }); location.hash = `#/product/${p.id}`; }
    catch (x) { showErrors(err, x); }
  };
}

// ------------------------------------------------------------------ 3D models
function reportHtml(r) {
  return `<p class="muted" style="margin:6px 0">${(r.bytes / 1048576).toFixed(1)} MB, ${r.total_triangles.toLocaleString()} triangles, ${r.meshes.length} part(s)</p>
    <table class="t"><thead><tr><th>Part name</th><th>Triangles</th><th>Can be printed on</th></tr></thead><tbody>
    ${r.meshes.map(m => `<tr><td>${esc(m.name)}</td><td>${m.triangles.toLocaleString()}</td><td>${m.has_uv ? '<span class="ok">Yes</span>' : '<span class="no">No (no UV map)</span>'}</td></tr>`).join('')}</tbody></table>
    ${r.warnings.length ? `<ul class="muted" style="margin:10px 0 0;padding-left:18px">${r.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}`;
}

async function viewModels() {
  const models = await api('/api/seller/models');
  view.innerHTML = `<div class="head"><div><h1>3D models</h1><p class="muted">Upload a .glb file of your product. We check it and tell you which parts can be printed on.</p></div></div>
    <form id="up" class="card upload"><label for="file"><b>Choose a .glb file</b> (up to 25 MB)</label>
      <input id="file" type="file" accept=".glb,model/gltf-binary" ${canEdit ? '' : 'disabled'}>
      <div class="errs" id="up-err" role="alert" hidden></div><p class="muted" id="up-status" style="margin:8px 0 0"></p></form>
    ${models.length ? models.map(m => `<section class="card"><div class="row" style="justify-content:space-between"><h3>${esc(m.name)}</h3>
        ${m.report.warnings.length ? '<span class="pill warn">Has warnings</span>' : '<span class="pill on">Looks good</span>'}</div>${reportHtml(m.report)}
        <p style="margin:12px 0 0"><a class="btn sm" href="#/new">Use for a product</a></p></section>`).join('') : '<p class="muted">No models uploaded yet.</p>'}`;
  view.onchange = async e => {
    if (e.target.id !== 'file' || !e.target.files[0]) return;
    const err = $('#up-err'); clearErrors(err); $('#up-status').textContent = 'Uploading and checking…';
    const fd = new FormData(); fd.append('file', e.target.files[0]);
    try { await api('/api/seller/models', { method: 'POST', form: fd }); toast('Model uploaded'); await viewModels(); }
    catch (x) { $('#up-status').textContent = ''; showErrors(err, x); e.target.value = ''; }
  };
}

// ------------------------------------------------------------------ designs customers saved
const fmtDate = iso => new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const SOURCES = { share: 'Share link', embed: 'Your website', preview: 'Your own test' };

async function viewDesigns() {
  const products = await api('/api/seller/products');
  const f = { q: '', product: '', page: 1 };
  view.innerHTML = `<div class="head"><div><h1>Designs</h1><p class="muted">Every design a customer saved. Open one to download the print files.</p></div></div>
    <div class="card filters"><div class="f grow"><label for="d-q">Search</label><input id="d-q" type="search" maxlength="80" placeholder="Name, message, order reference or design id"></div>
      <div class="f"><label for="d-p">Product</label><select id="d-p"><option value="">All products</option>${products.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div></div>
    <div id="d-list"></div><div id="d-pager" class="row" style="margin-top:12px"></div>`;
  async function load() {
    const r = await api(`/api/seller/designs?page=${f.page}&q=${encodeURIComponent(f.q)}${f.product ? '&product_id=' + f.product : ''}`);
    $('#d-list').innerHTML = r.designs.length ? `<div class="dgrid">${r.designs.map(d => `<article class="card dc">
        <img src="${esc(d.preview)}" alt="Preview of design ${esc(d.id)}" loading="lazy" width="320" height="200">
        <div class="dc-body"><div class="row" style="justify-content:space-between"><b>${esc(d.product)}</b><span class="pill ${d.source === 'embed' ? 'on' : ''}">${esc(SOURCES[d.source] || d.source)}</span></div>
          <p class="dtext">${d.text ? esc(d.text) : '<span class="muted">No text (picture or stickers only)</span>'}</p>
          <p class="muted" style="margin:0 0 4px">${esc(fmtDate(d.created_at))}${d.ref ? ' · Order ' + esc(d.ref) : ''}</p>
          <p class="muted" style="margin:0 0 10px">${d.images} picture(s), ${d.stickers} sticker(s) · id ${esc(d.id)}</p>
          <div class="row"><a class="btn sm" href="/print.html?design=${esc(d.id)}">Print files</a>
            <a class="btn sm ghost" href="/s/${esc(tenant.slug)}/${esc(d.product_slug)}?design=${esc(d.id)}" target="_blank" rel="noopener">Open</a></div></div></article>`).join('')}</div>`
      : `<div class="card"><p class="muted" style="margin:0">${f.q || f.product ? 'No designs match.' : 'No designs yet. They appear here when a customer saves one from your link or your website.'}</p></div>`;
    const pages = Math.max(1, Math.ceil(r.total / r.per_page));
    $('#d-pager').innerHTML = r.total ? `<button class="btn sm ghost" data-pg="-1" ${f.page <= 1 ? 'disabled' : ''}>Previous</button><span class="muted">Page ${f.page} of ${pages} · ${r.total} design(s)</span><button class="btn sm ghost" data-pg="1" ${f.page >= pages ? 'disabled' : ''}>Next</button>` : '';
  }
  let timer;
  view.oninput = e => { if (e.target.id === 'd-q') { clearTimeout(timer); timer = setTimeout(() => { f.q = e.target.value.trim(); f.page = 1; load().catch(x => toast(x.message)); }, 250); } };
  view.onchange = e => { if (e.target.id === 'd-p') { f.product = e.target.value; f.page = 1; load().catch(x => toast(x.message)); } };
  view.onclick = e => { const b = e.target.closest('[data-pg]'); if (b && !b.disabled) { f.page += Number(b.dataset.pg); load().catch(x => toast(x.message)); } };
  view.addEventListener('error', e => { if (e.target.tagName === 'IMG') { e.target.style.visibility = 'hidden'; } }, true);
  await load();
}

// ------------------------------------------------------------------ embed on your own website
async function viewEmbed() {
  const [st, products] = await Promise.all([api('/api/seller/settings'), api('/api/seller/products')]);
  const live = products.filter(p => p.published);
  let newSecret = '';
  const origin = location.origin;
  const snippet = () => {
    const p = $('#sn-p') ? $('#sn-p').value : (live[0] || {}).slug || 'your-product', btn = $('#sn-b') ? $('#sn-b').value.trim() : '';
    return `<div data-pp-product="${p}" data-pp-key="${st.public_key}"${btn ? ` data-pp-button="${btn.replace(/"/g, '')}"` : ''} data-pp-input="#design_id"></div>\n<script src="${origin}/embed.js" async><\/script>`;
  };
  function render() {
    view.innerHTML = `<div class="head"><div><h1>Embed on your website</h1><p class="muted">Show the customizer inside your own online shop, and get the design id back to attach to the order.</p></div></div>
      <section class="card"><h2>1. Allow your website</h2>
        <p class="muted" style="margin-top:0">Only websites on this list can show your customizer. One per line, for example <b>shop.example.com</b> or <b>*.example.com</b> (every subdomain). For testing on your computer add <b>localhost:3000</b>.</p>
        <div class="errs" id="dm-err" role="alert" hidden></div>
        <textarea id="dm" rows="4" maxlength="800" aria-label="Allowed websites" ${canEdit ? '' : 'disabled'}>${esc(st.allowed_domains.join('\n'))}</textarea>
        <div class="row" style="margin-top:8px"><button class="btn" data-act="save-domains" ${canEdit ? '' : 'disabled'}>Save websites</button>
          <span class="muted">${st.allowed_domains.length ? `${st.allowed_domains.length} website(s) allowed` : 'No website allowed yet: the embed will be blocked everywhere.'}</span></div></section>
      <section class="card"><h2>2. Copy the code into your page</h2>
        ${live.length ? `<div class="two"><div class="f"><label for="sn-p">Product</label><select id="sn-p">${live.map(p => `<option value="${esc(p.slug)}">${esc(p.name)}</option>`).join('')}</select></div>
          <div class="f"><label for="sn-b">Button text (optional)</label><input id="sn-b" type="text" maxlength="40" placeholder="Add to my order"></div></div>
          <pre class="code" id="sn-code" tabindex="0">${esc(snippet())}</pre>
          <div class="row"><button class="btn sm" data-act="copy-snippet">Copy code</button><span class="muted">Your public key <code>${esc(st.public_key)}</code> is not a secret.</span></div>
          <p class="muted">Add <code>&lt;input type="hidden" id="design_id" name="design_id"&gt;</code> inside your order form: it receives the design id when the customer saves.
            To react in code, listen on the page: <code>document.addEventListener('previewprint:design', e =&gt; console.log(e.detail.designId, e.detail.previewUrl))</code>.</p>`
          : '<p class="muted">Publish a product first. Then its embed code appears here.</p>'}</section>
      <section class="card"><h2>3. API keys for your server</h2>
        <p class="muted" style="margin-top:0">Secret keys let <b>your server</b> read designs (for example to show the preview on an order). Never put a secret key in a web page.</p>
        ${newSecret ? `<div class="secret"><b>Your new secret key. Copy it now: it is shown only once.</b><pre class="code" id="new-secret">${esc(newSecret)}</pre><button class="btn sm" data-act="copy-secret">Copy key</button></div>` : ''}
        ${st.secret_keys.length ? `<table class="t"><thead><tr><th>Key</th><th>Created</th><th>Last used</th><th></th></tr></thead><tbody>${st.secret_keys.map(k => `<tr><td><code>${esc(k.prefix)}…</code></td><td>${esc(fmtDate(k.created_at))}</td><td>${k.last_used_at ? esc(fmtDate(k.last_used_at)) : 'never'}</td>
          <td><button class="btn sm danger" data-act="revoke" data-id="${k.id}" ${canEdit ? '' : 'disabled'}>Revoke</button></td></tr>`).join('')}</tbody></table>` : '<p class="muted">No secret keys yet.</p>'}
        <div class="row" style="margin-top:10px"><button class="btn sm" data-act="new-secret" ${canEdit && st.secret_keys.length < st.max_secret_keys ? '' : 'disabled'}>Create a secret key</button>
          <button class="btn sm ghost" data-act="rotate" ${canEdit ? '' : 'disabled'}>Replace public key</button></div>
        <details style="margin-top:12px"><summary>How to use a secret key</summary><pre class="code" tabindex="0">curl ${esc(origin)}/api/v1/designs?limit=5 \\\n  -H "Authorization: Bearer sk_..."\n\n# one design (includes the full layers)\ncurl ${esc(origin)}/api/v1/designs/DESIGN_ID -H "Authorization: Bearer sk_..."\n\n# designs for one of your orders (the data-pp-ref you passed)\ncurl "${esc(origin)}/api/v1/designs?ref=ORDER-1042" -H "Authorization: Bearer sk_..."</pre></details></section>`;
    if (!canEdit) $$('input,select,textarea', view).forEach(el => { if (el.id !== 'sn-p' && el.id !== 'sn-b') el.disabled = true; });
  }
  render();
  view.oninput = view.onchange = e => { if (e.target.id === 'sn-p' || e.target.id === 'sn-b') $('#sn-code').textContent = snippet(); };
  view.onclick = async e => {
    const b = e.target.closest('[data-act]'); if (!b || b.disabled) return;
    const act = b.dataset.act;
    try {
      if (act === 'copy-snippet') return copy($('#sn-code').textContent);
      if (act === 'copy-secret') return copy(newSecret);
      if (act === 'save-domains') {
        clearErrors($('#dm-err'));
        Object.assign(st, await api('/api/seller/settings/domains', { method: 'PUT', json: { domains: $('#dm').value.split('\n').map(x => x.trim()).filter(Boolean) } }));
        toast('Websites saved'); render();
      } else if (act === 'new-secret') {
        const r = await api('/api/seller/keys', { method: 'POST', json: { kind: 'secret' } }); newSecret = r.new_secret; Object.assign(st, r); render();
      } else if (act === 'revoke') {
        if (!confirm('Revoke this key? Anything using it stops working immediately.')) return;
        Object.assign(st, await api(`/api/seller/keys/${b.dataset.id}`, { method: 'DELETE' })); toast('Key revoked'); render();
      } else if (act === 'rotate') {
        if (!confirm('Replace the public key? Every embed on your websites must be updated with the new code.')) return;
        Object.assign(st, await api('/api/seller/keys', { method: 'POST', json: { kind: 'public' } })); toast('New public key. Update your embed code.'); render();
      }
    } catch (x) { if ($('#dm-err') && act === 'save-domains') showErrors($('#dm-err'), x); else toast(x.message); }
  };
}

// ------------------------------------------------------------------ usage and plan
const rupees = n => '₹' + Number(n).toLocaleString('en-IN');
async function viewUsage(month) {
  const u = await api('/api/seller/usage' + (month ? `?month=${month}` : ''));
  const months = []; { const d = new Date(); for (let i = 0; i < 6; i++) { const m = new Date(d.getFullYear(), d.getMonth() - i, 1); months.push(`${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}`); } }
  const inv = u.invoice, days = Object.keys(u.days).sort(), max = Math.max(1, ...days.map(d => u.days[d].design || 0));
  const pct = Math.min(100, Math.round(inv.designs / Math.max(1, inv.included) * 100));
  view.innerHTML = `<div class="head"><div><h1>Usage and plan</h1><p class="muted">What your customers did, and what it costs. Days are counted in India time.</p></div>
      <div class="f" style="min-width:150px"><label for="u-m">Month</label><select id="u-m">${months.map(m => `<option ${m === u.month ? 'selected' : ''}>${m}</option>`).join('')}</select></div></div>
    <div class="stats"><div class="card stat"><b>${inv.designs}</b><span>designs saved</span></div><div class="card stat"><b>${inv.views}</b><span>times a customer opened a product</span></div>
      <div class="card stat"><b>${inv.exports}</b><span>print-file downloads</span></div></div>
    <section class="card"><h2>Your plan: ${esc(inv.plan_label)}</h2>
      <p class="muted" style="margin-top:0">${rupees(inv.monthly_fee)} a month, ${inv.included} designs included${inv.overage_rate ? `, then ${rupees(inv.overage_rate)} for each extra design` : ''}.</p>
      <div class="meter" role="img" aria-label="${inv.designs} of ${inv.included} included designs used"><span style="width:${pct}%"></span></div>
      <p class="muted">${inv.designs} of ${inv.included} included designs used${inv.extra_designs ? `. <b>${inv.extra_designs} extra</b> this month.` : '.'}</p>
      <table class="t"><tbody><tr><td>Monthly fee</td><td class="num">${rupees(inv.monthly_fee)}</td></tr>
        <tr><td>Extra designs (${inv.extra_designs} × ${rupees(inv.overage_rate)})</td><td class="num">${rupees(inv.extra_amount)}</td></tr>
        ${inv.setup_fee ? `<tr><td>One-time setup fee</td><td class="num">${rupees(inv.setup_fee)}</td></tr>` : ''}
        <tr><td>GST ${inv.gst_percent}%</td><td class="num">${rupees(inv.gst)}</td></tr>
        <tr><td><b>Estimated total</b></td><td class="num"><b>${rupees(inv.total)}</b></td></tr></tbody></table>
      <p class="muted">To change plan, contact us. ${canEdit ? `<a href="/api/seller/invoice.csv?month=${u.month}">Download this month as CSV</a>` : ''}</p></section>
    <section class="card"><h2>Designs per day</h2>${days.length ? `<div class="bars" role="img" aria-label="Designs saved per day">${days.map(d => { const n = u.days[d].design || 0; return `<div class="bar" title="${d}: ${n} design(s)"><span style="height:${Math.round(n / max * 100)}%"></span><small>${Number(d.slice(8))}</small></div>`; }).join('')}</div>` : '<p class="muted">Nothing yet this month.</p>'}</section>`;
  view.onchange = e => { if (e.target.id === 'u-m') viewUsage(e.target.value).catch(x => toast(x.message)); };
}

// ------------------------------------------------------------------ account
async function viewAccount() {
  view.innerHTML = `<div class="head"><div><h1>Account</h1></div></div>
    <section class="card"><h2>You</h2><p style="margin:0">${esc(user.name)}<br><span class="muted">${esc(user.email)} · ${user.role === 'seller_admin' ? 'shop admin' : 'staff'} at ${esc(tenant.name)}</span></p></section>
    <form class="card" id="pw" novalidate><h2>Change password</h2><div class="errs" id="pw-err" role="alert" hidden></div>
      <div class="f"><label for="pw-c">Current password</label><input id="pw-c" type="password" autocomplete="current-password" maxlength="200" required></div>
      <div class="f"><label for="pw-n">New password</label><input id="pw-n" type="password" autocomplete="new-password" maxlength="200" required><small>At least 10 characters. A few random words work well.</small></div>
      <button class="btn" type="submit">Change password</button><p class="muted">You stay logged in here; other devices are logged out.</p></form>`;
  view.onsubmit = async e => {
    e.preventDefault(); const err = $('#pw-err'); clearErrors(err);
    try { await api('/api/auth/password', { method: 'POST', json: { current: $('#pw-c').value, new: $('#pw-n').value } }); $('#pw-c').value = $('#pw-n').value = ''; toast('Password changed'); }
    catch (x) { showErrors(err, x); }
  };
}

// ------------------------------------------------------------------ product editor
async function viewProduct(id) {
  const p = await api(`/api/seller/products/${id}`);
  const draft = structuredClone(p.config);
  const isGlb = (draft.model || {}).type === 'glb';
  const off = canEdit ? '' : 'disabled';

  const colRows = (key, list) => list.map((c, i) => `<div class="colrow">
      ${c.hex || key === 'colors' ? `<input type="color" value="${esc(c.hex || '#000000')}" data-list="${key}" data-i="${i}" data-k="hex" aria-label="Colour">` : '<span class="muted" title="No colour: the text style picks one">auto</span>'}
      <input type="text" value="${esc(c.name)}" maxlength="30" data-list="${key}" data-i="${i}" data-k="name" aria-label="Colour name">
      <button class="x" type="button" data-act="del-${key}" data-i="${i}" aria-label="Remove ${esc(c.name)}">&times;</button></div>`).join('');

  const zoneCards = draft.zones.map((z, i) => `<div class="zone"><div class="row" style="justify-content:space-between"><h3>${esc(z.label)}</h3>
      <button class="btn sm danger" type="button" data-act="del-zone" data-i="${i}">Remove</button></div>
      <div class="three"><div class="f"><label>Name</label><input type="text" maxlength="60" value="${esc(z.label)}" data-z="${i}" data-k="label"></div>
        <div class="f"><label>Max letters</label><input type="number" min="1" max="500" value="${z.max_chars}" data-z="${i}" data-k="max_chars"></div>
        <div class="f"><label>Max lines</label><input type="number" min="1" max="10" value="${z.max_lines || 1}" data-z="${i}" data-k="max_lines"></div></div>
      <div class="f"><label>How it is made</label><select data-z="${i}" data-k="style">${PRINT_STYLES.map(([v, t]) => `<option value="${v}" ${z.style === v ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
      <div class="two"><div class="f"><label>Real width (mm)</label><input type="number" min="0" max="2000" step="0.5" value="${z.print_w_mm || ''}" placeholder="e.g. 90" data-z="${i}" data-k="print_w_mm"></div>
        <div class="f"><label>Real height (mm)</label><input type="number" min="0" max="2000" step="0.5" value="${z.print_h_mm || ''}" placeholder="e.g. 80" data-z="${i}" data-k="print_h_mm"></div></div>
      <p class="muted" style="margin:-6px 0 10px;font-size:13px">The size of the printed area on the real product. It makes print files exactly 300 dpi. Leave empty if you do not know yet.</p>
      <div class="opts"><label><input type="checkbox" data-z="${i}" data-k="allow_images" ${z.allow_images ? 'checked' : ''}> Customers can add a logo or photo</label>
        <label><input type="checkbox" data-z="${i}" data-k="allow_stickers" ${z.allow_stickers !== false ? 'checked' : ''}> Customers can add stickers</label>
        <label><input type="checkbox" data-z="${i}" data-k="guide" ${z.guide ? 'checked' : ''}> Show a dashed outline of the area</label></div>
      <p class="muted" style="margin:0">Position: ${Math.round(z.u0 * 100)}% to ${Math.round(z.u1 * 100)}% across, ${Math.round(z.y0 * 100)}% to ${Math.round(z.y1 * 100)}% down, on part <b>${esc(z.mesh)}</b>.</p></div>`).join('');

  function render() {
    view.innerHTML = `<div class="head"><div><h1>${esc(draft.name)}</h1><p class="muted"><a href="#/products">&larr; All products</a></p></div>
      <div class="row"><span class="pill ${p.published ? 'on' : ''}" id="state">${p.published ? 'Published' : 'Draft'}</span>
        <button class="btn ghost" type="button" data-act="publish" ${off}>${p.published ? 'Unpublish' : 'Publish'}</button>
        <button class="btn" type="button" data-act="save" ${off}>Save changes</button></div></div>
      <div class="errs" id="ed-err" role="alert" hidden></div>
      <div class="editor"><div>
        <section class="card"><h2>Basics</h2><div class="f"><label for="e-name">Product name</label><input id="e-name" type="text" maxlength="120" value="${esc(draft.name)}" data-f="name"></div>
          <div class="f"><label>Customer link</label><div class="row"><input type="text" readonly value="${esc(shareUrl(p.slug))}" style="flex:1;min-width:220px" aria-label="Customer link">
          <button class="btn sm ghost" type="button" data-act="copy">Copy</button></div><small>${p.published ? 'Anyone with this link can customise the product.' : 'Only you can see this until you publish.'}</small></div></section>
        <section class="card"><h2>Print areas</h2>
          ${zoneCards || '<p class="muted">No print areas yet. Customers need at least one before you can publish.</p>'}
          <a class="btn ${draft.zones.length ? 'ghost' : ''}" href="/zone-editor.html?product=${id}">${draft.zones.length ? 'Move or add print areas on the 3D model' : 'Mark print areas on the 3D model'}</a>
          ${isGlb && p.model_report ? `<details style="margin-top:12px"><summary>About your 3D model: ${esc(p.model_name || '')}</summary>${reportHtml(p.model_report)}</details>` : ''}</section>
        <section class="card"><h2>Product colours</h2>${colRows('colors', draft.colors)}<button class="btn sm ghost" type="button" data-act="add-colors">Add colour</button></section>
        <section class="card"><h2>Text colours</h2><p class="muted" style="margin-top:0">Colours customers can choose for their text. "auto" lets the text style choose.</p>${colRows('imprint_colors', draft.imprint_colors)}<button class="btn sm ghost" type="button" data-act="add-imprint_colors">Add colour</button></section>
        <section class="card"><h2>Fonts</h2>${FONTS.map(f => `<label class="fontopt" style="font-family:'${f}'"><input type="checkbox" data-font="${f}" ${draft.fonts.includes(f) ? 'checked' : ''}> ${f}</label>`).join('')}</section>
        <section class="card"><h2>What customers see first</h2><div class="two">
          <div class="f"><label>Starting colour</label><select data-f="defaults.bodyColor">${draft.colors.map(c => `<option value="${esc(c.hex)}" ${(draft.defaults || {}).bodyColor === c.hex ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></div>
          <div class="f"><label>Starting text style</label><select data-f="defaults.tpl">${textStyles.map(t => `<option value="${t.id}" ${(draft.defaults || {}).tpl === t.id ? 'selected' : ''}>${esc(t.label)}</option>`).join('')}</select></div>
          <div class="f"><label>Starting font</label><select data-f="defaults.font">${draft.fonts.map(f => `<option ${(draft.defaults || {}).font === f ? 'selected' : ''}>${f}</option>`).join('')}</select></div>
          <div class="f"><label>Starting text size: <span id="ts">${Math.round(((draft.defaults || {}).textSize || .45) * 100)}%</span></label><input type="range" min="20" max="80" value="${Math.round(((draft.defaults || {}).textSize || .45) * 100)}" data-f="defaults.textSize"></div></div>
          <div class="f"><label for="e-ph">Hint inside the empty message box</label><input id="e-ph" type="text" maxlength="100" value="${esc(draft.placeholder || '')}" data-f="placeholder"></div>
          <div class="f"><label for="e-sample">Sample text shown in the style previews</label><textarea id="e-sample" rows="2" maxlength="100" data-f="sample">${esc(draft.sample || '')}</textarea><small>Used until the customer types. Press Enter for a second line.</small></div></section>
        <section class="card"><h2>Price</h2><div class="f" style="max-width:240px"><label for="e-price">Price per item (INR)</label><input id="e-price" type="number" min="0" step="1" value="${(draft.price || {}).base ?? 0}" data-f="price.base"><small>Shown for your reference; checkout stays on your own shop.</small></div></section>
      </div>
      <aside class="preview"><h2>Preview</h2>
        ${draft.zones.length ? `<iframe title="Product preview" src="/s/${esc(tenant.slug)}/${esc(p.slug)}?t=${Date.now()}"></iframe><p class="muted" style="margin:6px 0 0">Shows the last saved version.</p>`
          : '<div class="card muted">Add a print area to see the preview.</div>'}</aside></div>`;
    if (!canEdit) $$('input,select,textarea', view).forEach(el => { if (!el.readOnly) el.disabled = true; });
  }
  render();

  const setPath = (obj, path, value) => { const k = path.split('.'); const last = k.pop(); k.reduce((o, x) => (o[x] ??= {}), obj)[last] = value; };
  view.oninput = view.onchange = e => {
    const t = e.target;
    if (t.dataset.f) {
      let v = t.value;
      if (t.dataset.f === 'defaults.textSize') { v = num(v, 45) / 100; $('#ts').textContent = Math.round(v * 100) + '%'; }
      if (t.dataset.f === 'price.base') v = num(v, 0);
      setPath(draft, t.dataset.f, v);
    } else if (t.dataset.list) {
      const row = draft[t.dataset.list][+t.dataset.i], old = row.hex;
      row[t.dataset.k] = t.value;
      if (t.dataset.k === 'hex' && t.dataset.list === 'colors' && (draft.defaults || {}).bodyColor === old) draft.defaults.bodyColor = t.value;   // keep the starting colour in step
    } else if (t.dataset.font) {
      draft.fonts = FONTS.filter(f => f === t.dataset.font ? t.checked : draft.fonts.includes(f));
      if (!draft.fonts.includes((draft.defaults || {}).font)) delete (draft.defaults || {}).font;
    } else if (t.dataset.z !== undefined) {
      const z = draft.zones[+t.dataset.z], k = t.dataset.k;
      z[k] = t.type === 'checkbox' ? t.checked : (k === 'max_chars' || k === 'max_lines') ? num(t.value, 1) : (k === 'print_w_mm' || k === 'print_h_mm') ? num(t.value, 0) : t.value;
    }
    if (e.type === 'change' && t.dataset.font) render();
  };

  view.onclick = async e => {
    const b = e.target.closest('[data-act]'); if (!b) return;
    const act = b.dataset.act, i = +b.dataset.i, err = $('#ed-err');
    if (act === 'copy') return copy(shareUrl(p.slug));
    if (act.startsWith('add-')) { const key = act.slice(4); draft[key].push({ name: 'New colour', hex: key === 'colors' ? '#888888' : '#222222' }); return render(); }
    if (act.startsWith('del-') && act !== 'del-zone') { draft[act.slice(4)].splice(i, 1); return render(); }
    if (act === 'del-zone') { draft.zones.splice(i, 1); return render(); }
    clearErrors(err);
    try {
      if (act === 'save') {
        const body = { name: draft.name, sizes: draft.sizes || [], colors: draft.colors, imprint_colors: draft.imprint_colors, fonts: draft.fonts,
                       zones: draft.zones, defaults: draft.defaults || {}, sample: draft.sample || '', placeholder: draft.placeholder || '', price: draft.price || {} };
        const saved = await api(`/api/seller/products/${id}`, { method: 'PUT', json: body });
        Object.assign(p, saved); Object.assign(draft, structuredClone(saved.config)); toast('Saved'); render();
      } else if (act === 'publish') {
        const r = await api(`/api/seller/products/${id}/publish`, { method: 'POST', json: { published: !p.published } });
        p.published = r.published; toast(r.published ? 'Published. Customers can use the link.' : 'Unpublished'); render();
      }
    } catch (x) { showErrors($('#ed-err'), x); window.scrollTo(0, 0); }
  };
}

route();

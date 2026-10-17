import { $, $$, esc, api, me, showErrors, clearErrors } from './api.js';

const user = await me().catch(() => null);
if (!user) location.replace('/account.html');
else if (user.role !== 'owner') location.replace('/dashboard.html');
$('#who').textContent = user.email;
$('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); location.href = '/account.html'; };

let filter = 'pending';
const pill = s => `<span class="pill ${s === 'active' ? 'on' : s === 'pending' ? 'warn' : 'bad'}">${esc(s)}</span>`;
const when = iso => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

async function loadTenants() {
  clearErrors($('#err'));
  const rows = await api('/api/owner/tenants' + (filter ? `?status=${filter}` : ''));
  $('#tenants').innerHTML = rows.length
    ? `<thead><tr><th>Shop</th><th>Link name</th><th>Contact</th><th>Joined</th><th>Products</th><th>Designs</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(t => `<tr>
        <td><b>${esc(t.name)}</b></td><td>${esc(t.slug)}</td><td>${esc(t.owner_name)}<br><span class="muted">${esc(t.email)}</span></td><td>${esc(when(t.created_at))}</td>
        <td>${t.products}</td><td>${t.designs}</td><td>${pill(t.status)}</td>
        <td><div class="row">${t.status !== 'active' ? `<button class="btn sm" data-set="active" data-id="${t.id}">Approve</button>` : ''}
          ${t.status !== 'suspended' ? `<button class="btn sm danger" data-set="suspended" data-id="${t.id}">Suspend</button>` : ''}</div></td></tr>`).join('')}</tbody>`
    : '<tbody><tr><td class="muted">Nobody here.</td></tr></tbody>';
}

async function loadLeads() {
  const rows = await api('/api/owner/leads');
  $('#leads').innerHTML = rows.length
    ? `<thead><tr><th>When</th><th>Business</th><th>Name</th><th>Phone</th><th>Email</th><th>Sells</th><th>Website</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td>${esc(when(r.created))}</td><td><b>${esc(r.business)}</b></td><td>${esc(r.name)}</td><td>${esc(r.phone)}</td><td>${esc(r.email)}</td><td>${esc(r.sells)}</td><td>${esc(r.website)}</td></tr>`).join('')}</tbody>`
    : '<tbody><tr><td class="muted">No sign-ups yet.</td></tr></tbody>';
}

const rupees = n => '₹' + Number(n).toLocaleString('en-IN');
let plans = {}, bmonth = '';
async function loadBilling() {
  clearErrors($('#berr'));
  plans = plans.pilot ? plans : await api('/api/owner/plans');
  if (!$('#bm').options.length) {
    const d = new Date();
    for (let i = 0; i < 12; i++) { const m = new Date(d.getFullYear(), d.getMonth() - i, 1); $('#bm').add(new Option(`${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}`)); }
  }
  bmonth = $('#bm').value;
  $('#csv').href = `/api/owner/invoice.csv?month=${bmonth}`;
  const rows = await api(`/api/owner/tenants?status=active&month=${bmonth}`);
  $('#billing').innerHTML = rows.length
    ? `<thead><tr><th>Shop</th><th>Plan</th><th>Setup fee</th><th>Designs</th><th>Views</th><th>Extra</th><th>Total with GST</th><th></th></tr></thead><tbody>${rows.map(t => `<tr data-t="${t.id}">
        <td><b>${esc(t.name)}</b></td>
        <td><select data-plan aria-label="Plan for ${esc(t.name)}">${Object.entries(plans).map(([k, p]) => `<option value="${k}" ${k === t.plan ? 'selected' : ''}>${esc(p.label)}</option>`).join('')}</select></td>
        <td><input type="number" min="0" step="1" value="${t.setup_fee}" data-setup style="width:90px" aria-label="Setup fee for ${esc(t.name)}"> <label style="display:inline;font-weight:400"><input type="checkbox" data-paid ${t.setup_fee_paid ? 'checked' : ''}> paid</label></td>
        <td>${t.invoice.designs} / ${t.invoice.included}</td><td>${t.invoice.views}</td><td>${t.invoice.extra_designs}</td><td><b>${rupees(t.invoice.total)}</b></td>
        <td><button class="btn sm" data-save-plan="${t.id}">Save</button></td></tr>`).join('')}</tbody>`
    : '<tbody><tr><td class="muted">No active shops yet.</td></tr></tbody>';
}

document.addEventListener('change', e => { if (e.target.id === 'bm') loadBilling().catch(x => showErrors($('#berr'), x)); });
document.addEventListener('click', async e => {
  const sp = e.target.closest('[data-save-plan]');
  if (sp) {
    const tr = sp.closest('tr'); sp.disabled = true;
    try {
      await api(`/api/owner/tenants/${sp.dataset.savePlan}/plan`, { method: 'POST', json: { plan: tr.querySelector('[data-plan]').value, setup_fee: Number(tr.querySelector('[data-setup]').value) || 0, setup_fee_paid: tr.querySelector('[data-paid]').checked } });
      await loadBilling();
    } catch (x) { showErrors($('#berr'), x); sp.disabled = false; }
    return;
  }
  const f = e.target.closest('[data-f]');
  if (f) { filter = f.dataset.f; $$('[data-f]').forEach(b => b.classList.toggle('on', b === f)); return loadTenants().catch(x => showErrors($('#err'), x)); }
  const s = e.target.closest('[data-set]');
  if (s) {
    s.disabled = true;
    try { await api(`/api/owner/tenants/${s.dataset.id}/status`, { method: 'POST', json: { status: s.dataset.set } }); await loadTenants(); }
    catch (x) { showErrors($('#err'), x); s.disabled = false; }
  }
});

await Promise.all([loadTenants(), loadLeads(), loadBilling()]).catch(x => showErrors($('#err'), x));

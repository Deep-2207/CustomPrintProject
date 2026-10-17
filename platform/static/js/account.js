import { $, api, me, showErrors, clearErrors, slugify } from './api.js';

// Already logged in: go straight to the right place.
const current = await me().catch(() => null);
if (current) go(current);

function go(user) { location.href = user.role === 'owner' ? '/owner.html' : '/dashboard.html'; }

// Tabs
function show(which) {
  for (const t of ['login', 'register']) {
    $('#' + t).hidden = t !== which;
    $('#tab-' + t).classList.toggle('on', t === which);
    $('#tab-' + t).setAttribute('aria-selected', t === which);
  }
}
$('#tab-login').onclick = () => show('login');
$('#tab-register').onclick = () => show('register');
if (location.hash === '#register') show('register');

// The link name follows the business name until the person edits it themselves.
let slugEdited = false;
$('#r-slug').addEventListener('input', () => { slugEdited = true; preview(); });
$('#r-business').addEventListener('input', () => { if (!slugEdited) { $('#r-slug').value = slugify($('#r-business').value); } preview(); });
function preview() { $('#slug-preview').textContent = `/s/${$('#r-slug').value || 'your-shop'}/…`; }

async function submit(form, errBox, button, work) {
  clearErrors(errBox);
  button.disabled = true;
  try { go(await work()); }
  catch (e) { showErrors(errBox, e); button.disabled = false; }
}

$('#login').addEventListener('submit', e => {
  e.preventDefault();
  submit(e.target, $('#l-err'), $('#login .cta'), () => api('/api/auth/login', { method: 'POST', json: { email: $('#l-email').value.trim(), password: $('#l-pass').value } }));
});

$('#register').addEventListener('submit', e => {
  e.preventDefault();
  const slug = $('#r-slug').value.trim();
  const body = { business: $('#r-business').value.trim(), name: $('#r-name').value.trim(), email: $('#r-email').value.trim(), password: $('#r-pass').value };
  if (slug) body.slug = slug;
  submit(e.target, $('#r-err'), $('#register .cta'), () => api('/api/auth/register', { method: 'POST', json: body }));
});

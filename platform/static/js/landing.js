// Landing page: demo tabs and the sign-up form.
const $ = s => document.querySelector(s);

// Demo tabs switch the product shown in the iframe.
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => { x.classList.toggle('on', x === t); x.setAttribute('aria-selected', x === t); });
  $('#frame').src = t.dataset.src;
}));

// Sign-up form: check on the page for a quick message, and again on the server (the server is the real check).
const form = $('#lead'), msg = $('#msg');
const PHONE = /^\+?[0-9 \-]{7,18}$/, EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

form.addEventListener('submit', async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach(k => { data[k] = String(data[k]).trim(); });
  form.querySelectorAll('.bad').forEach(x => x.classList.remove('bad'));
  const problems = [];
  const flag = (id, text) => { $('#' + id).classList.add('bad'); problems.push(text); };
  if (!data.business) flag('business', 'Please enter your shop name.');
  if (!data.name) flag('name', 'Please enter your name.');
  if (!PHONE.test(data.phone)) flag('phone', 'Please enter a valid phone or WhatsApp number (digits, spaces, + or -).');
  if (data.email && !EMAIL.test(data.email)) flag('email', 'That email address does not look right.');
  if (problems.length) { msg.textContent = problems[0]; $('#' + form.querySelector('.bad').id).focus(); return; }

  msg.textContent = ''; $('#send').disabled = true; $('#send').textContent = 'Sending…';
  try {
    const r = await fetch('/api/leads', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    if (r.ok) { form.hidden = true; $('#thanks').hidden = false; $('#thanks').scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    const j = await r.json().catch(() => ({}));
    msg.textContent = r.status === 429 ? j.detail : 'Sorry, that did not go through. Please check the details and try again.';
  } catch {
    msg.textContent = 'No connection. Please try again in a moment.';
  }
  $('#send').disabled = false; $('#send').textContent = 'Request a free pilot';
});

// Shared helpers for the seller pages (login, dashboard, owner, zone editor).

export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];

// Escape text before putting it into HTML. Everything a person typed goes through this.
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export class ApiError extends Error {
  constructor(status, messages) { super(messages[0]); this.status = status; this.messages = messages; }
}

// Turns the different error shapes the server can send into a list of plain sentences.
function messagesFrom(data) {
  const d = data && data.detail;
  if (typeof d === 'string') return [d];
  if (d && Array.isArray(d.errors)) return d.errors;
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).filter(x => x !== 'body').join(' > ')}: ${e.msg}`.replace(/^: /, ''));
  return ['Something went wrong. Please try again.'];
}

// Every change sends the X-Requested-With header the server requires (it blocks forged requests from other sites).
export async function api(path, { method = 'GET', json, form } = {}) {
  const opt = { method, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } };
  if (json !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(json); }
  if (form) opt.body = form;
  let r;
  try { r = await fetch(path, opt); } catch { throw new ApiError(0, ['No connection. Please check your internet and try again.']); }
  let data = null;
  try { data = await r.json(); } catch { /* empty or not JSON */ }
  if (!r.ok) throw new ApiError(r.status, messagesFrom(data));
  return data;
}

export const me = () => api('/api/auth/me');

// A simple version of the server's rule for turning a shop or product name into a link name.
export const slugify = (t, max = 40) => String(t).normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, max).replace(/-+$/, '');

export function showErrors(el, err) {
  const list = err instanceof ApiError ? err.messages : [String(err && err.message || err)];
  el.innerHTML = list.map(m => `<div>${esc(m)}</div>`).join('');
  el.hidden = false;
}
export const clearErrors = el => { el.innerHTML = ''; el.hidden = true; };

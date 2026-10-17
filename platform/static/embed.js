/* PreviewPrint embed loader. Put this on your own website:
 *
 *   <div data-pp-product="custom-printed-mug" data-pp-key="pk_xxxxxxxx"></div>
 *   <script src="https://YOUR-HOST/embed.js" async></script>
 *
 * Optional attributes on the div:
 *   data-pp-button="Add to my order"   text of the main button
 *   data-pp-ref="ORDER-1042"           your own reference; saved with the design
 *   data-pp-design="a1b2c3d4e5f6"      open an earlier design for editing
 *   data-pp-input="#design_id"         a form field (CSS selector) that receives the design id when the customer saves
 *   data-pp-height="720"               starting height in pixels
 *
 * When the customer saves, the div gets a "previewprint:design" event, and PreviewPrint.on('design', fn) callbacks run
 * with { designId, product, previewUrl, text }.
 */
(function () {
  'use strict';
  var script = document.currentScript || (function () { var s = document.getElementsByTagName('script'); return s[s.length - 1]; })();
  var host = new URL(script.src).origin;
  var listeners = { design: [], ready: [] }, frames = [];

  window.PreviewPrint = {
    on: function (name, fn) { (listeners[name] = listeners[name] || []).push(fn); return this; },
    mount: mount
  };

  function mount(el) {
    if (el.getAttribute('data-pp-mounted')) return;
    var key = el.getAttribute('data-pp-key'), product = el.getAttribute('data-pp-product');
    if (!/^pk_[A-Za-z0-9_-]+$/.test(key || '') || !/^[a-z0-9-]+$/.test(product || '')) {
      el.textContent = 'PreviewPrint: data-pp-key and data-pp-product are missing or wrong.';
      return;
    }
    el.setAttribute('data-pp-mounted', '1');
    var params = new URLSearchParams({ host: location.origin });
    ['button', 'ref', 'design'].forEach(function (n) { var v = el.getAttribute('data-pp-' + n); if (v) params.set(n, v); });
    var f = document.createElement('iframe');
    f.src = host + '/embed/' + key + '/' + product + '?' + params.toString();
    f.title = 'Customize your product';
    f.allow = 'clipboard-write';
    f.style.cssText = 'width:100%;border:0;display:block;min-height:480px;height:' + (parseInt(el.getAttribute('data-pp-height'), 10) || 720) + 'px';
    el.appendChild(f);
    frames.push({ frame: f, el: el });
  }

  window.addEventListener('message', function (e) {
    if (e.origin !== host || !e.data || e.data.source !== 'previewprint') return;
    var m = frames.filter(function (x) { return x.frame.contentWindow === e.source; })[0];
    if (!m) return;
    if (e.data.type === 'resize' && e.data.height > 200) m.frame.style.height = Math.min(e.data.height, 4000) + 'px';
    else if (e.data.type === 'design.saved' || e.data.type === 'ready') {
      var name = e.data.type === 'ready' ? 'ready' : 'design';
      var detail = { designId: e.data.designId, product: e.data.product, previewUrl: e.data.previewUrl, text: e.data.text };
      var sel = m.el.getAttribute('data-pp-input');
      if (name === 'design' && sel) { var inp = document.querySelector(sel); if (inp) { inp.value = detail.designId; inp.dispatchEvent(new Event('change', { bubbles: true })); } }
      m.el.dispatchEvent(new CustomEvent('previewprint:' + name, { detail: detail, bubbles: true }));
      (listeners[name] || []).forEach(function (fn) { try { fn(detail); } catch (err) { console.error(err); } });
    }
  });

  function scan() { Array.prototype.forEach.call(document.querySelectorAll('[data-pp-product][data-pp-key]'), mount); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan); else scan();
})();

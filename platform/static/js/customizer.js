// Generic 3D product customizer. Works for any product described by the product JSON
// (see app/main.py SEED): a GLB model (or the built-in procedural band) + printable zones.
import * as THREE from '../vendor/three.module.js';
import { OrbitControls } from '../vendor/addons/OrbitControls.js';
import { GLTFLoader } from '../vendor/addons/GLTFLoader.js';
import { templateFor } from './templates.js';
import { TEXT_STYLES, layoutLines } from './textstyles.js';

const CANVAS_W = 4096;
const lum = h => { const n = parseInt(h.slice(1), 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; };
const mix = (h, t, a) => { // mix hex with hex t by a
  const p = x => [parseInt(x.slice(1, 3), 16), parseInt(x.slice(3, 5), 16), parseInt(x.slice(5, 7), 16)];
  const A = p(h), B = p(t); return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * a).toString(16).padStart(2, '0')).join('');
};

export class Customizer extends EventTarget {
  constructor(el, product) {
    super();
    this.el = el; this.product = product;
    this.state = this.defaults();
    this.meshes = new Map();   // mesh name -> {mesh, canvas, bump, tex, bumpTex}
    this.imgCache = new Map();
    this.showGuides = true;
    try { this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: false }); }
    catch (e) { el.innerHTML = '<p style="padding:20px">3D preview needs WebGL, which this browser does not support.</p>'; this.noGL = true; return; }
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.enablePan = false; this.controls.minDistance = 1.5; this.controls.maxDistance = 12;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a93a6, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(3, 5, 4); this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xbcd4ff, .7); rim.position.set(-4, 2, -3); this.scene.add(rim);
    this.root = new THREE.Group(); this.scene.add(this.root);
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    const loop = () => { this.controls.update(); this.renderer.render(this.scene, this.camera); this._raf = requestAnimationFrame(loop); };
    loop();
  }

  defaults() {
    const p = this.product, z = {};
    p.zones.forEach(zn => z[zn.id] = { text: '', font: p.fonts[0], size: .45, x: .5, y: .5, color: '', image: null, stickers: [], tpl: 'plain' });
    return { size: p.sizes[0] ? p.sizes[0].id : null, bodyColor: p.colors[0].hex, imprintColor: '', zones: z };
  }

  resize() {
    if (this.noGL) return;
    const w = this.el.clientWidth || 600, h = this.el.clientHeight || 420;
    this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  // ---- model ----
  async load() {
    if (this.noGL) return;
    this.root.clear(); this.meshes.clear();
    const m = this.product.model;
    if (m.type === 'glb' && m.url) {
      const gltf = await new GLTFLoader().loadAsync(m.url);
      this.root.add(gltf.scene);
    } else {
      const tpl = templateFor(m);
      if (!tpl) throw new Error('Unknown product template: ' + (m.template || m.type));
      const size = this.product.sizes.find(s => s.id === this.state.size);
      this.root.add(tpl.build({ size }));
    }
    this.collect();
    this.fitCamera();
    this.redraw();
  }

  collect() {
    const zoneMeshes = new Set(this.product.zones.map(z => z.mesh));
    this.root.traverse(o => {
      if (!o.isMesh) return;
      o.material = (Array.isArray(o.material) ? o.material[0] : o.material).clone();
      if (zoneMeshes.has(o.name)) {
        const zs = this.product.zones.filter(z => z.mesh === o.name);
        const aspect = zs[0].aspect || this.root.children[0].userData.aspect || 8;
        const c = document.createElement('canvas'); c.width = CANVAS_W; c.height = Math.max(64, Math.round(CANVAS_W / aspect));
        const b = document.createElement('canvas'); b.width = c.width; b.height = c.height;
        const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
        const bt = new THREE.CanvasTexture(b);
        o.material.map = tex; o.material.bumpMap = bt; o.material.bumpScale = 1.6; o.material.color.set(0xffffff);
        this.meshes.set(o.name, { mesh: o, canvas: c, bump: b, tex, bt });
      }
    });
  }

  fitCamera() {
    const box = new THREE.Box3().setFromObject(this.root), s = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    this.controls.target.copy(c);
    // distance so the whole object fits the vertical field of view, with some margin
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    this.dist = (Math.max(s.x, s.y, s.z) / 2) / Math.tan(fov / 2) * 1.15 + s.z / 2;
    this.controls.minDistance = this.dist * 0.3;   // zoom limits scale with the product size
    this.controls.maxDistance = this.dist * 2.5;
    this.setView('front');
  }

  setView(v) {
    if (this.noGL) return;
    const a = v === 'back' ? Math.PI : 0, t = this.controls.target;
    this.camera.position.set(t.x + Math.sin(a) * this.dist * .85, t.y + this.dist * .42, t.z + Math.cos(a) * this.dist * .85);
    this.camera.lookAt(t);
  }

  // ---- drawing ----
  image(url) {
    let i = this.imgCache.get(url);
    if (!i) { i = new Image(); i.onload = () => this.redraw(); i.src = url; this.imgCache.set(url, i); }
    return i;
  }

  // A zone is a fixed rectangle on the surface: u0..u1 across, y0..y1 down (fractions of the texture).
  // Everything the customer adds is placed relative to that rectangle and clipped to it.
  zoneBox(z, W, H) {
    const y0 = z.y0 == null ? 0 : z.y0, y1 = z.y1 == null ? 1 : z.y1;
    return { x: z.u0 * W, y: y0 * H, w: (z.u1 - z.u0) * W, h: (y1 - y0) * H };
  }

  redraw() {
    if (this.noGL) return;
    const st = this.state, body = st.bodyColor;
    this.root.traverse(o => { if (o.isMesh && !this.meshes.has(o.name)) o.material.color.set(body); });
    for (const [name, m] of this.meshes) {
      const W = m.canvas.width, H = m.canvas.height, c = m.canvas.getContext('2d'), b = m.bump.getContext('2d');
      c.fillStyle = body; c.fillRect(0, 0, W, H); b.fillStyle = '#808080'; b.fillRect(0, 0, W, H);
      for (const z of this.product.zones.filter(z => z.mesh === name)) {
        const s = st.zones[z.id], box = this.zoneBox(z, W, H);
        c.save(); b.save(); [c, b].forEach(k => { k.beginPath(); k.rect(box.x, box.y, box.w, box.h); k.clip(); });
        if (s.image) {
          const im = this.image(s.image.url);
          if (im.complete && im.naturalWidth) {
            const sc = s.image.scale * box.h * 1.2 / Math.max(im.naturalWidth, im.naturalHeight);
            c.translate(box.x + s.image.x * box.w, box.y + s.image.y * box.h); c.rotate((s.image.rot || 0) * Math.PI / 180);
            c.drawImage(im, -im.naturalWidth * sc / 2, -im.naturalHeight * sc / 2, im.naturalWidth * sc, im.naturalHeight * sc);
          }
        }
        c.restore(); b.restore();
        s.stickers.forEach(k => this.drawSticker(c, b, z, k, box, body, st.imprintColor));
        if (s.text) this.drawText(c, b, z, s, box, body, st.imprintColor);
        if (z.guide && this.showGuides) this.drawGuide(c, box, body);
      }
      m.tex.needsUpdate = true; m.bt.needsUpdate = true;
    }
    this.dispatchEvent(new CustomEvent('redraw'));
  }

  // Dashed outline of the printable area. Shown on screen only; never in the saved preview.
  drawGuide(c, box, body) {
    c.save();
    c.strokeStyle = lum(body) < .5 ? 'rgba(255,255,255,.7)' : 'rgba(0,0,0,.45)';
    c.lineWidth = 6; c.setLineDash([28, 20]);
    c.strokeRect(box.x + 3, box.y + 3, box.w - 6, box.h - 6);
    c.restore();
  }

  // The ink colour used for text and stickers in an area: the customer's choice, else a sensible default.
  inkColor(z, body, imprint, own) {
    const dark = lum(body) < .5;
    return own || imprint || (z.style === 'print' ? (dark ? '#ffffff' : '#111111') : mix(body, dark ? '#ffffff' : '#000000', .16));
  }

  // Text always fits: the font shrinks until the widest line fits the width and all lines fit the height.
  // Line breaks (Enter) make a new line. Characters are never dropped.
  drawText(c, b, z, s, box, body, imprint) {
    if (s.tpl && s.tpl !== 'plain' && TEXT_STYLES[s.tpl]) return this.drawStyled(c, b, z, s, box, imprint);
    const lines = s.text.split('\n');
    const weight = s.font === 'Impact' ? '400' : '700', fam = `"${s.font}", sans-serif`, LH = 1.15;
    let px = s.size * box.h;
    c.font = `${weight} ${px}px ${fam}`;
    const widest = Math.max(...lines.map(l => c.measureText(l).width), 1);
    let k = 1;
    if (widest > box.w * .96) k = Math.min(k, (box.w * .96) / widest);
    if (lines.length * px * LH > box.h * .96) k = Math.min(k, (box.h * .96) / (lines.length * px * LH));
    px *= k;
    const font = `${weight} ${px}px ${fam}`, col = this.inkColor(z, body, imprint, s.color);
    [c, b].forEach(g => { g.save(); g.beginPath(); g.rect(box.x, box.y, box.w, box.h); g.clip(); g.translate(box.x + s.x * box.w, box.y + s.y * box.h); g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle'; });
    c.fillStyle = col;
    if (z.style !== 'print') { b.fillStyle = z.style === 'emboss' ? '#ffffff' : '#000000'; b.shadowColor = b.fillStyle; b.shadowBlur = px * .06; }
    lines.forEach((line, i) => {
      const dy = (i - (lines.length - 1) / 2) * px * LH;
      c.fillText(line, 0, dy);
      if (z.style !== 'print') b.fillText(line, 0, dy);
    });
    c.restore(); b.restore();
  }

  // A text style (textstyles.js): the customer's words in a finished design. The same drawing is
  // repeated in one solid colour on the relief map so embossed and debossed products look right.
  drawStyled(c, b, z, s, box, imprint) {
    const style = TEXT_STYLES[s.tpl], L = layoutLines(c, s.text.split('\n'), box, s, style), ink = s.color || imprint || '';
    [c, b].forEach(g => { g.save(); g.beginPath(); g.rect(box.x, box.y, box.w, box.h); g.clip(); });
    style.draw(c, L, { ink, mono: null });
    if (z.style !== 'print') style.draw(b, L, { ink: '', mono: z.style === 'emboss' ? '#ffffff' : '#000000' });
    c.restore(); b.restore();
  }

  // Small preview of the customer's own text in one style (the gallery under the message box).
  renderThumb(cv, z, tplId) {
    const st = this.state, s0 = st.zones[z.id], body = st.bodyColor, c = cv.getContext('2d');
    c.fillStyle = body; c.fillRect(0, 0, cv.width, cv.height);
    if (!this._scratch) this._scratch = document.createElement('canvas');
    this._scratch.width = cv.width; this._scratch.height = cv.height;
    const s = { ...s0, text: s0.text || 'Deep\nPatel', tpl: tplId, x: .5, y: .5, size: .6 };
    this.drawText(c, this._scratch.getContext('2d'), { ...z, style: 'print' }, s, { x: 0, y: 0, w: cv.width, h: cv.height }, body, st.imprintColor);
  }

  // Stickers are simple one-colour shapes (static/stickers.json) drawn from SVG, so they take the ink
  // colour and can be embossed or debossed exactly like text.
  stickerImage(id, color) {
    const key = id + color;
    let im = this.imgCache.get(key);
    if (!im) {
      const def = this.stickers && this.stickers[id]; if (!def) return null;
      im = new Image(); im.onload = () => this.redraw();
      im.src = 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512" fill="${color}">${def.svg}</svg>`);
      this.imgCache.set(key, im);
    }
    return im.complete && im.naturalWidth ? im : null;
  }

  drawSticker(c, b, z, k, box, body, imprint) {
    const size = k.scale * box.h * 1.2, col = this.inkColor(z, body, imprint, '');
    const im = this.stickerImage(k.id, col); if (!im) return;
    const relief = z.style !== 'print' ? this.stickerImage(k.id, z.style === 'emboss' ? '#ffffff' : '#000000') : null;
    [c, b].forEach(g => { g.save(); g.beginPath(); g.rect(box.x, box.y, box.w, box.h); g.clip(); g.translate(box.x + k.x * box.w, box.y + k.y * box.h); g.rotate((k.rot || 0) * Math.PI / 180); });
    c.drawImage(im, -size / 2, -size / 2, size, size);
    if (relief) b.drawImage(relief, -size / 2, -size / 2, size, size);
    c.restore(); b.restore();
  }

  // 2D strip: the unwrapped zone, used for drag-positioning
  zoneRect(z) {
    const m = this.meshes.get(z.mesh); if (!m) return null;
    const box = this.zoneBox(z, m.canvas.width, m.canvas.height);
    return { src: m.canvas, sx: box.x, sy: box.y, sw: box.w, sh: box.h };
  }

  // The saved preview never shows the dashed guides.
  snapshot() {
    const was = this.showGuides; this.showGuides = false; this.redraw();
    this.renderer.render(this.scene, this.camera);
    const url = this.renderer.domElement.toDataURL('image/png');
    this.showGuides = was; this.redraw();
    return url;
  }

  // ---- config <-> server layers ----
  toDesign() {
    const st = this.state, layers = [];
    this.product.zones.forEach(z => {
      const s = st.zones[z.id];
      if (s.text) layers.push({ zone: z.id, type: 'text', text: s.text, font: s.font, template: s.tpl, color: s.color, x: s.x, y: s.y, size: s.size, rot: 0 });
      if (s.image) layers.push({ zone: z.id, type: 'image', upload_id: s.image.upload_id, x: s.image.x, y: s.image.y, scale: s.image.scale, rot: s.image.rot || 0 });
      s.stickers.forEach(k => layers.push({ zone: z.id, type: 'sticker', sticker: k.id, x: k.x, y: k.y, scale: k.scale, rot: k.rot || 0 }));
    });
    return { slug: this.product.slug, size: st.size, body_color: st.bodyColor, imprint_color: st.imprintColor, layers };
  }

  fromDesign(d) {
    this.state = this.defaults();
    const st = this.state; st.size = d.size || st.size; st.bodyColor = d.body_color; st.imprintColor = d.imprint_color || '';
    d.layers.forEach(l => {
      const s = st.zones[l.zone]; if (!s) return;
      if (l.type === 'text') Object.assign(s, { text: l.text, tpl: l.template || 'plain', font: l.font, color: l.color || '', x: l.x, y: l.y, size: l.size });
      else if (l.type === 'sticker') s.stickers.push({ id: l.sticker, x: l.x, y: l.y, scale: l.scale, rot: l.rot || 0 });
      else s.image = { upload_id: l.upload_id, url: l.url || `/files/uploads/${l.upload_id}.png`, x: l.x, y: l.y, scale: l.scale, rot: l.rot };
    });
  }
}

// Generic 3D product customizer. Works for any product described by the product JSON
// (see app/main.py SEED): a GLB model (or the built-in procedural band) + printable zones.
import * as THREE from '../vendor/three.module.js';
import { OrbitControls } from '../vendor/addons/OrbitControls.js';
import { GLTFLoader } from '../vendor/addons/GLTFLoader.js';
import { templateFor } from './templates.js';

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
    p.zones.forEach(zn => z[zn.id] = { text: '', font: p.fonts[0], size: .45, x: .5, y: .5, color: '', image: null });
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
    this.dist = Math.max(s.x, s.y, s.z) * 1.9 + .8;
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

  redraw() {
    if (this.noGL) return;
    const st = this.state, body = st.bodyColor;
    this.root.traverse(o => { if (o.isMesh && !this.meshes.has(o.name)) o.material.color.set(body); });
    for (const [name, m] of this.meshes) {
      const W = m.canvas.width, H = m.canvas.height, c = m.canvas.getContext('2d'), b = m.bump.getContext('2d');
      c.fillStyle = body; c.fillRect(0, 0, W, H); b.fillStyle = '#808080'; b.fillRect(0, 0, W, H);
      for (const z of this.product.zones.filter(z => z.mesh === name)) {
        const s = st.zones[z.id], x0 = z.u0 * W, w = (z.u1 - z.u0) * W;
        c.save(); b.save(); [c, b].forEach(k => { k.beginPath(); k.rect(x0, 0, w, H); k.clip(); });
        if (s.image) {
          const im = this.image(s.image.url);
          if (im.complete && im.naturalWidth) {
            const sc = s.image.scale * H * 1.2 / Math.max(im.naturalWidth, im.naturalHeight);
            c.translate(x0 + s.image.x * w, s.image.y * H); c.rotate((s.image.rot || 0) * Math.PI / 180);
            c.drawImage(im, -im.naturalWidth * sc / 2, -im.naturalHeight * sc / 2, im.naturalWidth * sc, im.naturalHeight * sc);
          }
        }
        c.restore(); b.restore();
        if (s.text) this.drawText(c, b, z, s, x0, w, H, body, st.imprintColor);
      }
      m.tex.needsUpdate = true; m.bt.needsUpdate = true;
    }
    this.dispatchEvent(new CustomEvent('redraw'));
  }

  // Text always fits: the font shrinks to the zone width. Characters are never dropped.
  drawText(c, b, z, s, x0, w, H, body, imprint) {
    let px = s.size * H;
    const weight = s.font === 'Impact' ? '400' : '700', fam = `"${s.font}", sans-serif`;
    c.font = `${weight} ${px}px ${fam}`;
    const tw = c.measureText(s.text).width;
    if (tw > w * .96) px *= (w * .96) / tw;
    const font = `${weight} ${px}px ${fam}`;
    const dark = lum(body) < .5;
    const col = s.color || imprint || (z.style === 'print' ? (dark ? '#ffffff' : '#111111') : mix(body, dark ? '#ffffff' : '#000000', .16));
    [c, b].forEach(k => { k.save(); k.beginPath(); k.rect(x0, 0, w, H); k.clip(); k.translate(x0 + s.x * w, s.y * H); k.font = font; k.textAlign = 'center'; k.textBaseline = 'middle'; });
    c.fillStyle = col; c.fillText(s.text, 0, 0);
    if (z.style !== 'print') {
      b.fillStyle = z.style === 'emboss' ? '#ffffff' : '#000000'; b.shadowColor = b.fillStyle; b.shadowBlur = px * .06; b.fillText(s.text, 0, 0);
    }
    c.restore(); b.restore();
  }

  // 2D strip: the unwrapped zone, used for drag-positioning
  zoneRect(z) {
    const m = this.meshes.get(z.mesh); if (!m) return null;
    const W = m.canvas.width, H = m.canvas.height;
    return { src: m.canvas, sx: z.u0 * W, sw: (z.u1 - z.u0) * W, sh: H };
  }

  snapshot() { this.renderer.render(this.scene, this.camera); return this.renderer.domElement.toDataURL('image/png'); }

  // ---- config <-> server layers ----
  toDesign() {
    const st = this.state, layers = [];
    this.product.zones.forEach(z => {
      const s = st.zones[z.id];
      if (s.text) layers.push({ zone: z.id, type: 'text', text: s.text, font: s.font, color: s.color, x: s.x, y: s.y, size: s.size, rot: 0 });
      if (s.image) layers.push({ zone: z.id, type: 'image', upload_id: s.image.upload_id, x: s.image.x, y: s.image.y, scale: s.image.scale, rot: s.image.rot || 0 });
    });
    return { slug: this.product.slug, size: st.size, body_color: st.bodyColor, imprint_color: st.imprintColor, layers };
  }

  fromDesign(d) {
    this.state = this.defaults();
    const st = this.state; st.size = d.size || st.size; st.bodyColor = d.body_color; st.imprintColor = d.imprint_color || '';
    d.layers.forEach(l => {
      const s = st.zones[l.zone]; if (!s) return;
      if (l.type === 'text') Object.assign(s, { text: l.text, font: l.font, color: l.color || '', x: l.x, y: l.y, size: l.size });
      else s.image = { upload_id: l.upload_id, url: l.url || `/files/uploads/${l.upload_id}.png`, x: l.x, y: l.y, scale: l.scale, rot: l.rot };
    });
  }
}

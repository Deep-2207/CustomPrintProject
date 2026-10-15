// Template registry: each template builds one product shape from code (no 3D file needed).
//
// A template is { label, build(ctx) } where build returns a THREE.Group whose
//   - printable meshes are named exactly like the product's zone `mesh` field, and
//   - userData.aspect = surface width / height of the printable mesh (keeps text undistorted).
//
// To add a product (Day 3: the mug): add one entry here, nothing else in the viewer changes.
import * as THREE from '../vendor/three.module.js';

const MM = 0.05;   // 1 millimetre -> scene units

const material = () => new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.42, metalness: 0 });

export const TEMPLATES = {
  band: {
    label: 'Silicone wristband',
    // ctx.size = the size option chosen by the customer, e.g. { id: '1/2', mm: 12.7 }
    build({ size }) {
      const g = new THREE.Group();
      const R = 29 * MM, H = (size && size.mm ? size.mm : 12.7) * MM, T = 2.2 * MM;
      const outer = new THREE.Mesh(new THREE.CylinderGeometry(R + T, R + T, H, 160, 1, true), material());
      outer.name = 'band_outer';
      const inner = new THREE.Mesh(new THREE.CylinderGeometry(R, R, H, 160, 1, true), material());
      inner.name = 'band_inner';
      inner.material.side = THREE.BackSide;
      const rim = (y, up) => {
        const r = new THREE.Mesh(new THREE.RingGeometry(R, R + T, 160, 1), material());
        r.name = 'band_rim';
        r.rotation.x = up ? -Math.PI / 2 : Math.PI / 2;
        r.position.y = y;
        return r;
      };
      g.add(outer, inner, rim(H / 2, true), rim(-H / 2, false));
      g.rotation.y = -Math.PI / 2;   // the middle of the "front" half (u = 0.25) faces the camera
      g.userData.aspect = (2 * Math.PI * (R + T)) / H;
      return g;
    },
  },
};

// Old products stored model.type = 'procedural-band'; keep them working.
export function templateFor(model) {
  const key = model.template || (model.type === 'procedural-band' ? 'band' : null);
  return key ? TEMPLATES[key] || null : null;
}

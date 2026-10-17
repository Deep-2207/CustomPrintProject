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
  // Day 3: a mug. The cup wall is `mug_outer`; the handle sits on the side opposite the print area.
  mug: {
    label: 'Ceramic mug',
    // size = { mm: height, radius } in millimetres
    build({ size }) {
      const g = new THREE.Group();
      const H = (size && size.mm ? size.mm : 95) * MM, R = (size && size.radius ? size.radius : 41) * MM, W = 3 * MM;
      const outer = new THREE.Mesh(new THREE.CylinderGeometry(R, R, H, 160, 1, true, -Math.PI / 2), material());
      outer.name = 'mug_outer';   // texture seam (u = 0) sits under the handle, on the -X side
      const inner = new THREE.Mesh(new THREE.CylinderGeometry(R - W, R - W, H, 160, 1, true), material());
      inner.name = 'mug_inner';
      inner.material.side = THREE.BackSide;
      const rim = new THREE.Mesh(new THREE.RingGeometry(R - W, R, 160, 1), material());
      rim.name = 'mug_rim';
      rim.rotation.x = -Math.PI / 2;
      rim.position.y = H / 2;
      const floor = new THREE.Mesh(new THREE.CircleGeometry(R - W, 96), material());
      floor.name = 'mug_floor';
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -H / 2 + W;
      const base = new THREE.Mesh(new THREE.CircleGeometry(R, 96), material());
      base.name = 'mug_base';
      base.rotation.x = Math.PI / 2;
      base.position.y = -H / 2;
      // Handle: a half ring whose ends touch the wall, bulging away from the cup.
      const hr = H * 0.27;
      const handle = new THREE.Mesh(new THREE.TorusGeometry(hr, 4 * MM, 20, 48, Math.PI), material());
      handle.name = 'mug_handle';
      handle.rotation.z = Math.PI / 2;      // bulge towards -X
      handle.position.set(-R + 1.5 * MM, 0, 0);
      handle.scale.set(0.9, 1, 1);
      g.add(outer, inner, rim, floor, base, handle);
      // Handle on the viewer's left (-X). u = 0.25 faces the camera (the FRONT print area), u = 0.75 is the BACK area.
      g.userData.aspect = (2 * Math.PI * R) / H;
      return g;
    },
  },
};

// Old products stored model.type = 'procedural-band'; keep them working.
export function templateFor(model) {
  const key = model.template || (model.type === 'procedural-band' ? 'band' : null);
  return key ? TEMPLATES[key] || null : null;
}

// Evaluate an ergogen-emitted (CSG v1) .jscad file, report stats, write an STL,
// and optionally emit planar cross sections as SVG for visual verification.
//
// usage: node jscad_run.js <file.jscad> [--stl out.stl] [--cut axis=value,...] [--svg out.svg] [--scale N]
const fs = require('fs');
const { CSG, CAG } = require('@jscad/csg');

const argv = process.argv.slice(2);
const file = argv[0];
const opt = (name, dflt) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 ? argv[i + 1] : dflt;
};

// ---- OpenJSCAD v1 free-function shims -------------------------------------
const toArr = (a) => (Array.isArray(a[0]) ? a[0] : a);
const globals = {
  CSG, CAG,
  translate: (v, o) => o.translate(v),
  rotate: (v, o) => o.rotate([0, 0, 0], [0, 0, 1], v[2]).rotate([0, 0, 0], [1, 0, 0], v[0]).rotate([0, 0, 0], [0, 1, 0], v[1]),
  scale: (v, o) => o.scale(v),
  union: (...a) => toArr(a).reduce((x, y) => x.union(y)),
  subtract: (...a) => toArr(a).reduce((x, y) => x.subtract(y)),
  intersect: (...a) => toArr(a).reduce((x, y) => x.intersect(y)),
  difference: (...a) => toArr(a).reduce((x, y) => x.subtract(y)),
  console,
};
// Run in the host realm: a vm context would break `x instanceof Array`
// checks inside @jscad/csg for arrays created by the script.
const names = Object.keys(globals);
const body = fs.readFileSync(file, 'utf8') + '\n;return main();';
const solid = new Function(...names, body)(...names.map((n) => globals[n]));

const polys = solid.toPolygons();
const b = solid.getBounds();
console.log(`polygons: ${polys.length}`);
console.log(`bounds  : x ${b[0].x.toFixed(2)} .. ${b[1].x.toFixed(2)}  (${(b[1].x - b[0].x).toFixed(2)})`);
console.log(`          y ${b[0].y.toFixed(2)} .. ${b[1].y.toFixed(2)}  (${(b[1].y - b[0].y).toFixed(2)})`);
console.log(`          z ${b[0].z.toFixed(2)} .. ${b[1].z.toFixed(2)}  (${(b[1].z - b[0].z).toFixed(2)})`);

// signed volume, to catch inverted / broken solids
let vol = 0;
for (const p of polys) {
  const v = p.vertices;
  for (let i = 1; i < v.length - 1; i++) {
    const a = v[0].pos, c = v[i].pos, d = v[i + 1].pos;
    vol += (a.x * (c.y * d.z - d.y * c.z) - a.y * (c.x * d.z - d.x * c.z) + a.z * (c.x * d.y - d.x * c.y)) / 6;
  }
}
console.log(`volume  : ${vol.toFixed(1)} mm^3`);

// ---- STL ------------------------------------------------------------------
const stl = opt('stl');
if (stl) {
  const tris = [];
  for (const p of polys) {
    const v = p.vertices;
    for (let i = 1; i < v.length - 1; i++) tris.push([v[0].pos, v[i].pos, v[i + 1].pos]);
  }
  const buf = Buffer.alloc(84 + tris.length * 50);
  buf.writeUInt32LE(tris.length, 80);
  let o = 84;
  for (const t of tris) {
    o += 12; // zero normal is legal
    for (const p of t) { buf.writeFloatLE(p.x, o); buf.writeFloatLE(p.y, o + 4); buf.writeFloatLE(p.z, o + 8); o += 12; }
    o += 2;
  }
  fs.writeFileSync(stl, buf);
  console.log(`wrote ${stl} (${tris.length} triangles)`);
}

// ---- point-in-solid probes ------------------------------------------------
// --probe "label:x,y,z;label:x,y,z"   ray casts +z and reports solid/empty
const probe = opt('probe');
if (probe) {
  const tris = [];
  for (const p of polys) {
    const v = p.vertices;
    for (let i = 1; i < v.length - 1; i++) tris.push([v[0].pos, v[i].pos, v[i + 1].pos]);
  }
  const inside = (px, py, pz) => {
    let n = 0;
    for (const [a, b, c] of tris) {
      // 2D point-in-triangle in xy, then count faces strictly above pz
      const d = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
      if (Math.abs(d) < 1e-12) continue;
      const l1 = ((b.y - c.y) * (px - c.x) + (c.x - b.x) * (py - c.y)) / d;
      const l2 = ((c.y - a.y) * (px - c.x) + (a.x - c.x) * (py - c.y)) / d;
      const l3 = 1 - l1 - l2;
      if (l1 < 0 || l2 < 0 || l3 < 0) continue;
      if (l1 * a.z + l2 * b.z + l3 * c.z > pz) n++;
    }
    return n % 2 === 1;
  };
  for (const spec of probe.split(';')) {
    const [label, coords] = spec.includes(':') ? spec.split(':') : ['', spec];
    const [px, py, pz] = coords.split(',').map(Number);
    console.log(`  ${(label || coords).padEnd(34)} (${px}, ${py}, ${pz})  ->  ${inside(px, py, pz) ? 'SOLID' : 'empty'}`);
  }
}

// ---- planar cross sections ------------------------------------------------
// --cut z=5 | x=263 | y=-100   (repeatable, comma separated)
const cuts = opt('cut');
if (cuts) {
  const AX = { x: 0, y: 1, z: 2 };
  const segsByCut = [];
  for (const spec of cuts.split(',')) {
    const [an, vs] = spec.split('=');
    const ai = AX[an.trim()], val = parseFloat(vs);
    const other = [0, 1, 2].filter((i) => i !== ai);
    const segs = [];
    for (const p of polys) {
      const pts = p.vertices.map((v) => [v.pos.x, v.pos.y, v.pos.z]);
      const hits = [];
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i], c = pts[(i + 1) % pts.length];
        const da = a[ai] - val, dc = c[ai] - val;
        if ((da > 0 && dc > 0) || (da < 0 && dc < 0)) continue;
        if (da === 0 && dc === 0) continue;
        const t = da / (da - dc);
        hits.push([a[other[0]] + t * (c[other[0]] - a[other[0]]), a[other[1]] + t * (c[other[1]] - a[other[1]])]);
      }
      if (hits.length >= 2) segs.push([hits[0], hits[hits.length - 1]]);
    }
    const crop = opt('crop');
    const kept = crop
      ? (() => { const [a0, b0, a1, b1] = crop.split(',').map(Number);
          return segs.filter((s) => s.every((pt) => pt[0] >= a0 && pt[0] <= a1 && pt[1] >= b0 && pt[1] <= b1)); })()
      : segs;
    segsByCut.push({ label: spec, axes: other.map((i) => 'xyz'[i]), segs: kept });
    console.log(`cut ${spec}: ${segs.length} segments (${kept.length} after crop)`);
  }

  const svgOut = opt('svg');
  if (svgOut) {
    const S = parseFloat(opt('scale', '6'));
    const parts = [];
    let yCursor = 0;
    for (const c of segsByCut) {
      const xs = c.segs.flatMap((s) => [s[0][0], s[1][0]]);
      const ys = c.segs.flatMap((s) => [s[0][1], s[1][1]]);
      if (!xs.length) continue;
      const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2;
      const y0 = Math.min(...ys) - 2, y1 = Math.max(...ys) + 2;
      const g = [`<g transform="translate(0,${yCursor})">`,
        `<text x="2" y="12" font-size="11" font-family="monospace" fill="#c00">${c.label}  (${c.axes[0]} right, ${c.axes[1]} up)</text>`];
      for (const s of c.segs) {
        g.push(`<line x1="${((s[0][0] - x0) * S).toFixed(2)}" y1="${((y1 - s[0][1]) * S + 16).toFixed(2)}" x2="${((s[1][0] - x0) * S).toFixed(2)}" y2="${((y1 - s[1][1]) * S + 16).toFixed(2)}" stroke="#000" stroke-width="1.2"/>`);
      }
      g.push('</g>');
      parts.push(g.join('\n'));
      yCursor += (y1 - y0) * S + 26;
    }
    const W = Math.max(...segsByCut.map((c) => {
      const xs = c.segs.flatMap((s) => [s[0][0], s[1][0]]);
      return xs.length ? (Math.max(...xs) - Math.min(...xs) + 4) * S : 0;
    }));
    fs.writeFileSync(svgOut,
      `<svg xmlns="http://www.w3.org/2000/svg" width="${W.toFixed(0)}" height="${yCursor.toFixed(0)}" style="background:#fff">` +
      `<rect width="100%" height="100%" fill="#fff"/>` + parts.join('\n') + '</svg>');
    console.log(`wrote ${svgOut}`);
  }
}

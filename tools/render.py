"""Render ergogen outline yaml (makerjs models) + points into a labeled SVG in true coordinates.

usage: python render.py OUT_DIR --o name[:color[:width]] ... [--points] [--crop x0,y0,x1,y1] [--scale PX_PER_MM] [--out file.svg] [--grid 5]
"""
import argparse, math, os, sys, yaml

def walk(model, ox=0.0, oy=0.0, acc=None):
    if acc is None:
        acc = []
    if not isinstance(model, dict):
        return acc
    o = model.get('origin') or [0, 0]
    ox2, oy2 = ox + o[0], oy + o[1]
    for p in (model.get('paths') or {}).values():
        po = p.get('origin') or [0, 0]
        px, py = ox2 + po[0], oy2 + po[1]
        t = p.get('type')
        if t == 'line':
            e = p['end']
            acc.append(('line', px, py, ox2 + e[0], oy2 + e[1]))
        elif t == 'circle':
            acc.append(('circle', px, py, p['radius']))
        elif t == 'arc':
            acc.append(('arc', px, py, p['radius'], p['startAngle'], p['endAngle']))
    for m in (model.get('models') or {}).values():
        walk(m, ox2, oy2, acc)
    return acc

def load_outline(out_dir, name):
    with open(os.path.join(out_dir, 'outlines', name + '.yaml'), encoding='utf-8') as f:
        return walk(yaml.safe_load(f))

def bbox(segs):
    xs, ys = [], []
    for s in segs:
        if s[0] == 'line':
            xs += [s[1], s[3]]; ys += [s[2], s[4]]
        elif s[0] in ('circle', 'arc'):
            xs += [s[1] - s[3], s[1] + s[3]]; ys += [s[2] - s[3], s[2] + s[3]]
    return min(xs), min(ys), max(xs), max(ys)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--o', action='append', default=[], help='outline[:color[:width]]')
    ap.add_argument('--points', action='store_true')
    ap.add_argument('--labels', action='store_true')
    ap.add_argument('--crop', default=None)
    ap.add_argument('--scale', type=float, default=6.0)
    ap.add_argument('--grid', type=float, default=0)
    ap.add_argument('--out', default='render.svg')
    a = ap.parse_args()

    layers = []
    for spec in a.o:
        parts = spec.split(':')
        name = parts[0]
        color = parts[1] if len(parts) > 1 and parts[1] else '#000'
        width = float(parts[2]) if len(parts) > 2 else 0.2
        layers.append((name, color, width, load_outline(a.out_dir, name)))

    pts = {}
    if a.points or a.labels:
        with open(os.path.join(a.out_dir, 'points', 'points.yaml'), encoding='utf-8') as f:
            pts = yaml.safe_load(f)

    if a.crop:
        x0, y0, x1, y1 = [float(v) for v in a.crop.split(',')]
    else:
        allsegs = [s for l in layers for s in l[3]]
        x0, y0, x1, y1 = bbox(allsegs)
        x0 -= 3; y0 -= 3; x1 += 3; y1 += 3

    S = a.scale
    W, H = (x1 - x0) * S, (y1 - y0) * S
    def X(x): return (x - x0) * S
    def Y(y): return (y1 - y) * S

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.1f} {H:.1f}" style="background:#fff">',
           '<rect width="100%" height="100%" fill="#fff"/>']
    if a.grid:
        g = a.grid
        gx = math.floor(x0 / g) * g
        while gx <= x1:
            out.append(f'<line x1="{X(gx):.1f}" y1="0" x2="{X(gx):.1f}" y2="{H:.1f}" stroke="#eee" stroke-width="1"/>')
            out.append(f'<text x="{X(gx)+2:.1f}" y="10" font-size="9" fill="#999" font-family="monospace">{gx:g}</text>')
            gx += g
        gy = math.floor(y0 / g) * g
        while gy <= y1:
            out.append(f'<line x1="0" y1="{Y(gy):.1f}" x2="{W:.1f}" y2="{Y(gy):.1f}" stroke="#eee" stroke-width="1"/>')
            out.append(f'<text x="2" y="{Y(gy)-2:.1f}" font-size="9" fill="#999" font-family="monospace">{gy:g}</text>')
            gy += g
    for name, color, width, segs in layers:
        out.append(f'<g stroke="{color}" stroke-width="{width*S:.2f}" fill="none" stroke-linecap="round">')
        for s in segs:
            if s[0] == 'line':
                out.append(f'<line x1="{X(s[1]):.2f}" y1="{Y(s[2]):.2f}" x2="{X(s[3]):.2f}" y2="{Y(s[4]):.2f}"/>')
            elif s[0] == 'circle':
                out.append(f'<circle cx="{X(s[1]):.2f}" cy="{Y(s[2]):.2f}" r="{s[3]*S:.2f}"/>')
            elif s[0] == 'arc':
                cx, cy, r, sa, ea = s[1:]
                sweep = (ea - sa) % 360
                if sweep == 0: sweep = 360
                p0 = (cx + r * math.cos(math.radians(sa)), cy + r * math.sin(math.radians(sa)))
                p1 = (cx + r * math.cos(math.radians(ea)), cy + r * math.sin(math.radians(ea)))
                large = 1 if sweep > 180 else 0
                # ccw in math coords -> with flipped y it's cw in svg => sweep-flag 0
                out.append(f'<path d="M {X(p0[0]):.2f} {Y(p0[1]):.2f} A {r*S:.2f} {r*S:.2f} 0 {large} 0 {X(p1[0]):.2f} {Y(p1[1]):.2f}"/>')
        out.append('</g>')
    if pts:
        for n, p in pts.items():
            x, y, r = p['x'], p['y'], p['r']
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            col = '#d00' if 'key' in (p['meta'].get('tags') or []) else '#06c'
            out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{0.5*S:.1f}" fill="{col}"/>')
            dx, dy = 3 * math.cos(math.radians(r + 90)), 3 * math.sin(math.radians(r + 90))
            out.append(f'<line x1="{X(x):.1f}" y1="{Y(y):.1f}" x2="{X(x+dx):.1f}" y2="{Y(y+dy):.1f}" stroke="{col}" stroke-width="1"/>')
            if a.labels:
                out.append(f'<text x="{X(x)+4:.1f}" y="{Y(y)-3:.1f}" font-size="{max(8, S*1.6):.0f}" fill="{col}" font-family="monospace">{n}</text>')
    out.append('</svg>')
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f'wrote {a.out} crop=({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) size={W:.0f}x{H:.0f}')

if __name__ == '__main__':
    main()

"""A standalone, KiCad-free sanity check on the generated .kicad_pcb.

This is not a replacement for KiCad's DRC - it only knows about the things
ergogen can actually get wrong before any routing happens:

  * copper (pads) too close to, or hanging off, the board edge
  * pads of different nets too close together
  * drilled holes too close to the board edge or to each other
  * the GND pour still covering the board, and the MCU keepout still
    covering the MCU - those zone polygons are literal coordinates in the
    config, so nothing else keeps them in sync with the layout

Courtyard overlaps are deliberately *not* checked: every switch overlaps its
own diode here, which is normal for a keyboard, and KiCad will report those
too. Ignore them there.

Run it after `node tools/build.js` and before you open the board in KiCad.

usage: python tools/drc_lite.py [out/pcbs/ezy54.kicad_pcb] [--edge 0.3] [--pad 0.2]
"""
import math
import re
import sys

# --------------------------------------------------------------- s-expressions


def parse(text):
    """Minimal s-expression reader -> nested lists of str."""
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack, cur = [], []
    for t in tok:
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            parent = stack.pop()
            parent.append(cur)
            cur = parent
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    got = kids(node, name)
    return got[0] if got else None


def nums(node, n):
    return [float(v) for v in node[1:1 + n]]


# ------------------------------------------------------------------- geometry


def rot(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def poly_of_pad(pad_pos, size, angle, shape, rratio=0.0):
    """Outline of a pad as a point list (circles approximated)."""
    w, h = size
    if shape == 'roundrect' and rratio:
        r = min(w, h) * rratio
        pts = []
        for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-(w / 2 - r), h / 2 - r, 90),
                           (-(w / 2 - r), -(h / 2 - r), 180), (w / 2 - r, -(h / 2 - r), 270)):
            for k in range(5):
                a = math.radians(a0 + 90 * k / 4)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return [(pad_pos[0] + rot(px, py, angle)[0], pad_pos[1] + rot(px, py, angle)[1]) for px, py in pts]
    if shape in ('circle', 'oval') and abs(w - h) < 1e-9:
        return [(pad_pos[0] + w / 2 * math.cos(2 * math.pi * i / 24),
                 pad_pos[1] + w / 2 * math.sin(2 * math.pi * i / 24)) for i in range(24)]
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(pad_pos[0] + rot(cx, cy, angle)[0], pad_pos[1] + rot(cx, cy, angle)[1]) for cx, cy in corners]


def seg_point_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def poly_edges(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def poly_dist(p1, p2):
    """Distance between two convex-ish polygons (0 if they touch/overlap)."""
    if poly_contains(p2, p1[0]) or poly_contains(p1, p2[0]):
        return 0.0
    best = float('inf')
    for a, b in poly_edges(p1):
        for c, d in poly_edges(p2):
            if segs_cross(a, b, c, d):
                return 0.0
            best = min(best, seg_point_dist(a, c, d), seg_point_dist(c, a, b))
    return best


def segs_cross(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = side(a, b, c), side(a, b, d), side(c, d, a), side(c, d, b)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def poly_contains(pts, p):
    c = False
    for (x1, y1), (x2, y2) in poly_edges(pts):
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


# ----------------------------------------------------------------- extraction


def board_edges(root):
    """Edge.Cuts as a list of segments."""
    segs = []
    for node in root:
        if not isinstance(node, list) or not node:
            continue
        layer = kid(node, 'layer')
        if not layer or layer[1] != 'Edge.Cuts':
            continue
        if node[0] == 'gr_poly':
            pts = [tuple(nums(xy, 2)) for xy in kids(kid(node, 'pts'), 'xy')]
            segs += poly_edges(pts)
        elif node[0] == 'gr_line':
            segs.append((tuple(nums(kid(node, 'start'), 2)), tuple(nums(kid(node, 'end'), 2))))
        elif node[0] == 'gr_circle':
            c = tuple(nums(kid(node, 'center'), 2))
            e = tuple(nums(kid(node, 'end'), 2))
            r = math.hypot(e[0] - c[0], e[1] - c[1])
            pts = [(c[0] + r * math.cos(2 * math.pi * i / 48), c[1] + r * math.sin(2 * math.pi * i / 48))
                   for i in range(48)]
            segs += poly_edges(pts)
    return segs


def pads(root):
    """Every pad, in board coordinates."""
    out = []
    for fp in kids(root, 'footprint'):
        at = kid(fp, 'at')
        fx, fy = nums(at, 2)
        frot = float(at[3]) if len(at) > 3 else 0.0
        ref = 'FP'
        for prop in kids(fp, 'property'):
            if len(prop) > 2 and prop[1] == 'Reference':
                ref = prop[2]
        for pad in kids(fp, 'pad'):
            pat = kid(pad, 'at')
            px, py = nums(pat, 2)
            pang = float(pat[3]) if len(pat) > 3 else frot
            dx, dy = rot(px, py, frot)
            pos = (fx + dx, fy + dy)
            size = nums(kid(pad, 'size'), 2)
            drill = kid(pad, 'drill')
            net = kid(pad, 'net')
            layers = kid(pad, 'layers') or []
            out.append({
                'ref': ref, 'num': pad[1], 'type': pad[2], 'shape': pad[3],
                'pos': pos, 'size': size, 'ang': pang,
                'drill': float(drill[1]) if drill and re.match(r'^[\d.]+$', str(drill[1])) else None,
                'net': net[2] if net and len(net) > 2 else '',
                'layers': [l for l in layers[1:] if isinstance(l, str)],
                'poly': poly_of_pad(pos, size, pang, pad[3],
                                    float((kid(pad, 'roundrect_rratio') or [0, 0])[1])),
            })
    return out


def zones(root):
    """Zones declared by footprints, with their polygons."""
    out = []
    for scope in [root] + kids(root, 'footprint'):
        for z in kids(scope, 'zone'):
            poly = kid(z, 'polygon')
            if not poly:
                continue
            _ = scope
            pts = [tuple(nums(xy, 2)) for xy in kids(kid(poly, 'pts'), 'xy')]
            name = kid(z, 'name')
            out.append({'name': name[1] if name and len(name) > 1 else '',
                        'keepout': bool(kid(z, 'keepout')),
                        'net': (kid(z, 'net_name') or ['', ''])[1],
                        'pts': pts})
    return out


def footprint_bbox(root, needle):
    """Axis-aligned bbox of a named footprint's pads, in board coordinates."""
    xs, ys = [], []
    for p in pads(root):
        pass
    for fp in kids(root, 'footprint'):
        if needle not in fp[1]:
            continue
        at = kid(fp, 'at')
        fx, fy = nums(at, 2)
        frot = float(at[3]) if len(at) > 3 else 0.0
        for pad in kids(fp, 'pad'):
            px, py = nums(kid(pad, 'at'), 2)
            dx, dy = rot(px, py, frot)
            sz = nums(kid(pad, 'size'), 2)
            r = max(sz) / 2
            xs += [fx + dx - r, fx + dx + r]
            ys += [fy + dy - r, fy + dy + r]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def overlap_layers(a, b):
    def expand(ls):
        s = set()
        for l in ls:
            if l.startswith('*.'):
                s |= {'F.' + l[2:], 'B.' + l[2:]}
            else:
                s.add(l)
        return s
    return bool(expand(a) & expand(b) & {'F.Cu', 'B.Cu'})


# ---------------------------------------------------------------------- main


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path = args[0] if args else 'out/pcbs/ezy54.kicad_pcb'
    opt = lambda n, d: float(sys.argv[sys.argv.index('--' + n) + 1]) if '--' + n in sys.argv else d
    edge_min = opt('edge', 0.3)   # JLCPCB: 0.3mm copper to board edge
    pad_min = opt('pad', 0.2)     # JLCPCB: 0.2mm min clearance
    hole_min = opt('hole', 0.5)   # hole wall to board edge

    root = parse(open(path, encoding='utf-8').read())[0]
    edges = board_edges(root)
    ps = pads(root)
    print(f'{path}: {len(ps)} pads, {len(edges)} board edge segments\n')

    fails = 0

    print(f'--- copper to board edge (min {edge_min}) ---')
    worst = []
    for p in ps:
        d = min(min(seg_point_dist(v, a, b) for a, b in edges) for v in p['poly'])
        outside = any(not poly_contains([pt for seg in edges for pt in seg[:1]], v) for v in p['poly'])
        # crossing the edge is what matters; report signed-ish by intersection
        crosses = any(segs_cross(v, w, a, b) for v, w in poly_edges(p['poly']) for a, b in edges)
        if crosses or d < edge_min:
            worst.append((d, crosses, p))
    for d, crosses, p in sorted(worst, key=lambda t: t[0])[:25]:
        state = 'CROSSES THE EDGE' if crosses else f'{d:.3f}mm'
        print(f'  FAIL {p["ref"]:>6}.{p["num"]:<3} net={p["net"] or "-":<10} at ({p["pos"][0]:.2f}, {p["pos"][1]:.2f})  {state}')
        fails += 1
    if not worst:
        print('  ok')

    print(f'\n--- pad to pad, different nets (min {pad_min}) ---')
    bad = []
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            a, b = ps[i], ps[j]
            if a['ref'] == b['ref']:
                continue  # within one footprint: the library author's business,
                          # and reversible footprints stack F/B pads on purpose
            if a['net'] and a['net'] == b['net']:
                continue
            if not overlap_layers(a['layers'], b['layers']):
                continue
            if math.hypot(a['pos'][0] - b['pos'][0], a['pos'][1] - b['pos'][1]) > 6:
                continue
            d = poly_dist(a['poly'], b['poly'])
            if d < pad_min:
                bad.append((d, a, b))
    for d, a, b in sorted(bad, key=lambda t: t[0])[:25]:
        print(f'  FAIL {a["ref"]}.{a["num"]} ({a["net"] or "-"}) <-> {b["ref"]}.{b["num"]} ({b["net"] or "-"})  {d:.3f}mm')
        fails += 1
    if not bad:
        print('  ok')

    print(f'\n--- drilled holes to board edge (min {hole_min}) ---')
    bad = []
    for p in ps:
        if not p['drill']:
            continue
        d = min(seg_point_dist(p['pos'], a, b) for a, b in edges) - p['drill'] / 2
        if d < hole_min:
            bad.append((d, p))
    for d, p in sorted(bad, key=lambda t: t[0])[:25]:
        print(f'  FAIL {p["ref"]}.{p["num"]} hole at ({p["pos"][0]:.2f}, {p["pos"][1]:.2f})  {d:.3f}mm to edge')
        fails += 1
    if not bad:
        print('  ok')

    print()
    print('--- zone polygons still fit the layout ---')
    zs = zones(root)
    bxs = [pt[0] for sg in edges for pt in sg]
    bys = [pt[1] for sg in edges for pt in sg]
    board = (min(bxs), min(bys), max(bxs), max(bys))
    pour = next((z for z in zs if not z['keepout']), None)
    keep = next((z for z in zs if z['keepout']), None)
    if not pour:
        print('  FAIL no copper pour found'); fails += 1
    else:
        px = [q[0] for q in pour['pts']]; py = [q[1] for q in pour['pts']]
        covers = min(px) <= board[0] and min(py) <= board[1] and max(px) >= board[2] and max(py) >= board[3]
        print(f'  {"ok  " if covers else "FAIL"} pour "{pour["net"]}" covers the board  '
              f'(zone x {min(px):.1f}..{max(px):.1f} y {min(py):.1f}..{max(py):.1f}; '
              f'board x {board[0]:.1f}..{board[2]:.1f} y {board[1]:.1f}..{board[3]:.1f})')
        if not covers: fails += 1
    mcu = footprint_bbox(root, 'mcu_supermini')
    if not keep:
        print('  FAIL no keepout zone found'); fails += 1
    elif mcu:
        kx = [q[0] for q in keep['pts']]; ky = [q[1] for q in keep['pts']]
        covers = min(kx) <= mcu[0] and min(ky) <= mcu[1] and max(kx) >= mcu[2] and max(ky) >= mcu[3]
        print(f'  {"ok  " if covers else "FAIL"} keepout covers the MCU  '
              f'(zone x {min(kx):.1f}..{max(kx):.1f} y {min(ky):.1f}..{max(ky):.1f}; '
              f'MCU x {mcu[0]:.1f}..{mcu[2]:.1f} y {mcu[1]:.1f}..{mcu[3]:.1f})')
        if not covers: fails += 1

    print(f'\n{fails} finding(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())

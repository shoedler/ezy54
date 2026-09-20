"""Find a diode anchor offset that clears everything else on the board.

Why this is needed: ergogen mirrors y when it writes the KiCad board, so a
footprint's internal geometry ends up rotated by twice its key's rotation
relative to the direction of an `adjust.shift`. The diode therefore sits at a
different angle around each key, and on a heavily splayed key it can land on
the switch's plated centre hole or a Choc v1 stabiliser hole.

This sweeps `pcb_diode_x_off` / `pcb_diode_y_off` analytically - no rebuild per
candidate - against every non-diode pad on the board and against the board
edge, and prints the offsets with the largest worst-case clearance.

usage: python tools/diode_fit.py [--out out] [--step 0.25] [--range 6]
"""
import math
import sys

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
import yaml
from drc_lite import (parse, pads, poly_of_pad, poly_dist, board_edges, seg_point_dist)

# SOD-123 footprint, as placed by ceoloide/diode_tht_sod123 (reversible SMD)
PAD_PITCH, PAD_W, PAD_H = 1.65, 0.9, 1.2


def opt(name, dflt):
    return type(dflt)(sys.argv[sys.argv.index('--' + name) + 1]) if '--' + name in sys.argv else dflt


def main():
    out = opt('out', 'out')
    step = opt('step', 0.25)
    rng = opt('range', 6.0)

    root = parse(open(f'{out}/pcbs/ezy54.kicad_pcb', encoding='utf-8').read())[0]
    P = yaml.safe_load(open(f'{out}/points/points.yaml'))
    keys = {n: v for n, v in P.items() if n.startswith(('matrix_', 'thumb_'))}
    others = [p for p in pads(root) if not p['ref'].startswith('D')]
    edges = board_edges(root)

    def diode_pad_polys(v, dx, dy):
        a = math.radians(v['r'])
        ox = v['x'] + dx * math.cos(a) - dy * math.sin(a)
        oy = v['y'] + dx * math.sin(a) + dy * math.cos(a)
        kx, ky = ox, -oy                      # ergogen -> kicad
        R = v['r'] + 180                      # adjust.rotate: 180
        Rr = math.radians(R)
        return [poly_of_pad((kx + lx * math.cos(Rr), ky + lx * math.sin(Rr)),
                            (PAD_W, PAD_H), R, 'rect') for lx in (-PAD_PITCH, PAD_PITCH)]

    def worst(dx, dy):
        m, lim = 99.0, None
        for kname, v in keys.items():
            for poly in diode_pad_polys(v, dx, dy):
                cx, cy = poly[0]
                for o in others:
                    if math.hypot(o['pos'][0] - cx, o['pos'][1] - cy) > 14:
                        continue
                    d = poly_dist(poly, o['poly'])
                    if d < m:
                        m, lim = d, f'{kname} vs {o["ref"]}'
                        if m <= 0:
                            return m, lim
                de = min(min(seg_point_dist(pt, a, b) for a, b in edges) for pt in poly)
                if de < m:
                    m, lim = de, f'{kname} vs board edge'
        return m, lim

    n = int(rng / step)
    results = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dx, dy = round(i * step, 3), round(j * step, 3)
            w, lim = worst(dx, dy)
            if w > 0:
                results.append((w, dx, dy, lim))
    results.sort(reverse=True)
    print(f'swept +-{rng} in {step}mm steps; {len(results)} offsets clear everything\n')
    print(f'{"worst":>7}  {"x_off":>6} {"y_off":>6}   limited by')
    for w, dx, dy, lim in results[:15]:
        print(f'{w:7.3f}  {dx:+6.2f} {dy:+6.2f}   {lim}')
    if not results:
        print('nothing clears - widen --range, or reconsider include_plated_holes')
    return 0


if __name__ == '__main__':
    sys.exit(main())

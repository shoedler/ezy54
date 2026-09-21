"""Pin down drc_lite's footprint rotation against KiCad's own output.

KiCad footprint angles are counter-clockwise as displayed, but the file's y
axis points down, so rotating a footprint-local offset into board coordinates
is a rotation by *minus* the angle. Getting that sign backwards silently
misplaces the pads of every rotated footprint - which happened here, and cost
a PCB revision - so it is worth a test.

The test compares drc_lite's computed hole positions against the coordinates in
a KiCad-generated Excellon drill file. Non-plated holes are used because their
coordinates come straight from the footprint with no routing in between.

By default it reads the drill file straight out of the committed
kicad/gerber.zip, so it works on a fresh clone with no KiCad installed.

usage: python tools/test_rotation.py [drill-file-or-zip] [kicad/ezy54.kicad_pcb]
"""
import io
import math
import re
import sys
import zipfile

sys.path.insert(0, __file__.replace('\\', '/').rsplit('/', 1)[0])
from drc_lite import parse, pads

TOL = 0.02  # mm; drill files round to 3 decimals


def drill_lines(path):
    """Lines of an Excellon file, read from a .drl or from inside a .zip."""
    if path.lower().endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            name = next((n for n in z.namelist() if n.upper().endswith('NPTH.DRL')), None)
            if not name:
                raise FileNotFoundError(f'no *NPTH.drl inside {path}')
            return io.TextIOWrapper(io.BytesIO(z.read(name)), encoding='utf-8')
    return open(path, encoding='utf-8')


def drilled(path):
    """Every hole in an Excellon file, as (x, y_in_pcb_coords, diameter)."""
    tools, cur, out = {}, None, []
    for line in drill_lines(path):
        line = line.strip()
        m = re.match(r'^T(\d+)C([\d.]+)$', line)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r'^T(\d+)$', line)
        if m:
            cur = tools.get(m.group(1))
            continue
        m = re.match(r'^X(-?[\d.]+)Y(-?[\d.]+)$', line)
        if m and cur:
            # drill files are y-up; the .kicad_pcb is y-down
            out.append((float(m.group(1)), -float(m.group(2)), cur))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    drl = args[0] if args else 'kicad/gerber.zip'
    pcb = args[1] if len(args) > 1 else 'kicad/ezy54.kicad_pcb'

    try:
        holes = drilled(drl)
    except (FileNotFoundError, KeyError) as e:
        print(f'skipped: no drill file in {drl} ({e})')
        print('(export gerbers + drill files from KiCad to enable this test)')
        return 0
    if not holes:
        print(f'skipped: no holes found in {drl}')
        return 0

    root = parse(open(pcb, encoding='utf-8', errors='replace').read())[0]
    # non-plated holes only: a pad with a drill and no net
    mine = [p for p in pads(root) if p['drill'] and not p['net']]

    print(f'{len(holes)} holes in {drl}')
    print(f'{len(mine)} un-netted drilled pads in {pcb}\n')

    worst, bad = 0.0, []
    for hx, hy, dia in holes:
        cands = [p for p in mine if abs(p['drill'] - dia) < 0.01]
        if not cands:
            bad.append((f'{dia}mm hole at ({hx:.3f}, {hy:.3f})', 'no pad of that diameter'))
            continue
        d = min(math.hypot(p['pos'][0] - hx, p['pos'][1] - hy) for p in cands)
        worst = max(worst, d)
        if d > TOL:
            bad.append((f'{dia}mm hole at ({hx:.3f}, {hy:.3f})', f'nearest computed pad {d:.3f}mm away'))

    for what, why in bad[:15]:
        print(f'  FAIL {what}: {why}')
    if bad:
        print(f'\n{len(bad)} mismatch(es); worst matched offset {worst:.3f}mm (tolerance {TOL})')
        print('The footprint rotation convention in drc_lite.rot() is the usual cause.')
        return 1
    print(f'  ok   every drilled hole matches a computed pad (worst {worst:.4f}mm, tolerance {TOL})')
    return 0


if __name__ == '__main__':
    sys.exit(main())

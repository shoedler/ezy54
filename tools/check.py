"""Geometric assertions for the ezy54 outputs.

usage: python check.py [out_dir]
"""
import math, sys, yaml
sys.path.insert(0, '.')
from render import walk

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
P = yaml.safe_load(open(f'{OUT}/points/points.yaml'))
U = yaml.safe_load(open(f'{OUT}/points/units.yaml'))


def outline(name):
    return walk(yaml.safe_load(open(f'{OUT}/outlines/{name}.yaml')))


def pts(segs, n=60):
    """Dense sample of an outline's boundary."""
    out = []
    for s in segs:
        if s[0] == 'line':
            for i in range(n + 1):
                t = i / n
                out.append((s[1] + t * (s[3] - s[1]), s[2] + t * (s[4] - s[2])))
        elif s[0] == 'circle':
            for i in range(n):
                a = 2 * math.pi * i / n
                out.append((s[1] + s[3] * math.cos(a), s[2] + s[3] * math.sin(a)))
        elif s[0] == 'arc':
            cx, cy, r, sa, ea = s[1:]
            sweep = (ea - sa) % 360 or 360
            for i in range(n + 1):
                a = math.radians(sa + sweep * i / n)
                out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def inside(segs, px, py):
    c = False
    for s in segs:
        if s[0] != 'line':
            continue
        x1, y1, x2, y2 = s[1], s[2], s[3], s[4]
        if (y1 > py) != (y2 > py):
            if px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                c = not c
    return c


def seg_dist(p, s):
    if s[0] == 'circle':
        return abs(math.hypot(p[0] - s[1], p[1] - s[2]) - s[3])
    if s[0] == 'arc':
        return abs(math.hypot(p[0] - s[1], p[1] - s[2]) - s[3])
    x1, y1, x2, y2 = s[1], s[2], s[3], s[4]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / L2))
    return math.hypot(p[0] - (x1 + t * dx), p[1] - (y1 + t * dy))


def gap(a_segs, b_segs, n=60):
    """Minimum distance between two outlines' boundaries."""
    return min(min(seg_dist(p, s) for s in b_segs) for p in pts(a_segs, n))


def contained(inner, outer, eps=0.05, n=60):
    """Every point of `inner`, nudged inward, lies within `outer`. Returns #violations.

    Circles are nudged toward their own centre, everything else toward the
    outline's centroid - otherwise a shape made of several disjoint pieces
    (the two screw bosses) gets nudged sideways instead of inward.
    """
    allp = pts(inner, n)
    gx = sum(p[0] for p in allp) / len(allp)
    gy = sum(p[1] for p in allp) / len(allp)
    bad = 0
    for s in inner:
        cx, cy = (s[1], s[2]) if s[0] in ('circle', 'arc') else (gx, gy)
        for x, y in pts([s], n):
            d = math.hypot(cx - x, cy - y) or 1
            if not inside(outer, x + (cx - x) / d * eps, y + (cy - y) / d * eps):
                bad += 1
    return bad


def ok(cond):
    return 'ok  ' if cond else 'FAIL'


pcb = outline('ezy54')
shroud = outline('_shroud_outer')
cavity = outline('_shroud_inner')
caps = outline('_pcb_keycaps')
bosses = outline('_shroud_bosses')
bat = outline('_pcb_bat')

print('=== containment ===')
v = contained(shroud, pcb)
print(f'  {ok(v == 0)} housing inside the PCB outline            ({v} violations)')
v = contained(cavity, shroud)
print(f'  {ok(v == 0)} cavity inside the housing                  ({v} violations)')
v = contained(bosses, cavity)
print(f'  {ok(v == 0)} screw bosses inside the cavity             ({v} violations)')
v = contained(bat, cavity)
print(f'  {ok(v == 0)} battery + connector inside the cavity      ({v} violations)')

print('\n=== clearances (mm) ===')
g = gap(shroud, caps)
print(f'  housing outer wall  -> nearest keycap      {g:6.2f}   (target {U["mcu_col_gap"]})')
g = gap(bosses, bat)
print(f'  screw boss          -> battery/connector   {g:6.2f}   (target {U["bat_gap"]})')
g = gap(bosses, cavity)
print(f'  screw boss          -> cavity wall         {g:6.2f}')
mcu_rect = [('line', *a, *b) for a, b in zip(
    [(P['mcu']['x'] + dx * math.cos(math.radians(P['mcu']['r'])) - dy * math.sin(math.radians(P['mcu']['r'])),
      P['mcu']['y'] + dx * math.sin(math.radians(P['mcu']['r'])) + dy * math.cos(math.radians(P['mcu']['r'])))
     for dx, dy in [(-U['mcu_w'] / 2, -U['mcu_h'] / 2), (U['mcu_w'] / 2, -U['mcu_h'] / 2),
                    (U['mcu_w'] / 2, U['mcu_h'] / 2), (-U['mcu_w'] / 2, U['mcu_h'] / 2)]],
    [(P['mcu']['x'] + dx * math.cos(math.radians(P['mcu']['r'])) - dy * math.sin(math.radians(P['mcu']['r'])),
      P['mcu']['y'] + dx * math.sin(math.radians(P['mcu']['r'])) + dy * math.cos(math.radians(P['mcu']['r'])))
     for dx, dy in [(U['mcu_w'] / 2, -U['mcu_h'] / 2), (U['mcu_w'] / 2, U['mcu_h'] / 2),
                    (-U['mcu_w'] / 2, U['mcu_h'] / 2), (-U['mcu_w'] / 2, -U['mcu_h'] / 2)]])]
print(f'  screw boss          -> MCU board edge      {gap(bosses, mcu_rect):6.2f}   (target {U["case_shroud_gap"]})')
print(f'  MCU board edge      -> cavity wall         {gap(mcu_rect, cavity):6.2f}   (target {U["case_shroud_gap"]})')

print('\n=== IO openings ===')
t = math.radians(P['matrix_c5_r4']['r'])
def c5(dx, dy):
    return (P['matrix_c5_r4']['x'] + dx * math.cos(t) - dy * math.sin(t),
            P['matrix_c5_r4']['y'] + dx * math.sin(t) + dy * math.cos(t))
print(f'  reset slot spans x {U["sw_reset_x_off"]+U["sw_reset_slot_dx"]-U["sw_reset_slot_w"]/2:+7.2f} .. {U["sw_reset_slot_e"]:+7.2f}   (c5_r4 frame)')
print(f'  power slot spans x {U["sw_reset_slot_e"]:+7.2f} .. {U["sw_power_slot_e"]:+7.2f}')
print(f'  {ok(abs(U["sw_power_slot_x"] - U["sw_power_slot_w"]/2 - U["sw_reset_slot_e"]) < 1e-6)} the two openings meet - no post between them')
housing_w = U['mcu_x_off'] + U['shroud_w_off']
print(f'  power opening east  -> housing west wall   {housing_w - U["sw_power_slot_e"]:6.2f}')

print('\n=== USB-C window ===')
print(f'  receptacle sits z {U["mcu_usb_z"]:.2f} .. {U["mcu_usb_z"]+U["mcu_usb_t"]:.2f} above the PCB')
print(f'  window      spans z {U["usb_win_z0"]:.2f} .. {U["usb_win_z1"]:.2f}   ({U["usb_win_z1"]-U["usb_win_z0"]:.2f} tall, {U["usb_win_w"]:.2f} wide)')
print(f'  {ok(abs((U["usb_win_z1"]-U["usb_win_z0"]) - (U["mcu_usb_t"]+U["usb_win_fit"])) < 1e-9)} window is the receptacle + {U["usb_win_fit"]} in each dimension')
print(f'  material in front of the port             {U["case_shroud_n_wall_t"]:6.2f}   (north wall)')
print(f'  roof above the window                    {U["case_shroud_h"]-U["usb_win_z1"]:6.2f}')

print('\n=== heights above the PCB top ===')
print(f'  MCU assembly top        {U["mcu_top_h"]:6.2f}')
print(f'  battery                 {U["bat_t"]:6.2f}')
print(f'  cavity                  {U["case_shroud_inner_h"]:6.2f}  -> roof top {U["case_shroud_h"]:.2f}')
print(f'  keycap top              {U["keycap_h"]:6.2f}   {ok(U["keycap_h"] >= U["case_shroud_h"])} housing stays under the caps')
print(f'  screw length needed     {U["case_shroud_h"] + U["pcb_t"] + 3 - U["screw_head_h"]:6.2f}   (roof to the bottom of a 3mm insert, under the head)')
print(f'  half thickness          {U["case_bottom_t"]+U["case_wall_rise"]+U["pcb_t"]+U["keycap_h"]:6.2f}')
print(f'  carry case              pocket {U["carry_pocket_d"]:.2f}  void {U["carry_void_h"]:.2f}  total {U["carry_h"]:.2f}')

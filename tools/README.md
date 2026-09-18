# ezy54 tooling

Local build + verification for `ergogen/config.yml`. The point is to be able to
change a unit and immediately see whether the PCB, the switchplate, the bottom
case and the carry case are all still sane — without pasting into ergogen.xyz
and eyeballing it.

Everything here is optional: the config is still a plain ergogen config you can
paste into <https://ergogen.xyz>.

## Setup

Needs **Node 18+**, **Python 3.9+** and **git**. Then:

```bash
cd tools && npm run setup
```

That installs the node dependencies and clones
[ceoloide/ergogen-footprints](https://github.com/ceoloide/ergogen-footprints)
into `tools/vendor/` (gitignored — it carries its own licence). Python needs
`pyyaml`:

```bash
pip install pyyaml
```

## Build

```bash
node tools/build.js
```

Writes `out/` — `outlines/`, `cases/`, `pcbs/ezy54.kicad_pcb`, and (because it
runs ergogen in debug mode) `points/points.yaml` + `points/units.yaml`, which
every check below reads.

## Checks

### `python tools/check.py out`

Geometric assertions on the case: that the MCU/battery housing is inside the
board outline, the cavity inside the housing, the screw bosses inside the
cavity, the battery and connector inside the cavity — plus the clearances that
matter (housing wall to nearest keycap, boss to battery, MCU to cavity wall),
the USB-C window's position against the receptacle, and the stack heights.

### `python tools/drc_lite.py out/pcbs/ezy54.kicad_pcb`

A KiCad-free pre-flight on the generated board:

- copper too close to, or hanging off, the board edge
- pads of different nets too close together
- drilled holes too close to the board edge
- the GND pour still covering the board and the MCU keepout still covering the
  MCU — those two zone polygons are **literal coordinates** in the config
  (ergogen does not resolve unit names inside nested arrays), so nothing else
  keeps them in sync with the layout. Re-run this after moving anything in the
  MCU column.

Thresholds default to JLCPCB's (`--edge 0.3 --pad 0.2 --hole 0.5`).

It deliberately does **not** check courtyard overlaps: every switch overlaps its
own diode here, which is normal for a keyboard.

### `node tools/drc.js` — the real thing

Runs `kicad-cli pcb drc` and summarises it. Needs KiCad 8+ on PATH. Run it on
the generated board before routing, and again on `kicad/ezy54.kicad_pcb` after.

On an unrouted board every net is reported as an unconnected item — that is
expected, look at the `violations` group.

### `python tools/diode_fit.py`

Only needed if the key layout changes. See "the mirroring gotcha" below.

## Cases

```bash
node tools/cases.js
```

Evaluates each generated `.jscad` (they use the CSG v1 API) into `out/stl/`,
reporting bounds and volume — a negative or wildly wrong volume means the
booleans went bad.

`tools/jscad_run.js` does one case at a time and can do more:

```bash
# cross sections through the housing, as an SVG
node tools/jscad_run.js out/cases/ezy54_case_switchplate_right.jscad \
    --cut "x=263,y=-140,z=5" --svg out/section.svg --scale 6

# is there material at this point?
node tools/jscad_run.js out/cases/ezy54_case_left.jscad \
    --probe "reset opening:238.1,-82.7,5;floor:240,-90,1"
```

`--probe` ray-casts the mesh and answers SOLID/empty per point. It is the
fastest way to confirm a wall, a lip or a cutout is really where you think.

## Drawings

```bash
python tools/render.py out --o ezy54:#000:0.5 --o _shroud_outer:#f80:0.4 \
       --labels --grid 10 --scale 5 --out out/board.svg
node tools/svg2png.js out/board.svg out/board.png 1400
```

`--o name[:colour[:width]]` layers any generated outline; `--points`/`--labels`
overlay the ergogen points; `--crop x0,y0,x1,y1` zooms in. Coordinates are
ergogen's (y up), matching `points.yaml`.

## Routing, after all this

1. `node tools/build.js`, then `python tools/drc_lite.py out/pcbs/ezy54.kicad_pcb`
   until it is clean.
2. Copy `out/pcbs/ezy54.kicad_pcb` over `kicad/ezy54.kicad_pcb`.
3. Open it in KiCad, press `B` to fill the zones (the pours come out empty
   until KiCad calculates them once).
4. `Tools > External Plugins > Freerouting`.
5. Back in KiCad: teardrops, then curvy tracks.
6. `node tools/drc.js --pcb kicad/ezy54.kicad_pcb`.

## The mirroring gotcha

Worth knowing before you move anything, because it is silent and it bit this
board twice.

Ergogen works in a y-up coordinate system and negates y when it writes the
KiCad board. Footprint bodies, though, are authored in KiCad's own y-down
frame and are placed with a plain rotation. The result is that a footprint's
internal geometry ends up rotated by **twice its key's rotation** relative to
the direction of an `adjust.shift`.

Two consequences, both fixed in the current config:

- **`rotate: 90` aims a side-actuated switch the wrong way.** The power
  switch's slider pointed south, into the board, and its body pads hung off the
  board edge. It is `rotate: -90` now.
- **A diode at a fixed offset sits at a different angle around every key.** On
  the −45° inner thumb it landed on the switch's plated centre hole. There is
  no offset that is "correct" by construction, so `tools/diode_fit.py` sweeps
  `pcb_diode_x_off` / `pcb_diode_y_off` against every other pad and the board
  edge and reports the offsets with the most clearance. Re-run it if you change
  splay, spread or stagger, and put the winner back into the config.

This is not an ergogen bug — the whole board is mirrored consistently, which is
why the two halves come off one PCB and why one case half gets flipped in the
slicer. It only bites when a footprint's own geometry has to line up with
something positioned in ergogen's frame.

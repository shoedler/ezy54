# ezy54 tooling

Local build + verification for `ergogen/config.yml`. The point is to be able to
change a unit and immediately see whether the PCB, the switchplate, the bottom
case and the carry case are all still sane — without pasting into ergogen.xyz
and eyeballing it.

Everything here is optional: the config is still a plain ergogen config you can
paste into <https://ergogen.xyz>.

## Setup

Needs **Node 22.18+** (for running TypeScript without a build step) and
**git**. Then:

```bash
cd tools && npm run setup
```

That installs the node dependencies and clones
[ceoloide/ergogen-footprints](https://github.com/ceoloide/ergogen-footprints)
into `tools/vendor/` (gitignored — it carries its own licence).

The tools are TypeScript and run directly: `node tools/check.ts`, no build, no
`dist/`. `npm --prefix tools run typecheck` runs `tsc --noEmit` over them, and
`npm --prefix tools test` runs the unit tests.

## Build

```bash
node tools/build.ts
```

Writes `out/` — `outlines/`, `cases/`, `pcbs/ezy54.kicad_pcb`, and (because it
runs ergogen in debug mode) `points/points.yaml` + `points/units.yaml`, which
every check below reads.

## Checks

### `node tools/check.ts out`

Geometric assertions on the case: that the MCU/battery housing is inside the
board outline, the cavity inside the housing, the screw bosses inside the
cavity, the battery and connector inside the cavity — plus the clearances that
matter (housing wall to nearest keycap, boss to battery, MCU to cavity wall),
the USB-C window's position against the receptacle, and the stack heights.

### `node tools/drc-lite.ts out/pcbs/ezy54.kicad_pcb`

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

### `node tools/drc.ts` — the real thing

Runs `kicad-cli pcb drc` and summarises it. Needs KiCad 8+ on PATH. Run it on
the generated board before routing, and again on `kicad/ezy54.kicad_pcb` after.

On an unrouted board every net is reported as an unconnected item — that is
expected, look at the `violations` group.

### `npm --prefix tools test`

Unit tests over the geometry, the s-expression reader and the formatting, plus
the one regression test that has actually earned its keep — see "the rotation
gotcha" below. Run it whenever you touch `lib/geom.ts`.

### `node tools/diode-fit.ts`

Sweeps the diode anchor offset against every other pad and the board edge.
Only needed if the key layout changes.

## Cases

```bash
node tools/cases.ts
```

Evaluates each generated `.jscad` (they use the CSG v1 API) into `out/stl/`,
reporting bounds and volume — a negative or wildly wrong volume means the
booleans went bad.

`tools/jscad.ts` does one case at a time and can do more:

```bash
# cross sections through the housing, as an SVG
node tools/jscad.ts out/cases/ezy54_case_switchplate_right.jscad \
    --cut "x=263,y=-140,z=5" --svg out/section.svg --scale 6

# is there material at this point?
node tools/jscad.ts out/cases/ezy54_case_left.jscad \
    --probe "reset opening:238.1,-82.7,5;floor:240,-90,1"
```

`--probe` ray-casts the mesh and answers SOLID/empty per point. It is the
fastest way to confirm a wall, a lip or a cutout is really where you think.

## Drawings

```bash
node tools/render.ts out --o ezy54:#000:0.5 --o _shroud_outer:#f80:0.4 \
     --labels --grid 10 --scale 5 --out out/board.svg
node tools/svg2png.ts out/board.svg out/board.png 1400
```

`--o name[:colour[:width]]` layers any generated outline; `--points`/`--labels`
overlay the ergogen points; `--crop x0,y0,x1,y1` zooms in. Coordinates are
ergogen's (y up), matching `points.yaml`.

## Routing, after all this

1. `node tools/build.ts`, then `node tools/drc-lite.ts out/pcbs/ezy54.kicad_pcb`
   until it is clean.
2. Copy `out/pcbs/ezy54.kicad_pcb` over `kicad/ezy54.kicad_pcb`.
3. Open it in KiCad, press `B` to fill the zones (the pours come out empty
   until KiCad calculates them once).
4. `Tools > External Plugins > Freerouting`.
5. Back in KiCad: teardrops, then curvy tracks.
6. `node tools/drc.ts --pcb kicad/ezy54.kicad_pcb`.

## The rotation gotcha

Worth reading before you move a footprint, because it is silent and it cost a
PCB revision.

Ergogen works y-up and negates y when it writes the board. Footprint bodies,
though, are authored in KiCad's own y-down frame and placed with a rotation of
`key rotation + adjust.rotate`. To work out where a pad actually lands you need
KiCad's rotation convention, and it is the counter-intuitive one: angles are
counter-clockwise *as displayed*, and the file's y axis points down, so in file
coordinates a footprint-local offset is rotated by **minus** the angle:

```
x' =  x·cos(t) + y·sin(t)
y' = -x·sin(t) + y·cos(t)
```

Get that sign backwards and the y component of every footprint-internal offset
flips on any rotated footprint. The tooling did exactly that at first, and it
produced two confident, wrong conclusions:

- it said `rotate: 90` aimed the power switch's slider south into the board, so
  the config was changed to `-90`. It does not - `90` is correct, and `-90` is
  what actually pointed it the wrong way.
- it said diode pads on the splayed thumb keys collided with the switch's
  plated centre hole, which led to an unnecessary `pcb_diode_x_off`.

With the correct convention there is no dependence on the key's rotation at
all. Substituting `R = r + A` into the two transforms gives a footprint-local
offset, expressed in its own key's frame, of

```
Lx = lx·cos(A) + ly·sin(A)
Ly = lx·sin(A) - ly·cos(A)
```

— only `adjust.rotate` appears. A footprint's geometry sits in the same place
relative to every key, however splayed.

`lib/geom.ts` has the two conventions side by side as `rotateKicad` (this one)
and `rotateCcw` (ergogen's own y-up frame); confusing them is the mistake.
`test/rotation.test.ts` pins it down: it compares the computed hole positions
against the Excellon coordinates KiCad itself produced, read out of the
committed `kicad/gerber.zip`. Correct convention matches to 0.0005mm; the wrong
one misses 4 of 10 holes by up to 0.154mm. Run `npm --prefix tools test` after
touching `rotateKicad`.

What *did* survive the correction: the reset and power switches genuinely need
`sw_reset_y_in` / `sw_power_y_in` around 2.3 / 2.2. At the original 1.75 / 1.25
the power switch's mounting pads cross the board edge and the reset switch's
mounting boss sits exactly on it, whichever convention you use.

## Layout

| | |
|---|---|
| `build.ts` | ergogen config → `out/` |
| `cases.ts` | every `.jscad` → `out/stl/` |
| `jscad.ts` | one `.jscad`: stats, STL, probes, sections |
| `check.ts` | geometric assertions on the case |
| `drc-lite.ts` | KiCad-free pre-flight on the board |
| `drc.ts` | `kicad-cli` DRC, summarised |
| `diode-fit.ts` | diode anchor offset sweep |
| `render.ts` | outlines + points → SVG |
| `svg2png.ts` | SVG → PNG |
| `fetch-footprints.ts` | clone/update the vendored footprint library |
| `lib/` | the shared core: CLI parsing, formatting, geometry, KiCad and outline models, the JSCAD runtime |
| `test/` | `node --test` unit tests |
| `vendor/` | third-party, gitignored, do not edit |

One thing in `lib/` looks stranger than it is: `fmt.ts` reimplements Python's
number formatting and `geom.ts` has its own `hypot`. These tools were ported
from Python, and their output is diffed against the originals; `toFixed` and
`Math.hypot` each disagree with Python often enough to change a printed digit
or reorder two tied rows. Both are commented and tested.

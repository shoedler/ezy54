/**
 * Finds a diode anchor offset that clears everything else on the board.
 *
 * Ergogen mirrors y when it writes the KiCad board, so a footprint's internal
 * geometry ends up rotated by twice its key's rotation relative to the
 * direction of an `adjust.shift`. The diode therefore sits at a different angle
 * around each key, and on a heavily splayed key it can land on the switch's
 * plated centre hole or a Choc v1 stabiliser hole.
 *
 * This sweeps `pcb_diode_x_off` / `pcb_diode_y_off` analytically — no rebuild
 * per candidate — against every non-diode pad and against the board edge.
 */
import { parseCli, run } from './lib/cli.ts';
import { fixed, float, signed } from './lib/fmt.ts';
import {
  distance,
  distanceToEdges,
  minOf,
  placeCcw,
  polygonDistance,
  rotateKicad,
  translate,
  type Polygon,
  type Vec2,
} from './lib/geom.ts';
import { padPolygon, readBoard, type Board } from './lib/kicad.ts';
import { repoPath } from './lib/paths.ts';
import { loadPoints, type Point } from './lib/points.ts';

/** SOD-123, as placed by ceoloide/diode_tht_sod123 (reversible SMD). */
const PAD_PITCH = 1.65;
const PAD_SIZE: Vec2 = [0.9, 1.2];

/** Pads further than this from a diode pad's first corner cannot be the limit. */
const NEIGHBOUR_RADIUS = 14;

interface Candidate {
  readonly shift: Vec2;
  readonly clearance: number;
  readonly limitedBy: string;
}

function main(): void {
  const args = parseCli({
    usage: 'node tools/diode-fit.ts [--out dir] [--step mm] [--range mm]',
    options: {
      out: { type: 'string', default: 'out', help: 'build output directory' },
      step: { type: 'number', default: 0.25, help: 'sweep resolution' },
      range: { type: 'number', default: 6, help: 'sweep half-width, in each axis' },
    },
  });

  const outDir = repoPath(args.out);
  const board = readBoard(`${outDir}/pcbs/ezy54.kicad_pcb`);
  const keys = Object.entries(loadPoints(outDir)).filter(([name]) => /^(matrix|thumb)_/.test(name));
  // A diode is never the thing a diode has to clear.
  const obstacles = board.pads.filter((pad) => !pad.ref.startsWith('D'));

  const steps = Math.trunc(args.range / args.step);
  const clearing: Candidate[] = [];
  for (let i = -steps; i <= steps; i++) {
    for (let j = -steps; j <= steps; j++) {
      const shift: Vec2 = [round3(i * args.step), round3(j * args.step)];
      const found = worstClearance(shift, keys, obstacles, board);
      if (found.clearance > 0) clearing.push({ shift, ...found });
    }
  }
  clearing.sort(bestFirst);

  console.log(`swept +-${float(args.range)} in ${float(args.step)}mm steps; ${clearing.length} offsets clear everything\n`);
  console.log(`${'worst'.padStart(7)}  ${'x_off'.padStart(6)} ${'y_off'.padStart(6)}   limited by`);
  for (const { clearance, shift, limitedBy } of clearing.slice(0, 15)) {
    console.log(
      `${fixed(clearance, 3).padStart(7)}  ${signed(shift[0], 2).padStart(6)} ${signed(shift[1], 2).padStart(6)}   ${limitedBy}`,
    );
  }
  if (clearing.length === 0) console.log('nothing clears - widen --range, or reconsider include_plated_holes');
}

/** The tightest clearance this offset produces anywhere on the board. */
function worstClearance(
  shift: Vec2,
  keys: ReadonlyArray<readonly [string, Point]>,
  obstacles: Board['pads'],
  board: Board,
): { clearance: number; limitedBy: string } {
  let clearance = 99;
  let limitedBy = '';

  for (const [name, key] of keys) {
    for (const pad of diodePads(key, shift)) {
      for (const obstacle of obstacles) {
        if (distance(obstacle.pos, pad[0]!) > NEIGHBOUR_RADIUS) continue;
        const gap = polygonDistance(pad, obstacle.poly);
        if (gap < clearance) {
          [clearance, limitedBy] = [gap, `${name} vs ${obstacle.ref}`];
          if (clearance <= 0) return { clearance, limitedBy };
        }
      }
      const toEdge = minOf(pad, (corner) => distanceToEdges(corner, board.edges));
      if (toEdge < clearance) [clearance, limitedBy] = [toEdge, `${name} vs board edge`];
    }
  }
  return { clearance, limitedBy };
}

/** The two pads of the diode belonging to `key`, once its anchor is shifted. */
function diodePads(key: Point, shift: Vec2): Polygon[] {
  // The anchor shift happens in ergogen's own y-up frame...
  const [x, y] = placeCcw([key.x, key.y], shift, key.r);
  const centre: Vec2 = [x, -y]; // ...then ergogen negates y when it writes the board.
  const rotation = key.r + 180; // the footprint's own `adjust.rotate`
  // ...and the pads themselves rotate KiCad style, which is the whole reason
  // the diode sits differently around every key.
  return [-PAD_PITCH, PAD_PITCH].map((offset) =>
    padPolygon(translate(centre, rotateKicad([offset, 0], rotation)), PAD_SIZE, rotation, 'rect'),
  );
}

/** Widest clearance first, then the offset, matching the tool this replaced. */
const bestFirst = (a: Candidate, b: Candidate): number =>
  b.clearance - a.clearance ||
  b.shift[0] - a.shift[0] ||
  b.shift[1] - a.shift[1] ||
  (b.limitedBy < a.limitedBy ? -1 : b.limitedBy > a.limitedBy ? 1 : 0);

const round3 = (value: number): number => Number(fixed(value, 3));

run(main);

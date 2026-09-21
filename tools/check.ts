/**
 * Geometric assertions on the generated case: that each part is inside the one
 * that has to contain it, that the clearances which matter still hold, and that
 * the stack heights add up.
 *
 * It reports rather than asserts — the numbers are as useful as the verdicts.
 */
import { parseCli, run } from './lib/cli.ts';
import { fixed, signed, verdict } from './lib/fmt.ts';
import type { Vec2 } from './lib/geom.ts';
import { countOutside, gap, loadOutline, rectOutline, type Outline } from './lib/outline.ts';
import { repoPath } from './lib/paths.ts';
import { loadPoints, loadUnits, unit, type Points, type Units } from './lib/points.ts';

function main(): void {
  const args = parseCli({
    usage: 'node tools/check.ts [out]',
    positionals: { out: { type: 'string', default: 'out', help: 'build output directory' } },
  });

  const outDir = repoPath(args.out);
  const points = loadPoints(outDir);
  const units = loadUnits(outDir);
  const outline = (name: string) => loadOutline(outDir, name);

  const pcb = outline('ezy54');
  const housing = outline('_shroud_outer');
  const cavity = outline('_shroud_inner');
  const keycaps = outline('_pcb_keycaps');
  const bosses = outline('_shroud_bosses');
  const battery = outline('_pcb_bat');

  console.log('=== containment ===');
  containment('housing inside the PCB outline           ', housing, pcb);
  containment('cavity inside the housing                 ', cavity, housing);
  containment('screw bosses inside the cavity            ', bosses, cavity);
  containment('battery + connector inside the cavity     ', battery, cavity);

  console.log('\n=== clearances (mm) ===');
  const mcu = mcuOutline(points, units);
  clearance('housing outer wall  -> nearest keycap', gap(housing, keycaps), unit(units, 'mcu_col_gap'));
  clearance('screw boss          -> battery/connector', gap(bosses, battery), unit(units, 'bat_gap'));
  clearance('screw boss          -> cavity wall', gap(bosses, cavity));
  clearance('screw boss          -> MCU board edge', gap(bosses, mcu), unit(units, 'case_shroud_gap'));
  clearance('MCU board edge      -> cavity wall', gap(mcu, cavity), unit(units, 'case_shroud_gap'));

  reportIoOpenings(units);
  reportUsbWindow(units);
  reportHeights(units);
}

function containment(what: string, inner: Outline, outer: Outline): void {
  const violations = countOutside(inner, outer);
  console.log(`  ${verdict(violations === 0)} ${what} (${violations} violations)`);
}

/** The measurement column starts at a fixed offset, whatever the label. */
const LABEL_WIDTH = 43;

function clearance(what: string, measured: number, target?: number): void {
  const suffix = target === undefined ? '' : `   (target ${target})`;
  console.log(`  ${what.padEnd(LABEL_WIDTH)}${fixed(measured, 2).padStart(6)}${suffix}`);
}

/** The MCU board's own footprint, as a rectangle around its point. */
function mcuOutline(points: Points, units: Units): Outline {
  const mcu = points['mcu'];
  if (!mcu) throw new Error('points.yaml has no "mcu" point');
  const size: Vec2 = [unit(units, 'mcu_w'), unit(units, 'mcu_h')];
  return rectOutline([mcu.x, mcu.y], size, mcu.r);
}

function reportIoOpenings(units: Units): void {
  const u = (name: string) => unit(units, name);
  const resetStart = u('sw_reset_x_off') + u('sw_reset_slot_dx') - u('sw_reset_slot_w') / 2;
  const meet = Math.abs(u('sw_power_slot_x') - u('sw_power_slot_w') / 2 - u('sw_reset_slot_e')) < 1e-6;
  const housingWidth = u('mcu_x_off') + u('shroud_w_off');

  console.log('\n=== IO openings ===');
  console.log(`  reset slot spans x ${span(resetStart)} .. ${span(u('sw_reset_slot_e'))}   (c5_r4 frame)`);
  console.log(`  power slot spans x ${span(u('sw_reset_slot_e'))} .. ${span(u('sw_power_slot_e'))}`);
  console.log(`  ${verdict(meet)} the two openings meet - no post between them`);
  console.log(`  power opening east  -> housing west wall   ${fixed(housingWidth - u('sw_power_slot_e'), 2).padStart(6)}`);
}

function reportUsbWindow(units: Units): void {
  const u = (name: string) => unit(units, name);
  const height = u('usb_win_z1') - u('usb_win_z0');
  const fits = Math.abs(height - (u('mcu_usb_t') + u('usb_win_fit'))) < 1e-9;

  console.log('\n=== USB-C window ===');
  console.log(`  receptacle sits z ${fixed(u('mcu_usb_z'), 2)} .. ${fixed(u('mcu_usb_z') + u('mcu_usb_t'), 2)} above the PCB`);
  console.log(
    `  window      spans z ${fixed(u('usb_win_z0'), 2)} .. ${fixed(u('usb_win_z1'), 2)}   ` +
      `(${fixed(height, 2)} tall, ${fixed(u('usb_win_w'), 2)} wide)`,
  );
  console.log(`  ${verdict(fits)} window is the receptacle + ${u('usb_win_fit')} in each dimension`);
  console.log(`  material in front of the port             ${fixed(u('case_shroud_n_wall_t'), 2).padStart(6)}   (north wall)`);
  console.log(`  roof above the window                    ${fixed(u('case_shroud_h') - u('usb_win_z1'), 2).padStart(6)}`);
}

function reportHeights(units: Units): void {
  const u = (name: string) => unit(units, name);
  // Roof to the bottom of a 3mm insert, under the head.
  const screw = u('case_shroud_h') + u('pcb_t') + 3 - u('screw_head_h');
  const half = u('case_bottom_t') + u('case_wall_rise') + u('pcb_t') + u('keycap_h');

  console.log('\n=== heights above the PCB top ===');
  console.log(`  MCU assembly top        ${fixed(u('mcu_top_h'), 2).padStart(6)}`);
  console.log(`  battery                 ${fixed(u('bat_t'), 2).padStart(6)}`);
  console.log(`  cavity                  ${fixed(u('case_shroud_inner_h'), 2).padStart(6)}  -> roof top ${fixed(u('case_shroud_h'), 2)}`);
  console.log(
    `  keycap top              ${fixed(u('keycap_h'), 2).padStart(6)}   ` +
      `${verdict(u('keycap_h') >= u('case_shroud_h'))} housing stays under the caps`,
  );
  console.log(`  screw length needed     ${fixed(screw, 2).padStart(6)}   (roof to the bottom of a 3mm insert, under the head)`);
  console.log(`  half thickness          ${fixed(half, 2).padStart(6)}`);
  console.log(
    `  carry case              pocket ${fixed(u('carry_pocket_d'), 2)}  ` +
      `void ${fixed(u('carry_void_h'), 2)}  total ${fixed(u('carry_h'), 2)}`,
  );
}

const span = (value: number): string => signed(value, 2).padStart(7);

run(main);

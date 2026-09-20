// Run KiCad's own DRC on the generated board and summarise it.
//
// Needs kicad-cli (KiCad 8+) on PATH - so this is the Linux/KiCad-machine
// half of the checks; tools/drc_lite.py covers what can be checked without it.
//
// usage: node tools/drc.js [--pcb out/pcbs/ezy54.kicad_pcb] [--json out/drc.json]
//        node tools/drc.js --pcb kicad/ezy54.kicad_pcb        (after routing)
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const arg = (name, dflt) => {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 ? process.argv[i + 1] : dflt;
};
const pcb = path.resolve(root, arg('pcb', 'out/pcbs/ezy54.kicad_pcb'));
const json = path.resolve(root, arg('json', 'out/drc.json'));

if (spawnSync('kicad-cli', ['version'], { stdio: 'ignore' }).error) {
  console.error('kicad-cli not found on PATH.');
  console.error('Install KiCad 8+ (Linux: your package manager, or the KiCad flatpak -');
  console.error('for the flatpak use: flatpak run --command=kicad-cli org.kicad.KiCad ...).');
  console.error('Meanwhile `python tools/drc_lite.py` covers the pre-routing checks.');
  process.exit(2);
}

fs.mkdirSync(path.dirname(json), { recursive: true });
// --exit-code-violations makes a non-zero exit mean "found something", which we
// want to swallow here so we can print our own summary.
try {
  execFileSync('kicad-cli', ['pcb', 'drc', '--output', json, '--format', 'json',
    '--severity-all', '--exit-code-violations', pcb], { stdio: ['ignore', 'inherit', 'inherit'] });
} catch (e) {
  if (e.status === undefined) throw e;
}

const r = JSON.parse(fs.readFileSync(json, 'utf8'));
const groups = [
  ['violations', r.violations || []],
  ['unconnected items', r.unconnected_items || []],
  ['schematic parity', r.schematic_parity || []],
];

let errors = 0;
for (const [label, items] of groups) {
  const bySeverity = {};
  const byType = {};
  for (const v of items) {
    bySeverity[v.severity] = (bySeverity[v.severity] || 0) + 1;
    byType[v.type] = (byType[v.type] || 0) + 1;
    if (v.severity === 'error') errors++;
  }
  console.log(`\n--- ${label}: ${items.length} ---`);
  for (const [t, n] of Object.entries(byType).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${t}`);
  }
  if (items.length) console.log(`  severities: ${JSON.stringify(bySeverity)}`);
}

// Before routing, "unconnected items" is every net on the board - not a defect.
console.log(`\nfull report: ${path.relative(root, json)}`);
console.log(`${errors} error-severity item(s)`);
console.log('Note: on an unrouted board every net shows up as an unconnected item,');
console.log('and each switch overlaps its own diode courtyard. Both are expected.');

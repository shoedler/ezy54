// Evaluate every generated .jscad into an STL and report its bounds/volume.
// usage: node tools/cases.js [--out out]
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const i = process.argv.indexOf('--out');
const out = path.resolve(root, i >= 0 ? process.argv[i + 1] : 'out');
const cases = path.join(out, 'cases');
const stl = path.join(out, 'stl');
fs.mkdirSync(stl, { recursive: true });

for (const f of fs.readdirSync(cases).filter((f) => f.endsWith('.jscad'))) {
  const name = path.basename(f, '.jscad');
  if (name.startsWith('_')) continue; // intermediate parts
  console.log(`### ${name}`);
  execFileSync(process.execPath,
    [path.join(__dirname, 'jscad_run.js'), path.join(cases, f), '--stl', path.join(stl, name + '.stl')],
    { stdio: 'inherit' });
}

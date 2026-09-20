// Build ergogen/config.yml into out/.
//
// Ergogen wants a folder holding config.yaml plus footprints/<lib>/*.js, so
// this assembles one in a temp dir and points the CLI at it.
//
// usage: node tools/build.js [--config ergogen/config.yml] [--out out]
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const root = path.join(__dirname, '..');
const arg = (name, dflt) => {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 ? process.argv[i + 1] : dflt;
};
const config = path.resolve(root, arg('config', 'ergogen/config.yml'));
const out = path.resolve(root, arg('out', 'out'));
const footprints = path.join(__dirname, 'vendor', 'ergogen-footprints');

if (!fs.existsSync(footprints)) {
  console.error('missing footprints - run: npm --prefix tools run footprints');
  process.exit(1);
}

const bundle = fs.mkdtempSync(path.join(os.tmpdir(), 'ezy54-'));
const lib = path.join(bundle, 'footprints', 'ceoloide');
fs.mkdirSync(lib, { recursive: true });
for (const f of fs.readdirSync(footprints).filter((f) => f.endsWith('.js'))) {
  fs.copyFileSync(path.join(footprints, f), path.join(lib, f));
}
fs.copyFileSync(config, path.join(bundle, 'config.yaml'));

fs.rmSync(out, { recursive: true, force: true });
try {
  execFileSync(process.execPath, [require.resolve('ergogen/src/cli.js'), bundle, '-o', out, '-d'],
    { stdio: 'inherit' });
} finally {
  fs.rmSync(bundle, { recursive: true, force: true });
}
console.log(`\nwrote ${path.relative(root, out)}/ (outlines, cases, pcbs, points)`);

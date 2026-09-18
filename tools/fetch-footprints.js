// Clone (or update) the ceoloide footprint library the config depends on.
// Kept out of git: it has its own licence (CC BY-NC-SA / MIT per file).
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO = 'https://github.com/ceoloide/ergogen-footprints';
const dir = path.join(__dirname, 'vendor', 'ergogen-footprints');

fs.mkdirSync(path.dirname(dir), { recursive: true });
if (fs.existsSync(path.join(dir, '.git'))) {
  console.log('updating', dir);
  execFileSync('git', ['-C', dir, 'pull', '--ff-only'], { stdio: 'inherit' });
} else {
  console.log('cloning', REPO);
  execFileSync('git', ['clone', '--depth', '1', REPO, dir], { stdio: 'inherit' });
}
const n = fs.readdirSync(dir).filter((f) => f.endsWith('.js')).length;
console.log(`${n} footprints available`);

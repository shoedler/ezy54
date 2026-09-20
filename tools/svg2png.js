const { Resvg } = require('@resvg/resvg-js');
const fs = require('fs');
const [,, inp, outp, width] = process.argv;
const svg = fs.readFileSync(inp, 'utf8');
const r = new Resvg(svg, { fitTo: width ? { mode: 'width', value: parseInt(width) } : { mode: 'original' }, background: 'white' });
fs.writeFileSync(outp, r.render().asPng());
console.log('wrote', outp);

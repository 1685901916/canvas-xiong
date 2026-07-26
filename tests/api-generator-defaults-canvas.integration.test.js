const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

assert.match(html, /api-generator-defaults\.js[^]*canvas\.js/);
assert.match(canvas, /ApiGeneratorDefaults\??\.createDefaultNode/);
assert.match(canvas, /ApiGeneratorDefaults\??\.shouldAdoptSourceRatio/);
assert.match(canvas, /node\._apiRatioUserSet\s*=\s*true/);
assert.match(canvas, /API_GENERATOR_DEFAULTS_VERSION\s*=\s*3/);

console.log('api-generator-defaults canvas integration tests passed');

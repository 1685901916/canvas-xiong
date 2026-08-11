const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

assert.match(html, /free-compositor\.css/);
assert.match(html, /id="freeCompositorRoot"/);
assert.match(html, /free-compositor-core\.js/);
assert.match(html, /free-compositor\.js/);
assert.match(html, /openFreeCompositorFromSelection\(\)/);
assert.match(canvas, /window\.canvasFreeCompositorAdapter\s*=/);
assert.match(canvas, /getSelectedImages\s*\(/);
assert.match(canvas, /commitPngBlob\s*\(/);
assert.match(canvas, /url:canvasDisplayMediaUrl\(node\.url, node\.name\)/);
assert.match(canvas, /function freeCompositorNotice\(/);
assert.doesNotMatch(canvas, /function openFreeCompositorFromSelection\(\)[^]*?\n}\n[^]*?toast\(/);

console.log('free compositor integration tests passed');

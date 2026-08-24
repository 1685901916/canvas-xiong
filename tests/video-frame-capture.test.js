const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'canvas.css'), 'utf8');
const i18n = fs.readFileSync(path.join(root, 'static', 'js', 'i18n', 'canvas.js'), 'utf8');
const i18nLoader = fs.readFileSync(path.join(root, 'static', 'js', 'i18n.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');

assert.match(canvas, /class="canvas-video-capture"/);
assert.match(canvas, /data-video-frame-mode="first"/);
assert.match(canvas, /data-video-frame-mode="last"/);
assert.match(canvas, /data-video-frame-mode="current"/);
assert.match(canvas, /async function videoFrameBlob/);
assert.match(canvas, /async function captureVideoFrame/);
assert.match(canvas, /frameSourceId:node\.id/);
assert.match(canvas, /kind:'frameCapture'/);
assert.match(canvas, /to\.frameSourceId === from\.id/);
assert.match(canvas, /uploadCroppedBlob\(frame\.blob/);
assert.match(canvas, /function videoFrameText/);
assert.match(canvas, /translated\s*!==\s*key/);
assert.match(css, /\.canvas-video-capture/);
assert.match(css, /\.canvas-video-capture-menu/);
assert.match(i18nLoader, /2026\.07\.17\.media-tools\.3/);
assert.match(html, /canvas\.css\?v=2026\.07\.17-media-tools-3/);
assert.match(html, /canvas\.js\?v=2026\.08\.24-autodl-h3-1/);

for(const key of [
  'canvas.captureVideoFrame',
  'canvas.captureFirstFrame',
  'canvas.captureLastFrame',
  'canvas.captureCurrentFrame',
  'canvas.capturingFrame',
  'canvas.frameCaptured',
  'canvas.videoFrameFailed',
]) assert.ok(i18n.includes(`"${key}"`), `missing i18n key: ${key}`);

console.log('video frame capture tests passed');

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'canvas.css'), 'utf8');

assert.match(html, /id="outputVideoCaptureBtn"/);
assert.match(html, /id="outputVideoCaptureMenu"/);
assert.match(html, /data-lightbox-video-frame-mode="first"/);
assert.match(html, /data-lightbox-video-frame-mode="last"/);
assert.match(html, /data-lightbox-video-frame-mode="current"/);
assert.match(canvas, /videoFrameBlob\(node, mode, card, explicitVideo=null\)/);
assert.match(canvas, /explicitVideo \|\| card\?\.querySelector\('video'\)/);
assert.match(canvas, /video:outputLightboxVideo/);
assert.match(canvas, /sourceUrl:currentOutputLightboxUrl/);
assert.match(canvas, /outputVideoCaptureWrap\.style\.display = videoMode && hasSource/);
assert.match(canvas, /syncOutputMediaToolVisibility\(false, null, ''\)/);
assert.match(canvas, /kind:'frameCapture'/);
assert.match(css, /\.output-action-menu/);

console.log('video lightbox frame capture tests passed');

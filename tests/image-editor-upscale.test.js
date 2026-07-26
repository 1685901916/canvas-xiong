const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'smart-canvas.css'), 'utf8');

assert.match(html, /id="imageEditorUpscaleBtn"[^>]*data-image-edit-mode="upscale"/);
assert.match(html, /id="imageEditorUpscaleModel"/);
assert.match(html, /value="RealESRGAN_x4plus_anime_6B"/);
assert.match(html, /value="Waifu2x_CUNet"/);
assert.match(html, /id="imageEditorUpscaleScale"[^]*value="2"[^]*value="4"/);
assert.match(html, /id="imageEditorUpscaleRunBtn"/);
assert.match(canvas, /async function prepareImageEditorUpscale/);
assert.match(canvas, /async function runImageEditorUpscale/);
assert.match(canvas, /ensureRealESRGANStatus\(\)/);
assert.match(canvas, /\/api\/realesrgan\/upscale/);
assert.match(canvas, /api\.resultMeta\(await response\.json\(\)\)/);
assert.match(canvas, /upscaleSourceId:sourceNode\.id/);
assert.match(canvas, /upscaleModel:model/);
assert.match(canvas, /upscaleScale:scale/);
assert.doesNotMatch(canvas, /kind:'upscale'/);
assert.match(css, /\.image-upscale-tools/);
assert.match(css, /\.crop-canvas\.upscale-mode \.crop-box/);

console.log('image editor upscale tests passed');

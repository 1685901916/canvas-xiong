const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const i18n = fs.readFileSync(path.join(root, 'static', 'js', 'i18n', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'canvas.css'), 'utf8');

assert.match(html, /menuAdd\('realesrgan'\)/);
assert.match(html, /realesrgan-node\.js[^]*canvas\.js/);

assert.match(canvas, /function addRealESRGANNode/);
assert.match(canvas, /type:\s*'realesrgan'/);
assert.match(canvas, /function renderRealESRGANBody/);
assert.match(canvas, /function ensureRealESRGANStatus/);
assert.match(canvas, /function ensureRealESRGANOutput/);
assert.match(canvas, /async function runRealESRGANNode/);
assert.match(canvas, /\/api\/realesrgan\/status/);
assert.match(canvas, /\/api\/realesrgan\/upscale/);
assert.match(canvas, /node\.type === 'realesrgan'[^]*runRealESRGANNode/);
assert.match(canvas, /CANVAS_GENERATOR_TYPES\s*=\s*\[[^\]]*'realesrgan'/);
assert.match(canvas, /CANVAS_IMAGE_OUTPUT_TYPES\s*=\s*\[[^\]]*'realesrgan'/);
assert.match(canvas, /CANVAS_MEDIA_OUTPUT_TYPES\s*=\s*\[[^\]]*'realesrgan'/);
assert.match(canvas, /if\s*\(to\.type === 'realesrgan'\)[^]*\['image','group','output'\]/);
assert.match(canvas, /cascadeParallelLimit[^]*realesrgan[^]*return 1/);
assert.match(canvas, /mergeGeneratedOutputs\(node,\s*\[result\],\s*true\)/);
assert.match(canvas, /appendOutputImagesWithoutDuplicates\(out,\s*\[result\]/);
assert.match(canvas, /function realESRGANFeedbackHtml/);
assert.match(canvas, /function bindRealESRGANProgress/);
assert.match(canvas, /node\.lastResult\s*=\s*api\.normalizeResultSummary/);
assert.match(canvas, /deviceStatus\.textContent\s*=\s*api\.deviceLabelForModel\(status,\s*node\.model\)/);

for(const key of [
  'canvas.qualityUpscale',
  'canvas.realesrganTitle',
  'canvas.realesrganModel',
  'canvas.upscaleScale',
  'canvas.runDevice',
  'canvas.startUpscale',
  'canvas.upscaling',
  'canvas.upscalePreparing',
  'canvas.upscaleProcessing',
  'canvas.upscaleProgressHint',
  'canvas.upscaleSuccess',
  'canvas.upscaleSavedToOutput',
  'canvas.cpuSlow',
  'canvas.realesrganModelMissing',
  'canvas.realesrganRuntimeUnavailable',
  'canvas.realesrganUnsupportedImage',
  'canvas.realesrganOom',
  'canvas.realesrganTimeout',
  'canvas.realesrganNoOutput',
]) {
  assert.ok(i18n.includes(`"${key}"`), `missing i18n key: ${key}`);
}

assert.match(css, /\.realesrgan-node/);
assert.match(css, /\.realesrgan-device-status/);
assert.match(css, /\.realesrgan-progress/);
assert.match(css, /\.realesrgan-result/);

console.log('realesrgan canvas integration tests passed');

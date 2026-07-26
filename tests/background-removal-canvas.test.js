const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const i18n = fs.readFileSync(path.join(root, 'static', 'js', 'i18n', 'canvas.js'), 'utf8');

assert.match(html, /id="outputBackgroundRemovalBtn"/);
assert.match(html, /id="imageEditorBackgroundRemovalBtn"/);
assert.match(canvas, /data-image-background-removal/);
assert.match(canvas, /async function runBackgroundRemoval/);
assert.match(canvas, /async function runBackgroundRemovalFromEditor/);
assert.match(canvas, /runBackgroundRemovalFromEditor\(event\.currentTarget\)/);
assert.match(canvas, /\/api\/koukoutu\/remove-background/);
assert.match(canvas, /backgroundRemovalSourceId:sourceNode\.id/);
assert.match(canvas, /backgroundRemovalProvider:'koukoutu'/);
assert.doesNotMatch(canvas, /kind:'backgroundRemoval'/);
assert.doesNotMatch(canvas, /to\.backgroundRemovalSourceId === from\.id/);
assert.match(canvas, /markCanvasMediaMutation\(\)[^]*render\(\)[^]*scheduleSave\(\)/);

for(const key of [
  'canvas.backgroundRemoval',
  'canvas.backgroundRemoving',
  'canvas.backgroundRemovalComplete',
  'canvas.backgroundRemovalFailed',
]) assert.ok(i18n.includes(`"${key}"`), `missing i18n key: ${key}`);

console.log('background removal canvas tests passed');

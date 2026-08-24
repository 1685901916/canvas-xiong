const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvasHtml = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvasJs = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const settingsHtml = fs.readFileSync(path.join(root, 'static', 'api-settings.html'), 'utf8');
const settingsJs = fs.readFileSync(path.join(root, 'static', 'js', 'api-settings.js'), 'utf8');

const helperIndex = canvasHtml.indexOf('/static/js/autodl-video.js');
const canvasIndex = canvasHtml.indexOf('/static/js/canvas.js');
assert(helperIndex >= 0, 'canvas should load the AutoDL helper');
assert(helperIndex < canvasIndex, 'AutoDL helper must load before canvas.js');

const addVideoStart = canvasJs.indexOf('function addVideoNode');
const addVideoEnd = canvasJs.indexOf('function addRhNode', addVideoStart);
const addVideoSource = canvasJs.slice(addVideoStart, addVideoEnd);
assert.match(addVideoSource, /apiProvider\s*:\s*['"]autodl['"]/);
assert.match(addVideoSource, /workflowMode\s*:\s*['"]auto['"]/);
assert.match(addVideoSource, /workflowId\s*:\s*['"]['"]/);
assert.match(addVideoSource, /resolvedWorkflowId\s*:\s*['"]minimax_h3_lightx2v_v5['"]/);

assert.match(canvasJs, /fetch\(['"]\/api\/autodl\/workflows['"]\)/);
assert.match(canvasJs, /自动选择/);
assert.match(canvasJs, /autodl-workflow-reason/);
assert.match(canvasJs, /autodl-media-counts/);
assert.match(canvasJs, /workflowMode\s*=\s*['"]manual['"]/);
assert.match(canvasJs, /workflowMode\s*=\s*['"]auto['"]/);

assert.match(settingsJs, /fetch\(['"]\/api\/autodl\/status['"]\)/);
assert.match(settingsHtml, /id=["']autodlStatus["']/);
assert.match(settingsHtml, /AUTODL_TOKEN/);
assert.doesNotMatch(settingsHtml, /<input[^>]+(?:autodl|AUTODL_TOKEN)/i);

console.log('autodl canvas integration tests passed');

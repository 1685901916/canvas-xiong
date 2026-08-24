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

assert.match(canvasJs, /async function runAutoDLVideoNode\s*\(/);
assert.match(canvasJs, /fetch\(['"]\/api\/autodl\/tasks['"]/);
assert.match(canvasJs, /pending\.task_id\s*=\s*submission\.task_id/);
assert.match(canvasJs, /await saveCanvas\(\)[\s\S]{0,500}pollAutoDLTask/);
assert.match(canvasJs, /async function pollAutoDLTask\s*\(/);
assert.match(canvasJs, /\/api\/autodl\/tasks\/\$\{encodeURIComponent\(taskId\)\}/);
assert.match(canvasJs, /['"]QUEUED['"]/);
assert.match(canvasJs, /['"]RUNNING['"]/);
assert.match(canvasJs, /['"]SUCCESS['"]/);
assert.match(canvasJs, /['"]FAILED['"]/);
assert.match(canvasJs, /function resumeAutoDLVideoTasks\s*\(/);
assert.match(canvasJs, /unknown_submission/);

const resumeStart = canvasJs.indexOf('function resumeAutoDLVideoTasks');
const resumeEnd = canvasJs.indexOf('\nfunction ', resumeStart + 10);
const resumeSource = canvasJs.slice(resumeStart, resumeEnd < 0 ? undefined : resumeEnd);
assert.doesNotMatch(resumeSource, /method\s*:\s*['"]POST['"]/);
assert.doesNotMatch(resumeSource, /runAutoDLVideoNode\s*\(/);
assert.match(canvasJs, /\['image','video','audio'\]\.includes\(mediaKindForRef\(ref\)\)/);
assert.match(canvasJs, /没有需要上传的本地图片、视频或音频/);

const autoRunStart = canvasJs.indexOf('async function runAutoDLVideoNode');
const autoRunEnd = canvasJs.indexOf('async function runVideoNode', autoRunStart);
const autoRunSource = canvasJs.slice(autoRunStart, autoRunEnd);
assert.doesNotMatch(autoRunSource, /uploadCanvasMediaRefToCloud/);
assert.doesNotMatch(autoRunSource, /\/api\/cloud-video\/upload/);

console.log('autodl canvas integration tests passed');

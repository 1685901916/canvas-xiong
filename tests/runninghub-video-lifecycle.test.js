const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvasJs = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

assert.match(canvasJs, /async function runRunningHubVideoNode\s*\(/);
assert.match(canvasJs, /fetch\(['"]\/api\/runninghub\/video-submit['"]/);
assert.match(canvasJs, /pending\.task_id\s*=\s*submission\.task_id/);
assert.match(canvasJs, /pending\.canvasTaskId\s*=\s*submission\.task_id/);
assert.match(canvasJs, /await saveCanvas\(\)[\s\S]{0,600}pollRunningHubVideoTask/);
assert.match(canvasJs, /async function pollRunningHubVideoTask\s*\(/);
assert.match(canvasJs, /\/api\/runninghub\/query\?taskId=\$\{encodeURIComponent\(taskId\)\}/);
assert.match(canvasJs, /function resumeRunningHubVideoTasks\s*\(/);
assert.match(canvasJs, /function findRunningHubVideoPending\s*\(/);
assert.match(canvasJs, /function lockVideoNodeConfigToPendingTask\s*\(/);

const mergeStart = canvasJs.indexOf('function mergeRemoteCanvasIntoLocalForSave');
const mergeEnd = canvasJs.indexOf('\nasync function saveCanvas', mergeStart);
const mergeSource = canvasJs.slice(mergeStart, mergeEnd);
assert.match(mergeSource, /lockVideoNodeConfigToPendingTask/);

const resumeStart = canvasJs.indexOf('function resumeRunningHubVideoTasks');
const resumeEnd = canvasJs.indexOf('\nfunction ', resumeStart + 10);
const resumeSource = canvasJs.slice(resumeStart, resumeEnd < 0 ? undefined : resumeEnd);
assert.doesNotMatch(resumeSource, /method\s*:\s*['"]POST['"]/);
assert.doesNotMatch(resumeSource, /runRunningHubVideoNode\s*\(/);

const runVideoStart = canvasJs.indexOf('async function runVideoNode');
const runVideoEnd = canvasJs.indexOf('\nasync function ', runVideoStart + 10);
const runVideoSource = canvasJs.slice(runVideoStart, runVideoEnd < 0 ? undefined : runVideoEnd);
assert.match(runVideoSource, /isRunningHubVideoProvider/);
assert.match(runVideoSource, /runRunningHubVideoNode/);
assert.match(runVideoSource, /findRunningHubVideoPending/);

console.log('runninghub video lifecycle tests passed');

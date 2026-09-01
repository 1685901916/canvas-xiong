const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvasJs = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

assert.match(canvasJs, /MiniMax Design（本机）/);
assert.match(canvasJs, /async function loadMiniMaxDesignVideoModels\s*\(/);
assert.match(canvasJs, /fetch\(['"]\/api\/minimax-design\/models\/video['"]\)/);
assert.match(canvasJs, /async function runMiniMaxDesignVideoNode\s*\(/);
assert.match(canvasJs, /fetch\(['"]\/api\/minimax-design\/video-submit['"]/);
assert.match(canvasJs, /pending\.task_id\s*=\s*submission\.task_id/);
assert.match(canvasJs, /await saveCanvas\(\)[\s\S]{0,700}pollMiniMaxDesignVideoTask/);
assert.match(canvasJs, /async function pollMiniMaxDesignVideoTask\s*\(/);
assert.match(canvasJs, /\/api\/minimax-design\/tasks\/\$\{encodeURIComponent\(taskId\)\}/);
assert.match(canvasJs, /function findMiniMaxDesignVideoPending\s*\(/);
assert.match(canvasJs, /function resumeMiniMaxDesignVideoTasks\s*\(/);

const resumeStart = canvasJs.indexOf('function resumeMiniMaxDesignVideoTasks');
const resumeEnd = canvasJs.indexOf('\nfunction ', resumeStart + 10);
const resumeSource = canvasJs.slice(resumeStart, resumeEnd < 0 ? undefined : resumeEnd);
assert.doesNotMatch(resumeSource, /method\s*:\s*['"]POST['"]/);
assert.doesNotMatch(resumeSource, /runMiniMaxDesignVideoNode\s*\(/);

const runStart = canvasJs.indexOf('async function runVideoNode');
const runEnd = canvasJs.indexOf('\nasync function ', runStart + 10);
const runSource = canvasJs.slice(runStart, runEnd < 0 ? undefined : runEnd);
assert.match(runSource, /findActivePaidVideoPending/);
assert.match(runSource, /runMiniMaxDesignVideoNode/);

console.log('MiniMax Design video lifecycle tests passed');

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

/* MiniMax 官方改走异步：提交拿 task_id -> 落盘 -> 轮询。
   以前是一个 POST 挂到出片，连接一断 task_id 就没了，任务无法恢复。 */

// 三个函数都在，且有独立的任务类型
assert.match(canvas, /const MINIMAX_VIDEO_TASK_TYPE = 'minimax-video';/);
assert.match(canvas, /async function runMinimaxVideoNode\(/);
assert.match(canvas, /async function pollMinimaxVideoTask\(/);
assert.match(canvas, /function resumeMinimaxVideoTasks\(\)/);
assert.match(canvas, /function findMinimaxVideoPending\(/);

// 提交后必须先落盘再轮询——这一步之后刷新/重启才能靠 task_id 找回结果
const run = canvas.slice(canvas.indexOf('async function runMinimaxVideoNode('),
                         canvas.indexOf('function resumeMinimaxVideoTasks()'));
assert.match(run, /pending\.task_id = submission\.task_id;/);
const idIdx = run.indexOf('pending.task_id = submission.task_id;');
const saveIdx = run.indexOf('await saveCanvas();', idIdx);
const pollIdx = run.indexOf('return pollMinimaxVideoTask(', idIdx);
assert.ok(idIdx < saveIdx && saveIdx < pollIdx, '顺序必须是：存 task_id -> 落盘 -> 轮询');
assert.match(run, /'\/api\/minimax\/video-submit'/);

// 轮询走新接口，并复用已有的"上游任务已消失"判定
const poll = canvas.slice(canvas.indexOf('async function pollMinimaxVideoTask('),
                          canvas.indexOf('async function runMinimaxVideoNode('));
assert.match(poll, /\/api\/minimax\/tasks\//);
assert.match(poll, /isUpstreamTaskGone\(response\.status, failMsg\)/);
assert.match(poll, /latest\.terminal = true;/);
assert.match(poll, /activeMinimaxVideoPolls/, '同一任务不能并发轮询');

// 路由：必须在通用同步路径之前截住，否则又走回长请求
const runner = canvas.slice(canvas.indexOf('async function runVideoNode(nodeId'));
const dispatchIdx = runner.indexOf('return runMinimaxVideoNode(');
const syncIdx = runner.indexOf("cascadeFetch('/api/canvas-video'");
assert.ok(dispatchIdx > 0 && dispatchIdx < syncIdx, 'minimax 要在通用同步路径之前分流');

// 已有在跑的任务直接接上轮询，不重复提交（避免重复扣费）
assert.match(runner.slice(0, dispatchIdx), /const existing = findMinimaxVideoPending\(node\);/);

// 恢复链路两处都要带上
assert.strictEqual(canvas.split('resumeMinimaxVideoTasks();').length - 1, 2);

console.log('minimax-async-video: 全部通过');

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const canvas = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'canvas.js'), 'utf8');

/* 点生成时先建本地占位，拿到服务器返回再贴真 task_id。中间页面一刷新，占位就成了
   孤儿：没有任务号 -> 结果匹配不上、也轮询不了 -> 永远转圈，还挡着「再跑一次」
   提示会重复计费。实测攒了 6 个，最久转了 3 天多。 */

assert.match(canvas, /function sweepOrphanPendings\(\)/);
const fn = canvas.slice(canvas.indexOf('function sweepOrphanPendings'),
                        canvas.indexOf('function resumeCanvasImageTasks'));
// 有任务号的一律不动，别把真在跑的任务清了
assert.ok(fn.includes('if(serverTaskIdOf(p) || p?.canvasTaskId) return true;'),
  '有任务号的任务不能被清掉');
// 只清超时的，刚提交还没回来的要留着
assert.match(fn, /Date\.now\(\) - started < ORPHAN_PENDING_MAX_MS\) return true;/,
  '刚提交的要留着，只清超时的');
assert.match(canvas, /const ORPHAN_PENDING_MAX_MS = 10 \* 60 \* 1000;/);
// 清完要落盘，否则刷新一次又回来了
assert.ok(fn.includes('scheduleSave()'), '清完要保存');
// 挂在恢复任务的入口上，每次打开画布都扫一遍
assert.match(canvas, /function resumeCanvasImageTasks\(\)\{\s*\n\s*sweepOrphanPendings\(\);/);

console.log('orphan-pending-sweep: 全部通过');

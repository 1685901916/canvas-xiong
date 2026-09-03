const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

/* 通用视频路径（MiniMax 官方 / comfly / 火山 等）是一个 POST 同步挂到生成完，
   上游不返回 task_id。此前它从不设置 canvasTaskType，保存时被兜底成 'online-image'，
   于是被图片恢复逻辑接管，报出"提交状态未知"这种对不上的错。 */

// 1. 有独立类型，不再混进图片任务
assert.match(canvas, /const SYNC_VIDEO_TASK_TYPE = 'canvas-video';/);
assert.notStrictEqual('canvas-video', 'online-image');

// 2. 发请求前显式打上类型
const generic = canvas.slice(canvas.indexOf('const syncPending = pendingById(out, pendingId);'),
                             canvas.indexOf('const syncPending = pendingById(out, pendingId);') + 420);
assert.ok(generic.length > 0, '通用视频路径没有设置 pending 类型');
assert.match(generic, /syncPending\.canvasTaskType = SYNC_VIDEO_TASK_TYPE;/);
assert.ok(canvas.indexOf('const syncPending = pendingById(out, pendingId);')
        < canvas.indexOf("cascadeFetch('/api/canvas-video'"), '必须在发请求之前就打好类型');

// 3. 保存兜底按来源节点推断，不再一律 online-image
assert.doesNotMatch(canvas, /copy\.canvasTaskType = copy\.canvasTaskType \|\| item\.type \|\| 'online-image';/,
  '不能再无条件兜底成图片任务');
assert.match(canvas, /item\?\.run\?\.node\?\.type === 'video' \? SYNC_VIDEO_TASK_TYPE : 'online-image'/);

// 4. 恢复时要明确告知，而不是悄悄消失或给含糊的错
const resume = canvas.slice(canvas.indexOf('function resumeSyncVideoTasks()'),
                            canvas.indexOf('function resumeSyncVideoTasks()') + 1500);
assert.match(resume, /pending\.terminal = true;/, '断掉的同步请求要标终态，否则会一直挂在生成中');
assert.match(resume, /可能已经生成并计费/, '必须提示可能已计费，让用户去核对');
assert.match(resume, /无法再取回/, '要说清结果取不回来了');
assert.match(resume, /videoNode\.running = false;/, '节点要退出"生成中"状态');

// 5. 有时间阈值：别的标签页可能正在跑同一个任务，不能一打开就判死
assert.match(canvas, /const SYNC_VIDEO_LOST_AFTER_MS = 30 \* 60 \* 1000;/);
assert.match(resume, /if\(!\(age > SYNC_VIDEO_LOST_AFTER_MS\)\) return;/, '未超时的不能动');
assert.ok(resume.indexOf('SYNC_VIDEO_LOST_AFTER_MS') < resume.indexOf('pending.terminal = true;'),
  '先判超时再标终态');

// 6. 挂进两条恢复链路（打开画布 / 远端覆盖）
assert.match(canvas, /function resumeSyncVideoTasks\(\)\{/, '要有定义');
assert.strictEqual(canvas.split('resumeSyncVideoTasks();').length - 1, 2,
  '打开画布和远端覆盖两条链路都要调用');
// 紧跟在其它 resume 之后，别漏在某一条链路上
const pairs = canvas.split('resumeMiniMaxDesignVideoTasks();').slice(1)
  .filter(chunk => chunk.slice(0, 40).includes('resumeSyncVideoTasks();')).length;
assert.strictEqual(pairs, 2, '两条恢复链路都要带上同步视频恢复');

console.log('sync-video-task-type: 全部通过');

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

/* 多标签页下 pending 的合并。
   原来 409 冲突时无条件保留本地那份：没在跑任务的标签页手里是旧快照
   （还停在 submitting、只有本地兜底 id），一保存就把另一个标签页刚拿到的
   真 task_id 覆盖掉，服务端在新旧之间来回震荡，任务再也恢复不了。 */

assert.doesNotMatch(canvas, /const localPending = activePendingItems\(localNode\._pending \|\| \[\]\);/,
  '不能再无条件保留本地 pending');
assert.match(canvas, /merged\._pending = mergePendingLists\(remoteNode\._pending \|\| \[\], localNode\._pending \|\| \[\]\);/);

// 取出合并逻辑实际跑一遍
const si = canvas.indexOf('function pendingProgressScore(pending)');
const ei = canvas.indexOf('function mergeRemoteCanvasIntoLocalForSave');
const block = canvas.slice(si, ei);
const { mergePendingLists, pickBetterPending } = new Function(
  'serverTaskIdOf', 'isResumableCanvasPending', 'nowMs',
  block + '; return {mergePendingLists, pickBetterPending};'
)(
  p => { const id = String(p?.task_id || p?.canvasTaskId || ''); return (!id || id === String(p?.id||'') || /^p_[0-9a-z]+_\d+$/i.test(id)) ? '' : id; },
  () => true,
  () => 1000000
);

const stale = { id: 'p_1', canvasTaskId: 'p_1', canvasTaskStatus: 'submitting', startedAt: 100 };
const fresh = { id: 'p_1', task_id: '437706239734023', canvasTaskStatus: 'running', startedAt: 100 };

// 真任务 id 必须胜出，方向无关
assert.strictEqual(pickBetterPending(stale, fresh), fresh, '真任务 id 要赢过本地兜底 id');
assert.strictEqual(pickBetterPending(fresh, stale), fresh, '换个顺序结论要一致');

// 合并后同一个 id 只留一条，且是信息量大的那条
const merged = mergePendingLists([stale], [stale, fresh]);
assert.strictEqual(merged.length, 1, '同一个 pending 不能重复');
assert.strictEqual(merged[0].task_id, '437706239734023');

// 终态不能被中间态覆盖回去
const running = { id: 'p_2', task_id: 'T2', canvasTaskStatus: 'running', startedAt: 1 };
const done = { id: 'p_2', task_id: 'T2', terminal: true, canvasTaskStatus: 'failed', startedAt: 1 };
assert.strictEqual(pickBetterPending(running, done), done, '终态是确定结论，不能退回中间态');

// 分数相同时取更晚的
const older = { id: 'p_3', task_id: 'T3', startedAt: 10 };
const newer = { id: 'p_3', task_id: 'T3', startedAt: 20 };
assert.strictEqual(pickBetterPending(older, newer), newer);

// 本地独有的一定保留
const onlyLocal = { id: 'l_1', task_id: 'L1', startedAt: 1 };
assert.strictEqual(mergePendingLists([], [onlyLocal]).length, 1, '本地独有的要保留');

// 远端独有 + 很新 = 别的标签页刚提交的，接纳
const freshRemote = { id: 'r_new', task_id: 'RN', startedAt: 1000000 - 5000 };
assert.strictEqual(mergePendingLists([freshRemote], []).length, 1, '别的标签页刚提交的要接纳');

// 远端独有 + 很旧 = 本地已经把它了结了，远端只是旧副本，必须丢弃。
// 不丢的话输出节点上会永远挂着一张已完成任务的"生成中"僵尸卡片。
const staleRemote = { id: 'r_old', task_id: 'RO', startedAt: 1 };
assert.strictEqual(mergePendingLists([staleRemote], []).length, 0, '已了结任务的远端旧副本不能复活');

// 本地已移除、远端还留着旧副本 —— 这正是实测中出现的僵尸场景
const zombie = { id: 'p_done', canvasTaskId: 'p_done', canvasTaskStatus: 'submitting', startedAt: 1 };
assert.strictEqual(mergePendingLists([zombie], [{id:'other', task_id:'X', startedAt: 999999}]).length, 1,
  '完成后被移除的 pending 不该被远端加回来');

console.log('pending-merge: 全部通过');

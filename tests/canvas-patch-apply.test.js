const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const shell = fs.readFileSync(path.join(root, 'static', 'index.html'), 'utf8');

/* agent 用原语改画布 → 服务端广播 canvas_patch → 页面按 id 增量落地。
   不能再走 applyRemoteCanvasData 的全量 render()（实测 358ms 冻结）。 */

assert.match(canvas, /function handleCanvasPatchMessage\(data\)/);
assert.match(canvas, /if\(event\.data\?\.type === 'canvas_patch'\) handleCanvasPatchMessage\(event\.data\);/,
  'WS 分发要注册 canvas_patch');
assert.match(shell, /data\.type === 'canvas_updated' \|\| data\.type === 'canvas_patch'/,
  'shell 要把 canvas_patch 转发给 iframe');

const h = canvas.slice(canvas.indexOf('function handleCanvasPatchMessage(data)'),
                       canvas.indexOf('function handleCanvasUpdatedMessage(data)'));

// 新节点直接 append DOM，而不是触发全量 render
assert.match(h, /nodesEl\.appendChild\(renderNode\(remote\)\)/, '新增节点要直接挂 DOM');
assert.doesNotMatch(h, /\brender\(\);/, '补丁处理里不能出现全量 render()');
assert.match(h, /refreshNodes\(changedIds\)/, '已有节点按 id 刷新');

// 删除要打墓碑，否则本地待保存的合并会把节点加回来
assert.ok(h.indexOf('markNodesDeleted([...removed])') > 0, '删除要打墓碑');
assert.ok(h.indexOf('markNodesDeleted') < h.indexOf('nodes = nodes.filter(n => !removed.has(n.id))'),
  '先打墓碑再过滤');

// 版本号对齐，避免页面自己的下一次保存撞 409
assert.match(h, /lastCanvasUpdatedAt = Math\.max\(Number\(lastCanvasUpdatedAt \|\| 0\), at\);/);
assert.match(h, /lastAppliedCanvasPatchAt = at;/);

// 本地瞬态运行字段不能被远端补丁抹掉
assert.match(h, /\['running','runStatus','runError','_pending','_cascadeIdx','_cascadeFailed'\]/,
  '要保留本地 running/_pending 等瞬态字段');

// 已经用补丁应用过的版本，canvas_updated 不能再触发全量同步
const upd = canvas.slice(canvas.indexOf('function handleCanvasUpdatedMessage(data)'),
                         canvas.indexOf('function handleCanvasUpdatedMessage(data)') + 900);
assert.match(upd, /remoteUpdatedAt <= Number\(lastAppliedCanvasPatchAt \|\| 0\)\) return;/,
  '补丁已落地的版本不能再全量同步');

// 服务重启后 shell 要自动重连，否则补丁通道悄悄死掉、页面退化成 2.5s 轮询 + 全量重绘
assert.match(shell, /function connectStats\(\)/, 'shell 要有 connectStats');
assert.match(shell, /ws\.onclose = \(\) => \{\s*setTimeout\(connectStats, statsRetryMs\);/, 'onclose 要重连');
assert.match(shell, /ws\.onopen = \(\) => \{ statsRetryMs = 1000; \};/, '连上后退避归零');

console.log('canvas-patch-apply: 全部通过');

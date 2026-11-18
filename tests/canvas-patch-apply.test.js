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

// 单独打开 canvas.html 时没有 shell 转发 WebSocket，必须自己连一条，
// 否则 agent 改了画布页面完全没反应（用户实测「没变化」）。
assert.match(canvas, /function startStandaloneCanvasSocket\(\)/);
assert.match(canvas, /if\(window\.top !== window\.self\) return;/, '在 iframe 里要让 shell 转发，别重复连');
assert.match(canvas, /ws\/stats\?client_id=\$\{CLIENT_ID\}/);
assert.match(canvas, /data\?\.type === 'canvas_patch'\) handleCanvasPatchMessage\(data\)/);

// 空转保存死循环：每次远端同步都会重渲染节点，重渲染走到 updateSourceRatioFromFirstRef，
// 它以前无条件 scheduleSave() -> 版本号变 -> 轮询发现更新 -> 再同步，永不停歇。
// 副作用是页面拿着旧数据把 agent 刚改好的东西盖回去。
const ratioFn = canvas.slice(canvas.indexOf('const updateSourceRatioFromFirstRef'),
                             canvas.indexOf('const syncSizeControls'));
assert.doesNotMatch(ratioFn, /\n\s*scheduleSave\(\);/, '不能无条件保存');
assert.match(ratioFn, /if\(changed\) scheduleSave\(\);/, '值没变就不要保存');

// 页面保存只报改过的节点：没报的服务器保持自己的版本，页面的旧副本覆盖不了别人
assert.match(canvas, /const savedNodeSignatures = new Map\(\)/);
assert.match(canvas, /dirty_node_ids:dirtyIds/, '保存要带上脏节点清单');
assert.match(canvas, /removed_node_ids:\[\.\.\.deletedNodeIds\]/, '删除要显式告诉服务器');
assert.match(canvas, /const dirtyIds = dirtyNodeIdsFrom\(payloadNodes, payloadSignatures\)/);
// 快照必须在三个地方对齐，否则要么整份都算脏、要么改动被漏掉。
// 查「函数体里有没有调用」，不查两行是否相邻——别人往中间加一行注释不该让测试挂掉。
function bodyOf(head){
  const i = canvas.indexOf(head);
  if (i < 0) return '';
  const ends = [canvas.indexOf('\nasync function ', i + 10), canvas.indexOf('\nfunction ', i + 10)]
    .filter(n => n > 0);
  return ends.length ? canvas.slice(i, Math.min(...ends)) : canvas.slice(i);
}
const saveBody = bodyOf('async function saveCanvas()');
assert.ok(saveBody.includes('clearDeletedNodeMarks()'), '保存成功后要清墓碑');
// 对齐的是「这次发出去的」签名（发送时算好），保存请求在路上时的新改动不能被记成已保存
assert.ok(saveBody.includes('rememberSentCanvasState(payloadSignatures, payloadConnectionKeys)'), '保存成功后要对齐快照');
// 保存要带上版本基准：服务器据此不复活别处删掉的节点、按字段三方合并、按增删合并连线
assert.ok(saveBody.includes('...saveBase'), '保存要带上版本基准');
const openBody = bodyOf('async function openCanvas(');
assert.ok(openBody.includes('rememberSavedNodes(nodes, connections)'), '打开画布时就要记下服务器上的样子，否则第一次保存会整份覆盖');
assert.ok(saveBody.includes('dirty_node_ids'), '保存要带上脏节点清单');
const applyBody = bodyOf('function applyRemoteCanvasData(');
assert.ok(applyBody.includes('rememberSavedNodes()'), '整份同步后要对齐快照');
assert.match(canvas, /removed\.forEach\(id => savedNodeSignatures\.delete\(id\)\)/, '增量补丁后对齐');

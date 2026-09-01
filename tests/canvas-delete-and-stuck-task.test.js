const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');

/* ===== 1. 卡死的 pending：本地 id 不能当服务端任务 id ===== */
const i = canvas.indexOf('function serverTaskIdOf');
assert.ok(i > 0, '缺少 serverTaskIdOf');
const fnSrc = canvas.slice(i, canvas.indexOf('}', canvas.indexOf('return id;', i)) + 1);
const serverTaskIdOf = new Function(fnSrc + '; return serverTaskIdOf;')();

// 提交没拿到 task_id 时 canvasTaskId 会兜底成本地 pending id，拿它查询永远 404
assert.strictEqual(
  serverTaskIdOf({ id: 'p_cb5bfc98caa8f_1788234611446', canvasTaskId: 'p_cb5bfc98caa8f_1788234611446' }), '',
  '本地 pending id 必须判为"没有任务 id"');
assert.strictEqual(serverTaskIdOf({ id: 'p_x_1', canvasTaskId: 'p_y_2' }), '', '任何 p_xxx_数字 都是本地 id');
assert.strictEqual(serverTaskIdOf({}), '');
assert.strictEqual(serverTaskIdOf({ id: 'p_a_1', canvasTaskId: '' }), '');
// 真的服务端 id 必须保留，否则会误杀正在跑的任务
assert.strictEqual(
  serverTaskIdOf({ id: 'p_a_1', canvasTaskId: 'canvas_img_abaa271f5d00486c' }), 'canvas_img_abaa271f5d00486c');
assert.strictEqual(serverTaskIdOf({ id: 'p_a_1', task_id: '12345678', canvasTaskId: 'p_a_1' }), '12345678',
  'task_id 优先于 canvasTaskId');

// 三处 resume（autodl / runninghub / minimax-design）都要改过来
const legacy = canvas.split("String(pending.task_id || pending.canvasTaskId || '').trim()").length - 1;
assert.strictEqual(legacy, 0, '还有 resume 分支在直接拼 task_id||canvasTaskId');
assert.strictEqual(canvas.split('const taskId = serverTaskIdOf(pending);').length - 1, 3,
  '应有 3 处 resume 使用 serverTaskIdOf');

/* ===== 2. 删除的节点不能被远端合并复活 ===== */
assert.match(canvas, /const deletedNodeIds = new Set\(\);/);
assert.match(canvas, /function markNodesDeleted\(ids\)/);
assert.match(canvas, /function clearDeletedNodeMarks\(\)/);
assert.match(canvas, /function dropDeletedFromRemote\(remoteNodes, remoteConnections\)/);

// 两条删除路径都要打墓碑
const single = canvas.slice(canvas.indexOf('function deleteNode(id, event)'), canvas.indexOf('function deleteNode(id, event)') + 420);
assert.match(single, /markNodesDeleted\(\[id\]\);/, '单节点删除要打墓碑');
assert.ok(single.indexOf('markNodesDeleted') < single.indexOf('nodes = nodes.filter'), '先打墓碑再过滤');

const multi = canvas.slice(canvas.indexOf('function deleteSelectedNodes()'), canvas.indexOf('function deleteSelectedNodes()') + 900);
assert.match(multi, /markNodesDeleted\(\[\.\.\.toDelete\]\);/, '批量删除要打墓碑');

// 两条"远端数据进本地"的路径都要过滤
const merge = canvas.slice(canvas.indexOf('function mergeRemoteCanvasIntoLocalForSave'), canvas.indexOf('function mergeRemoteCanvasIntoLocalForSave') + 600);
assert.match(merge, /dropDeletedFromRemote\(remote\.nodes, remote\.connections\)/, '409 合并要过滤');
const apply = canvas.slice(canvas.indexOf('function applyRemoteCanvasData'), canvas.indexOf('function applyRemoteCanvasData') + 1400);
assert.match(apply, /dropDeletedFromRemote\(remote\.nodes, remote\.connections\)/, '远端覆盖也要过滤');

// 保存成功后必须清墓碑，否则以后别的客户端新增的同 id 节点会被永久挡掉
assert.match(canvas, /if\(!res\.ok\) throw new Error\('save failed'\);[\s\S]{0,140}clearDeletedNodeMarks\(\);/,
  '保存成功后要清墓碑');

/* ===== 3. 缓存版本号由服务端启动时同步，来源是 main.py ===== */
// canvas.html 里的 ?v= 是 sync_static_html_versions() 每次启动重写的，
// 断言那个文件没意义（手改会被覆盖）。要断言的是版本来源和覆盖范围。
const mainPy = fs.readFileSync(path.join(root, 'main.py'), 'utf8');
assert.doesNotMatch(mainPy, /CANVAS_RUNTIME_VERSION = "2026\.08\.28-minimax-design-local-1"/,
  '画布运行时脚本改过了，CANVAS_RUNTIME_VERSION 必须跟着顶');

// 这轮改的 canvas-list.js / smart-canvas.js 也必须纳入运行时版本同步，
// 否则它们只跟 VERSION 文件走，改了代码用户刷新还是旧缓存
assert.match(mainPy, /"canvas-list\.html":\s*\("\/static\/js\/canvas-list\.js",\)/,
  '列表页脚本要纳入运行时版本同步');
assert.match(mainPy, /"smart-canvas\.html":\s*\("\/static\/js\/smart-canvas\.js",\)/,
  '智能画布脚本要纳入运行时版本同步');
assert.match(mainPy, /"canvas\.html":\s*\("\/static\/css\/canvas\.css".*canvas\.js"\)/,
  'canvas.html 原有的三个资源不能漏');

/* ===== 4. dropDeletedFromRemote 的实际行为 ===== */
const di = canvas.indexOf('const deletedNodeIds = new Set();');
const helpers = canvas.slice(di, canvas.indexOf('// 取"真正的服务端任务 id"', di));
const H = new Function(helpers + '; return {markNodesDeleted, clearDeletedNodeMarks, dropDeletedFromRemote};')();
H.markNodesDeleted(['n1', 'n3']);
const r = H.dropDeletedFromRemote(
  [{ id: 'n1' }, { id: 'n2' }, { id: 'n3' }, { id: 'n4' }],
  [{ from: 'n1', to: 'n2' }, { from: 'n2', to: 'n4' }, { from: 'n4', to: 'n3' }]);
assert.deepStrictEqual(r.nodes.map(n => n.id), ['n2', 'n4'], '已删除的节点必须被挡掉');
assert.strictEqual(r.connections.length, 1, '连到已删除节点的连线也要挡掉');
assert.deepStrictEqual(r.connections[0], { from: 'n2', to: 'n4' });
H.clearDeletedNodeMarks();
assert.strictEqual(H.dropDeletedFromRemote([{ id: 'n1' }], []).nodes.length, 1, '清空后不再拦截');

/* ===== 5. 上游任务消失必须判为终态 ===== */
// 之前 404「任务未找到」被当成临时查询失败：不标 terminal，于是每次打开画布
// 恢复逻辑又把节点置成"生成中"，生成按钮永远灰着，用户既看不到失败也没法重来。
const gi = canvas.indexOf('function isUpstreamTaskGone');
assert.ok(gi > 0, '缺少 isUpstreamTaskGone');
const goneSrc = canvas.slice(gi, canvas.indexOf('}', canvas.indexOf('return /', gi)) + 1);
const isUpstreamTaskGone = new Function(goneSrc + '; return isUpstreamTaskGone;')();

assert.strictEqual(isUpstreamTaskGone(404, 'whatever'), true, '404 就是没了');
assert.strictEqual(isUpstreamTaskGone(500, '上游生成任务未找到，可能已过期或被清理'), true);
assert.strictEqual(isUpstreamTaskGone(500, 'task not found'), true);
assert.strictEqual(isUpstreamTaskGone(500, 'Task Not Found'), true);
assert.strictEqual(isUpstreamTaskGone(502, '网关超时'), false, '临时故障不能误判成终态');
assert.strictEqual(isUpstreamTaskGone(503, ''), false);
assert.strictEqual(isUpstreamTaskGone(200, ''), false);

// 两个 poller 都要用它，并且都要标 terminal（否则恢复逻辑还会复活）
const gonePatch = /if\(isUpstreamTaskGone\(response\.status, failMsg\)\)\{[\s\S]{0,420}?latest\.terminal = true;[\s\S]{0,420}?node\.running = false;/g;
assert.strictEqual((canvas.match(gonePatch) || []).length, 2,
  'MiniMax Design 和 RunningHub 两个 poller 都要处理"任务已消失"');
// 不能再有裸抛的查询失败分支
assert.doesNotMatch(canvas, /if\(!response\.ok\) throw new Error\(await responseErrorMessage\(response, 'MiniMax Design 任务查询失败'\)\);/);
assert.doesNotMatch(canvas, /if\(!response\.ok\) throw new Error\(await responseErrorMessage\(response, 'RunningHub 任务查询失败'\)\);/);

/* ===== 6. pending 生命周期：死任务不能锁死节点 ===== */
// 症状：节点永远"生成中"/"任务仍在运行"，删掉失败卡片一刷新又回来。
// 根因有三个，缺一个都修不好。

// (a) 删 pending 卡片必须落盘 —— 原来只有删图片那条分支调了 scheduleSave()
const delHandler = canvas.slice(canvas.indexOf("const pid = wrap.dataset.pendingId;"),
                                canvas.indexOf("const pid = wrap.dataset.pendingId;") + 700);
assert.match(delHandler, /node\._pending = \(node\._pending \|\| \[\]\)\.filter\(p => p\.id !== pid\);[\s\S]{0,180}?scheduleSave\(\);/,
  '删除 pending 后必须 scheduleSave()，否则刷新就回来了');

// (b) 拦截新提交时，本地兜底 id 不能算"有任务在跑"
const guard = canvas.slice(canvas.indexOf('function findActivePaidVideoPending'),
                           canvas.indexOf('function findActivePaidVideoPending') + 900);
assert.match(guard, /Boolean\(serverTaskIdOf\(item\)\)/, '拦截条件必须用真任务 id');
assert.doesNotMatch(guard, /Boolean\(item\.task_id \|\| item\.canvasTaskId\)/,
  '不能再用"有任何 id 就算在跑"——本地 p_xxx 兜底 id 会把节点永久锁死');

// (c) unknown_submission 分两类，处理方式不同：
//   · 恢复阶段（3 处）：已经确认没有服务端任务 id，标 terminal 停止复活
//   · 提交 catch（2 处）：上游可能已建任务，故意保持非终态，留给用户手动查询
// 但两类的共同不变式是——都不能拦截新提交，因为都拿不出真任务 id。
assert.strictEqual(canvas.split("pending.canvasTaskStatus = 'unknown_submission';").length - 1, 5);
assert.strictEqual(canvas.split('pending.terminal = true;').length - 1, 3,
  '恢复阶段的三处要标终态');
assert.match(canvas, /pending\.terminal = false;/,
  '提交 catch 处保持非终态是有意的（上游可能已建任务），不要顺手改掉');
// 共同不变式：两类都拿不出真任务 id，所以都不会走进拦截分支
assert.strictEqual(serverTaskIdOf({ id: 'p_a_1', canvasTaskId: 'p_a_1' }), '',
  'unknown_submission 的兜底 id 必须判为无任务，否则仍会锁死节点');

// (d) 拦截提示要能让用户自救：给出任务 ID 和清除办法
const msg = canvas.slice(canvas.indexOf('任务仍在排队或生成中'), canvas.indexOf('任务仍在排队或生成中') + 260);
assert.match(msg, /任务 ID：/, '拦截时要告诉用户是哪个任务挡住了');
assert.match(msg, /删掉它的进度卡片/, '要告诉用户怎么解除');

console.log('canvas-delete-and-stuck-task: 全部通过');

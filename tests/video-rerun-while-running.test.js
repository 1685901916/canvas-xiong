const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8').replace(/\r\n/g, '\n');

/* 生成中也要能再跑一次：原来按钮 disabled + 两道硬拦截，用户只能干等。
   现在改成"可点 + 明确确认"，既不会误触重复计费，也不把人锁死。 */

// 1. 按钮不再 disabled，文案要提示可以再跑
const btn = canvas.slice(canvas.indexOf('data-lucide="clapperboard" class="w-4 h-4"></i>${node.running'),
                         canvas.indexOf('data-lucide="clapperboard" class="w-4 h-4"></i>${node.running') + 200);
assert.ok(btn.length > 0, '找不到视频生成按钮');
const btnLine = canvas.split('\n').find(l => l.includes('gen-btn') && l.includes('clapperboard'));
assert.doesNotMatch(btnLine, /disabled/, '生成中不应再禁用按钮');
assert.match(btnLine, /再跑一次/, '生成中要提示可以再跑一次');

// 2. 调度入口支持 force，但级联运行中的节点仍然要挡
const dispatch = canvas.slice(canvas.indexOf('async function runCanvasGenerate(nodeId'),
                              canvas.indexOf('async function runCanvasGenerate(nodeId') + 700);
assert.match(dispatch, /runCanvasGenerate\(nodeId, opts=\{\}\)/, '要能接收 opts');
assert.match(dispatch, /if\(cascadeRunningIds\.has\(nodeId\)\) return;/, '级联运行中仍要挡');
assert.match(dispatch, /if\(node\.running && !opts\.force\) return;/, 'force 才放行运行中的节点');
assert.match(dispatch, /\{cascade:false, \.\.\.opts\}/, 'opts 要透传下去');

// 3. 视频节点的两道拦截都要认 force
const runner = canvas.slice(canvas.indexOf('async function runVideoNode(nodeId'),
                            canvas.indexOf('async function runVideoNode(nodeId') + 700);
assert.match(runner, /node\.running && !opts\.cascade && !opts\.force/, '早退判断要认 force');
assert.match(runner, /opts\.force \? null : findActivePaidVideoPending\(node\)/,
  '付费任务拦截要认 force');

// 4. 强制之前必须确认，且要说清会重复计费
const handler = canvas.slice(canvas.indexOf("wrap.querySelector('.gen-btn').onclick = e => {\n        e.stopPropagation();\n        if(node.running){"),
                             canvas.indexOf("wrap.querySelector('.gen-btn').onclick = e => {\n        e.stopPropagation();\n        if(node.running){") + 900);
assert.ok(handler.length > 0, '找不到带确认的点击处理');
assert.match(handler, /confirm\(/, '强制重跑前必须确认');
assert.match(handler, /都会计费/, '确认文案要讲清重复计费');
assert.match(handler, /runCanvasGenerate\(node\.id, \{force:true\}\)/, '确认后才强制跑');
assert.ok(handler.indexOf('confirm(') < handler.indexOf('{force:true}'),
  '必须先确认再提交');

console.log('video-rerun-while-running: 全部通过');

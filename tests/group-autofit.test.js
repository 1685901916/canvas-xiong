const assert = require('assert');
const fs = require('fs');
const path = require('path');

const canvas = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'canvas.js'), 'utf8');

/* 组框只在建组那一刻算过一次包围盒。成员之后被拖动、改大小、删掉，框都不跟着动，
   越用越对不上——用户反复说「框还是不行」。拖拽/缩放结束时要重新贴合。 */

assert.match(canvas, /function fitGroupToMembers\(group\)/);
assert.match(canvas, /function fitGroupsContaining\(nodeIds, skipIds=\[\]\)/);

const fit = canvas.slice(canvas.indexOf('function fitGroupToMembers'),
                         canvas.indexOf('function connectedClusterIds'));

// 必须用 nodeBounds：它读真实 DOM 尺寸，服务端那套估值在这里会算错
assert.ok(fit.includes('nodeBounds(ids)'), '包围盒要按真实渲染尺寸算');
// 内边距和 groupSelectedImages 建组时一致，自动贴合的和手动框选的要长一样
assert.match(canvas, /GROUP_FIT_PAD = \{left:24, top:GROUP_HEADER_H, right:24, bottom:32\}/);
const manual = canvas.slice(canvas.indexOf('function groupSelectedImages'),
                            canvas.indexOf('function nodeBounds'));
assert.ok(manual.includes('box.x - 24') && manual.includes('box.y - GROUP_HEADER_H')
       && manual.includes('box.w + 48') && manual.includes('box.h + GROUP_HEADER_H + 32'),
  '手动建组和自动贴合共用同一套边距');
// 没变化就不要动，免得每次拖拽都产生一次多余保存
assert.ok(fit.includes('if(same) return false'), '尺寸没变时不应报告改动');

// 被拖动或被缩放的如果是组自己，跳过——用户手动调框的时候别跟他较劲
const end = canvas.slice(canvas.indexOf('function endDrag('), canvas.indexOf('function nodeRect('));
assert.ok(end.includes('fitGroupsContaining('), '拖拽结束要贴合');
assert.match(end, /draggedGroupIds[\s\S]{0,200}\.type === 'group'/, '要挑出被拖的组');
assert.match(end, /fitGroupsContaining\(\[\.\.\.nodeDragCompletedIds, \.\.\.resizeCompletedIds\], draggedGroupIds\)/,
  '把被拖的组作为跳过名单传进去');

console.log('group-autofit: 全部通过');

// 组框头部实测 134px（标题 42 + 提示行 + 已成组行 + 「设为对话目标」按钮）。
// 上边距小于它，成员就压在那个蓝色按钮上——原来建组用 58，画布上 12 个组无一幸免。
assert.match(canvas, /const GROUP_HEADER_H = 150;/, '上边距要盖过 134px 的头部');
const mk = canvas.slice(canvas.indexOf('function groupSelectedImages'),
                        canvas.indexOf('function nodeBounds'));
assert.ok(mk.includes('box.y - GROUP_HEADER_H'), '手动框选建组也要用它');
assert.ok(mk.includes('box.h + GROUP_HEADER_H + 32'), '高度跟着上边距一起算');
assert.ok(!/box\.y - 58/.test(mk), '不能再留 58 这个魔数');

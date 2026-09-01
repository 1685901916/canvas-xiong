const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

// 新建视频节点默认开「全能参考」。不开的话，非 multimodal 路径下多张参考图
// 只有第一张会被当 first_frame 提交，其余静默丢弃（main.py 的三条分支）。
const factory = canvas.slice(canvas.indexOf('function addVideoNode(point)'),
                             canvas.indexOf('function addVideoNode(point)') + 1600);
assert.match(factory, /multimodal:true,/, '新建视频节点要默认开启全能参考');
assert.match(factory, /useFrameRoles:false,/, '首尾帧与全能参考互斥，默认关闭');

// 两者互斥必须继续成立，否则可能同时为 true，后端分支判断会乱
assert.match(canvas, /if\(field === 'multimodal' && node\.multimodal\) node\.useFrameRoles = false;/);
assert.match(canvas, /if\(field === 'useFrameRoles' && node\.useFrameRoles\) node\.multimodal = false;/);

// 工厂只能有一个，否则改默认值会漏掉另一处。
// （另外两处 type:'video' 是菜单项描述，不是工厂）
assert.strictEqual(canvas.split('function addVideoNode(point)').length - 1, 1,
  '视频节点工厂只应有一个定义');
assert.strictEqual(canvas.split("id:uid('vid')").length - 1, 1,
  "只应有一处 uid('vid') 建节点，别处硬造会绕开默认值");

// 两个建节点入口都要路由到同一个工厂
assert.match(canvas, /if\(type === 'video'\) return addVideoNode\(point\);/, '连线建节点要走同一工厂');
assert.match(canvas, /if\(type === 'video'\) addVideoNode\(menuPoint\);/, '右键菜单要走同一工厂');

console.log('video-node-defaults: 全部通过');

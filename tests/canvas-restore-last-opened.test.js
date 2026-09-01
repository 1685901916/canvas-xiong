const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');

// —— 三个辅助函数都在 ——
assert.match(canvas, /const CANVAS_LAST_OPENED_KEY = 'canvasLastOpenedId';/);
assert.match(canvas, /function rememberLastOpenedCanvas\(id\)/);
assert.match(canvas, /function forgetLastOpenedCanvas\(\)/);
assert.match(canvas, /function lastOpenedCanvasId\(\)/);

// —— localStorage 一律包 try/catch，隐私模式下不能炸掉初始化 ——
for (const fn of ['rememberLastOpenedCanvas', 'forgetLastOpenedCanvas', 'lastOpenedCanvasId']) {
  const body = canvas.slice(canvas.indexOf(`function ${fn}`), canvas.indexOf(`function ${fn}`) + 260);
  assert.match(body, /try \{/, `${fn} 必须包 try`);
  assert.match(body, /catch\(e\)/, `${fn} 必须包 catch`);
}

// —— 初始化：没有 ?id 时回退到上次打开的画布 ——
assert.match(canvas, /const openId = new URLSearchParams\(window\.location\.search\)\.get\('id'\) \|\| lastOpenedCanvasId\(\);/);

// —— 打开成功要记住 ——
const openFn = canvas.slice(canvas.indexOf('async function openCanvas(id)'));
assert.match(openFn.slice(0, 900), /rememberLastOpenedCanvas\(canvas\.id\);/);

// —— 打开失败要清掉，否则坏 id 会每次刷新都失败一遍 ——
assert.match(canvas, /forgetLastOpenedCanvas\(\);\s*\n\s*window\.location\.replace\(canvasListUrlForProject\(canvas\?\.project/);

// —— 点“返回列表”必须清掉，否则用户再也待不住列表页 ——
const backBtn = canvas.slice(canvas.indexOf("backToManagerBtn?.addEventListener"), canvas.indexOf("backToManagerBtn?.addEventListener") + 420);
assert.match(backBtn, /forgetLastOpenedCanvas\(\);/, '返回按钮必须清记录');
assert.ok(backBtn.indexOf('forgetLastOpenedCanvas') < backBtn.indexOf('window.location.href'),
  '必须先清记录再跳转');

// —— canvas.html 的 ?v= 由服务端启动时重写，断言具体版本号只会在下次合理升级时误报。
// 这里只保证 canvas.js/css 确实带了版本参数，真正的版本来源在下面断言 main.py。——
assert.match(html, /canvas\.js\?v=[\w.\-]+/);
assert.match(html, /canvas\.css\?v=[\w.\-]+/);

// ===== canvas-list.js：刷新真正走的路径 =====
// 首页 shell 的 iframe 固定加载 canvas-list.html，所以恢复逻辑必须也在这里，
// 只改 canvas.js 是修不好刷新的。
const list = fs.readFileSync(path.join(root, 'static', 'js', 'canvas-list.js'), 'utf8');
const listHtml = fs.readFileSync(path.join(root, 'static', 'canvas-list.html'), 'utf8');
const shell = fs.readFileSync(path.join(root, 'static', 'index.html'), 'utf8');

assert.match(shell, /id="frame-canvas" data-src="\/static\/canvas-list\.html/,
  'shell 仍然把 canvas-list.html 作为画布页入口——恢复逻辑必须在列表页');

assert.match(list, /const CANVAS_LAST_OPENED_KEY = 'canvasLastOpenedId';/);
assert.match(list, /function rememberLastOpenedCanvas\(id\)/);
assert.match(list, /function lastOpenedCanvasId\(\)/);
assert.match(list, /function restoreLastOpenedCanvas\(\)/);
assert.match(list, /window\.location\.replace\(`\/static\/canvas\.html\?id=\$\{encodeURIComponent\(lastId\)\}`\)/);

// 恢复必须在 Boot 段的 loadAll() 之前，否则会先闪一下列表
// （loadAll(); 在别处的错误处理里也出现，所以只在 Boot 段内比较）
const bootIdx = list.indexOf('/* ===== Boot ===== */');
assert.ok(bootIdx > 0, '找不到 Boot 段');
const boot = list.slice(bootIdx);
assert.ok(boot.indexOf('restoreLastOpenedCanvas') < boot.indexOf('loadAll();'),
  '恢复逻辑要排在 Boot 段的 loadAll() 前面');

// 列表页打开画布时也要记住 —— smart 画布不经过 canvas.js，只能靠这里
const listOpen = list.slice(list.indexOf('function openCanvas(c)'), list.indexOf('function openCanvas(c)') + 500);
assert.match(listOpen, /rememberLastOpenedCanvas\(c\.id\);/, 'smart 画布只能靠列表页记住');

// localStorage 一律 try/catch
for (const fn of ['rememberLastOpenedCanvas', 'lastOpenedCanvasId']) {
  const body = list.slice(list.indexOf(`function ${fn}`), list.indexOf(`function ${fn}`) + 220);
  assert.match(body, /try \{[\s\S]*catch\(e\)/, `${fn} 必须包 try/catch`);
}

// ===== smart-canvas.js：返回也要清记录，否则智能画布回不到列表 =====
const smart = fs.readFileSync(path.join(root, 'static', 'js', 'smart-canvas.js'), 'utf8');
const smartBack = smart.slice(smart.indexOf('function backToCanvasList()'), smart.indexOf('function backToCanvasList()') + 400);
assert.match(smartBack, /removeItem\('canvasLastOpenedId'\)/, 'smart 返回必须清记录');

// ===== 缓存版本号由服务端启动时同步，断言来源而不是生成物 =====
// canvas-list.html / smart-canvas.html 里的 ?v= 是 sync_static_html_versions() 每次
// 启动重写的，手写死具体版本号的断言会在下一次合理升级时误报。
const mainPySrc = fs.readFileSync(path.join(root, 'main.py'), 'utf8');
assert.match(mainPySrc, /"canvas-list\.html":\s*\("\/static\/js\/canvas-list\.js",\)/,
  '列表页脚本必须纳入运行时版本同步，否则改了代码用户刷新还是旧缓存');
assert.match(mainPySrc, /"smart-canvas\.html":\s*\("\/static\/js\/smart-canvas\.js",\)/,
  '智能画布脚本必须纳入运行时版本同步');

console.log('canvas-restore-last-opened: 全部通过');

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const compositor = fs.readFileSync(path.join(root, 'static', 'js', 'free-compositor.js'), 'utf8');
const compositorCss = fs.readFileSync(path.join(root, 'static', 'css', 'free-compositor.css'), 'utf8');

async function run(){
  assert.match(html, /free-compositor\.css/);
  assert.match(html, /id="freeCompositorRoot"/);
  assert.match(html, /free-compositor-core\.js/);
  assert.match(html, /free-compositor\.js/);
  assert.match(html, /openFreeCompositorFromSelection\(\)/);
  assert.match(canvas, /window\.canvasFreeCompositorAdapter\s*=/);
  assert.match(canvas, /getSelectedImages\s*\(/);
  assert.match(canvas, /commitPngBlob\s*\(/);
  assert.match(canvas, /url:canvasDisplayMediaUrl\(node\.url, node\.name\)/);
  assert.match(canvas, /function freeCompositorNotice\(/);
  assert.doesNotMatch(canvas, /function openFreeCompositorFromSelection\(\)[^]*?\n}\n[^]*?toast\(/);

  assert.match(compositor, /acceptedImageFiles/);
  assert.match(compositor, /importDroppedFiles/);
  assert.match(compositor, /dataTransfer\.files/);
  assert.match(compositor, /core\.placeImportedLayers/);
  assert.match(compositor, /URL\.createObjectURL/);
  assert.match(compositor, /doc\.selectedId\s*=\s*imported\.at\(-1\)\.id/);
  assert.match(compositorCss, /\.fc-viewport\.drop-active/);
  assert.match(compositorCss, /\.fc-drop-hint/);

  const runtime = {window:{}, document:{getElementById:() => null}};
  vm.runInNewContext(compositor, runtime);
  const createDropController = runtime.window.createFreeCompositorDropController;
  assert.strictEqual(typeof createDropController, 'function');

  function createHarness({decode, files, documentState}={}){
    const doc = documentState || {layers:[{id:'base'}], selectedId:'base', width:1000, height:1600};
    const decoded = [];
    const placed = [];
    const statuses = [];
    const revoked = [];
    const cacheDeletes = [];
    const active = [];
    let commits = 0;
    let renders = 0;
    const controller = createDropController({
      getDocument:() => doc,
      getPoint:() => ({x:300, y:400}),
      createObjectURL:file => `blob:${file.name}`,
      revokeObjectURL:url => revoked.push(url),
      deleteCachedUrl:url => cacheDeletes.push(url),
      decode:async item => {
        decoded.push(item.file.name);
        if(decode) return decode(item);
        return {naturalWidth:100, naturalHeight:200};
      },
      placeImportedLayers:(layers, state, point, options) => {
        placed.push({layers, state, point, options});
        return layers.map((layer, index) => ({...layer, x:index, y:index}));
      },
      nextId:() => `import-${decoded.length}`,
      commit:() => { commits++; },
      render:() => { renders++; },
      setStatus:(message, error) => statuses.push({message, error}),
      setActive:value => active.push(value),
    });
    const event = {dataTransfer:{files:files || [], types:['Files'], dropEffect:''}, prevented:false, preventDefault(){ this.prevented = true; }};
    return {controller, doc, decoded, placed, statuses, revoked, cacheDeletes, active, event, commits:() => commits, renders:() => renders};
  }

  {
    let resolveDecode;
    const harness = createHarness({files:[{name:'one.png', type:'image/png'}], decode:() => new Promise(resolve => { resolveDecode = resolve; })});
    harness.controller.onDragEnter(harness.event);
    harness.controller.onDragOver(harness.event);
    assert.strictEqual(harness.event.prevented, true);
    assert.strictEqual(harness.event.dataTransfer.dropEffect, 'copy');
    assert.strictEqual(harness.active.at(-1), true);
    const pending = harness.controller.onDrop(harness.event);
    assert.strictEqual(harness.active.at(-1), false);
    resolveDecode({naturalWidth:100, naturalHeight:100});
    await pending;
  }

  {
    const harness = createHarness({files:[{name:'first.png', type:'image/png'}, {name:'note.txt', type:'text/plain'}]});
    await harness.controller.onDrop(harness.event);
    assert.deepStrictEqual(harness.decoded, ['first.png']);
    assert.deepStrictEqual(harness.doc.layers.map(layer => layer.name), [undefined, 'first.png']);
    assert.strictEqual(harness.statuses.at(-1).message, '已导入 1 张，跳过 1 个无效文件');
    assert.strictEqual(harness.placed[0].options.maxRatio, .8);
    assert.strictEqual(harness.placed[0].options.offset, 24);
    assert.strictEqual(harness.doc.selectedId, 'import-1');
  }

  {
    const harness = createHarness({
      files:[{name:'bad.png', type:'image/png'}, {name:'good.jpg', type:'image/jpeg'}],
      decode:item => item.file.name === 'bad.png' ? Promise.reject(new Error('bad image')) : {naturalWidth:30, naturalHeight:40},
    });
    await harness.controller.onDrop(harness.event);
    assert.deepStrictEqual(harness.decoded, ['bad.png', 'good.jpg']);
    assert.strictEqual(harness.doc.layers.at(-1).name, 'good.jpg');
    assert.strictEqual(harness.statuses.at(-1).message, '已导入 1 张，跳过 1 个无效文件');
  }

  {
    const harness = createHarness({files:[{name:'bad.gif', type:'image/gif'}], decode:() => Promise.reject(new Error('bad image'))});
    await harness.controller.onDrop(harness.event);
    assert.strictEqual(harness.commits(), 0);
    assert.deepStrictEqual(harness.doc.layers.map(layer => layer.id), ['base']);
    assert.strictEqual(harness.doc.selectedId, 'base');
    assert.strictEqual(harness.statuses.at(-1).error, true);
  }

  {
    const harness = createHarness({files:[{name:'cleanup.webp', type:'image/webp'}]});
    await harness.controller.onDrop(harness.event);
    harness.controller.cleanup();
    assert.deepStrictEqual(harness.revoked, ['blob:cleanup.webp']);
    assert.deepStrictEqual(harness.cacheDeletes, ['blob:cleanup.webp']);
  }

  console.log('free compositor integration tests passed');
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

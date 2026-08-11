const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const compositorCss = fs.readFileSync(path.join(root, 'static', 'css', 'free-compositor.css'), 'utf8');

async function run(){
  const compositorSource = fs.readFileSync(path.join(root, 'static', 'js', 'free-compositor.js'), 'utf8');
  const openStart = canvas.indexOf('function openFreeCompositorFromSelection()');
  const openEnd = canvas.indexOf('function videoFrameText', openStart);
  const openFunction = canvas.slice(openStart, openEnd);
  const compositorOpenStart = compositorSource.indexOf('async function open(items, nextAdapter)');
  const compositorOpenEnd = compositorSource.indexOf('root.freeCompositor', compositorOpenStart);
  const compositorOpenFunction = compositorSource.slice(compositorOpenStart, compositorOpenEnd);

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
  assert.ok(openStart >= 0 && openEnd > openStart, 'canvas compositor entry function should be available for source assertions');
  assert.ok(compositorOpenStart >= 0 && compositorOpenEnd > compositorOpenStart, 'compositor open function should be available for source assertions');
  assert.doesNotMatch(openFunction, /items\.length\s*<\s*2/);
  assert.doesNotMatch(compositorOpenFunction, /items\.length\s*<\s*2/);

  function createBrowserHarness({imageWidth=200, imageHeight=100, imageBehavior}={}){
    const hostListeners = {};
    const windowListeners = {};
    const createdUrls = [];
    const classList = () => {
      const values = new Set();
      return {
        add(...names){ names.forEach(name => values.add(name)); },
        remove(...names){ names.forEach(name => values.delete(name)); },
        toggle(name, force){
          const next = force === undefined ? !values.has(name) : Boolean(force);
          next ? values.add(name) : values.delete(name);
          return next;
        },
        contains:name => values.has(name),
      };
    };
    const artboard = {style:{}, getBoundingClientRect:() => ({left:0, top:0})};
    const stage = {style:{}, innerHTML:'', querySelector:selector => selector === '.fc-artboard' ? artboard : null};
    const generic = {style:{}, innerHTML:'', value:'', textContent:'', disabled:false, classList:classList()};
    const viewport = {...generic, classList:classList(), clientWidth:1000, clientHeight:800};
    const host = {
      classList:classList(),
      setAttribute(){},
      addEventListener(type, listener){ hostListeners[type] = listener; },
      querySelector(selector){
        if(selector === '.fc-stage') return stage;
        if(selector === '.fc-artboard') return artboard;
        if(selector === '.fc-viewport') return viewport;
        return generic;
      },
      set innerHTML(value){ this.shell = value; },
    };
    class TestImage {
      constructor(){ this.naturalWidth = imageWidth; this.naturalHeight = imageHeight; }
      set src(value){
        this._src = value;
        if(imageBehavior) imageBehavior(this, value);
        else this.onload?.();
      }
    }
    const canvasElement = {
      width:0,
      height:0,
      getContext:() => ({save(){}, restore(){}, translate(){}, rotate(){}, drawImage(){}, fillRect(){}, globalAlpha:1, fillStyle:''}),
      toBlob:resolve => resolve({type:'image/png'}),
    };
    const browser = {
      FreeCompositorCore:require(path.join(root, 'static', 'js', 'free-compositor-core.js')),
      document:{getElementById:id => id === 'freeCompositorRoot' ? host : null, body:{classList:classList()}, createElement:tag => tag === 'canvas' ? canvasElement : {}},
      addEventListener(type, listener){ windowListeners[type] = listener; },
      requestAnimationFrame(){},
      Image:TestImage,
      URL:{createObjectURL(file){ createdUrls.push(file?.name); return `blob:${file?.name || 'test'}`; }, revokeObjectURL(){}},
    };
    browser.window = browser;
    vm.runInNewContext(compositorSource, browser, {filename:'free-compositor.js'});
    return {browser, host, hostListeners, windowListeners, stage, status:generic, createdUrls};
  }

  function droppedFilesEvent(files){
    const target = {closest:selector => selector === '.fc-viewport' ? target : null};
    return {target, clientX:10, clientY:10, dataTransfer:{files, types:['Files'], dropEffect:''}, preventDefault(){}};
  }

  function clickAction(hostListeners, name){
    const target = {
      dataset:{fcAction:name},
      closest(selector){
        if(selector === '[data-fc-action]') return target;
        return null;
      },
    };
    hostListeners.click({target});
  }

  const flushAsync = () => new Promise(resolve => setImmediate(resolve));

  {
    const notices = [];
    const opens = [];
    const windowState = {
      canvasFreeCompositorAdapter:{getSelectedImages:() => [{id:'only', url:'/only.png'}]},
      freeCompositor:{open:(items, adapter) => { opens.push({items, adapter}); return Promise.resolve(); }},
    };
    const openFromSelection = new Function('window', 'freeCompositorNotice', `${openFunction}; return openFreeCompositorFromSelection;`)(windowState, message => notices.push(message));
    openFromSelection();
    assert.strictEqual(opens.length, 1);
    assert.deepStrictEqual(opens[0].items, [{id:'only', url:'/only.png'}]);
    assert.deepStrictEqual(notices, []);

    windowState.canvasFreeCompositorAdapter.getSelectedImages = () => [];
    openFromSelection();
    assert.strictEqual(opens.length, 1);
    assert.deepStrictEqual(notices, ['请先选择至少一张图片']);
  }

  {
    const {browser, stage} = createBrowserHarness();
    await browser.freeCompositor.open([{id:'only', name:'only', url:'/only.png'}], {});
    assert.match(stage.innerHTML, /width:200px;height:100px/);
  }

  {
    const {browser, stage} = createBrowserHarness({imageWidth:640, imageHeight:960});
    await browser.freeCompositor.open([{id:'zero-size', name:'zero-size', url:'/zero-size.png', naturalWidth:0, naturalHeight:0, width:0, height:0}], {});
    assert.match(stage.innerHTML, /width:640px;height:960px/);
    assert.match(stage.innerHTML, /data-layer-id="zero-size" style="left:0px;top:0px;width:640px;height:960px/);
  }

  {
    const invalidDimensionGroups = [
      {id:'partial-natural', naturalWidth:320, naturalHeight:0},
      {id:'nan-natural', naturalWidth:NaN, naturalHeight:960},
      {id:'negative-natural', naturalWidth:-1, naturalHeight:960},
      {id:'missing-natural'},
      {id:'partial-size', naturalWidth:0, naturalHeight:0, width:320, height:0},
    ];
    for(const item of invalidDimensionGroups){
      const {browser, stage} = createBrowserHarness({imageWidth:640, imageHeight:960});
      await browser.freeCompositor.open([{...item, name:item.id, url:`/${item.id}.png`}], {});
      assert.match(stage.innerHTML, /width:640px;height:960px/);
      assert.match(stage.innerHTML, new RegExp(`data-layer-id="${item.id}" style="left:0px;top:0px;width:640px;height:960px`));
    }
  }

  {
    let pendingDropImage;
    const commits = [];
    const {browser, host, hostListeners, status} = createBrowserHarness({
      imageBehavior(image, url){
        if(url === 'blob:drop.png') pendingDropImage = image;
        else image.onload?.();
      },
    });
    await browser.freeCompositor.open([{id:'base', name:'base', url:'/base.png'}], {commitPngBlob:async (...args) => commits.push(args)});
    const pendingDrop = hostListeners.drop(droppedFilesEvent([{name:'drop.png', type:'image/png'}]));
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(commits.length, 0);
    assert.strictEqual(host.classList.contains('open'), true);
    assert.strictEqual(status.textContent, '图片正在导入，请稍候');
    pendingDropImage.onload();
    await pendingDrop;
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(commits.length, 1);
  }

  {
    let finishCommit;
    const {browser, hostListeners, createdUrls} = createBrowserHarness();
    await browser.freeCompositor.open([{id:'base', name:'base', url:'/base.png'}], {commitPngBlob:() => new Promise(resolve => { finishCommit = resolve; })});
    clickAction(hostListeners, 'export');
    await flushAsync();
    await hostListeners.drop(droppedFilesEvent([{name:'late.png', type:'image/png'}]));
    assert.deepStrictEqual(createdUrls, []);
    finishCommit();
    await flushAsync();
  }

  {
    let oldDropImage;
    const newCommits = [];
    const {browser, hostListeners} = createBrowserHarness({
      imageBehavior(image, url){
        if(url === 'blob:old.png') oldDropImage = image;
        else image.onload?.();
      },
    });
    await browser.freeCompositor.open([{id:'old-base', name:'old-base', url:'/old-base.png'}], {commitPngBlob:async () => {}});
    const oldDrop = hostListeners.drop(droppedFilesEvent([{name:'old.png', type:'image/png'}]));
    browser.freeCompositor.close();
    await browser.freeCompositor.open([{id:'new-base', name:'new-base', url:'/new-base.png'}], {commitPngBlob:async (...args) => newCommits.push(args)});
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(newCommits.length, 1);
    oldDropImage.onload();
    await oldDrop;
  }

  {
    let oldDropImage;
    let newDropImage;
    const newCommits = [];
    const {browser, host, hostListeners, status} = createBrowserHarness({
      imageBehavior(image, url){
        if(url === 'blob:old.png') oldDropImage = image;
        else if(url === 'blob:new.png') newDropImage = image;
        else image.onload?.();
      },
    });
    await browser.freeCompositor.open([{id:'old-base', name:'old-base', url:'/old-base.png'}], {commitPngBlob:async () => {}});
    const oldDrop = hostListeners.drop(droppedFilesEvent([{name:'old.png', type:'image/png'}]));
    browser.freeCompositor.close();
    await browser.freeCompositor.open([{id:'new-base', name:'new-base', url:'/new-base.png'}], {commitPngBlob:async (...args) => newCommits.push(args)});
    const newDrop = hostListeners.drop(droppedFilesEvent([{name:'new.png', type:'image/png'}]));
    oldDropImage.onload();
    await oldDrop;
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(newCommits.length, 0);
    assert.strictEqual(host.classList.contains('open'), true);
    assert.strictEqual(status.textContent, '图片正在导入，请稍候');
    newDropImage.onload();
    await newDrop;
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(newCommits.length, 1);
  }

  {
    let newBaseImage;
    let transitionDropImage;
    const newCommits = [];
    const {browser, hostListeners} = createBrowserHarness({
      imageBehavior(image, url){
        if(url === '/new-base.png') newBaseImage = image;
        else if(url === 'blob:transition.png') transitionDropImage = image;
        else image.onload?.();
      },
    });
    await browser.freeCompositor.open([{id:'old-base', name:'old-base', url:'/old-base.png'}], {commitPngBlob:async () => {}});
    const openingNew = browser.freeCompositor.open([{id:'new-base', name:'new-base', url:'/new-base.png'}], {commitPngBlob:async (...args) => newCommits.push(args)});
    const transitionDrop = hostListeners.drop(droppedFilesEvent([{name:'transition.png', type:'image/png'}]));
    newBaseImage.onload();
    await openingNew;
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(newCommits.length, 1);
    transitionDropImage.onload();
    await transitionDrop;
  }

  {
    let slowAImage;
    const adapterACommits = [];
    const adapterBCommits = [];
    const {browser, hostListeners, stage} = createBrowserHarness({
      imageBehavior(image, url){
        if(url === '/A.png'){
          image.naturalWidth = 100;
          image.naturalHeight = 50;
          slowAImage = image;
          return;
        }
        image.naturalWidth = 300;
        image.naturalHeight = 150;
        image.onload?.();
      },
    });
    const openA = browser.freeCompositor.open([{id:'A', name:'A', url:'/A.png'}], {commitPngBlob:async (...args) => adapterACommits.push(args)});
    const openB = browser.freeCompositor.open([{id:'B', name:'B', url:'/B.png'}], {commitPngBlob:async (...args) => adapterBCommits.push(args)});
    await openB;
    assert.match(stage.innerHTML, /data-layer-id="B"/);
    slowAImage.onload();
    await openA;
    assert.match(stage.innerHTML, /data-layer-id="B"/);
    assert.doesNotMatch(stage.innerHTML, /data-layer-id="A"/);
    clickAction(hostListeners, 'export');
    await flushAsync();
    assert.strictEqual(adapterACommits.length, 0);
    assert.strictEqual(adapterBCommits.length, 1);
    assert.strictEqual(adapterBCommits[0][1].width, 300);
  }

  {
    const {browser, hostListeners, windowListeners, stage} = createBrowserHarness();
    await browser.freeCompositor.open([{id:'only', name:'only', url:'/only.png'}], {});
    const handle = {dataset:{fcHandle:'se'}, closest:selector => selector === '[data-fc-handle]' ? handle : null};
    const pointerDown = options => hostListeners.pointerdown({button:0, clientX:0, clientY:0, target:handle, preventDefault(){}, stopPropagation(){}, ...options});
    pointerDown();
    windowListeners.pointermove({clientX:100, clientY:10, shiftKey:true, altKey:false});
    assert.match(stage.innerHTML, /width:300px;height:110px/);
  }

  {
    const {browser, hostListeners, windowListeners, stage} = createBrowserHarness();
    await browser.freeCompositor.open([{id:'only', name:'only', url:'/only.png'}], {});
    const handle = {dataset:{fcHandle:'se'}, closest:selector => selector === '[data-fc-handle]' ? handle : null};
    hostListeners.pointerdown({button:0, clientX:0, clientY:0, target:handle, preventDefault(){}, stopPropagation(){}});
    windowListeners.pointermove({clientX:100, clientY:10, shiftKey:false, altKey:true});
    assert.match(stage.innerHTML, /left:-100px;top:-50px;width:400px;height:200px/);
  }

  assert.match(compositorCss, /\.fc-viewport\.drop-active/);
  assert.match(compositorCss, /\.fc-drop-hint/);

  let compositorApi;
  assert.doesNotThrow(() => { compositorApi = require(path.join(root, 'static', 'js', 'free-compositor.js')); });
  const {createFreeCompositorDropController:createDropController} = compositorApi;
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
    let idSequence = 0;
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
      nextId:() => `import-${++idSequence}`,
      commit:() => { commits++; },
      render:() => { renders++; },
      setStatus:(message, error) => statuses.push({message, error}),
      setActive:value => active.push(value),
    });
    const eventFor = eventFiles => ({dataTransfer:{files:eventFiles || [], types:['Files'], dropEffect:''}, prevented:false, preventDefault(){ this.prevented = true; }});
    return {controller, doc, decoded, placed, statuses, revoked, cacheDeletes, active, event:eventFor(files), eventFor, commits:() => commits, renders:() => renders};
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

  {
    let resolveSlow;
    const harness = createHarness({
      decode:item => item.file.name === 'A.png'
        ? new Promise(resolve => { resolveSlow = resolve; })
        : {naturalWidth:20, naturalHeight:20},
    });
    const pendingA = harness.controller.onDrop(harness.eventFor([{name:'A.png', type:'image/png'}]));
    const pendingB = harness.controller.onDrop(harness.eventFor([{name:'B.png', type:'image/png'}, {name:'note.txt', type:'text/plain'}]));
    await pendingB;
    assert.strictEqual(harness.commits(), 1);
    assert.strictEqual(harness.doc.selectedId, 'import-1');
    assert.strictEqual(harness.statuses.at(-1).message, '已导入 1 张，跳过 1 个无效文件');
    resolveSlow({naturalWidth:20, naturalHeight:20});
    await pendingA;
    assert.strictEqual(harness.commits(), 2);
    assert.deepStrictEqual(harness.doc.layers.map(layer => layer.name), [undefined, 'B.png', 'A.png']);
    assert.strictEqual(harness.doc.selectedId, 'import-1');
    assert.strictEqual(harness.statuses.at(-1).message, '已导入 1 张，跳过 1 个无效文件');
  }

  {
    let resolveSlow;
    const harness = createHarness({decode:() => new Promise(resolve => { resolveSlow = resolve; })});
    const pendingA = harness.controller.onDrop(harness.eventFor([{name:'A.png', type:'image/png'}]));
    harness.controller.cleanup();
    harness.controller.onDragEnter(harness.eventFor([{name:'B.png', type:'image/png'}]));
    assert.strictEqual(harness.active.at(-1), true);
    resolveSlow({naturalWidth:20, naturalHeight:20});
    await pendingA;
    assert.strictEqual(harness.active.at(-1), true);
  }

  {
    let resolveSlow;
    const harness = createHarness({decode:() => new Promise(resolve => { resolveSlow = resolve; })});
    const pendingA = harness.controller.onDrop(harness.eventFor([{name:'A.png', type:'image/png'}]));
    harness.controller.onDragEnter(harness.eventFor([{name:'B.png', type:'image/png'}]));
    assert.strictEqual(harness.active.at(-1), true);
    resolveSlow({naturalWidth:20, naturalHeight:20});
    await pendingA;
    assert.strictEqual(harness.active.at(-1), true);
  }

  console.log('free compositor integration tests passed');
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

# Free Compositor Direct Image Drop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free compositor accept local image files by direct drag-and-drop, place them at the pointer as independent layers, fit oversized images without enlarging small ones, and immediately expose Photoshop-like transform controls.

**Architecture:** Add deterministic import-placement calculations to the existing UMD core so they can be tested without a browser. Keep file decoding, object URL lifecycle, drop feedback, history integration, and DOM events inside the existing compositor module; retain the classic canvas adapter as the entry and export boundary.

**Tech Stack:** Vanilla JavaScript, HTML Drag and Drop API, object URLs, DOM/CSS transforms, Node `assert`, Playwright browser verification.

---

### Task 1: Deterministic imported-layer placement

**Files:**
- Modify: `static/js/free-compositor-core.js`
- Modify: `tests/free-compositor-core.test.js`

- [ ] **Step 1: Write the failing placement tests**

Append tests that describe the approved 80% fitting rule, pointer-centered placement, no small-image enlargement, and 24px multi-file cascade:

```js
{
  const small = core.placeImportedLayer({
    id: 'small', naturalWidth: 200, naturalHeight: 100,
  }, { width: 1000, height: 1600 }, { x: 500, y: 800 });
  assert.deepStrictEqual(
    { x: small.x, y: small.y, width: small.width, height: small.height },
    { x: 400, y: 750, width: 200, height: 100 },
  );

  const large = core.placeImportedLayer({
    id: 'large', naturalWidth: 2000, naturalHeight: 1000,
  }, { width: 1000, height: 1600 }, { x: 500, y: 800 });
  assert.deepStrictEqual(
    { x: large.x, y: large.y, width: large.width, height: large.height },
    { x: 100, y: 600, width: 800, height: 400 },
  );

  const batch = core.placeImportedLayers([
    { id: 'one', naturalWidth: 100, naturalHeight: 100 },
    { id: 'two', naturalWidth: 100, naturalHeight: 100 },
  ], { width: 1000, height: 1600 }, { x: 300, y: 400 });
  assert.deepStrictEqual(batch.map(({id, x, y}) => ({id, x, y})), [
    { id: 'one', x: 250, y: 350 },
    { id: 'two', x: 274, y: 374 },
  ]);
}
```

- [ ] **Step 2: Run the core test and verify RED**

Run: `node tests/free-compositor-core.test.js`

Expected: FAIL with `TypeError: core.placeImportedLayer is not a function`.

- [ ] **Step 3: Implement the minimum placement API**

Add these pure functions and export both names:

```js
function placeImportedLayer(layer, documentState, point, options={}){
    const naturalWidth = Math.max(1, number(layer?.naturalWidth, layer?.width || 1));
    const naturalHeight = Math.max(1, number(layer?.naturalHeight, layer?.height || 1));
    const maxRatio = clamp(number(options.maxRatio, .8), .1, 1);
    const maxWidth = Math.max(1, number(documentState?.width, naturalWidth) * maxRatio);
    const maxHeight = Math.max(1, number(documentState?.height, naturalHeight) * maxRatio);
    const scale = Math.min(1, maxWidth / naturalWidth, maxHeight / naturalHeight);
    const width = naturalWidth * scale;
    const height = naturalHeight * scale;
    const centerX = number(point?.x, number(documentState?.width) / 2);
    const centerY = number(point?.y, number(documentState?.height) / 2);
    return normalizeLayer({...layer, naturalWidth, naturalHeight,
        width, height, x:centerX - width / 2, y:centerY - height / 2});
}

function placeImportedLayers(layers, documentState, point, options={}){
    const offset = number(options.offset, 24);
    return (layers || []).map((layer, index) => placeImportedLayer(
        layer,
        documentState,
        {x:number(point?.x) + index * offset, y:number(point?.y) + index * offset},
        options,
    ));
}
```

- [ ] **Step 4: Run the core test and verify GREEN**

Run: `node tests/free-compositor-core.test.js`

Expected: `free compositor core tests passed`.

- [ ] **Step 5: Commit the core behavior**

```powershell
git add -- static/js/free-compositor-core.js tests/free-compositor-core.test.js
git commit -m "feat: calculate compositor drop placement"
```

### Task 2: Direct file drop and immediate transform selection

**Files:**
- Modify: `static/js/free-compositor.js`
- Modify: `static/css/free-compositor.css`
- Modify: `tests/free-compositor-integration.test.js`

- [ ] **Step 1: Write the failing integration assertions**

Read `static/js/free-compositor.js` and `static/css/free-compositor.css`, then assert the direct-drop contract exists:

```js
const compositor = fs.readFileSync(path.join(root, 'static', 'js', 'free-compositor.js'), 'utf8');
const compositorCss = fs.readFileSync(path.join(root, 'static', 'css', 'free-compositor.css'), 'utf8');
assert.match(compositor, /function acceptedImageFiles\(/);
assert.match(compositor, /async function importDroppedFiles\(/);
assert.match(compositor, /dataTransfer\.files/);
assert.match(compositor, /core\.placeImportedLayers\(/);
assert.match(compositor, /URL\.createObjectURL\(/);
assert.match(compositor, /doc\.selectedId\s*=\s*imported\.at\(-1\)\.id/);
assert.match(compositorCss, /\.fc-viewport\.drop-active/);
assert.match(compositorCss, /\.fc-drop-hint/);
```

- [ ] **Step 2: Run the integration test and verify RED**

Run: `node tests/free-compositor-integration.test.js`

Expected: FAIL on the first missing direct-drop function assertion.

- [ ] **Step 3: Add drop feedback markup and CSS**

Add a persistent hint inside `.fc-viewport` and only reveal it during an external file drag:

```html
<div class="fc-drop-hint"><strong>松开以放置图片</strong><span>PNG、JPG、WEBP 或 GIF 将成为独立图层</span></div>
```

```css
.fc-drop-hint { position:absolute; inset:24px; display:none; place-content:center; text-align:center; border:2px dashed #e55b86; border-radius:16px; background:rgba(229,91,134,.14); z-index:20; pointer-events:none; }
.fc-viewport.drop-active .fc-drop-hint { display:grid; }
```

- [ ] **Step 4: Decode accepted files and create layers**

Implement file filtering, image dimension decoding, unique IDs, placement, history, selection, and rejected-file reporting:

```js
function acceptedImageFiles(fileList){
    const supported = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
    const files = [...(fileList || [])];
    return {
        accepted:files.filter(file => supported.has(file.type)),
        rejected:files.filter(file => !supported.has(file.type)),
    };
}

async function droppedFileLayer(file){
    const url = URL.createObjectURL(file);
    try {
        const image = await loadImage({url, name:file.name});
        return {id:`drop-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
            name:file.name, url, naturalWidth:image.naturalWidth, naturalHeight:image.naturalHeight,
            opacity:1, visible:true, locked:false, objectUrl:true};
    } catch(error){
        URL.revokeObjectURL(url);
        throw error;
    }
}

async function importDroppedFiles(fileList, point){
    const {accepted, rejected} = acceptedImageFiles(fileList);
    const decoded = [];
    const failed = [];
    for(const file of accepted){
        try { decoded.push(await droppedFileLayer(file)); }
        catch(error){ failed.push(file); }
    }
    const imported = core.placeImportedLayers(decoded, doc, point, {maxRatio:.8, offset:24});
    doc.layers.push(...imported);
    if(imported.length) doc.selectedId = imported.at(-1).id;
    if(imported.length) commit();
    renderWorkspace();
    const skipped = rejected.length + failed.length;
    setStatus(skipped ? `已导入 ${imported.length} 张，跳过 ${skipped} 个无效文件` : `已导入 ${imported.length} 张图片`, skipped > 0);
}
```

- [ ] **Step 5: Translate the browser drop point into artboard coordinates**

Handle `dragenter`, `dragover`, `dragleave`, and `drop` on `.fc-viewport`. Compute the point from `.fc-artboard.getBoundingClientRect()` and current zoom, clamp it to the artboard, prevent browser navigation, and clear `drop-active` on every exit path:

```js
function dropPoint(event){
    const rect = host.querySelector('.fc-artboard').getBoundingClientRect();
    return {
        x:core.clamp((event.clientX - rect.left) / zoom, 0, doc.width),
        y:core.clamp((event.clientY - rect.top) / zoom, 0, doc.height),
    };
}
```

- [ ] **Step 6: Revoke object URLs when layers are permanently discarded**

Track compositor-created object URLs and revoke them when closing without export or deleting a dropped layer. Do not revoke URLs while undo history can still restore the layer; perform final cleanup in `close()` after the editor no longer needs them.

- [ ] **Step 7: Run integration and syntax checks**

Run:

```powershell
node tests/free-compositor-integration.test.js
node --check static/js/free-compositor.js
```

Expected: integration test prints `free compositor integration tests passed`; syntax check exits 0.

- [ ] **Step 8: Commit direct drop UI**

```powershell
git add -- static/js/free-compositor.js static/css/free-compositor.css tests/free-compositor-integration.test.js
git commit -m "feat: drag images into free compositor"
```

### Task 3: One-image entry and modern Photoshop resize modifier

**Files:**
- Modify: `static/js/canvas.js`
- Modify: `static/js/free-compositor.js`
- Modify: `static/js/free-compositor-core.js`
- Modify: `tests/free-compositor-core.test.js`
- Modify: `tests/free-compositor-integration.test.js`

- [ ] **Step 1: Write failing one-image and Shift-toggle tests**

Add a core assertion showing corners keep ratio by default and Shift unlocks it through an explicit `freeRatio` option:

```js
{
  const layer = core.normalizeLayer({id:'ratio', width:200, height:100});
  const proportional = core.resizeLayer(layer, {handle:'se', dx:100, dy:10});
  assert.strictEqual(proportional.width / proportional.height, 2);
  const free = core.resizeLayer(layer, {handle:'se', dx:100, dy:10, freeRatio:true});
  assert.deepStrictEqual({width:free.width, height:free.height}, {width:300, height:110});
}
```

Change the integration assertions to require `items.length < 1` and the single-image canvas entry message:

```js
assert.match(compositor, /items\.length < 1/);
assert.match(canvas, /items\.length < 1/);
assert.doesNotMatch(compositor, /items\.length < 2/);
```

- [ ] **Step 2: Run both focused tests and verify RED**

Run:

```powershell
node tests/free-compositor-core.test.js
node tests/free-compositor-integration.test.js
```

Expected: core fails because `freeRatio` is ignored; integration fails because both entry points still require two images.

- [ ] **Step 3: Implement Shift as a ratio-lock toggle**

Update `resizeLayer` so corner handles keep ratio unless `options.freeRatio === true`; pass `freeRatio:event.shiftKey` from `onPointerMove` while preserving `Alt` center scaling.

- [ ] **Step 4: Allow a single selected image to open the compositor**

Change `openFreeCompositorFromSelection()` and `freeCompositor.open()` to reject only an empty image list. Keep the first image as the artboard-sized background to preserve current document sizing behavior.

- [ ] **Step 5: Run focused tests and syntax checks**

Run:

```powershell
node tests/free-compositor-core.test.js
node tests/free-compositor-integration.test.js
node --check static/js/free-compositor-core.js
node --check static/js/free-compositor.js
node --check static/js/canvas.js
```

Expected: both focused tests pass and all syntax checks exit 0.

- [ ] **Step 6: Commit entry and modifier behavior**

```powershell
git add -- static/js/canvas.js static/js/free-compositor.js static/js/free-compositor-core.js tests/free-compositor-core.test.js tests/free-compositor-integration.test.js
git commit -m "feat: align compositor transforms with Photoshop"
```

### Task 4: Browser drag-and-drop verification

**Files:**
- Modify only if browser verification reveals a direct-drop defect in the files listed above.

- [ ] **Step 1: Run the focused automated suite**

Run:

```powershell
node tests/free-compositor-core.test.js
node tests/free-compositor-integration.test.js
```

Expected: both tests print their pass messages.

- [ ] **Step 2: Open the existing wheel composition canvas**

Open `http://127.0.0.1:3001/static/canvas.html?id=44b047feb474463187c16aa3082ce17b&project=default`, select one image node, and enter `自由合成`.

- [ ] **Step 3: Exercise a real browser File drag payload**

Use Playwright to dispatch a drop containing one small PNG and one oversized PNG onto a known artboard coordinate. Confirm both new rows appear in the layer panel, the second layer is selected, the transform box is visible, and the browser reports no console errors.

- [ ] **Step 4: Verify manipulation and history**

Drag the selected image, resize from a corner with and without Shift, use Alt center resize, press `Ctrl+Z`, and verify the expected geometry values in the properties panel after each operation.

- [ ] **Step 5: Verify unsupported files do not create layers**

Drop one text file together with one PNG. Confirm only the PNG is added and the status bar reports one skipped file.

- [ ] **Step 6: Capture the finished UI**

Save a high-resolution browser screenshot to `output/playwright/free-compositor-direct-drop.png` and visually inspect the drop hint, transform box, layer list, and artboard placement.

- [ ] **Step 7: Run diff hygiene checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only the planned compositor files plus previously known user changes are present.

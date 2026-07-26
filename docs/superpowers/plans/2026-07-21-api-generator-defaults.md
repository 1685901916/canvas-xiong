# API Generator Fixed Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every newly created classic-canvas API generator start with stable local defaults: preferred configured provider (65535 in the current setup), `gpt-image-2`, 2K, 1:1 until an image is connected, high quality, force-fill off, and count 1, without changing saved nodes.

**Architecture:** Put provider/model ranking and node construction in a small UMD/CommonJS helper so Node tests can exercise the behavior without loading the 831 KB browser file. `canvas.js` will call the helper from `addGeneratorNode()`, mark manual ratio changes, and adopt the first reference image ratio only for newly created nodes whose ratio has not been manually changed. Existing migration and saved-node loading paths remain unchanged.

**Tech Stack:** Native browser JavaScript, CommonJS-compatible UMD helper, Node.js `assert`, existing static HTML and classic canvas runtime, Playwright CLI for browser verification.

---

## File map

- Create `static/js/api-generator-defaults.js`: pure provider/model ranking, default node construction, and source-ratio eligibility.
- Create `tests/api-generator-defaults.test.js`: unit tests for new defaults, fallback behavior, and manual-ratio protection.
- Create `tests/api-generator-defaults-canvas.integration.test.js`: static integration contract for script order and `canvas.js` wiring.
- Modify `static/canvas.html`: load the helper before `canvas.js` and bump the local canvas cache token.
- Modify `static/js/canvas.js`: use the helper, adopt source ratio on reference-image connection, and record manual ratio selection.
- Create `backups/api-generator-defaults-20260721/`: local pre-change copies of modified runtime files; no Git commit or remote action.

### Task 1: Add failing unit tests for the default policy

**Files:**
- Create: `tests/api-generator-defaults.test.js`
- Test: `tests/api-generator-defaults.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
const assert = require('assert');
const defaults = require('../static/js/api-generator-defaults.js');

const providers = [
  { id:'custom-api-7', name:'comfly', enabled:true, has_key:true, image_models:['gpt-image-2-all'] },
  { id:'custom-api-2', name:'65535', enabled:true, has_key:true, image_models:['gpt-image-2'] },
  { id:'custom-api-3', name:'Nano', enabled:true, has_key:true, image_models:['nano-banana-pro','gpt-image-2'] },
];

{
  const node = defaults.createDefaultNode({id:'gen_1', x:10, y:20, providers});
  assert.deepStrictEqual(node, {
    id:'gen_1', type:'generator', x:10, y:20,
    apiProvider:'custom-api-2', model:'gpt-image-2',
    ratio:'square', resolution:'2k', quality:'high',
    forceFill:false, count:1,
    customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'',
    customWidth:'', customHeight:'', inputs:[],
    apiDefaultsVersion:3, _apiRatioUserSet:false, _apiResolutionUserSet:true,
  });
}

{
  const primary = defaults.selectProvider([
    ...providers,
    {id:'preferred', name:'Preferred', enabled:true, primary:true, has_key:true, image_models:['gpt-image-2']},
  ]);
  assert.strictEqual(primary.id, 'preferred');
}

{
  const fallback = defaults.createDefaultNode({
    id:'gen_2', x:0, y:0,
    providers:[{id:'fallback', name:'Fallback', enabled:true, image_models:['other-model']}],
  });
  assert.strictEqual(fallback.apiProvider, 'fallback');
  assert.strictEqual(fallback.model, 'other-model');
}

{
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'square', _apiRatioUserSet:false}, true), true);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'story', _apiRatioUserSet:true}, true), false);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:2, ratio:'square'}, true), false);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'square'}, false), false);
}

console.log('api-generator-defaults tests passed');
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node tests/api-generator-defaults.test.js
```

Expected: FAIL with `Cannot find module '../static/js/api-generator-defaults.js'`.

### Task 2: Implement the pure default-policy helper

**Files:**
- Create: `static/js/api-generator-defaults.js`
- Test: `tests/api-generator-defaults.test.js`

- [ ] **Step 1: Add the minimal UMD/CommonJS implementation**

```javascript
(function(root, factory){
  const api = factory();
  if(typeof module === 'object' && module.exports) module.exports = api;
  else root.ApiGeneratorDefaults = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function(){
  function imageModels(provider){
    return Array.isArray(provider?.image_models)
      ? provider.image_models.map(value => String(value || '').trim()).filter(Boolean)
      : [];
  }

  function eligibleProviders(providers){
    return (Array.isArray(providers) ? providers : []).filter(provider =>
      provider && provider.id !== 'modelscope' && provider.enabled !== false && imageModels(provider).length
    );
  }

  function is65535(provider){
    return String(provider?.id || '').toLowerCase() === 'custom-api-2'
      || String(provider?.name || '').trim() === '65535';
  }

  function selectProvider(providers){
    const items = eligibleProviders(providers);
    return items.find(provider => provider.primary && provider.has_key)
      || items.find(provider => is65535(provider) && provider.has_key)
      || items.find(provider => provider.has_key)
      || items.find(is65535)
      || items.find(provider => provider.primary)
      || items[0]
      || null;
  }

  function selectModel(provider){
    const models = imageModels(provider);
    return models.find(model => model.toLowerCase() === 'gpt-image-2') || models[0] || '';
  }

  function createDefaultNode({id, x=0, y=0, providers=[]}={}){
    const provider = selectProvider(providers);
    return {
      id, type:'generator', x, y,
      apiProvider:provider?.id || '', model:selectModel(provider),
      ratio:'square', resolution:'2k', quality:'high',
      forceFill:false, count:1,
      customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'',
      customWidth:'', customHeight:'', inputs:[],
      apiDefaultsVersion:3, _apiRatioUserSet:false, _apiResolutionUserSet:true,
    };
  }

  function shouldAdoptSourceRatio(node, hasReferenceImage){
    return Boolean(
      hasReferenceImage
      && Number(node?.apiDefaultsVersion || 0) >= 3
      && node?._apiRatioUserSet !== true
      && (node?.ratio || 'square') === 'square'
    );
  }

  return {imageModels, eligibleProviders, selectProvider, selectModel, createDefaultNode, shouldAdoptSourceRatio};
});
```

- [ ] **Step 2: Run the unit test and verify GREEN**

Run:

```powershell
node tests/api-generator-defaults.test.js
```

Expected: `api-generator-defaults tests passed` and exit code 0.

### Task 3: Add failing canvas integration contracts

**Files:**
- Create: `tests/api-generator-defaults-canvas.integration.test.js`
- Test: `tests/api-generator-defaults-canvas.integration.test.js`

- [ ] **Step 1: Write the failing integration test**

```javascript
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'canvas.html'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');

assert.match(html, /api-generator-defaults\.js[^]*canvas\.js/);
assert.match(canvas, /ApiGeneratorDefaults\.createDefaultNode/);
assert.match(canvas, /ApiGeneratorDefaults\.shouldAdoptSourceRatio/);
assert.match(canvas, /node\._apiRatioUserSet\s*=\s*true/);
assert.match(canvas, /API_GENERATOR_DEFAULTS_VERSION\s*=\s*3/);

console.log('api-generator-defaults canvas integration tests passed');
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node tests/api-generator-defaults-canvas.integration.test.js
```

Expected: FAIL because `static/canvas.html` does not yet load `api-generator-defaults.js` and `canvas.js` does not call the helper.

### Task 4: Wire fixed defaults into classic canvas

**Files:**
- Modify: `static/canvas.html`
- Modify: `static/js/canvas.js:707-720`
- Modify: `static/js/canvas.js:3171-3176`
- Modify: `static/js/canvas.js:9775-9786`
- Modify: `static/js/canvas.js:10007-10021`
- Test: `tests/api-generator-defaults-canvas.integration.test.js`

- [ ] **Step 1: Create local safety copies**

Run:

```powershell
New-Item -ItemType Directory -Force 'backups\api-generator-defaults-20260721' | Out-Null
Copy-Item 'static\canvas.html' 'backups\api-generator-defaults-20260721\canvas.html'
Copy-Item 'static\js\canvas.js' 'backups\api-generator-defaults-20260721\canvas.js'
```

Expected: both backup files exist. This is a local backup only; do not initialize Git or contact a remote.

- [ ] **Step 2: Load the helper before `canvas.js`**

Change the script block at the end of `static/canvas.html` to:

```html
<script src="/static/js/ltx-director-timeline.js?v=2026.07.17-media-tools-3"></script>
<script src="/static/js/realesrgan-node.js?v=2026.07.17-media-tools-3"></script>
<script src="/static/js/api-generator-defaults.js?v=2026.07.21-api-defaults-1"></script>
<script src="/static/js/canvas.js?v=2026.07.21-api-defaults-1"></script>
```

- [ ] **Step 3: Prevent the old migration from touching version-3 nodes**

Keep the existing version guard and make the new-node version explicit in the source so the integration contract can verify it:

```javascript
const API_GENERATOR_DEFAULTS_VERSION = 3;

function applyGeneratorApiDefaults(node){
    if(!node || node.type !== 'generator') return false;
    let changed = false;
    if(Number(node.apiDefaultsVersion || 0) >= 2) return false;
    // existing version-2 legacy migration remains unchanged
}
```

Pass `apiDefaultsVersion:API_GENERATOR_DEFAULTS_VERSION` into the helper result override in the next step.

- [ ] **Step 4: Replace ad-hoc construction in `addGeneratorNode()`**

```javascript
function addGeneratorNode(point){
    const p = point || defaultPoint(120, 0);
    const api = window.ApiGeneratorDefaults;
    const node = api?.createDefaultNode({
        id:uid('gen'),
        x:p.x,
        y:p.y,
        providers:apiProviders.length ? apiProviders : defaultApiProviders(),
    }) || {
        id:uid('gen'), type:'generator', x:p.x, y:p.y,
        apiProvider:preferredImageApiProvider()?.id || imageApiProviders()[0]?.id || '',
        model:preferredImageModel(preferredImageApiProvider()?.id || ''),
        ratio:'square', resolution:'2k', quality:'high', forceFill:false, count:1,
        customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'',
        customWidth:'', customHeight:'', inputs:[],
        apiDefaultsVersion:API_GENERATOR_DEFAULTS_VERSION,
        _apiRatioUserSet:false,
        _apiResolutionUserSet:true,
    };
    node.apiDefaultsVersion = API_GENERATOR_DEFAULTS_VERSION;
    return addNode(node);
}
```

Use one generated node ID in the final implementation; store `const id = uid('gen')` before the helper/fallback expression so fallback cannot produce a second ID.

- [ ] **Step 5: Adopt the first reference image ratio only before manual selection**

Immediately after `inputSources` and `ordered` are calculated in `renderGeneratorBody(node)`:

```javascript
const hasReferenceImage = ordered.some(source =>
    source.refs?.some(ref => ref?.url && mediaKindForRef(ref) === 'image')
);
if(window.ApiGeneratorDefaults?.shouldAdoptSourceRatio(node, hasReferenceImage)){
    node.ratio = 'source';
    node.customRatio = '';
    node.customRatioWidth = '';
    node.customRatioHeight = '';
}
```

This does not call `scheduleSave()` during rendering; the connection operation already schedules a save. The changed node state is included in that save.

- [ ] **Step 6: Protect manual ratio choices**

At the start of `ratioSelect.onchange` after stopping propagation:

```javascript
node._apiRatioUserSet = true;
```

Keep all existing ratio normalization and save behavior after that line.

- [ ] **Step 7: Run the focused tests and verify GREEN**

Run:

```powershell
node tests/api-generator-defaults.test.js
node tests/api-generator-defaults-canvas.integration.test.js
```

Expected: both commands print their `... tests passed` message and exit code 0.

### Task 5: Verify regressions and browser behavior

**Files:**
- Verify: `static/js/api-generator-defaults.js`
- Verify: `static/js/canvas.js`
- Verify: `static/canvas.html`
- Verify: existing `tests/*.test.js`

- [ ] **Step 1: Run all JavaScript tests**

Run:

```powershell
Get-ChildItem tests -Filter '*.test.js' | Sort-Object Name | ForEach-Object {
  node $_.FullName
  if($LASTEXITCODE -ne 0){ throw "Failed: $($_.Name)" }
}
```

Expected: every test prints its success message; PowerShell exits 0.

- [ ] **Step 2: Check JavaScript syntax**

Run:

```powershell
node --check static/js/api-generator-defaults.js
node --check static/js/canvas.js
```

Expected: no output and exit code 0 for both commands.

- [ ] **Step 3: Confirm the local server is reachable**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:3001/' -TimeoutSec 5 | Select-Object StatusCode
```

Expected: `StatusCode 200`. If the server is not running, start it with `powershell -ExecutionPolicy Bypass -File .\launch-canvas.ps1`, then repeat the check.

- [ ] **Step 4: Verify the new-node UI with Playwright**

Open the current canvas URL, click the toolbar “API生成” button, and inspect the newest `.generator-node`. Verify:

```javascript
({
  provider: node.querySelector('.provider-select')?.value,
  model: node.querySelector('.model-select')?.value,
  resolution: node.querySelector('.resolution')?.value,
  ratio: node.querySelector('.ratio')?.value,
  quality: node.querySelector('.quality-select')?.value,
  forceFill: node.querySelector('.force-fill-toggle')?.classList.contains('active'),
  count: node.querySelector('.gen-count-input')?.value,
})
```

Expected in the current configuration:

```javascript
{
  provider:'custom-api-2',
  model:'gpt-image-2',
  resolution:'2k',
  ratio:'square',
  quality:'high',
  forceFill:false,
  count:'1'
}
```

- [ ] **Step 5: Verify reference-image and manual-ratio behavior**

Connect an image node to a fresh API generator and verify its ratio becomes `source`. Change the ratio manually to `story` (`9:16`), trigger a node refresh or reconnect an image, and verify the ratio remains `story`.

- [ ] **Step 6: Verify persistence and old-node compatibility**

Save/reload the canvas and confirm the manually selected ratio, quality, count, provider, and model remain unchanged. Inspect at least one pre-existing API generator and confirm its saved settings were not replaced with the new fixed defaults.

- [ ] **Step 7: Review local diff without committing**

Run:

```powershell
Compare-Object (Get-Content 'backups\api-generator-defaults-20260721\canvas.html') (Get-Content 'static\canvas.html')
Compare-Object (Get-Content 'backups\api-generator-defaults-20260721\canvas.js') (Get-Content 'static\js\canvas.js')
```

Expected: differences are limited to helper loading/cache version and the approved API-generator default behavior. Do not run `git init`, `git commit`, `git push`, or any GitHub command.

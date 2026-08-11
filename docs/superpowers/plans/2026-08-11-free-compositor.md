# Free Compositor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Photoshop-like free compositor to the classic infinite canvas that turns selected image nodes into an editable layered artboard and writes the rendered PNG back as a new image node.

**Architecture:** Keep deterministic layer state and geometry in a small UMD core module, implement the modal editor in a separate browser module, and expose a narrow adapter from the existing classic canvas. The existing canvas persistence format remains unchanged because only the flattened output becomes a normal image node.

**Tech Stack:** Vanilla JavaScript, DOM/CSS transforms, Canvas 2D export, existing upload API, Node `assert` tests.

---

### Task 1: Layer model and transform geometry

**Files:**
- Create: `static/js/free-compositor-core.js`
- Create: `tests/free-compositor-core.test.js`

- [ ] **Step 1: Write failing model tests**

Test default layer placement, clamped opacity, layer reorder, proportional corner resize, rotation, snapshots, undo and redo using Node `assert`.

- [ ] **Step 2: Verify the tests fail**

Run: `node tests/free-compositor-core.test.js`

Expected: failure because `free-compositor-core.js` does not exist.

- [ ] **Step 3: Implement the core API**

Export `createDocument`, `normalizeLayer`, `moveLayer`, `resizeLayer`, `rotateLayer`, `reorderLayer`, `duplicateLayer`, `deleteLayer`, `snapshot`, and `createHistory`. Keep all functions deterministic and independent of the DOM.

- [ ] **Step 4: Verify the core tests pass**

Run: `node tests/free-compositor-core.test.js`

Expected: `free compositor core tests passed`.

### Task 2: Editor shell and canvas integration contract

**Files:**
- Create: `static/js/free-compositor.js`
- Create: `static/css/free-compositor.css`
- Create: `tests/free-compositor-integration.test.js`
- Modify: `static/canvas.html`
- Modify: `static/js/canvas.js`

- [ ] **Step 1: Write the failing integration test**

Assert that `canvas.html` loads both compositor scripts and stylesheet, contains `#freeCompositorRoot`, and that `canvas.js` exposes `window.canvasFreeCompositorAdapter` with `getSelectedImages` and `commitPngBlob`.

- [ ] **Step 2: Verify the integration test fails**

Run: `node tests/free-compositor-integration.test.js`

Expected: assertion failure for missing compositor assets or adapter.

- [ ] **Step 3: Add the thin canvas adapter**

Implement `getSelectedImages()` by filtering the existing `selected` IDs to valid image nodes. Implement `commitPngBlob(blob, meta)` by uploading through the existing cropped-blob upload helper and creating/selecting a normal image node to the right of the selected bounds.

- [ ] **Step 4: Add the editor shell**

Mount a modal with toolbar, centered artboard viewport, left layer panel and right properties panel. Provide `window.freeCompositor.open(items, adapter)` and `close()`.

- [ ] **Step 5: Verify integration tests pass**

Run: `node tests/free-compositor-integration.test.js`

Expected: `free compositor integration tests passed`.

### Task 3: Layer manipulation and keyboard controls

**Files:**
- Modify: `static/js/free-compositor.js`
- Modify: `static/css/free-compositor.css`
- Modify: `tests/free-compositor-core.test.js`

- [ ] **Step 1: Add failing geometry edge-case tests**

Cover minimum size, negative scale prevention, locked-layer immutability, Shift proportional scaling and Alt center scaling.

- [ ] **Step 2: Verify the new tests fail**

Run: `node tests/free-compositor-core.test.js`

Expected: assertions fail for the new constraints.

- [ ] **Step 3: Implement editor interactions**

Render every layer with CSS transforms, add selection bounding box, eight resize handles and one rotation handle. Add pointer capture for move/resize/rotate and keyboard nudge, delete, duplicate, undo and redo shortcuts.

- [ ] **Step 4: Add layer and property controls**

Support select, rename, show/hide, lock/unlock, reorder, duplicate and delete in the layer panel. Bind X, Y, width, height, angle and opacity inputs to the selected layer.

- [ ] **Step 5: Verify core tests stay green**

Run: `node tests/free-compositor-core.test.js`

Expected: `free compositor core tests passed`.

### Task 4: Snapping, artboard settings and PNG export

**Files:**
- Modify: `static/js/free-compositor.js`
- Modify: `static/js/free-compositor-core.js`
- Modify: `static/css/free-compositor.css`
- Modify: `tests/free-compositor-core.test.js`

- [ ] **Step 1: Write failing snap and render-order tests**

Test center/edge snapping within tolerance and verify visible layers are returned bottom-to-top while hidden layers are excluded.

- [ ] **Step 2: Verify the new tests fail**

Run: `node tests/free-compositor-core.test.js`

Expected: assertions fail for missing snap and render-list functions.

- [ ] **Step 3: Implement snapping and artboard controls**

Add center/edge snap calculations, temporary guide rendering, editable width/height, transparent/white/custom background and fit-to-window zoom.

- [ ] **Step 4: Implement high-resolution export**

Preload source images, render background and visible layers bottom-to-top on an offscreen canvas with translate/rotate/globalAlpha, create a PNG blob, call `commitPngBlob`, then close only after success.

- [ ] **Step 5: Verify all focused tests pass**

Run: `node tests/free-compositor-core.test.js` and `node tests/free-compositor-integration.test.js`

Expected: both print their pass messages.

### Task 5: Browser verification and regression check

**Files:**
- Modify only if browser verification reveals a compositor-specific defect.

- [ ] **Step 1: Run the focused existing tests**

Run: `node tests/image-editor-upscale.test.js`, `node tests/background-removal-canvas.test.js`, and `node tests/video-frame-capture.test.js`.

Expected: all existing tests pass.

- [ ] **Step 2: Run JavaScript syntax checks**

Run: `node --check static/js/free-compositor-core.js`, `node --check static/js/free-compositor.js`, and `node --check static/js/canvas.js`.

Expected: all commands exit with code 0.

- [ ] **Step 3: Verify in the running browser**

Open the classic canvas, select two PNG nodes, enter free composition, move/resize/rotate/reorder one layer, export, and confirm a new image node appears with a matching flattened result.

- [ ] **Step 4: Check diff hygiene**

Run: `git status --short` and `git diff --check`.

Expected: only planned files are changed and `git diff --check` is clean.

# AIKO First-Person Batch Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `canvas-generation-orchestrator` and execute through the visible canvas generation workflow.

**Goal:** Build and run a six-lane canvas that generates three AIKO first-person first frames per location.

**Architecture:** Use the existing `canvasctl.py compose` action to create a new visible canvas without running paid tasks. Verify the saved `Group -> API生成 -> Output` structure, then open that exact canvas and invoke each visible generator through the frontend runner. Poll the canvas/task APIs and verify eighteen accepted outputs or report exact deficits.

**Tech Stack:** Infinite Canvas local API, `canvasctl.py`, Playwright browser automation, provider `custom-api-2`, model `gpt-image-2`.

---

### Task 1: Create the visible canvas structure

**Files:**
- Read: `tools/canvasctl.py`
- Create through API: new canvas `AIKO第一人称首帧批量测试_20260721`

- [ ] Compose six independent targets with one shared character reference.
- [ ] Configure count `3`, ratio `9:16`, resolution `1k`, quality `auto`.
- [ ] Do not use `--run` during structure creation.

### Task 2: Verify before paid generation

- [ ] Fetch the saved canvas JSON.
- [ ] Assert six input groups, six prompt nodes, six generator nodes and six outputs.
- [ ] Assert each generator has one output, count three, provider `custom-api-2`, model `gpt-image-2`.
- [ ] Assert output nodes have fixed dimensions.

### Task 3: Run visible generators

- [ ] Navigate to the exact canvas URL.
- [ ] Invoke the six generator nodes through the frontend `runGenerator` path, equivalent to pressing `API生成`.
- [ ] Keep each requirement's results in its connected output node.

### Task 4: Poll and review

- [ ] Poll saved canvas/task state without short artificial timeouts.
- [ ] Count only real output images as accepted task results.
- [ ] Inspect a contact sheet or visible canvas output for face, hair, composition, lighting and artifact failures.
- [ ] Refill only deficits if a provider attempt fails.

### Task 5: Final verification

- [ ] Report canvas title, id, URL, node counts and per-location output counts.
- [ ] Distinguish completed, pending and failed tasks.
- [ ] Preserve all generated results visibly in their original output nodes.


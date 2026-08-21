# AIKO2D Midnight Swim Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and verify four cohesive AIKO2D Midnight Swim promotional images that look like real mobile-game activity screens using the approved C layout.

**Architecture:** Create a new inspectable canvas rather than overwriting the rejected campaign. Each screen receives one independent `Group -> Generator -> Output` lane containing the identity reference, mood reference, and a screen-specific prompt derived from one shared layout contract. Generate one candidate per lane, visually review every output, refill only rejected or failed lanes, and retain all run metadata.

**Tech Stack:** Infinite Canvas local REST API, `tools/canvasctl.py`, mikoto `gpt-image-2`, PowerShell verification, Codex image inspection.

---

### Task 1: Preflight and preserve the current campaign

**Files:**
- Read: `docs/superpowers/specs/2026-08-21-aiko2d-midnight-swim-layout-redesign.md`
- Preserve canvas: `6c7458a8bce341bfb560ea71e41f9f78`

- [ ] **Step 1: Confirm the local canvas adapter and provider**

Run:

```powershell
& 'E:\cursor\project29 画布工具\Infinite-Canvas-main\python\python.exe' `
  'E:\cursor\project29 画布工具\Infinite-Canvas-main\tools\canvasctl.py' `
  --base 'http://127.0.0.1:3001' doctor
```

Expected: service reports OK and `custom-api-6 / mikoto / gpt-image-2` is enabled.

- [ ] **Step 2: Verify the rejected campaign remains intact**

Run:

```powershell
$canvas = Invoke-RestMethod -Uri 'http://127.0.0.1:3001/api/canvases/6c7458a8bce341bfb560ea71e41f9f78'
$canvas.canvas.nodes.Count
$canvas.canvas.connections.Count
```

Expected: 24 nodes and 8 connections. Do not modify this canvas.

### Task 2: Build four C-layout canvas lanes

**Files:**
- Reference: `C:\本地资源库\本地资源库\AIKO\三视图\canvas-output-1784780287312.png`
- Reference: `C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-da4887c5-9e05-4a26-8fe5-80a998a44a43.png`
- Create canvas: `AIKO2D_EN_MidnightSwim_CLayout_4Screens_20260821`

- [ ] **Step 1: Define the shared layout contract in every prompt**

Use this exact shared contract before each screen-specific instruction:

```text
Create a polished vertical 9:16 screen from the AIKO2D mobile AI companion game. Reference 1 is the authoritative identity sheet; preserve the same clearly adult 25-year-old silver-haired catwoman with white cat ears, rose-red eyes, facial identity, and mature proportions. Reference 2 supplies only the midnight rooftop pool, navy-violet neon, moonlight, and reflective-water atmosphere. Use a real mobile-game activity-screen layout: top 10 percent contains only a small AIKO2D wordmark and one short section label; middle 60 percent is uninterrupted character-and-environment key art; bottom 30 percent is one compact dark translucent action sheet. Use modern game UI sans-serif typography, one violet primary action, consistent spacing and rounded corners. No oversized serif headline, no three-column features, no repeated logos, no stacked glass panels, no QR code, no store badges, no reviews, no icon cloud, no watermark. Keep the character integrated into the scene and under 40 percent of the total area. Use short, correctly spelled English text.
```

- [ ] **Step 2: Create the four screen-specific prompts**

Append exactly one of these blocks to the shared contract:

```text
Screen 1 - Event Entry. Top label: LIMITED EVENT. Bottom-sheet title: MIDNIGHT SWIM. Supporting line: A private story beneath the moonlight. Compact status: ENDS IN 06D 18H. Primary button: ENTER EVENT.

Screen 2 - Story Choice. Top label: INTERACTIVE STORY. Bottom-sheet title: CHOOSE YOUR REPLY. Dialogue: Stay a little longer? Show exactly two restrained choice rows: STAY WITH HER and MAKE HER SMILE. Do not add another CTA.

Screen 3 - Voice Call. Top label: VOICE COMPANION. Bottom-sheet title: AIKO IS CALLING. Show one compact violet waveform and timer 00:18. Primary button: ANSWER.

Screen 4 - Bond Reward. Top label: BOND REWARD. Bottom-sheet title: LEVEL 07 REACHED. Show one compact 72 percent progress bar and one small MIDNIGHT OUTFIT reward thumbnail. Primary button: CLAIM REWARD.
```

- [ ] **Step 3: Compose the visible workflow without running**

Run `canvasctl.py compose` with four `--target` arguments, both `--image` references, `--multi-ref`, `--provider custom-api-6`, `--model gpt-image-2`, `--count 1`, `--ratio 9:16`, `--resolution 2K`, and `--quality high`; omit `--run` for the structure-only pass.

Expected: one new canvas with four Groups, four prompts, four visible generators, four fixed-size outputs, and eight `Group -> Generator -> Output` connections.

### Task 3: Run one candidate per screen

**Files:**
- Modify canvas: the ID returned by Task 2

- [ ] **Step 1: Run the four visible generator plans**

Submit exactly one task per screen to `/api/canvas-image-tasks` using the prompt, provider, model, size, quality, and two references stored in each lane.

Expected: four task IDs, never more than four initial paid calls.

- [ ] **Step 2: Poll tasks without duplicate submission**

Poll each task at `/api/canvas-image-tasks/{task_id}` until `succeeded`, explicit failure, or a 15-minute timeout.

Expected: every terminal state and upstream error is retained in canvas logs.

- [ ] **Step 3: Write real outputs to connected Output nodes**

For each success, append the returned `/assets/output/*.png` item to the matching Output node and generator metadata. For a failure, set the generator failure status and keep the error log visible.

Expected: no generated image is placed inside an input Group.

### Task 4: Visual review and deficit-only refill

**Files:**
- Inspect: every generated file under `assets/output/` returned by Task 3

- [ ] **Step 1: Review each actual image**

Check each candidate against these exact conditions:

```text
shared top-10 / middle-60 / bottom-30 grid
modern sans-serif game UI
one bottom action sheet only
no oversized editorial headline
character under approximately 40 percent
screen function understood within one glance
correct short English copy
same navy-violet UI kit across all four screens
```

Expected: each output receives `accepted` or a concrete rejection reason such as `oversized typography`, `stacked panels`, `text error`, `identity drift`, or `layout inconsistency`.

- [ ] **Step 2: Refill only rejected or failed lanes**

Reuse the same Group, Generator, and Output. Modify only the prompt constraint that caused rejection, then submit one replacement for each deficit.

Expected: accepted count reaches four without rerunning accepted screens.

### Task 5: Structured verification and handoff

**Files:**
- Verify canvas: the ID returned by Task 2

- [ ] **Step 1: Verify structured state through the canvas API**

Confirm exactly four Groups, four prompts, four generators, four outputs, eight ordered connections, four accepted real images, and fixed output dimensions near `780x680`.

Expected: all four lanes are `Group -> Generator -> Output`, with prompts and both references inside their respective Groups.

- [ ] **Step 2: Present the four accepted files and canvas URL**

Report the canvas title and ID, provider/model, task success count, any retained failures, and absolute local output paths. Render all four accepted images in the final handoff.

Expected: the user can inspect the generation workflow and open each generated poster directly.

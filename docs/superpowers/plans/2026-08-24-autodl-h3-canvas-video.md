# AutoDL H3 Canvas Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AutoDL as the default provider for new canvas video nodes, automatically route prompt/image/audio inputs to one of seven verified MiniMax H3 workflows, resume asynchronous tasks without duplicate billing, and persist successful videos locally in the connected Output node.

**Architecture:** Put AutoDL workflow schemas, routing, validation, authentication discovery, and HTTP behavior in a focused `autodl_support.py` module. Expose small FastAPI routes from `main.py`; add a CommonJS/browser helper for deterministic UI routing; reuse the existing video node and Output rendering while giving AutoDL its own submit/status lifecycle. Existing providers keep their current `/api/canvas-video` path.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, httpx, unittest, browser JavaScript, CommonJS-compatible helpers, Node.js `assert`, existing Infinite Canvas JSON persistence.

---

## File map

- Create `autodl_support.py`: secure token discovery, seven-workflow registry, automatic resolver, exact body builder, doctor, submit, query, and result URL parsing.
- Create `tests/test_autodl_support.py`: pure resolver, validation, body-schema, authentication, and client tests.
- Create `tests/test_autodl_api.py`: FastAPI route, task status, idempotent download, and sanitization tests.
- Create `static/js/autodl-video.js`: pure UI resolver, labels, field limits, and resolution mapping driven by backend workflow metadata.
- Create `tests/autodl-video.test.js`: browser-helper unit tests.
- Create `tests/autodl-canvas.integration.test.js`: static contracts for script loading, defaults, UI controls, async endpoints, pending persistence, and audio cloud upload.
- Modify `main.py`: register `autodl` protocol/provider, add safe API models/routes, map successful remote results into local Output URLs, and extend cloud upload MIME support to audio.
- Modify `static/js/api-settings.js`: render built-in AutoDL connection state without accepting or displaying the token.
- Modify `static/api-settings.html`: add fixed AutoDL status copy explaining that authentication comes from `AUTODL_TOKEN` or `.env.autodl`, with no browser token field.
- Modify `static/js/canvas.js`: make new video nodes default to AutoDL auto mode, render dynamic workflow controls, submit/poll/resume AutoDL tasks, and upload audio references explicitly.
- Modify `static/canvas.html`: load `autodl-video.js` before `canvas.js` and bump only the affected cache tokens while preserving the user's existing free-compositor cache-token edits.

### Task 1: Build the workflow registry and automatic resolver with TDD

**Files:**
- Create: `tests/test_autodl_support.py`
- Create: `autodl_support.py`

- [ ] **Step 1: Write failing registry and routing tests**

Create `tests/test_autodl_support.py` with `unittest.TestCase` cases that assert:

```python
import unittest

import autodl_support as support


class AutoDLWorkflowTests(unittest.TestCase):
    def test_registry_contains_exact_verified_workflows(self):
        self.assertEqual({
            "minimax_h3_lightx2v_v5",
            "minimax_h3_lightx2v_v5_15s",
            "minimax_h3_lightx2v_no_pic",
            "minimax_h3_lightx2v",
            "minimax_h3_image_audio_to_video_v2",
            "minimax_h3_image_audio_to_video_v2_15s",
            "minimax_h3_image_audio_to_video",
        }, set(support.WORKFLOWS))

    def test_routes_by_media_duration_and_lip_sync_intent(self):
        cases = [
            ({"prompt":"cloud walk","duration":8,"images":[],"audios":[]}, "minimax_h3_lightx2v_no_pic"),
            ({"prompt":"walk","duration":10,"images":["a"],"audios":[]}, "minimax_h3_lightx2v_v5"),
            ({"prompt":"walk","duration":11,"images":["a"],"audios":[]}, "minimax_h3_lightx2v_v5_15s"),
            ({"prompt":"talk","duration":8,"images":["a"],"audios":["b"]}, "minimax_h3_image_audio_to_video_v2"),
            ({"prompt":"角色说话并自动对口型","duration":8,"images":["a"],"audios":["b"]}, "minimax_h3_image_audio_to_video"),
            ({"prompt":"montage","duration":15,"images":["a"],"audios":["b","c"]}, "minimax_h3_image_audio_to_video_v2_15s"),
        ]
        for request, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, support.resolve_workflow(**request).workflow_id)

    def test_first_last_and_invalid_inputs_fail_before_submission(self):
        resolved = support.resolve_workflow(
            prompt="transition", duration=8, images=["a", "b"], audios=[], first_last=True
        )
        self.assertEqual("minimax_h3_lightx2v", resolved.workflow_id)
        for changes in (
            {"duration":16,"images":["a"],"audios":[]},
            {"duration":8,"images":[str(i) for i in range(10)],"audios":[]},
            {"duration":8,"images":["a"],"audios":["a","b","c","d"]},
            {"duration":8,"images":["a"],"audios":[],"videos":["v.mp4"]},
            {"duration":8,"images":["a"],"audios":[],"first_last":True},
        ):
            with self.subTest(changes=changes), self.assertRaises(support.AutoDLValidationError):
                support.resolve_workflow(prompt="x", **changes)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& .\python\python.exe -m unittest tests.test_autodl_support -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autodl_support'`.

- [ ] **Step 3: Implement the fixed registry and resolver**

Create `autodl_support.py` with immutable workflow definitions for the seven IDs. Each definition contains `name`, `min_duration`, `max_duration`, `min_images`, `max_images`, `min_audios`, `max_audios`, `supports_prompt`, `supports_seed`, `supports_square`, and `max_resolution`. Add:

```python
@dataclass(frozen=True)
class ResolvedWorkflow:
    workflow_id: str
    name: str
    reason: str


LIP_SYNC_RE = re.compile(
    r"对口型|口型|嘴型|说话|讲话|念台词|配音|唱歌|演唱|lip\s*sync|lipsync|speaking|talking|singing",
    re.I,
)


def resolve_workflow(*, prompt, duration, images, audios, videos=(), first_last=False,
                     mode="auto", workflow_id=""):
    duration = int(duration)
    images, audios, videos = list(images or ()), list(audios or ()), list(videos or ())
    if not 1 <= duration <= 15:
        raise AutoDLValidationError("AutoDL H3 视频时长必须为 1–15 秒")
    if videos:
        raise AutoDLValidationError("AutoDL H3 工作流不支持参考视频，请先截取图片帧")
    if len(images) > 9 or len(audios) > 3:
        raise AutoDLValidationError("AutoDL H3 最多支持 9 张图片和 3 段音频")
    if mode == "manual":
        return validate_manual_workflow(workflow_id, prompt, duration, images, audios, first_last)
    if len(images) == 1 and len(audios) == 1 and LIP_SYNC_RE.search(str(prompt or "")):
        selected = "minimax_h3_image_audio_to_video"
        reason = "单图单音频，提示词包含说话、唱歌或对口型意图"
    elif audios:
        selected = "minimax_h3_image_audio_to_video_v2" if duration <= 10 else "minimax_h3_image_audio_to_video_v2_15s"
        reason = f"连接了 {len(images)} 张图片、{len(audios)} 段音频，时长 {duration} 秒"
    elif first_last:
        if len(images) != 2:
            raise AutoDLValidationError("首尾帧工作流必须正好连接 2 张图片")
        selected, reason = "minimax_h3_lightx2v", "已开启首尾帧并连接 2 张图片"
    elif images:
        selected = "minimax_h3_lightx2v_v5" if duration <= 10 else "minimax_h3_lightx2v_v5_15s"
        reason = f"连接了 {len(images)} 张图片，时长 {duration} 秒，无音频"
    else:
        selected, reason = "minimax_h3_lightx2v_no_pic", "只有提示词，没有参考图片或音频"
    return validate_resolved(selected, prompt, duration, images, audios, reason)
```

Implement `validate_resolved()` and `validate_manual_workflow()` from the registry limits so manual mode cannot bypass required inputs.

- [ ] **Step 4: Run the test and verify GREEN**

Run the same unittest command. Expected: all registry/routing cases PASS.

- [ ] **Step 5: Commit the pure domain layer**

```powershell
git add autodl_support.py tests/test_autodl_support.py
git commit -m "feat: add AutoDL H3 workflow resolver"
```

### Task 2: Build exact request bodies and the asynchronous AutoDL client

**Files:**
- Modify: `tests/test_autodl_support.py`
- Modify: `autodl_support.py`

- [ ] **Step 1: Add failing body-schema and token-safety tests**

Add tests asserting exact keys for all workflow families:

```python
def test_exact_body_keys(self):
    refs = [f"https://example.test/{i}.png" for i in range(2)]
    self.assertEqual(
        {"prompt","duration","resolution","seed","ref_image_0","ref_image_1"},
        set(support.build_request_body("minimax_h3_lightx2v_v5", "move", 8, "768p竖", refs, [], seed=7)),
    )
    self.assertEqual(
        {"prompt","duration","resolution","first_frame","last_frame"},
        set(support.build_request_body("minimax_h3_lightx2v", "move", 8, "768p横", refs, [])),
    )
    self.assertEqual(
        {"resolution","ref_image_0","ref_audio_0","audio_duration"},
        set(support.build_request_body(
            "minimax_h3_image_audio_to_video", "ignored", 8, "768p竖",
            refs[:1], ["https://example.test/a.wav"]
        )),
    )

def test_discover_token_and_sanitize_errors(self):
    env = {"AUTODL_TOKEN":"secret-token"}
    token, source = support.discover_token(environ=env, cwd=Path("."), home=Path("."))
    self.assertEqual("secret-token", token)
    self.assertEqual("process environment", source)
    self.assertNotIn("secret-token", support.safe_error(RuntimeError("Authorization: secret-token"), token))
```

Mock `httpx.AsyncClient` and assert submit uses the wrapped endpoint, returns `data.task_id`, query preserves `QUEUED/RUNNING/SUCCESS/FAILED`, doctor sends no paid request, and `collect_result_urls()` reads only `data.results` HTTP(S) URLs.

- [ ] **Step 2: Run tests and verify RED**

Expected: failures for missing `build_request_body`, `discover_token`, `AutoDLClient`, and `collect_result_urls`.

- [ ] **Step 3: Implement exact body construction and client methods**

Add `build_request_body()` with explicit branches for the five schema families. Add async methods:

```python
class AutoDLClient:
    def __init__(self, token, base_url="https://autodl.art", client_factory=httpx.AsyncClient):
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.client_factory = client_factory

    async def submit(self, workflow_id, body):
        url = f"{self.base_url}/api/v1/comfyui/comfyui_workflow/{quote(workflow_id, safe='_.-')}"
        async with self.client_factory(timeout=VIDEO_TIMEOUT, follow_redirects=True) as client:
            response = await client.post(url, headers=self.headers(), json=body)
            return parse_success_response(response, require_task_id=True)

    async def query(self, task_id):
        safe_id = validate_task_id(task_id)
        url = f"{self.base_url}/api/v1/comfyui/comfyui_workflow/result/{safe_id}"
        async with self.client_factory(timeout=QUERY_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers())
            return parse_success_response(response)
```

Implement doctor with the all-zero fake task ID and accept authenticated `InternalError / 工作流不可用` as connected. Never include headers or token values in returned structures.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: exact-body, auth, doctor, submit, query, status, and URL tests PASS.

- [ ] **Step 5: Commit the client layer**

```powershell
git add autodl_support.py tests/test_autodl_support.py
git commit -m "feat: add AutoDL wrapped workflow client"
```

### Task 3: Add safe FastAPI provider and task routes

**Files:**
- Create: `tests/test_autodl_api.py`
- Modify: `main.py`
- Modify: `autodl_support.py`

- [ ] **Step 1: Write failing route and idempotency tests**

Test that routes exist with expected methods, `/api/autodl/workflows` exposes no token fields, `/api/autodl/status` sanitizes failures, task submission returns the resolved workflow and task ID, and polling success downloads once. Use `TemporaryDirectory`, patch `OUTPUT_DIR`, and mock the support client. Assert a second success poll returns the existing local path without another download.

- [ ] **Step 2: Run `tests.test_autodl_api` and verify RED**

Run:

```powershell
& .\python\python.exe -m unittest tests.test_autodl_api -v
```

Expected: route lookup fails because `/api/autodl/*` is not registered.

- [ ] **Step 3: Register provider protocol and request models**

In `main.py`, import `autodl_support as autodl`, add `autodl` to `SUPPORTED_PROVIDER_PROTOCOLS`, and add a built-in provider whose `video_models` are the seven workflow IDs. Define `AutoDLTaskRequest` with prompt, duration, ratio, resolution, seed, images, videos, audios, first-last flag, workflow mode, and workflow ID.

- [ ] **Step 4: Add routes with backend-authoritative resolution**

Implement:

```python
@app.get("/api/autodl/workflows")
async def autodl_workflows():
    return {"workflows": autodl.public_workflows(), "default": autodl.DEFAULT_WORKFLOW}

@app.get("/api/autodl/status")
async def autodl_status():
    return await autodl.doctor_safe()

@app.post("/api/autodl/tasks")
async def autodl_submit_task(payload: AutoDLTaskRequest):
    resolved = autodl.resolve_canvas_request(payload)
    body = autodl.build_canvas_request_body(payload, resolved)
    result = await autodl.client_from_environment().submit(resolved.workflow_id, body)
    return autodl.public_submission(result, resolved)

@app.get("/api/autodl/tasks/{task_id}")
async def autodl_task_status(task_id: str):
    result = await autodl.client_from_environment().query(task_id)
    return await finalize_autodl_result(task_id, result)
```

Use a deterministic sanitized filename such as `autodl_<task-id>.mp4`; download to a temporary sibling and atomically rename. Validate media content type/extension and reuse an already-valid local file.

- [ ] **Step 5: Run API and support tests and verify GREEN**

Run both Python test modules. Expected: all PASS and no real network request occurs.

- [ ] **Step 6: Commit API integration**

```powershell
git add main.py autodl_support.py tests/test_autodl_api.py
git commit -m "feat: expose resumable AutoDL video tasks"
```

### Task 4: Add the pure browser workflow helper

**Files:**
- Create: `static/js/autodl-video.js`
- Create: `tests/autodl-video.test.js`

- [ ] **Step 1: Write failing Node tests**

Require the missing helper and assert automatic choices, lip-sync keywords, manual override validation, ratio mapping, 1080p-to-768p downgrade for 15-second workflows, and rejection of reference videos.

- [ ] **Step 2: Run and verify RED**

```powershell
node tests/autodl-video.test.js
```

Expected: `Cannot find module '../static/js/autodl-video.js'`.

- [ ] **Step 3: Implement a UMD/CommonJS helper**

Expose `resolveWorkflow`, `validateSelection`, `resolutionValue`, `workflowOptions`, and `explainResolutionAdjustment`. The resolver consumes metadata returned by `/api/autodl/workflows`; do not hard-code request field names in JavaScript. Return `{workflowId, reason, error, maxDuration, maxResolution}` without mutating the node.

- [ ] **Step 4: Run and verify GREEN**

Expected: `autodl-video tests passed` and exit code 0.

- [ ] **Step 5: Commit helper and tests**

```powershell
git add static/js/autodl-video.js tests/autodl-video.test.js
git commit -m "feat: add AutoDL video routing helper"
```

### Task 5: Make AutoDL the new-video default and render dynamic controls

**Files:**
- Create: `tests/autodl-canvas.integration.test.js`
- Modify: `static/canvas.html`
- Modify: `static/js/canvas.js:925-955`
- Modify: `static/js/canvas.js:3411-3445`
- Modify: `static/js/canvas.js:10235-10370`
- Modify: `static/js/api-settings.js`
- Modify: `static/api-settings.html`

- [ ] **Step 1: Write failing static integration contracts**

Assert `autodl-video.js` loads before `canvas.js`, new video nodes contain `apiProvider:'autodl'` and `workflowMode:'auto'`, the UI contains an Auto option and visible resolution reason, and the API settings page references `/api/autodl/status` without a token input value.

- [ ] **Step 2: Run and verify RED**

Expected: assertions fail because the helper is not loaded and current defaults still select the first configured video provider/model.

- [ ] **Step 3: Load the helper without overwriting the user's unrelated HTML changes**

Add only:

```html
<script src="/static/js/autodl-video.js?v=2026.08.24-autodl-h3-1"></script>
```

immediately before `canvas.js`, and update the `canvas.js` cache token. Preserve the current free-compositor script/style tokens exactly as found at implementation time.

- [ ] **Step 4: Update new-node defaults and AutoDL workflow UI**

Create new nodes with AutoDL auto fields while leaving loaded nodes unchanged. In `renderVideoBody()`, when provider is AutoDL, label the second selector “工作流”, prepend “自动选择”, render the resolved workflow/reason, constrain duration/resolution options, and render accurate image/audio counts. Manual selection sets `workflowMode='manual'`; choosing auto clears `workflowId`.

- [ ] **Step 5: Add safe AutoDL status to API settings**

Render `已连接`, `未配置`, or `鉴权失败` from `/api/autodl/status`. Do not create a browser-visible token field or include `api_key` for the AutoDL provider in `PUT /api/providers`.

- [ ] **Step 6: Run unit and integration tests and verify GREEN**

Run `node tests/autodl-video.test.js` and `node tests/autodl-canvas.integration.test.js`. Expected: both PASS.

- [ ] **Step 7: Commit UI defaults and controls**

```powershell
git add static/canvas.html static/js/canvas.js static/js/api-settings.js static/api-settings.html tests/autodl-canvas.integration.test.js
git commit -m "feat: add AutoDL workflow controls to video nodes"
```

### Task 6: Implement submit, poll, persist, and reload recovery

**Files:**
- Modify: `tests/autodl-canvas.integration.test.js`
- Modify: `static/js/canvas.js:12702-12776`

- [ ] **Step 1: Add failing lifecycle contracts**

Assert AutoDL uses `/api/autodl/tasks`, stores returned `task_id` in Output pending metadata before polling, polls `/api/autodl/tasks/{task_id}`, maps `QUEUED/RUNNING/SUCCESS/FAILED`, and has a load-time resumer that never calls submit for an existing task ID.

- [ ] **Step 2: Run and verify RED**

Expected: lifecycle assertions fail because `runVideoNode()` only calls `/api/canvas-video`.

- [ ] **Step 3: Add AutoDL-specific asynchronous branch**

Implement `runAutoDLVideoNode(node, snapshot, out, pending)` and `pollAutoDLTask(node, out, pending)`. Save pending immediately after receiving the task ID. On success, append only backend-local URLs to Output and preserve provider/workflow/reason/task metadata. On failure, keep the visible pending/error card and never submit again automatically.

- [ ] **Step 4: Resume pending tasks on canvas load**

Scan saved Output pending items after nodes load. Resume entries with `provider_id==='autodl'` and a valid `task_id`; mark entries without task IDs as `unknown_submission` and require an explicit new run.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: helper and canvas lifecycle tests PASS.

- [ ] **Step 6: Commit lifecycle integration**

```powershell
git add static/js/canvas.js tests/autodl-canvas.integration.test.js
git commit -m "feat: resume AutoDL canvas video tasks"
```

### Task 7: Extend explicit cloud upload to audio and enforce public-URL preflight

**Files:**
- Modify: `tests/test_autodl_api.py`
- Modify: `tests/autodl-canvas.integration.test.js`
- Modify: `main.py:11300-11382`
- Modify: `static/js/canvas.js:4490-4604`

- [ ] **Step 1: Add failing upload and preflight tests**

Assert local audio MIME types are accepted by `/api/cloud-video/upload`, video references remain rejected by AutoDL submission, local image/audio references without public mappings fail before client submit, and public/PUBLIC_MEDIA_BASE_URL references pass unchanged.

- [ ] **Step 2: Run and verify RED**

Expected: audio upload is rejected by current MIME prefixes and UI filters omit audio refs.

- [ ] **Step 3: Extend the existing explicit upload path**

Allow `audio/` in `local_media_path_for_cloud_upload()` only for the generic cloud-media endpoint. Update the video-node upload button to gather `image`, `video`, and `audio` refs and adjust user-facing messages to “媒体文件”. Keep upload user-triggered; `runAutoDLVideoNode()` only consumes stored mappings and never calls the uploader.

- [ ] **Step 4: Run focused Python and JavaScript tests and verify GREEN**

Expected: explicit audio upload is supported, AutoDL preflight rejects unresolved local media, and no test makes a paid request.

- [ ] **Step 5: Commit media preflight**

```powershell
git add main.py static/js/canvas.js tests/test_autodl_api.py tests/autodl-canvas.integration.test.js
git commit -m "feat: validate AutoDL public media inputs"
```

### Task 8: Regression verification and non-billing acceptance

**Files:**
- Verify: `autodl_support.py`
- Verify: `main.py`
- Verify: `static/js/autodl-video.js`
- Verify: `static/js/canvas.js`
- Verify: `static/js/api-settings.js`
- Verify: `static/canvas.html`
- Verify: `tests/test_autodl_support.py`
- Verify: `tests/test_autodl_api.py`
- Verify: `tests/autodl-video.test.js`
- Verify: `tests/autodl-canvas.integration.test.js`

- [ ] **Step 1: Run focused Python tests**

```powershell
& .\python\python.exe -m unittest tests.test_autodl_support tests.test_autodl_api -v
```

Expected: all tests PASS with no external paid task.

- [ ] **Step 2: Run every Python test**

```powershell
& .\python\python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all project Python tests PASS.

- [ ] **Step 3: Run every JavaScript test and syntax check**

```powershell
Get-ChildItem tests -Filter '*.test.js' | Sort-Object Name | ForEach-Object {
  node $_.FullName
  if($LASTEXITCODE -ne 0){ throw "Failed: $($_.Name)" }
}
node --check static/js/autodl-video.js
node --check static/js/canvas.js
```

Expected: every test prints its success marker; syntax checks produce no output.

- [ ] **Step 4: Run the non-billing AutoDL doctor**

```powershell
& "$env:USERPROFILE\.codex\skills\autodl\scripts\autodl.ps1" doctor
```

Expected: `status=ok`, `authenticated=true`, and `paid_task_submitted=false`. Never print the token.

- [ ] **Step 5: Verify saved structure through the local API**

Check `http://127.0.0.1:3001/`; when offline, start the server with `powershell -ExecutionPolicy Bypass -File .\launch-canvas.ps1`. Create a test canvas lane and verify structured JSON contains one Group, one video generator, one Output, `Group -> video -> Output` connections, AutoDL auto-mode fields, and no token. Use mocked task responses for `QUEUED`, `RUNNING`, `SUCCESS`, refresh recovery, and `FAILED`.

- [ ] **Step 6: Visually verify the existing node layout**

Open the exact test canvas and confirm the AutoDL platform/workflow selectors, automatic reason, dynamic constraints, pending status, and local video result fit the existing screenshot-derived node layout without obscuring ports or the run button.

- [ ] **Step 7: Review the final diff and commit only concrete verification fixes**

```powershell
git status --short
git diff --check
git diff --stat
```

Expected: only approved AutoDL files plus the user's pre-existing unrelated `static/canvas.html` edits are present. Stage implementation hunks deliberately so unrelated user changes are never absorbed into an AutoDL commit.

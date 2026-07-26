const fs = require('fs');
const path = require('path');

const BASE = 'http://127.0.0.1:3001';
const CANVAS_ID = '0872cb9368c440bcbca49eb43110652c';
const TARGET_PER_DIFF = 5;
const TASK_TIMEOUT_MS = 240000;
const GLOBAL_ACTIVE_LIMIT = 10;
const LANE_ACTIVE_LIMIT = 4;

const PROVIDER_MODELS = {
  'custom-api-2': 'gpt-image-2',
  apimart: 'gpt-image-2',
  'custom-api-5': 'gpt-image-2',
  'custom-api-6': 'gpt-image-2',
  'custom-api-3': 'gpt-image-2',
  'custom-api': 'gpt-image-2',
};

function nowMs(){ return Date.now(); }
function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
function uid(prefix){ return `${prefix}_${Math.random().toString(16).slice(2, 14)}_${nowMs()}`; }

function latestProgressPath(){
  const dir = path.join(__dirname, '..', 'output');
  return fs.readdirSync(dir)
    .filter(name => /^codex_bgdiff_.*_progress\.json$/.test(name))
    .map(name => path.join(dir, name))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
}

const PROGRESS_PATH = process.env.CODEX_BGDIFF_PROGRESS || latestProgressPath();
if(!PROGRESS_PATH) throw new Error('no codex bgdiff progress file found');

async function httpJson(method, endpoint, body=null, timeoutMs=60000){
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${endpoint}`, {
      method,
      headers: body ? {'Content-Type':'application/json'} : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = {raw:text}; }
    if(!res.ok){
      const detail = data?.detail?.message || data?.detail || data?.message || text || `${res.status} ${res.statusText}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

async function loadCanvas(){
  return (await httpJson('GET', `/api/canvases/${CANVAS_ID}`, null, 60000)).canvas;
}

async function saveCanvas(canvas, reason){
  const payload = {
    title: canvas.title,
    icon: canvas.icon || '🗺️',
    nodes: canvas.nodes || [],
    connections: canvas.connections || [],
    viewport: canvas.viewport || {x:0,y:0,scale:1},
    logs: canvas.logs || [],
    settings: canvas.settings || {},
    client_id: reason,
    base_updated_at: canvas.updated_at || 0,
  };
  try {
    return (await httpJson('PUT', `/api/canvases/${CANVAS_ID}`, payload, 120000)).canvas;
  } catch(err) {
    if(String(err.message || '').includes('画布已被其他页面更新')){
      const latest = await loadCanvas();
      latest.nodes = payload.nodes;
      latest.connections = payload.connections;
      latest.logs = payload.logs;
      latest.settings = payload.settings;
      return saveCanvas(latest, `${reason}-retry`);
    }
    throw err;
  }
}

function nodeMap(canvas){
  return new Map((canvas.nodes || []).map(node => [node.id, node]));
}

function outputUrlValue(item){
  return typeof item === 'string' ? item : item?.url || '';
}

function isSuccessItem(item){
  const url = outputUrlValue(item);
  return Boolean(url && !String(url).startsWith('failed://') && item?.kind !== 'error');
}

function uniqueAppend(list, items){
  const seen = new Set((list || []).map(outputUrlValue).filter(Boolean));
  let added = 0;
  for(const item of items){
    const url = outputUrlValue(item);
    if(!url || seen.has(url)) continue;
    seen.add(url);
    list.push(item);
    added++;
  }
  return added;
}

function requestMetaFromTask(task){
  const req = task.request || {};
  const resolved = task.resolved || {};
  const params = task.params || {};
  return {
    canvas_task_id: task.id || task.task_id || '',
    task_id: task.task_id || task.id || '',
    provider_id: resolved.provider_id || task.provider_id || params.provider_id || req.provider_id || '',
    provider_name: resolved.provider_name || task.provider_name || params.provider_name || req.provider_name || '',
    requested_provider_id: req.provider_id || '',
    requested_provider_name: req.provider_name || '',
    model: resolved.model || task.model || params.model || req.model || '',
    requested_model: req.model || '',
    size: resolved.size || params.size || req.size || '',
    api_size: resolved.api_size || '',
    resolution: resolved.resolution || '',
    quality: resolved.quality || params.quality || req.quality || '',
    n: resolved.n ?? params.n ?? req.n ?? '',
    reference_count: resolved.reference_count ?? params.reference_count ?? req.reference_count ?? '',
    reference_count_sent: resolved.reference_count_sent ?? '',
    protocol: resolved.protocol || task.protocol || '',
    endpoint_family: resolved.endpoint_family || '',
    endpoint_host: resolved.endpoint_host || '',
    endpoint_path: resolved.endpoint_path || '',
    reference_transport: resolved.reference_transport || '',
    reference_transport_actual: resolved.reference_transport_actual || '',
    reference_transport_mode: resolved.reference_transport_mode || '',
    remapped: Boolean(resolved.remapped || task.remapped),
    backend: task.backend || resolved.provider_id || params.provider_id || req.provider_id || '',
  };
}

function errorOutput(message, run, runMs){
  return {
    url: `failed://codex-bgdiff/${uid('err')}`,
    kind: 'error',
    name: '生成失败',
    error: String(message || '生成失败'),
    runMs,
    run,
  };
}

function logEntry(status, run, outputs, runMs, error=''){
  return {
    id: uid('log'),
    createdAt: nowMs(),
    status,
    platform: run?.request?.provider_name || run?.request?.provider_id || '',
    nodeType: 'generator',
    model: run?.request?.model || '',
    request: run?.request || {},
    prompt: run?.prompt || '',
    outputs: outputs || [],
    refs: run?.refs || [],
    runMs: Number(runMs || 0),
    error: error ? String(error) : '',
  };
}

function appendOutput(canvas, lane, item, runMs, error=''){
  const by = nodeMap(canvas);
  const out = by.get(lane.outId);
  const gen = by.get(lane.genId);
  if(!out || !gen) return 0;
  const outputItem = typeof item === 'string'
    ? {url:item, viewed:false, runMs, run:lane.lastRun || null}
    : item;
  out.images = out.images || [];
  const added = uniqueAppend(out.images, [outputItem]);
  const url = outputUrlValue(outputItem);
  if(url && !String(url).startsWith('failed://')){
    out.imageComparisons = out.imageComparisons || {};
    out.imageComparisons[url] = {url: lane.ref.url, name: lane.ref.name || 'input image'};
    gen.generatedOutputs = gen.generatedOutputs || [];
    uniqueAppend(gen.generatedOutputs, [url]);
  }
  canvas.logs = canvas.logs || [];
  canvas.logs.unshift(logEntry(error ? 'failed' : 'success', lane.lastRun, [outputItem], runMs, error));
  canvas.logs = canvas.logs.slice(0, 500);
  return added;
}

function removePending(canvas, outId, pendingId){
  const out = nodeMap(canvas).get(outId);
  if(!out) return;
  out._pending = (out._pending || []).filter(p => p.id !== pendingId);
}

async function providerPool(progress){
  const failureByProvider = {};
  const successByProvider = {};
  for(const task of Object.values(progress.tasks || {})){
    if(['failed','timeout','poll-error','failed-empty'].includes(task.status)){
      failureByProvider[task.provider_id] = (failureByProvider[task.provider_id] || 0) + 1;
    }
    if(task.status === 'succeeded'){
      successByProvider[task.provider_id] = (successByProvider[task.provider_id] || 0) + 1;
    }
  }
  const providers = (await httpJson('GET', '/api/providers', null, 30000)).providers || [];
  return providers
    .filter(provider => provider.enabled !== false && provider.has_key && PROVIDER_MODELS[provider.id])
    .map((provider, index) => ({
      id: provider.id,
      name: provider.name || provider.id,
      model: PROVIDER_MODELS[provider.id],
      rank: ['custom-api-2','custom-api-5','custom-api-6','custom-api-3','custom-api','apimart'].indexOf(provider.id),
      active: 0,
      uses: 0,
      failures: failureByProvider[provider.id] || 0,
      successes: successByProvider[provider.id] || 0,
      disabled: provider.id === 'apimart' && (failureByProvider[provider.id] || 0) > 0,
      index,
    }))
    .filter(provider => !provider.disabled)
    .sort((a, b) => a.rank - b.rank || a.index - b.index);
}

function pickProvider(providers){
  const available = providers.filter(p => p.failures < 20);
  if(!available.length) return null;
  available.sort((a, b) => a.active - b.active || a.failures - b.failures || a.uses - b.uses || b.successes - a.successes || a.rank - b.rank);
  return available[0];
}

function readProgress(){
  return JSON.parse(fs.readFileSync(PROGRESS_PATH, 'utf8'));
}

function writeProgress(progress){
  fs.writeFileSync(PROGRESS_PATH, JSON.stringify(progress, null, 2), 'utf8');
}

function buildLanes(canvas, progress){
  const by = nodeMap(canvas);
  return Object.entries(progress.lanes).map(([key, state]) => {
    const gen = by.get(state.generator_id);
    const out = by.get(state.output_id);
    const groupId = (canvas.connections || []).find(c => c.to === state.generator_id)?.from;
    const group = by.get(groupId);
    const refNode = (group?.items || []).map(id => by.get(id)).find(n => n?.type === 'image');
    const promptNode = (group?.items || []).map(id => by.get(id)).find(n => n?.type === 'prompt');
    if(!gen || !out || !group || !refNode || !promptNode) throw new Error(`lane is incomplete: ${key}`);
    out.images = out.images || [];
    out._pending = out._pending || [];
    const accepted = out.images.filter(isSuccessItem).length;
    state.accepted = accepted;
    return {
      key,
      label: state.label,
      groupId,
      genId: state.generator_id,
      outId: state.output_id,
      ref: {url: refNode.url, name: refNode.name || refNode.id},
      prompt: promptNode.text || '',
      accepted,
      submitted: state.submitted || 0,
      failed: state.failed || 0,
      timedOut: state.timedOut || 0,
      active: new Map(),
      lastRun: null,
    };
  });
}

function runFor(lane, provider){
  return {
    nodeType:'generator',
    node:{id:lane.genId, type:'generator', apiProvider:provider.id, model:provider.model, count:TARGET_PER_DIFF, forceFill:true, name:lane.label},
    prompt: lane.prompt,
    refs:[{url:lane.ref.url, name:lane.ref.name || 'source'}],
    request:{
      provider_id: provider.id,
      provider_name: provider.name,
      model: provider.model,
      size:'1344x1008',
      quality:'auto',
      n:1,
      reference_count:1,
      force_fill:true,
      force_target:TARGET_PER_DIFF,
      scheduler:'codex-three-bg-diff-resume',
      lane:lane.key,
      batch_id:readProgress().batch_id,
    },
  };
}

async function createTaskForLane(canvas, lane, provider, progress){
  provider.active++;
  provider.uses++;
  lane.submitted++;
  const run = runFor(lane, provider);
  lane.lastRun = run;
  const payload = {
    prompt: lane.prompt,
    provider_id: provider.id,
    model: provider.model,
    size: '1344x1008',
    quality: 'auto',
    reference_images: [{url:lane.ref.url, name:lane.ref.name || 'source'}],
  };
  const start = nowMs();
  try {
    const task = await httpJson('POST', '/api/canvas-image-tasks', payload, 60000);
    const taskId = task.task_id || task.id;
    run.request = {...run.request, ...requestMetaFromTask(task)};
    const pendingId = uid('p');
    const out = nodeMap(canvas).get(lane.outId);
    out._pending = out._pending || [];
    out._pending.push({
      id: pendingId,
      startedAt: start,
      run,
      canvasTaskId: taskId,
      canvasTaskType: 'online-image',
      canvasTaskStatus: 'queued',
      appendGenerated: true,
      previewSize: {width: 1344, height: 1008},
      requestSize: '1344x1008',
    });
    lane.active.set(pendingId, {pendingId, taskId, provider, run, start});
    progress.submitted = (progress.submitted || 0) + 1;
    progress.lanes[lane.key].submitted = lane.submitted;
    progress.tasks[pendingId] = {lane:lane.key, task_id:taskId, provider_id:provider.id, provider_name:provider.name, status:'queued', started_at:start};
    return true;
  } catch(err) {
    provider.active = Math.max(0, provider.active - 1);
    provider.failures++;
    lane.failed++;
    const runMs = nowMs() - start;
    const message = err.message || String(err);
    appendOutput(canvas, lane, errorOutput(message, run, runMs), runMs, message);
    progress.failed = (progress.failed || 0) + 1;
    progress.lanes[lane.key].failed = lane.failed;
    return false;
  }
}

async function pollActive(canvas, lane, item, progress){
  const elapsed = nowMs() - item.start;
  if(elapsed > TASK_TIMEOUT_MS){
    removePending(canvas, lane.outId, item.pendingId);
    item.provider.active = Math.max(0, item.provider.active - 1);
    item.provider.failures++;
    lane.active.delete(item.pendingId);
    lane.failed++;
    lane.timedOut++;
    const message = '单次请求等待超时，已换 API 补位';
    appendOutput(canvas, lane, errorOutput(message, item.run, elapsed), elapsed, message);
    progress.failed = (progress.failed || 0) + 1;
    progress.timeouts = (progress.timeouts || 0) + 1;
    progress.lanes[lane.key].failed = lane.failed;
    progress.lanes[lane.key].timedOut = lane.timedOut;
    progress.tasks[item.pendingId].status = 'timeout';
    progress.tasks[item.pendingId].error = message;
    return true;
  }
  const task = await httpJson('GET', `/api/canvas-image-tasks/${encodeURIComponent(item.taskId)}`, null, 30000);
  const taskProgress = progress.tasks[item.pendingId] || {};
  taskProgress.status = task.status;
  taskProgress.queue_ms = task.queue_ms || 0;
  taskProgress.run_ms = task.run_ms || 0;
  taskProgress.total_ms = task.total_ms || 0;
  progress.tasks[item.pendingId] = taskProgress;
  const out = nodeMap(canvas).get(lane.outId);
  const pending = (out?._pending || []).find(p => p.id === item.pendingId);
  if(pending){
    pending.canvasTaskStatus = task.status || pending.canvasTaskStatus;
    pending.queue_ms = task.queue_ms || pending.queue_ms || 0;
    pending.run_ms = task.run_ms || pending.run_ms || 0;
    pending.total_ms = task.total_ms || pending.total_ms || 0;
    pending.started_at = task.started_at || pending.started_at || 0;
    pending.updated_at = task.updated_at || pending.updated_at || 0;
    if(task.error) pending.error = task.error;
  }
  if(!['succeeded','failed','jimeng_pending'].includes(task.status)) return false;
  removePending(canvas, lane.outId, item.pendingId);
  item.provider.active = Math.max(0, item.provider.active - 1);
  lane.active.delete(item.pendingId);
  const runMs = task.run_ms || task.total_ms || (nowMs() - item.start);
  item.run.request = {...item.run.request, ...requestMetaFromTask(task)};
  lane.lastRun = item.run;
  if(task.status === 'succeeded'){
    const images = task.result?.images || [];
    if(images.length && lane.accepted < TARGET_PER_DIFF){
      appendOutput(canvas, lane, images[0], runMs, '');
      lane.accepted++;
      progress.succeeded = (progress.succeeded || 0) + 1;
      progress.appended = (progress.appended || 0) + 1;
      progress.tasks[item.pendingId].status = 'succeeded';
      progress.tasks[item.pendingId].image = images[0];
    } else if(!images.length) {
      const message = 'task succeeded but returned no image';
      appendOutput(canvas, lane, errorOutput(message, item.run, runMs), runMs, message);
      lane.failed++;
      progress.failed = (progress.failed || 0) + 1;
      progress.tasks[item.pendingId].status = 'failed-empty';
      progress.tasks[item.pendingId].error = message;
    }
  } else {
    const message = task.error || '生成失败';
    item.provider.failures++;
    lane.failed++;
    appendOutput(canvas, lane, errorOutput(message, item.run, runMs), runMs, message);
    progress.failed = (progress.failed || 0) + 1;
    progress.tasks[item.pendingId].status = task.status || 'failed';
    progress.tasks[item.pendingId].error = message;
  }
  progress.lanes[lane.key].accepted = lane.accepted;
  progress.lanes[lane.key].failed = lane.failed;
  return true;
}

function attachExistingActive(canvas, lanes, providers, progress){
  const laneByKey = new Map(lanes.map(lane => [lane.key, lane]));
  const providerById = new Map(providers.map(provider => [provider.id, provider]));
  for(const [pendingId, task] of Object.entries(progress.tasks || {})){
    if(!['queued','running','pending','waiting'].includes(task.status)) continue;
    if(progress.paused_at && task.started_at && task.started_at < progress.paused_at){
      task.status = 'ignored-old-prompt';
      task.error = 'Ignored because prompt was updated after this task was submitted';
      continue;
    }
    const lane = laneByKey.get(task.lane);
    const provider = providerById.get(task.provider_id);
    if(!lane || !provider) continue;
    const run = runFor(lane, provider);
    run.request = {...run.request, provider_id:task.provider_id, provider_name:task.provider_name, task_id:task.task_id, canvas_task_id:task.task_id};
    lane.lastRun = run;
    provider.active++;
    lane.active.set(pendingId, {pendingId, taskId:task.task_id, provider, run, start:task.started_at || nowMs()});
    const out = nodeMap(canvas).get(lane.outId);
    out._pending = out._pending || [];
    if(!out._pending.some(p => p.id === pendingId)){
      out._pending.push({
        id: pendingId,
        startedAt: task.started_at || nowMs(),
        run,
        canvasTaskId: task.task_id,
        canvasTaskType: 'online-image',
        canvasTaskStatus: task.status,
        appendGenerated: true,
        previewSize: {width: 1344, height: 1008},
        requestSize: '1344x1008',
      });
    }
  }
}

async function main(){
  let progress = readProgress();
  let canvas = await loadCanvas();
  let lanes = buildLanes(canvas, progress);
  const providers = await providerPool(progress);
  if(!providers.length) throw new Error('no usable providers');
  attachExistingActive(canvas, lanes, providers, progress);
  let lastSave = 0;
  while(lanes.some(lane => lane.accepted < TARGET_PER_DIFF)){
    for(const lane of lanes){
      while(
        lane.accepted + lane.active.size < TARGET_PER_DIFF
        && lane.active.size < LANE_ACTIVE_LIMIT
        && lanes.reduce((sum, l) => sum + l.active.size, 0) < GLOBAL_ACTIVE_LIMIT
      ){
        const provider = pickProvider(providers);
        if(!provider) break;
        await createTaskForLane(canvas, lane, provider, progress);
      }
    }
    if(nowMs() - lastSave > 1500){
      canvas = await saveCanvas(canvas, `${progress.batch_id}-resume-pending`);
      lastSave = nowMs();
    }
    const activeItems = lanes.flatMap(lane => [...lane.active.values()].map(item => ({lane, item})));
    if(!activeItems.length) break;
    await Promise.all(activeItems.map(({lane, item}) => pollActive(canvas, lane, item, progress).catch(err => {
      const message = err.message || String(err);
      item.provider.active = Math.max(0, item.provider.active - 1);
      item.provider.failures++;
      lane.active.delete(item.pendingId);
      removePending(canvas, lane.outId, item.pendingId);
      appendOutput(canvas, lane, errorOutput(message, item.run, nowMs() - item.start), nowMs() - item.start, message);
      lane.failed++;
      progress.failed = (progress.failed || 0) + 1;
      progress.tasks[item.pendingId].status = 'poll-error';
      progress.tasks[item.pendingId].error = message;
    })));
    for(const lane of lanes){
      const state = progress.lanes[lane.key];
      state.accepted = lane.accepted;
      state.submitted = lane.submitted;
      state.failed = lane.failed;
      state.timedOut = lane.timedOut;
    }
    writeProgress(progress);
    canvas = await saveCanvas(canvas, `${progress.batch_id}-resume-tick`);
    lastSave = nowMs();
    await sleep(1800);
  }
  for(const lane of lanes){
    const out = nodeMap(canvas).get(lane.outId);
    if(out) out._pending = [];
  }
  progress.finished_at = nowMs();
  progress.providers = providers.map(provider => ({id:provider.id, name:provider.name, model:provider.model, uses:provider.uses, failures:provider.failures}));
  writeProgress(progress);
  canvas = await saveCanvas(canvas, `${progress.batch_id}-resume-finished`);
  console.log(JSON.stringify({
    batch_id: progress.batch_id,
    progress_path: PROGRESS_PATH,
    target_total: progress.target_total,
    submitted: progress.submitted,
    succeeded: progress.succeeded,
    failed: progress.failed,
    timeouts: progress.timeouts,
    appended: progress.appended,
    lanes: progress.lanes,
  }, null, 2));
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});

const fs = require('fs');
const path = require('path');

const BASE = 'http://127.0.0.1:3001';
const CANVAS_ID = '0872cb9368c440bcbca49eb43110652c';
const SOURCE_GROUP_ID = 'grp_88d7724708085_1780989853190';
const TARGET_PER_DIFF = 5;
const TASK_TIMEOUT_MS = 240000;
const GLOBAL_ACTIVE_LIMIT = 12;
const LANE_ACTIVE_LIMIT = 5;
const BATCH_ID = `codex_bgdiff_${Date.now().toString(36)}`;
const PROGRESS_PATH = path.join(__dirname, '..', 'output', `${BATCH_ID}_progress.json`);

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
    let data = null;
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

async function saveCanvas(canvas, reason='codex-bgdiff'){
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

function providerRank(providerId){
  return ['custom-api-2','apimart','custom-api-5','custom-api-6','custom-api-3','custom-api'].indexOf(providerId);
}

async function providerPool(){
  const providers = (await httpJson('GET', '/api/providers', null, 30000)).providers || [];
  return providers
    .filter(provider => provider.enabled !== false && provider.has_key && PROVIDER_MODELS[provider.id])
    .map(provider => ({
      id: provider.id,
      name: provider.name || provider.id,
      model: PROVIDER_MODELS[provider.id],
      active: 0,
      uses: 0,
      failures: 0,
      rank: providerRank(provider.id),
    }))
    .sort((a, b) => a.rank - b.rank);
}

function pickProvider(providers){
  const available = providers.filter(p => p.failures < 3);
  if(!available.length) return null;
  available.sort((a, b) => a.active - b.active || a.uses - b.uses || a.rank - b.rank);
  return available[0];
}

function pendingCard(id, run, taskId, requestSize){
  return {
    id,
    startedAt: nowMs(),
    run,
    canvasTaskId: taskId,
    canvasTaskType: 'online-image',
    canvasTaskStatus: 'queued',
    appendGenerated: true,
    previewSize: {width: 1344, height: 1008},
    requestSize,
  };
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
  if(outputUrlValue(outputItem) && !String(outputUrlValue(outputItem)).startsWith('failed://')){
    out.imageComparisons = out.imageComparisons || {};
    out.imageComparisons[outputUrlValue(outputItem)] = {url: lane.ref.url, name: lane.ref.name || 'input image'};
    gen.generatedOutputs = gen.generatedOutputs || [];
    uniqueAppend(gen.generatedOutputs, [outputUrlValue(outputItem)]);
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

function buildPrompt(refName, variant){
  if(variant === 'afternoon'){
    return `${refName}。将这个 UI 图生成“下午差分”。必须以原图为准，画面整体不要变换：构图、比例、建筑位置、道路形状、物体大小、线条粗细、UI 地图风格都保持一致，只改变时间和光线。\n\n这是 galgame 地图 UI，要有温暖的感觉，但温暖要克制：像下午 3-4 点的柔和自然光，整体仍然明亮清爽，只是轻微偏暖。不要夕阳感，不要金黄色，不要橙黄色，不要整体变黄，不要重阴影，不要暗，不要高对比。\n\n不要有外部背景，不要樱花、不要花瓣，不要新增地标，不要人物、文字、logo、路标、图钉或圆形 marker。保持干净细线条、柔和手绘质感和原图可读性。`;
  }
  return `${refName}。生成“晚上差分 / 明亮夜晚 UI 版本”。必须以原图为准，画面整体不要变换：构图、比例、建筑位置、道路形状、物体大小、线条粗细、UI 地图风格都保持一致，只改变时间和光线。\n\n这是 galgame 地图 UI，夜晚也要温暖、干净、可读，不要做成很黑的黑夜图。整体亮度参考原图，只比白天降低一档；道路、建筑轮廓和色块必须清楚。可以有少量柔和窗灯/路灯作为夜晚提示，但不要明显大面积亮灯，不要霓虹，不要赛博朋克。\n\n不要太黑，不要太暗，不要偏紫，不要深蓝压暗，不要太黄，不要粗线条，不要高对比。不要有外部背景，不要樱花、不要花瓣，不要新增地标，不要人物、文字、logo、路标、图钉或圆形 marker。保持干净细线条、柔和手绘质感和原图可读性。`;
}

function buildWorkflow(canvas, sourceGroup, refs){
  const existing = new Set((canvas.nodes || []).map(n => n.id));
  const by = nodeMap(canvas);
  const lanes = [];
  const variants = [
    {id:'afternoon', label:'下午差分'},
    {id:'night', label:'晚上差分'},
  ];
  const startX = sourceGroup.x + sourceGroup.w + 420;
  const startY = sourceGroup.y;
  const rowH = 520;
  refs.forEach((ref, refIndex) => {
    variants.forEach((variant, variantIndex) => {
      const laneIndex = refIndex * variants.length + variantIndex;
      const x = startX;
      const y = startY + laneIndex * rowH;
      const groupId = uid('grp');
      const imgId = uid('img');
      const promptId = uid('prompt');
      const genId = uid('gen');
      const outId = uid('out');
      if(existing.has(groupId) || existing.has(imgId) || existing.has(promptId) || existing.has(genId) || existing.has(outId)){
        throw new Error('ID collision');
      }
      const refLabel = `源图${refIndex + 1} ${ref.name || ''}`.trim();
      const prompt = buildPrompt(refLabel, variant.id);
      canvas.nodes.push(
        {id: groupId, type:'group', x, y, w:900, h:430, items:[imgId, promptId], name:`${refLabel}｜${variant.label} 输入`},
        {id: imgId, type:'image', x:x+36, y:y+88, url:ref.url, name:ref.name || `source-${refIndex + 1}.png`},
        {id: promptId, type:'prompt', x:x+338, y:y+88, w:500, h:260, text:prompt, name:`${variant.label} 提示词`},
        {id: genId, type:'generator', x:x+950, y:y+92, apiProvider:'custom-api-2', model:'gpt-image-2', ratio:'landscape43', resolution:'1k', quality:'auto', customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'', customWidth:'', customHeight:'', inputs:[`${groupId}:${imgId}`, `${groupId}:prompts`], count:TARGET_PER_DIFF, forceFill:true, apiDefaultsVersion:2, name:`${refLabel}｜${variant.label}｜补满${TARGET_PER_DIFF}`},
        {id: outId, type:'output', x:x+1335, y:y+18, w:760, h:660, images:[], _pending:[], name:`${refLabel}｜${variant.label} 输出`}
      );
      canvas.connections.push(
        {id:uid('c'), from:groupId, to:genId},
        {id:uid('c'), from:genId, to:outId}
      );
      lanes.push({
        key:`src${refIndex + 1}-${variant.id}`,
        ref,
        refLabel,
        variant: variant.id,
        label: `${refLabel}｜${variant.label}`,
        groupId,
        genId,
        outId,
        prompt,
        accepted: 0,
        submitted: 0,
        failed: 0,
        timedOut: 0,
        active: new Map(),
      });
    });
  });
  canvas.viewport = {x:startX - 220, y:startY - 120, scale:0.72};
  return lanes;
}

function writeProgress(progress){
  fs.mkdirSync(path.dirname(PROGRESS_PATH), {recursive:true});
  fs.writeFileSync(PROGRESS_PATH, JSON.stringify(progress, null, 2), 'utf8');
}

async function createTaskForLane(canvas, lane, provider, progress){
  provider.active++;
  provider.uses++;
  lane.submitted++;
  const run = {
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
      scheduler:'codex-three-bg-diff-pool',
      lane:lane.key,
      batch_id:BATCH_ID,
    },
  };
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
    out._pending.push(pendingCard(pendingId, run, taskId, '1344x1008'));
    lane.active.set(pendingId, {pendingId, taskId, provider, run, start});
    progress.submitted++;
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
    progress.failed++;
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
    progress.failed++;
    progress.timeouts++;
    progress.lanes[lane.key].failed = lane.failed;
    progress.lanes[lane.key].timedOut = lane.timedOut;
    progress.tasks[item.pendingId].status = 'timeout';
    progress.tasks[item.pendingId].error = message;
    return true;
  }
  const task = await httpJson('GET', `/api/canvas-image-tasks/${encodeURIComponent(item.taskId)}`, null, 30000);
  progress.tasks[item.pendingId].status = task.status;
  progress.tasks[item.pendingId].queue_ms = task.queue_ms || 0;
  progress.tasks[item.pendingId].run_ms = task.run_ms || 0;
  progress.tasks[item.pendingId].total_ms = task.total_ms || 0;
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
      progress.succeeded++;
      progress.appended++;
      progress.tasks[item.pendingId].status = 'succeeded';
      progress.tasks[item.pendingId].image = images[0];
    } else {
      const message = '任务成功但没有返回图片';
      appendOutput(canvas, lane, errorOutput(message, item.run, runMs), runMs, message);
      lane.failed++;
      progress.failed++;
      progress.tasks[item.pendingId].status = 'failed-empty';
      progress.tasks[item.pendingId].error = message;
    }
  } else {
    const message = task.error || '生成失败';
    item.provider.failures++;
    lane.failed++;
    appendOutput(canvas, lane, errorOutput(message, item.run, runMs), runMs, message);
    progress.failed++;
    progress.tasks[item.pendingId].status = task.status || 'failed';
    progress.tasks[item.pendingId].error = message;
  }
  progress.lanes[lane.key].accepted = lane.accepted;
  progress.lanes[lane.key].failed = lane.failed;
  return true;
}

async function main(){
  let canvas = await loadCanvas();
  const by = nodeMap(canvas);
  const sourceGroup = by.get(SOURCE_GROUP_ID);
  if(!sourceGroup) throw new Error(`source group not found: ${SOURCE_GROUP_ID}`);
  const refs = (sourceGroup.items || []).map(id => by.get(id)).filter(n => n?.type === 'image').map(n => ({id:n.id, name:n.name || n.id, url:n.url}));
  if(refs.length !== 3) throw new Error(`expected 3 source images, got ${refs.length}`);
  const providers = await providerPool();
  if(!providers.length) throw new Error('no usable providers');
  const lanes = buildWorkflow(canvas, sourceGroup, refs);
  let progress = {
    batch_id:BATCH_ID,
    canvas_id:CANVAS_ID,
    source_group_id:SOURCE_GROUP_ID,
    started_at:nowMs(),
    target_total:lanes.length * TARGET_PER_DIFF,
    submitted:0,
    succeeded:0,
    failed:0,
    timeouts:0,
    appended:0,
    providers:providers.map(p => ({id:p.id, name:p.name, model:p.model})),
    lanes:Object.fromEntries(lanes.map(lane => [lane.key, {label:lane.label, target:TARGET_PER_DIFF, accepted:0, submitted:0, failed:0, timedOut:0, output_id:lane.outId, generator_id:lane.genId}])),
    tasks:{},
    progress_path:PROGRESS_PATH,
  };
  writeProgress(progress);
  canvas = await saveCanvas(canvas, `${BATCH_ID}-workflows`);
  let lastSave = nowMs();
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
    if(nowMs() - lastSave > 1200){
      canvas = await saveCanvas(canvas, `${BATCH_ID}-pending`);
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
      progress.failed++;
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
    canvas = await saveCanvas(canvas, `${BATCH_ID}-tick`);
    lastSave = nowMs();
    await sleep(1800);
  }
  for(const lane of lanes){
    const out = nodeMap(canvas).get(lane.outId);
    if(out) out._pending = [];
  }
  progress.finished_at = nowMs();
  progress.providers = providers.map(p => ({id:p.id, name:p.name, model:p.model, uses:p.uses, failures:p.failures}));
  writeProgress(progress);
  canvas = await saveCanvas(canvas, `${BATCH_ID}-finished`);
  console.log(JSON.stringify({
    batch_id:BATCH_ID,
    canvas_id:CANVAS_ID,
    target_total:progress.target_total,
    submitted:progress.submitted,
    succeeded:progress.succeeded,
    failed:progress.failed,
    timeouts:progress.timeouts,
    appended:progress.appended,
    progress_path:PROGRESS_PATH,
    lanes:progress.lanes,
  }, null, 2));
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});

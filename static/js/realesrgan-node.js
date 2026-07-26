(function(root, factory){
  const api = factory();
  if(typeof module === 'object' && module.exports) module.exports = api;
  else root.RealESRGANCanvas = api;
})(typeof self !== 'undefined' ? self : this, function(){
  'use strict';

  const DEFAULT_MODEL = 'RealESRGAN_x4plus_anime_6B';
  const WAIFU2X_MODEL = 'Waifu2x_CUNet';
  const DEFAULT_SCALE = 4;
  const IMAGE_SOURCE_TYPES = [
    'image', 'group', 'output',
    'generator', 'msgen', 'comfy', 'ltxDirector', 'rh', 'realesrgan'
  ];

  function finiteNumber(value, fallback){
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function normalizeScale(value){
    const scale = Number(value);
    return scale === 2 || scale === 4 ? scale : DEFAULT_SCALE;
  }

  function normalizeModel(value, models){
    const ids = (Array.isArray(models) ? models : [])
      .map(function(item){ return item && typeof item.id === 'string' ? item.id : ''; })
      .filter(Boolean);
    if(ids.indexOf(value) >= 0) return value;
    return ids[0] || DEFAULT_MODEL;
  }

  function createDefaultNode(options){
    const source = options || {};
    return {
      id: source.id,
      type: 'realesrgan',
      x: finiteNumber(source.x, 0),
      y: finiteNumber(source.y, 0),
      w: 360,
      h: 390,
      model: DEFAULT_MODEL,
      scale: DEFAULT_SCALE,
      device: 'auto',
      inputs: [],
      generatedOutputs: [],
      lastResult: null,
      runStatus: '',
      runError: ''
    };
  }

  function normalizeNode(node, models){
    const source = node && typeof node === 'object' ? node : {};
    const result = Object.assign(createDefaultNode(source), source);
    result.type = 'realesrgan';
    result.x = finiteNumber(result.x, 0);
    result.y = finiteNumber(result.y, 0);
    result.w = 360;
    result.h = 390;
    result.model = normalizeModel(result.model, models);
    result.scale = normalizeScale(result.scale);
    result.device = 'auto';
    result.inputs = Array.isArray(result.inputs) ? result.inputs : [];
    result.generatedOutputs = Array.isArray(result.generatedOutputs) ? result.generatedOutputs : [];
    result.lastResult = normalizeResultSummary(result.lastResult);
    result.runStatus = '';
    result.runError = '';
    return result;
  }

  function isMenuSourceType(type){
    return IMAGE_SOURCE_TYPES.indexOf(type) >= 0;
  }

  function firstImageRef(sources){
    for(const source of Array.isArray(sources) ? sources : []){
      const refs = source && Array.isArray(source.refs) ? source.refs : [];
      for(const ref of refs){
        if(ref && ref.url && (!ref.kind || ref.kind === 'image')) return ref;
      }
    }
    return null;
  }

  function buildRequest(node, ref){
    if(!ref || !ref.url) throw new Error('请先连接一张图片');
    return {
      source_url: String(ref.url),
      model: node && typeof node.model === 'string' && node.model ? node.model : DEFAULT_MODEL,
      scale: normalizeScale(node && node.scale)
    };
  }

  function normalizeStatus(payload){
    const source = payload && typeof payload === 'object' ? payload : {};
    const models = (Array.isArray(source.models) ? source.models : [])
      .filter(function(item){ return item && typeof item.id === 'string' && item.id; })
      .map(function(item){
        return {
          id: item.id,
          name: typeof item.name === 'string' ? item.name : item.id,
          native_scale: Number(item.native_scale) || 4
        };
      });
    return {
      ok: Boolean(source.ok),
      python: Boolean(source.python),
      cuda: Boolean(source.cuda),
      device: String(source.device || ''),
      models: models,
      message: String(source.message || '')
    };
  }

  function deviceLabel(status){
    const value = normalizeStatus(status);
    if(!value.ok) return value.message || 'RealESRGAN 运行环境不可用';
    return value.cuda ? 'CUDA · ' + (value.device || 'GPU') : 'CPU · 较慢';
  }

  function deviceLabelForModel(status, model){
    if(model === WAIFU2X_MODEL) return 'Vulkan · GPU 0';
    return deviceLabel(status);
  }

  function positiveNumber(value){
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : 0;
  }

  function normalizeResultSummary(payload){
    const source = payload && typeof payload === 'object' ? payload : {};
    const width = positiveNumber(source.width);
    const height = positiveNumber(source.height);
    const sourceWidth = positiveNumber(source.source_width);
    const sourceHeight = positiveNumber(source.source_height);
    if(!source.url || !width || !height || !sourceWidth || !sourceHeight) return null;
    return {
      url: String(source.url),
      kind: 'image',
      model: typeof source.model === 'string' && source.model ? source.model : DEFAULT_MODEL,
      scale: normalizeScale(source.scale),
      source_width: sourceWidth,
      source_height: sourceHeight,
      width: width,
      height: height,
      device: String(source.device || ''),
      run_ms: Math.max(0, finiteNumber(source.run_ms, 0)),
      completed_at: Math.max(0, finiteNumber(source.completed_at, 0))
    };
  }

  function resultMeta(payload){
    const source = payload && typeof payload === 'object' ? payload : {};
    const width = positiveNumber(source.width);
    const height = positiveNumber(source.height);
    const sourceWidth = positiveNumber(source.source_width);
    const sourceHeight = positiveNumber(source.source_height);
    if(!source.ok || !source.url || !width || !height || !sourceWidth || !sourceHeight){
      throw new Error('RealESRGAN 未生成输出图片');
    }
    const result = normalizeResultSummary(source);
    delete result.completed_at;
    return result;
  }

  return {
    DEFAULT_MODEL: DEFAULT_MODEL,
    WAIFU2X_MODEL: WAIFU2X_MODEL,
    DEFAULT_SCALE: DEFAULT_SCALE,
    normalizeScale: normalizeScale,
    normalizeModel: normalizeModel,
    createDefaultNode: createDefaultNode,
    normalizeNode: normalizeNode,
    isMenuSourceType: isMenuSourceType,
    firstImageRef: firstImageRef,
    buildRequest: buildRequest,
    normalizeStatus: normalizeStatus,
    deviceLabel: deviceLabel,
    deviceLabelForModel: deviceLabelForModel,
    normalizeResultSummary: normalizeResultSummary,
    resultMeta: resultMeta
  };
});

(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.AutoDLVideo = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DEFAULT_WORKFLOW = 'minimax_h3_lightx2v_v5';
  const LIP_SYNC_RE = /对口型|口型|嘴型|说话|讲话|念台词|配音|唱歌|演唱|lip\s*sync|lipsync|speaking|talking|singing/i;

  function list(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

  function metadataMap(workflows) {
    const map = new Map();
    list(workflows).forEach((workflow) => {
      const id = String(workflow && workflow.workflow_id || '').trim();
      if (id) map.set(id, workflow);
    });
    return map;
  }

  function resultFor(workflow, reason, error) {
    return {
      workflowId: workflow ? workflow.workflow_id : '',
      name: workflow ? workflow.name : '',
      reason: reason || '',
      error: error || '',
      maxDuration: workflow ? Number(workflow.max_duration || 15) : 15,
      maxResolution: workflow ? String(workflow.max_resolution || '768p') : '768p',
      supportsSquare: !!(workflow && workflow.supports_square),
    };
  }

  function validateSelection(workflowId, input, workflows, reason) {
    const map = metadataMap(workflows);
    const workflow = map.get(String(workflowId || '').trim());
    if (!workflow) return resultFor(null, reason, '未知的 AutoDL H3 工作流');
    const images = list(input && input.images);
    const audios = list(input && input.audios);
    const duration = Number(input && input.duration);
    if (!Number.isInteger(duration) || duration < 1 || duration > 15) {
      return resultFor(workflow, reason, 'AutoDL H3 视频时长必须为 1–15 秒');
    }
    if (duration < Number(workflow.min_duration || 1) || duration > Number(workflow.max_duration || 15)) {
      return resultFor(workflow, reason, `${workflow.name} 仅支持 ${workflow.min_duration}–${workflow.max_duration} 秒`);
    }
    const minImages = Number(workflow.min_images || 0);
    const maxImages = Number(workflow.max_images || 0);
    if (images.length < minImages || images.length > maxImages) {
      const range = minImages === maxImages ? `${minImages} 张图片` : `${minImages}–${maxImages} 张图片`;
      return resultFor(workflow, reason, `${workflow.name} 需要${minImages === maxImages ? '正好 ' : ''}${range}`);
    }
    const minAudios = Number(workflow.min_audios || 0);
    const maxAudios = Number(workflow.max_audios || 0);
    if (audios.length < minAudios || audios.length > maxAudios) {
      const range = minAudios === maxAudios ? `${minAudios} 段音频` : `${minAudios}–${maxAudios} 段音频`;
      return resultFor(workflow, reason, `${workflow.name} 需要${minAudios === maxAudios ? '正好 ' : ''}${range}`);
    }
    if (workflow.supports_prompt !== false && !String(input && input.prompt || '').trim()) {
      return resultFor(workflow, reason, `${workflow.name} 需要提示词`);
    }
    return resultFor(workflow, reason, '');
  }

  function resolveWorkflow(input, workflows) {
    const request = input || {};
    const map = metadataMap(workflows);
    const images = list(request.images);
    const audios = list(request.audios);
    const videos = list(request.videos);
    const prompt = String(request.prompt || '');
    const duration = Number(request.duration);
    const fallback = map.get(DEFAULT_WORKFLOW) || list(workflows)[0] || null;

    if (videos.length) return resultFor(fallback, '', 'AutoDL H3 工作流不支持参考视频，请先截取图片帧');
    if (images.length > 9 || audios.length > 3) {
      return resultFor(fallback, '', 'AutoDL H3 最多支持 9 张图片和 3 段音频');
    }
    if (!Number.isInteger(duration) || duration < 1 || duration > 15) {
      return resultFor(fallback, '', 'AutoDL H3 视频时长必须为 1–15 秒');
    }
    if (request.mode === 'manual') {
      if (!request.workflowId) return resultFor(null, '', '手动模式必须选择 AutoDL H3 工作流');
      if (request.firstLast && request.workflowId !== 'minimax_h3_lightx2v') {
        return resultFor(map.get(request.workflowId), '', '已开启首尾帧时必须选择 H3 首尾帧视频工作流');
      }
      return validateSelection(request.workflowId, request, workflows, '用户手动选择工作流');
    }
    if (!prompt.trim() && images.length === 0 && audios.length === 0) {
      return resultFor(fallback, '空节点默认显示 H3 多图参考生视频', '');
    }

    let workflowId = '';
    let reason = '';
    if (images.length === 1 && audios.length === 1 && LIP_SYNC_RE.test(prompt)) {
      workflowId = 'minimax_h3_image_audio_to_video';
      reason = '单图单音频，提示词包含说话、唱歌或对口型意图';
    } else if (audios.length) {
      workflowId = duration <= 10
        ? 'minimax_h3_image_audio_to_video_v2'
        : 'minimax_h3_image_audio_to_video_v2_15s';
      reason = `连接了 ${images.length} 张图片、${audios.length} 段音频，时长 ${duration} 秒`;
    } else if (request.firstLast) {
      if (images.length !== 2) return resultFor(map.get('minimax_h3_lightx2v'), '', '首尾帧工作流必须正好连接 2 张图片');
      workflowId = 'minimax_h3_lightx2v';
      reason = '已开启首尾帧并连接 2 张图片';
    } else if (images.length) {
      workflowId = duration <= 10 ? DEFAULT_WORKFLOW : 'minimax_h3_lightx2v_v5_15s';
      reason = `连接了 ${images.length} 张图片，时长 ${duration} 秒，无音频`;
    } else {
      workflowId = 'minimax_h3_lightx2v_no_pic';
      reason = '只有提示词，没有参考图片或音频';
    }
    return validateSelection(workflowId, request, workflows, reason);
  }

  function explainResolutionAdjustment(requested, actual, workflow) {
    if (!workflow || String(requested) === String(actual)) return '';
    return `${workflow.name}最高支持 ${actual}，已从 ${requested} 调整为 ${actual}`;
  }

  function resolutionValue(resolution, aspectRatio, workflow) {
    const requested = String(resolution || '768p').replace(/(横|竖|1:1)$/, '');
    const maxResolution = String(workflow && workflow.max_resolution || '768p');
    const rank = { '480p': 1, '768p': 2, '1080p': 3 };
    const actual = (rank[requested] || 2) > (rank[maxResolution] || 2) ? maxResolution : requested;
    const ratio = String(aspectRatio || '16:9');
    if (ratio === '1:1' && !(workflow && workflow.supports_square)) {
      return { value: '', adjusted: false, reason: '', error: `${workflow && workflow.name || '当前工作流'}不支持 1:1 比例` };
    }
    const suffix = ratio === '1:1' ? '1:1' : ['9:16', '3:4', '2:3'].includes(ratio) ? '竖' : '横';
    const adjusted = actual !== requested;
    return {
      value: `${actual}${suffix}`,
      adjusted,
      reason: adjusted ? explainResolutionAdjustment(requested, actual, workflow) : '',
      error: '',
    };
  }

  function workflowOptions(workflows) {
    return list(workflows).map((workflow) => ({
      value: workflow.workflow_id,
      label: workflow.name
        ? `${workflow.name} · ${workflow.workflow_id}`
        : workflow.workflow_id,
      workflow,
    }));
  }

  return {
    DEFAULT_WORKFLOW,
    LIP_SYNC_RE,
    resolveWorkflow,
    validateSelection,
    resolutionValue,
    workflowOptions,
    explainResolutionAdjustment,
  };
});

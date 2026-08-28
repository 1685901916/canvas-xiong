const assert = require('assert');
const AutoDLVideo = require('../static/js/autodl-video.js');

const workflows = [
  { workflow_id: 'minimax_h3_lightx2v_v5', name: 'H3 多图参考生视频', min_duration: 1, max_duration: 10, min_images: 1, max_images: 9, min_audios: 0, max_audios: 0, supports_square: true, max_resolution: '1080p' },
  { workflow_id: 'minimax_h3_lightx2v_v5_15s', name: 'H3 多图生视频 15 秒', min_duration: 1, max_duration: 15, min_images: 1, max_images: 9, min_audios: 0, max_audios: 0, supports_square: true, max_resolution: '768p' },
  { workflow_id: 'minimax_h3_lightx2v_no_pic', name: 'H3 文生视频', min_duration: 1, max_duration: 15, min_images: 0, max_images: 0, min_audios: 0, max_audios: 0, supports_square: false, max_resolution: '768p' },
  { workflow_id: 'minimax_h3_lightx2v', name: 'H3 首尾帧视频', min_duration: 1, max_duration: 15, min_images: 2, max_images: 2, min_audios: 0, max_audios: 0, supports_square: false, max_resolution: '768p' },
  { workflow_id: 'minimax_h3_image_audio_to_video_v2', name: 'H3 多图多音频生视频', min_duration: 1, max_duration: 10, min_images: 0, max_images: 9, min_audios: 0, max_audios: 3, supports_square: false, max_resolution: '1080p' },
  { workflow_id: 'minimax_h3_image_audio_to_video_v2_15s', name: 'H3 多图多音频生视频 15 秒', min_duration: 1, max_duration: 15, min_images: 0, max_images: 9, min_audios: 0, max_audios: 3, supports_square: false, max_resolution: '768p' },
  { workflow_id: 'minimax_h3_image_audio_to_video', name: 'H3 自动对口型', min_duration: 1, max_duration: 15, min_images: 1, max_images: 1, min_audios: 1, max_audios: 1, supports_square: false, max_resolution: '1080p' },
];

function resolve(changes = {}) {
  return AutoDLVideo.resolveWorkflow({
    prompt: 'move',
    duration: 8,
    images: [],
    audios: [],
    videos: [],
    firstLast: false,
    mode: 'auto',
    workflowId: '',
    ...changes,
  }, workflows);
}

assert.equal(
  resolve({ prompt: '', images: [] }).workflowId,
  'minimax_h3_lightx2v_v5',
  'empty nodes should preview the requested default workflow',
);
assert.equal(resolve({ images: [] }).workflowId, 'minimax_h3_lightx2v_no_pic');
assert.equal(resolve({ images: ['a'], duration: 10 }).workflowId, 'minimax_h3_lightx2v_v5');
assert.equal(resolve({ images: ['a'], duration: 11 }).workflowId, 'minimax_h3_lightx2v_v5_15s');
assert.equal(resolve({ images: ['a'], audios: ['b'] }).workflowId, 'minimax_h3_image_audio_to_video_v2');
assert.equal(
  resolve({ prompt: '角色唱歌并对口型', images: ['a'], audios: ['b'] }).workflowId,
  'minimax_h3_image_audio_to_video',
);
assert.equal(
  resolve({ prompt: 'talking portrait', images: ['a'], audios: ['b'] }).workflowId,
  'minimax_h3_image_audio_to_video',
);
assert.equal(
  resolve({ images: ['first', 'last'], firstLast: true }).workflowId,
  'minimax_h3_lightx2v',
);
assert.match(resolve({ videos: ['video.mp4'] }).error, /不支持参考视频/);

const manualInvalid = resolve({
  mode: 'manual',
  workflowId: 'minimax_h3_lightx2v',
  images: ['only-one'],
});
assert.match(manualInvalid.error, /2 张图片/);
const manualValid = resolve({
  mode: 'manual',
  workflowId: 'minimax_h3_lightx2v',
  images: ['first', 'last'],
});
assert.equal(manualValid.error, '');

const shortWorkflow = workflows[0];
assert.deepEqual(
  AutoDLVideo.resolutionValue('1080p', '9:16', shortWorkflow),
  { value: '1080p竖', adjusted: false, reason: '', error: '' },
);
const longWorkflow = workflows[1];
assert.deepEqual(
  AutoDLVideo.resolutionValue('1080p', '16:9', longWorkflow),
  {
    value: '768p横',
    adjusted: true,
    reason: 'H3 多图生视频 15 秒最高支持 768p，已从 1080p 调整为 768p',
    error: '',
  },
);
assert.match(
  AutoDLVideo.resolutionValue('768p', '1:1', workflows[2]).error,
  /不支持 1:1/,
);
const workflowOptions = AutoDLVideo.workflowOptions(workflows);
assert.equal(workflowOptions.length, 7);
assert.equal(
  workflowOptions[0].label,
  'H3 多图参考生视频 · minimax_h3_lightx2v_v5',
  'model choices should show both the friendly name and the real workflow id',
);
assert.match(
  AutoDLVideo.explainResolutionAdjustment('1080p', '768p', longWorkflow),
  /最高支持 768p/,
);

console.log('autodl-video tests passed');

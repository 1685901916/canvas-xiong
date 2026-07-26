const assert = require('assert');
const real = require('../static/js/realesrgan-node.js');

{
  const node = real.createDefaultNode({ id: 'realesr_1', x: 10, y: 20 });
  assert.strictEqual(node.id, 'realesr_1');
  assert.strictEqual(node.type, 'realesrgan');
  assert.strictEqual(node.x, 10);
  assert.strictEqual(node.y, 20);
  assert.strictEqual(node.w, 360);
  assert.strictEqual(node.h, 390);
  assert.strictEqual(node.model, 'RealESRGAN_x4plus_anime_6B');
  assert.strictEqual(node.scale, 4);
  assert.strictEqual(node.device, 'auto');
  assert.deepStrictEqual(node.inputs, []);
  assert.deepStrictEqual(node.generatedOutputs, []);
  assert.strictEqual(node.lastResult, null);
  assert.strictEqual(node.runStatus, '');
  assert.strictEqual(node.runError, '');
}

{
  assert.strictEqual(real.normalizeScale('2'), 2);
  assert.strictEqual(real.normalizeScale(4), 4);
  assert.strictEqual(real.normalizeScale(3), 4);
  assert.strictEqual(real.normalizeScale(null), 4);
}

{
  const models = [
    { id: 'local-a', name: 'Local A' },
    { id: 'local-b', name: 'Local B' },
  ];
  assert.strictEqual(real.normalizeModel('local-b', models), 'local-b');
  assert.strictEqual(real.normalizeModel('missing', models), 'local-a');
  assert.strictEqual(real.normalizeModel('', []), 'RealESRGAN_x4plus_anime_6B');
}

{
  const restored = real.normalizeNode({
    id: 'realesr_old',
    type: 'wrong',
    x: '12',
    y: 'bad',
    w: 999,
    h: 1,
    model: 'missing',
    scale: 3,
    device: 'cuda',
    inputs: 'bad',
    generatedOutputs: null,
    runStatus: 'running',
    runError: 'stale',
    lastResult: { url: '/bad.png', width: 0 },
  }, [{ id: 'RealESRGAN_x4plus_anime_6B' }]);
  assert.strictEqual(restored.type, 'realesrgan');
  assert.strictEqual(restored.x, 12);
  assert.strictEqual(restored.y, 0);
  assert.strictEqual(restored.w, 360);
  assert.strictEqual(restored.h, 390);
  assert.strictEqual(restored.model, 'RealESRGAN_x4plus_anime_6B');
  assert.strictEqual(restored.scale, 4);
  assert.strictEqual(restored.device, 'auto');
  assert.deepStrictEqual(restored.inputs, []);
  assert.deepStrictEqual(restored.generatedOutputs, []);
  assert.strictEqual(restored.lastResult, null);
  assert.strictEqual(restored.runStatus, '');
  assert.strictEqual(restored.runError, '');
}

{
  const summary = real.normalizeResultSummary({
    url: '/assets/output/realesrgan_saved.png',
    model: 'RealESRGAN_x4plus_anime_6B',
    scale: 4,
    source_width: 1402,
    source_height: 1122,
    width: 5608,
    height: 4488,
    device: 'cuda:0',
    run_ms: 18545,
    completed_at: 123456,
  });
  assert.strictEqual(summary.url, '/assets/output/realesrgan_saved.png');
  assert.strictEqual(summary.width, 5608);
  assert.strictEqual(summary.height, 4488);
  assert.strictEqual(summary.run_ms, 18545);
  assert.strictEqual(summary.completed_at, 123456);
  assert.strictEqual(real.normalizeResultSummary({ url: '/bad.png', width: 0 }), null);
}

{
  const ref = real.firstImageRef([
    { refs: [{ url: '/a.mp4', kind: 'video' }] },
    { refs: [{ url: '/a.png', kind: 'image' }, { url: '/b.png', kind: 'image' }] },
  ]);
  assert.deepStrictEqual(ref, { url: '/a.png', kind: 'image' });
  assert.strictEqual(real.firstImageRef([{ refs: [{ url: '', kind: 'image' }] }]), null);
}

{
  assert.strictEqual(real.isMenuSourceType('image'), true);
  assert.strictEqual(real.isMenuSourceType('group'), true);
  assert.strictEqual(real.isMenuSourceType('output'), true);
  assert.strictEqual(real.isMenuSourceType('generator'), true);
  assert.strictEqual(real.isMenuSourceType('realesrgan'), true);
  assert.strictEqual(real.isMenuSourceType('prompt'), false);
  assert.strictEqual(real.isMenuSourceType('loop'), false);
  assert.strictEqual(real.isMenuSourceType('promptGroup'), false);
  assert.strictEqual(real.isMenuSourceType('llm'), false);
  assert.strictEqual(real.isMenuSourceType('video'), false);
}

{
  assert.deepStrictEqual(real.buildRequest(
    { model: 'RealESRGAN_x4plus_anime_6B', scale: 4 },
    { url: '/assets/input/a.png' },
  ), {
    source_url: '/assets/input/a.png',
    model: 'RealESRGAN_x4plus_anime_6B',
    scale: 4,
  });
  assert.throws(() => real.buildRequest({}, null), /请先连接一张图片/);
}

{
  const status = real.normalizeStatus({
    ok: 1,
    cuda: 1,
    device: 'NVIDIA GPU',
    models: [{ id: 'RealESRGAN_x4plus_anime_6B' }, null, { name: 'bad' }],
    message: null,
    secret: 'discard me',
  });
  assert.deepStrictEqual(status, {
    ok: true,
    python: false,
    cuda: true,
    device: 'NVIDIA GPU',
    models: [{
      id: 'RealESRGAN_x4plus_anime_6B',
      name: 'RealESRGAN_x4plus_anime_6B',
      native_scale: 4,
    }],
    message: '',
  });
  assert.strictEqual(real.deviceLabel(status), 'CUDA · NVIDIA GPU');
  assert.strictEqual(real.deviceLabel({ ok: true, cuda: false }), 'CPU · 较慢');
  assert.strictEqual(real.deviceLabel({ ok: false, message: '模型缺失' }), '模型缺失');
  assert.strictEqual(real.deviceLabel({ ok: false }), 'RealESRGAN 运行环境不可用');
  assert.strictEqual(real.deviceLabelForModel(status, 'Waifu2x_CUNet'), 'Vulkan · GPU 0');
}

{
  assert.deepStrictEqual(real.buildRequest(
    { model: 'Waifu2x_CUNet', scale: 2 },
    { url: '/assets/input/anime.png' },
  ), {
    source_url: '/assets/input/anime.png',
    model: 'Waifu2x_CUNet',
    scale: 2,
  });
}

{
  const meta = real.resultMeta({
    ok: true,
    url: '/assets/output/realesrgan_abc.png',
    model: 'RealESRGAN_x4plus_anime_6B',
    scale: '4',
    source_width: '202',
    source_height: 360,
    width: '808',
    height: 1440,
    device: 'cuda',
    run_ms: '1234',
  });
  assert.deepStrictEqual(meta, {
    url: '/assets/output/realesrgan_abc.png',
    kind: 'image',
    model: 'RealESRGAN_x4plus_anime_6B',
    scale: 4,
    source_width: 202,
    source_height: 360,
    width: 808,
    height: 1440,
    device: 'cuda',
    run_ms: 1234,
  });
  assert.throws(() => real.resultMeta({ ok: false }), /RealESRGAN 未生成输出图片/);
  assert.throws(() => real.resultMeta({ ok: true, url: '/x.png', width: 0, height: 10 }), /RealESRGAN 未生成输出图片/);
}

console.log('realesrgan-node tests passed');

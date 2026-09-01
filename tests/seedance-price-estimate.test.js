const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'canvas.css'), 'utf8');

// 取出计费模块单独求值，避免把整个 canvas.js（依赖 document）拉进来
const start = canvas.indexOf('const ARK_SEEDANCE_TOKENS_PER_SEC');
const endMarker = 'function renderVideoBody(node){';
assert.ok(start > 0, '找不到 Seedance 计费模块');
const block = canvas.slice(start, canvas.indexOf(endMarker));
const { estimate, costText, variant } = new Function(
  `${block}; return { estimate: arkSeedanceEstimate, costText: arkSeedanceCostText, variant: arkSeedanceVariant };`
)();

const M2_0 = 'doubao-seedance-2-0-260128';
const M_FAST = 'doubao-seedance-2-0-fast-260128';
const M_MINI = 'doubao-seedance-2-0-mini-260615';
const M2_5 = 'doubao-seedance-2-5-260628';

// —— 型号识别：注意 seedance-2-0 是 fast/mini 的子串，顺序错了这里就会挂 ——
assert.strictEqual(variant(M2_0), '2-0');
assert.strictEqual(variant(M_FAST), '2-0-fast');
assert.strictEqual(variant(M_MINI), '2-0-mini');
assert.strictEqual(variant(M2_5), '2-5');
assert.strictEqual(variant('veo3-fast'), '');
assert.strictEqual(variant('doubao_seedance.2.0.fast-260128'), '2-0-fast', '分隔符归一化');

// —— 逐条对齐方舟官网「价格示例」的 视频费用 列（不含视频输入，输出 5s）——
const officialNoVideoIn = [
  [M2_0,  '480p',  5,  2.31],
  [M2_0,  '720p',  5,  4.97],
  [M2_0,  '1080p', 5, 12.39],
  [M2_0,  '4k',    5, 25.27],
  [M_FAST,'480p',  5,  1.86],
  [M_FAST,'720p',  5,  4.00],
  [M_MINI,'480p',  5,  1.16],
  [M_MINI,'720p',  5,  2.48],
  [M2_5,  '480p',  5,  3.36],
  [M2_5,  '720p',  5,  7.56],
  [M2_5,  '1080p', 5, 18.71],
];
for (const [model, res, secs, expected] of officialNoVideoIn) {
  const got = estimate(model, secs, res, false).yuan;
  assert.ok(Math.abs(got - expected) < 0.01,
    `${model} ${res} ${secs}s 应为 ¥${expected}，实得 ¥${got.toFixed(2)}`);
}

// —— 含视频输入：官网示例是 输入10s + 输出10s，即计费 20s ——
const officialWithVideoIn = [
  [M2_0,  '480p',   5.62],
  [M2_0,  '720p',  12.10],
  [M2_0,  '1080p', 30.13],
  [M2_0,  '4k',    62.21],
  [M_FAST,'480p',   4.42],
  [M_FAST,'720p',   9.50],
  [M2_5,  '480p',   8.07],
  [M2_5,  '720p',  18.14],
  [M2_5,  '1080p', 44.71],
];
for (const [model, res, expected] of officialWithVideoIn) {
  const got = estimate(model, 20, res, true).yuan;
  assert.ok(Math.abs(got - expected) < 0.02,
    `${model} ${res} 输入10s+输出10s 应为 ¥${expected}，实得 ¥${got.toFixed(2)}`);
}

// —— 有视频参考时反而更贵：720P 纯生成 1.0 元/秒 vs V2V 等长输入 1.21 元/秒 ——
const pure10 = estimate(M2_0, 10, '720p', false).yuan;
const v2v10in10out = estimate(M2_0, 20, '720p', true).yuan;
assert.ok(v2v10in10out > pure10, '等长参考的 V2V 必须比纯生成贵');

// —— fast / mini 不支持 1080p / 4k ——
for (const model of [M_FAST, M_MINI]) {
  assert.strictEqual(estimate(model, 5, '1080p', false).unsupported, true);
  assert.strictEqual(estimate(model, 5, '4k', false).unsupported, true);
}
// 2.5 没有 4K
assert.strictEqual(estimate(M2_5, 5, '4k', false).unsupported, true);

// —— 非 Seedance 型号不显示价格 ——
assert.strictEqual(estimate('veo3-fast', 5, '720p', false), null);
assert.strictEqual(costText('sora-2', 5, '720p', false), '');

// —— Auto 分辨率不瞎猜，提示用户先选 ——
assert.strictEqual(estimate(M2_0, 5, '', false).needResolution, true);
assert.match(costText(M2_0, 5, '', false), /选择分辨率/);

// —— 文案 ——
assert.match(costText(M2_0, 10, '720p', false), /约 ¥9\.94/);
assert.match(costText(M2_0, 10, '720p', false), /0\.99 元\/秒/);
assert.match(costText(M2_0, 10, '720p', true), /≥ ¥/);
assert.match(costText(M2_0, 10, '720p', true), /参考视频越长越贵/);
assert.match(costText(M_FAST, 5, '1080p', false), /自动降档/);

// —— UI 接线 ——
assert.match(canvas, /class="video-cost-hint" hidden/);
assert.match(canvas, /function refreshVideoCostHint\(\)/);
assert.match(canvas, /refreshVideoCostHint\(\); scheduleSave\(\);/, '改时长要联动');
assert.match(canvas, /else refreshVideoCostHint\(\);/, '改分辨率要联动');
assert.match(css, /\.video-cost-hint\s*\{/);

console.log('seedance-price-estimate: 全部通过');

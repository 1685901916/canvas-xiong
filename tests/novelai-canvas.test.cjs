const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/canvas.js'), 'utf8');
const sandbox = {window:{}, resolveImageModel: value => value};
vm.createContext(sandbox);
for(const name of ['SIZE_MAP','RES_LONG_SIDE','RES_PIXEL_LIMIT']){
    const pattern = name === 'SIZE_MAP' ? new RegExp(`const ${name} = \\{[\\s\\S]*?\\n\\};`) : new RegExp(`const ${name} = [^\\n]+`);
    vm.runInContext(source.match(pattern)[0], sandbox);
}
for(const name of ['parseRatioValue','apiImageSize','parseSizePair','isNovelAIImageModel','novelaiImageSize','isGptImageAutoSizeModel','defaultApiImageResolution','normalizeApiNodeSizeChoice','generatorForceFillEnabled']){
    vm.runInContext(source.match(new RegExp(`function ${name}\\([^]*?\\n\\}`))[0], sandbox);
}

test('every standard canvas ratio satisfies NovelAI size limits', () => {
    for(const ratio of ['square','portrait','portrait43','landscape','landscape43','story','wide','ultrawide','ultratall']){
        const [w,h] = sandbox.novelaiImageSize(ratio, '1k').split('x').map(Number);
        assert.equal(w % 64, 0, ratio);
        assert.equal(h % 64, 0, ratio);
        assert.ok(w*h <= 1048576, ratio);
    }
    assert.equal(sandbox.novelaiImageSize('square', '1k'), '1024x1024');
});

test('custom pixel sizes remain exact for backend validation', () => {
    assert.equal(sandbox.novelaiImageSize('square', 'custom', '', '1000x1000'), '1000x1000');
});

test('NovelAI suppresses cross-provider refill and resets unsupported standard size', () => {
    const node = {model:'nai-diffusion-5-full', resolution:'4k', forceFill:true};
    sandbox.normalizeApiNodeSizeChoice(node);
    assert.equal(node.resolution, '1k');
    assert.equal(sandbox.generatorForceFillEnabled(node), false);
    assert.equal(sandbox.generatorForceFillEnabled({model:'other', forceFill:true}), true);
    const other = {model:'other', resolution:'4k'};
    sandbox.normalizeApiNodeSizeChoice(other);
    assert.equal(other.resolution, '4k');
});

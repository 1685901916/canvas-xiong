const test = require('node:test');
const assert = require('node:assert/strict');
const pro = require('../static/js/seedream-pro.js');
const model = 'doubao-seedream-5-0-pro-260628';
test('automatic layers retain empty prompt and use auto size',()=>{
    const node={apiProvider:'volcengine',model,seedreamOptions:{layer_decomposition:true}};
    const request=pro.apply(node,{prompt:'Edit the reference images.',size:'4096x4096'},'');
    assert.equal(request.prompt,'');
    assert.equal(request.size,'auto');
    assert.equal(request.seedream_options.layer_decomposition,true);
});
test('special settings never leak into another provider',()=>{
    const request={prompt:'edit',size:'1024x1024'};
    pro.apply({apiProvider:'other',model,seedreamOptions:{layer_decomposition:true}},request,'');
    assert.deepEqual(request,{prompt:'edit',size:'1024x1024'});
});
test('custom dimensions and transparent PNG survive request construction',()=>{
    const node={apiProvider:'volcengine',model,seedreamSize:'custom',seedreamWidth:1920,seedreamHeight:1080,seedreamOptions:{background:'transparent',output_format:'png'}};
    const request=pro.apply(node,{},'keep transparency');
    assert.equal(request.size,'1920x1080');
    assert.equal(request.seedream_options.background,'transparent');
    assert.equal(request.seedream_options.output_format,'png');
});

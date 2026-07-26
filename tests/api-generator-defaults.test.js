const assert = require('assert');
const defaults = require('../static/js/api-generator-defaults.js');

const providers = [
  { id:'custom-api-7', name:'comfly', enabled:true, has_key:true, image_models:['gpt-image-2-all'] },
  { id:'custom-api-2', name:'65535', enabled:true, has_key:true, image_models:['gpt-image-2'] },
  { id:'custom-api-3', name:'Nano', enabled:true, has_key:true, image_models:['nano-banana-pro','gpt-image-2'] },
];

{
  const node = defaults.createDefaultNode({id:'gen_1', x:10, y:20, providers});
  assert.deepStrictEqual(node, {
    id:'gen_1', type:'generator', x:10, y:20,
    apiProvider:'custom-api-2', model:'gpt-image-2',
    ratio:'square', resolution:'2k', quality:'high',
    forceFill:false, count:1,
    customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'',
    customWidth:'', customHeight:'', inputs:[],
    apiDefaultsVersion:3, _apiRatioUserSet:false, _apiResolutionUserSet:true,
  });
}

{
  const primary = defaults.selectProvider([
    ...providers,
    {id:'preferred', name:'Preferred', enabled:true, primary:true, has_key:true, image_models:['gpt-image-2']},
  ]);
  assert.strictEqual(primary.id, 'preferred');
}

{
  const fallback = defaults.createDefaultNode({
    id:'gen_2', x:0, y:0,
    providers:[{id:'fallback', name:'Fallback', enabled:true, image_models:['other-model']}],
  });
  assert.strictEqual(fallback.apiProvider, 'fallback');
  assert.strictEqual(fallback.model, 'other-model');
}

{
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'square', _apiRatioUserSet:false}, true), true);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'story', _apiRatioUserSet:true}, true), false);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:2, ratio:'square'}, true), false);
  assert.strictEqual(defaults.shouldAdoptSourceRatio({apiDefaultsVersion:3, ratio:'square'}, false), false);
}

console.log('api-generator-defaults tests passed');

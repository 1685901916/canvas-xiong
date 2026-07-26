(function(root, factory){
  const api = factory();
  if(typeof module === 'object' && module.exports) module.exports = api;
  else root.ApiGeneratorDefaults = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function(){
  function imageModels(provider){
    return Array.isArray(provider?.image_models)
      ? provider.image_models.map(value => String(value || '').trim()).filter(Boolean)
      : [];
  }

  function eligibleProviders(providers){
    return (Array.isArray(providers) ? providers : []).filter(provider =>
      provider && provider.id !== 'modelscope' && provider.enabled !== false && imageModels(provider).length
    );
  }

  function is65535(provider){
    return String(provider?.id || '').toLowerCase() === 'custom-api-2'
      || String(provider?.name || '').trim() === '65535';
  }

  function selectProvider(providers){
    const items = eligibleProviders(providers);
    return items.find(provider => provider.primary && provider.has_key)
      || items.find(provider => is65535(provider) && provider.has_key)
      || items.find(provider => provider.has_key)
      || items.find(is65535)
      || items.find(provider => provider.primary)
      || items[0]
      || null;
  }

  function selectModel(provider){
    const models = imageModels(provider);
    return models.find(model => model.toLowerCase() === 'gpt-image-2') || models[0] || '';
  }

  function createDefaultNode({id, x=0, y=0, providers=[]}={}){
    const provider = selectProvider(providers);
    return {
      id, type:'generator', x, y,
      apiProvider:provider?.id || '', model:selectModel(provider),
      ratio:'square', resolution:'2k', quality:'high',
      forceFill:false, count:1,
      customRatio:'', customSize:'', customRatioWidth:'', customRatioHeight:'',
      customWidth:'', customHeight:'', inputs:[],
      apiDefaultsVersion:3, _apiRatioUserSet:false, _apiResolutionUserSet:true,
    };
  }

  function shouldAdoptSourceRatio(node, hasReferenceImage){
    return Boolean(
      hasReferenceImage
      && Number(node?.apiDefaultsVersion || 0) >= 3
      && node?._apiRatioUserSet !== true
      && (node?.ratio || 'square') === 'square'
    );
  }

  return {imageModels, eligibleProviders, selectProvider, selectModel, createDefaultNode, shouldAdoptSourceRatio};
});

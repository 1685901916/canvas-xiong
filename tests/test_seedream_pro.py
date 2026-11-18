from pathlib import Path
import pytest
from PIL import Image
import seedream_pro as pro

MODEL = "doubao-seedream-5-0-pro-260628"

def test_layer_payload_allows_empty_prompt_and_keeps_options():
    body = pro.payload(MODEL, "", "auto", ["source"], {"layer_decomposition": True, "response_format":"b64_json"})
    assert body["layer_decomposition"] is True
    assert body["size"] == "auto"
    assert body["prompt"] == ""
    assert body["response_format"] == "b64_json"
    assert "quality" not in body

@pytest.mark.parametrize("size,refs,count", [("4K",["a"],1),("1024x1024",["a"],1),("auto",[],1),("auto",["a","b"],1),("auto",["a"],2)])
def test_invalid_layer_requests_fail_before_network(size,refs,count):
    with pytest.raises(ValueError):
        pro.payload(MODEL,"",size,refs,{"layer_decomposition":True},count)

def test_response_preserves_layer_metadata():
    row={"url":"https://example.com/a.png","z_index":2,"name":"眼睛","bounding_box":{"absolute":[2,3,5,7]}}
    assert pro.images({"data":[row]})[0]["bounding_box"] == row["bounding_box"]

def test_full_resolution_alpha_and_layer_export(tmp_path):
    base=tmp_path/'base.png'; part=tmp_path/'part.png'
    Image.new('RGBA',(32,48),(255,255,255,255)).save(base)
    Image.new('RGBA',(8,9),(15,30,45,128)).save(part)
    assert pro.local_reference(part,True).startswith('data:image/png;base64,')
    with pytest.raises(ValueError): pro.local_reference(base,True)
    items=[{"url":str(base),"z_index":0},{"url":str(part),"z_index":1,"name":"蓝色长发","bounding_box":{"absolute":[5,7,13,16]}}]
    result=pro.bundle(items,lambda p:p,tmp_path,lambda p:p)
    from psd_tools import PSDImage
    psd=PSDImage.open(tmp_path/result['psd'])
    assert psd[0].visible is True
    assert psd[1].offset == (5,7)
    assert psd[1].name == "蓝色长发"
    assert psd[1].topil().getpixel((0,0)) == (15,30,45,128)
    assert (tmp_path/result['zip']).is_file()

def test_wrong_provider_rejects_pro_options(monkeypatch):
    import main
    provider={"id":"test","image_models":["test"],"protocol":"openai"}
    monkeypatch.setattr(main,"preferred_image_api_provider",lambda _:provider)
    monkeypatch.setattr(main,"provider_has_usable_key",lambda _:True)
    with pytest.raises(main.HTTPException,match="Seedream"):
        main.resolve_online_image_request(main.OnlineImageRequest(prompt="x",provider_id="test",seedream_options={}))

def test_resized_layer_uses_official_box_and_preserves_original(tmp_path):
    import json
    from psd_tools import PSDImage
    base=tmp_path/'base.png'; part=tmp_path/'part.png'
    Image.new('RGBA',(64,64),'white').save(base)
    Image.new('RGBA',(16,16),(0,80,160,128)).save(part)
    result=pro.bundle([{'url':str(base),'z_index':0}, {'url':str(part),'z_index':1,'bounding_box':{'absolute':[4,5,12,13]}}],lambda p:p,tmp_path,lambda p:p)
    psd=PSDImage.open(tmp_path/result['psd'])
    assert psd[1].size == (8,8)
    manifest=json.loads((tmp_path/result['manifest']).read_text(encoding='utf-8'))
    layer=manifest['layers'][1]
    assert layer['original_size'] == [16,16]
    assert layer['aligned_file'] != layer['file']

def test_build_result_uses_official_adapter_and_preserves_layer_fields(monkeypatch,tmp_path):
    import asyncio
    import main
    provider={'id':'volcengine','image_models':[MODEL],'protocol':'volcengine','base_url':'https://ark.cn-beijing.volces.com/api/v3'}
    monkeypatch.setattr(main,'preferred_image_api_provider',lambda _:provider)
    monkeypatch.setattr(main,'provider_has_usable_key',lambda _:True)
    calls=[]
    async def official(prompt,size,model,refs,provider,options):
        calls.append(options.response_format)
        raw={'data':[{'url':'/assets/output/test.png','z_index':0,'name':'Base'}]}
        return pro.images(raw)[0],raw
    async def store(item,**kwargs):return item['value']
    monkeypatch.setattr(main,'generate_volcengine_provider_image',official)
    monkeypatch.setattr(main,'save_ai_image_to_output',store)
    monkeypatch.setattr(main,'save_to_history',lambda _:None)
    monkeypatch.setattr(main,'GLOBAL_LOOP',None)
    req=main.OnlineImageRequest(prompt='test',provider_id='volcengine',model=MODEL,size='1.5K',seedream_options={'response_format':'b64_json'})
    result=asyncio.run(main.build_online_image_result(req))
    assert calls == ['b64_json']
    assert result['image_items'][0]['z_index'] == 0
    assert result['params']['seedream_options']['response_format'] == 'b64_json'

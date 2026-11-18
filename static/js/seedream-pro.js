(function(root){
    'use strict';
    const enabled = node => node?.apiProvider === 'volcengine' && /seedream-5-0-pro/i.test(node?.model || '');
    function apply(node, request, prompt){
        if(!enabled(node)) return request;
        const options = {layer_decomposition:false, output_format:'png', response_format:'url', watermark:false,
            optimize_mode:'standard', background:'opaque', ...node.seedreamOptions};
        request.seedream_options = options;
        request.size = node.seedreamSize || (options.layer_decomposition ? 'auto' : '2K');
        if(request.size === 'custom') request.size = `${node.seedreamWidth || 2048}x${node.seedreamHeight || 2048}`;
        request.prompt = options.layer_decomposition ? prompt : (prompt || 'Edit the reference images.');
        return request;
    }
    function mount(wrap, node, save){
        let panel = wrap.querySelector('.seedream-pro-settings');
        if(!panel){ panel = document.createElement('div'); panel.className = 'seedream-pro-settings'; wrap.querySelector('.gen-settings').appendChild(panel); }
        const sync = () => {
            const active = enabled(node);
            panel.hidden = !active;
            if(!active) wrap.querySelector('.api-size-row').style.display = '';
            for(const selector of ['.api-size-row', '.custom-size-row', '.custom-ratio-row']){
                const el = wrap.querySelector(selector);
                if(el && active) el.style.display = 'none';
            }
            if(!active) return;
            const opts = node.seedreamOptions || {};
            const layers = !!opts.layer_decomposition;
            panel.innerHTML = `<div style="font-size:11px;line-height:1.6;margin:8px 0">Seedream 5.0 Pro · 火山官方<br>文生图 / 多图编辑 / 标注与草图编辑 / 图像分层</div>`;
            function select(label, choices, value, change){
                const row = document.createElement('label'); row.className = 'gen-settings-row';
                const title = document.createElement('span'); title.textContent = label; title.style.cssText='font-size:11px;min-width:65px';
                const input = document.createElement('select'); input.className = 'select-lite';
                for(const [id,text] of choices){ const opt = new Option(text,id); input.add(opt); }
                input.value = value;
                input.onchange = e => { e.stopPropagation(); change(input.value); save(); sync(); };
                row.append(title,input); panel.appendChild(row);
            }
            const set = (key,value) => { node.seedreamOptions = {...node.seedreamOptions,[key]:value}; };
            select('模式', [['image','生图 / 参考图编辑'],['layers','图像分层（透明 PNG + PSD）']], layers?'layers':'image', value=>{
                set('layer_decomposition',value==='layers'); set('background','opaque');
                node.seedreamSize = value==='layers'?'auto':'2K'; if(value==='layers') node.count=1;
            });
            select('尺寸', [...(layers?[['auto','自动（保留画幅）']]:[]),['1K','1K'],['1.5K','1.5K'],['2K','2K'],...(!layers?[['custom','自定义像素']]:[])], node.seedreamSize || (layers?'auto':'2K'), v=>node.seedreamSize=v);
            if(node.seedreamSize==='custom'){
                for(const [key,label] of [['seedreamWidth','宽'],['seedreamHeight','高']]){
                    const row=document.createElement('label'); row.className='gen-settings-row'; row.textContent=label;
                    const input=document.createElement('input'); input.type='number'; input.min='16'; input.className='setting-input'; input.value=node[key]||2048;
                    input.onchange=()=>{node[key]=Number(input.value);save();}; row.append(input); panel.append(row);
                }
            }
            select('输出格式',[['png','PNG'],['jpeg','JPEG（分层仍为 PNG）']],opts.output_format||'png',v=>set('output_format',v));
            select('返回方式',[['url','链接（自动保存本地）'],['b64_json','Base64（自动保存本地）']],opts.response_format||'url',v=>set('response_format',v));
            select('提示词优化',[['standard','标准'],['fast','快速']],opts.optimize_mode||'standard',v=>set('optimize_mode',v));
            if(!layers) select('背景',[['opaque','默认背景'],['transparent','透明背景编辑（需透明参考图）']],opts.background||'opaque',v=>{set('background',v);if(v==='transparent')set('output_format','png');});
            select('水印',[['off','关闭'],['on','开启']],opts.watermark?'on':'off',v=>set('watermark',v==='on'));
            if(!layers) select('生成数量',Array.from({length:8},(_,i)=>[String(i+1),String(i+1)]),String(node.count||1),v=>node.count=Number(v));
            const note=document.createElement('div'); note.style.cssText='font-size:11px;color:var(--muted);line-height:1.6;margin-top:6px';
            note.textContent=layers?'连接 1 张参考图；提示词留空自动分层，也可指定部件。输出保留坐标并提供图层预览、ZIP 和 PSD。':'最多 10 张参考图；比例、标注与草图要求写在提示词里。批量为独立请求。原生最高 2K。';
            panel.append(note);
        };
        wrap.querySelector('.provider-select').addEventListener('change',sync);
        wrap.querySelector('.model-select').addEventListener('change',sync);
        panel.onmousedown = e=>e.stopPropagation(); panel.onclick=e=>e.stopPropagation();
        sync();
    }
    root.SeedreamPro={enabled,apply,mount};
    if(typeof module!=='undefined') module.exports=root.SeedreamPro;
})(typeof window!=='undefined'?window:globalThis);

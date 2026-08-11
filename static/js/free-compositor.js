(function(root, factory){
    const api = factory(root);
    if(typeof module === 'object' && module.exports) module.exports = api;
    root.createFreeCompositorDropController = api.createFreeCompositorDropController;
})(typeof window !== 'undefined' ? window : globalThis, function(root){
    'use strict';

    function createDropController(options={}){
        const acceptedTypes = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
        const trackedUrls = new Set();
        let dragDepth = 0;
        let fallbackSequence = 0;
        let cleanupSession = 0;
        let latestRequestId = 0;
        const getDocument = options.getDocument || (() => null);
        const getPoint = options.getPoint || (() => ({x:0, y:0}));
        const createObjectURL = options.createObjectURL || (file => URL.createObjectURL(file));
        const revokeObjectURL = options.revokeObjectURL || (url => URL.revokeObjectURL(url));
        const deleteCachedUrl = options.deleteCachedUrl || (() => {});
        const decode = options.decode || (async () => { throw new Error('缺少图片解码器'); });
        const placeImportedLayers = options.placeImportedLayers || (() => []);
        const nextId = options.nextId || (() => `imported-${Date.now().toString(36)}-${++fallbackSequence}`);
        const commit = options.commit || (() => {});
        const render = options.render || (() => {});
        const setStatus = options.setStatus || (() => {});
        const setActive = options.setActive || (() => {});

        const acceptedImageFiles = files => Array.from(files || []).filter(file => acceptedTypes.has(file?.type));
        const hasExternalFiles = dataTransfer => Boolean(dataTransfer?.files?.length || Array.from(dataTransfer?.types || []).includes('Files'));
        const clearActive = () => { dragDepth = 0; setActive(false); };
        const releaseObjectUrl = url => {
            if(!trackedUrls.has(url)) return;
            trackedUrls.delete(url);
            deleteCachedUrl(url);
            revokeObjectURL(url);
        };

        async function importDroppedFiles(files, event){
            const fileList = Array.from(files || []);
            const filesToImport = acceptedImageFiles(fileList);
            const session = cleanupSession;
            const requestId = ++latestRequestId;
            if(!filesToImport.length){
                if(requestId === latestRequestId) setStatus('没有可导入的图片', true);
                return [];
            }
            const point = getPoint(event);
            const decoded = await Promise.all(filesToImport.map(async (file, index) => {
                let url = '';
                try {
                    url = createObjectURL(file);
                    trackedUrls.add(url);
                    const image = await decode({file, url, name:file.name});
                    return {
                        id:nextId(),
                        name:file.name || `导入图片 ${index + 1}`,
                        url,
                        naturalWidth:image.naturalWidth,
                        naturalHeight:image.naturalHeight,
                        visible:true,
                        locked:false,
                        opacity:1,
                    };
                } catch(error){
                    if(url) releaseObjectUrl(url);
                    return null;
                }
            }));
            const valid = decoded.filter(Boolean);
            const skipped = fileList.length - valid.length;
            if(session !== cleanupSession) return [];
            if(!valid.length){
                if(requestId === latestRequestId) setStatus('没有可导入的图片', true);
                return [];
            }
            const doc = getDocument();
            const imported = placeImportedLayers(valid, doc, point, {maxRatio:.8, offset:24}).map(layer => ({
                ...layer,
                visible:true,
                locked:false,
                opacity:1,
            }));
            doc.layers.push(...imported);
            if(requestId === latestRequestId) doc.selectedId = imported.at(-1).id;
            commit();
            render();
            if(requestId === latestRequestId) setStatus(skipped ? `已导入 ${imported.length} 张，跳过 ${skipped} 个无效文件` : `已导入 ${imported.length} 张图片`, Boolean(skipped));
            return imported;
        }

        return {
            acceptedImageFiles,
            onDragEnter(event){
                if(!hasExternalFiles(event.dataTransfer)) return false;
                event.preventDefault();
                dragDepth++;
                setActive(true);
                return true;
            },
            onDragOver(event){
                if(!hasExternalFiles(event.dataTransfer)) return false;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'copy';
                setActive(true);
                return true;
            },
            onDragLeave(event){
                if(!hasExternalFiles(event.dataTransfer)) return false;
                event.preventDefault();
                dragDepth = Math.max(0, dragDepth - 1);
                if(!dragDepth) setActive(false);
                return true;
            },
            async onDrop(event){
                if(!hasExternalFiles(event.dataTransfer)) return [];
                event.preventDefault();
                clearActive();
                return await importDroppedFiles(event.dataTransfer.files, event);
            },
            cleanup(){
                cleanupSession++;
                clearActive();
                [...trackedUrls].forEach(releaseObjectUrl);
            },
        };
    }

    const core = root.FreeCompositorCore;
    const host = root.document?.getElementById('freeCompositorRoot');
    if(!core || !host) return {createFreeCompositorDropController:createDropController};

    let doc = null;
    let history = null;
    let adapter = null;
    let zoom = 1;
    let interaction = null;
    let guides = [];
    let exporting = false;
    const imageCache = new Map();
    let dropController = null;

    const html = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    const num = (value, fallback=0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
    const selectedLayer = () => doc?.layers.find(layer => layer.id === doc.selectedId) || null;

    function loadImage(item){
        if(imageCache.has(item.url)) return imageCache.get(item.url);
        const promise = new Promise((resolve, reject) => {
            const image = new Image();
            image.crossOrigin = 'anonymous';
            image.onload = () => resolve(image);
            image.onerror = () => reject(new Error(`图片加载失败：${item.name || item.url}`));
            image.src = item.url;
        });
        imageCache.set(item.url, promise);
        return promise;
    }

    async function prepareItems(items){
        return Promise.all(items.map(async (item, index) => {
            const image = await loadImage(item);
            const naturalWidth = num(item.naturalWidth);
            const naturalHeight = num(item.naturalHeight);
            const width = num(item.width);
            const height = num(item.height);
            const hasNaturalSize = naturalWidth > 0 && naturalHeight > 0;
            const hasSize = width > 0 && height > 0;
            return {
                ...item,
                naturalWidth:hasNaturalSize ? naturalWidth : image.naturalWidth,
                naturalHeight:hasNaturalSize ? naturalHeight : image.naturalHeight,
                width:hasSize ? width : undefined,
                height:hasSize ? height : undefined,
                role:index === 0 ? 'background' : '',
            };
        }));
    }

    function shellMarkup(){
        return `<div class="fc-shell" role="dialog" aria-modal="true" aria-label="自由合成">
            <header class="fc-topbar">
                <div class="fc-brand"><strong>自由合成</strong><span>像 PS 一样调整分件</span></div>
                <div class="fc-top-actions">
                    <button type="button" data-fc-action="undo" title="撤销 Ctrl+Z">↶</button>
                    <button type="button" data-fc-action="redo" title="重做 Ctrl+Shift+Z">↷</button>
                    <label>缩放 <input data-fc-field="zoom" type="range" min="10" max="200" step="5" value="${Math.round(zoom * 100)}"><span data-fc-zoom-label>${Math.round(zoom * 100)}%</span></label>
                    <button type="button" data-fc-action="fit">适合窗口</button>
                    <button type="button" data-fc-action="close">取消</button>
                    <button type="button" class="fc-primary" data-fc-action="export">生成到画布</button>
                </div>
            </header>
            <div class="fc-main">
                <aside class="fc-panel fc-layers-panel">
                    <div class="fc-panel-title"><strong>图层</strong><button type="button" data-fc-action="duplicate" title="复制图层">＋</button></div>
                    <div class="fc-layer-list"></div>
                </aside>
                <main class="fc-viewport">
                    <div class="fc-drop-hint" aria-hidden="true"><strong>松开以放置图片</strong><span>PNG/JPG/WEBP/GIF 成为独立图层</span></div>
                    <div class="fc-stage"></div>
                </main>
                <aside class="fc-panel fc-properties-panel"></aside>
            </div>
            <footer class="fc-status"><span data-fc-status>拖动图层，使用控制点缩放或旋转</span><span>${doc.width} × ${doc.height}px</span></footer>
        </div>`;
    }

    function layerListMarkup(){
        return [...doc.layers].reverse().map(layer => `<div class="fc-layer-row ${layer.id === doc.selectedId ? 'active' : ''}" data-layer-id="${html(layer.id)}">
            <button type="button" data-fc-layer-action="visible" title="显示/隐藏">${layer.visible ? '◉' : '○'}</button>
            <button type="button" data-fc-layer-action="lock" title="锁定/解锁">${layer.locked ? '🔒' : '◇'}</button>
            <img src="${html(layer.url)}" alt="">
            <span title="${html(layer.name)}">${html(layer.name)}</span>
            <div class="fc-layer-order">
                <button type="button" data-fc-layer-action="up" title="上移">↑</button>
                <button type="button" data-fc-layer-action="down" title="下移">↓</button>
            </div>
        </div>`).join('');
    }

    function propertiesMarkup(){
        const layer = selectedLayer();
        const layerFields = layer ? `<section>
            <h3>图层属性</h3>
            <label class="fc-wide">名称<input data-fc-prop="name" type="text" value="${html(layer.name)}"></label>
            <div class="fc-field-grid">
                <label>X<input data-fc-prop="x" type="number" step="1" value="${Math.round(layer.x)}"></label>
                <label>Y<input data-fc-prop="y" type="number" step="1" value="${Math.round(layer.y)}"></label>
                <label>宽<input data-fc-prop="width" type="number" min="8" step="1" value="${Math.round(layer.width)}"></label>
                <label>高<input data-fc-prop="height" type="number" min="8" step="1" value="${Math.round(layer.height)}"></label>
                <label>角度<input data-fc-prop="rotation" type="number" step="1" value="${Math.round(layer.rotation)}"></label>
                <label>透明度<input data-fc-prop="opacity" type="number" min="0" max="100" step="1" value="${Math.round(layer.opacity * 100)}"></label>
            </div>
            <div class="fc-button-grid">
                <button type="button" data-fc-action="center-x">水平居中</button>
                <button type="button" data-fc-action="center-y">垂直居中</button>
                <button type="button" data-fc-action="duplicate">复制</button>
                <button type="button" data-fc-action="delete">删除</button>
            </div>
        </section>` : '<section><p>请选择一个图层</p></section>';
        const backgroundMode = doc.background === 'transparent' || doc.background === '#ffffff' ? doc.background : 'custom';
        const customColor = backgroundMode === 'custom' ? doc.background : '#f7dce3';
        return `<section>
            <h3>画板</h3>
            <div class="fc-field-grid">
                <label>宽<input data-fc-doc="width" type="number" min="1" max="12000" value="${doc.width}"></label>
                <label>高<input data-fc-doc="height" type="number" min="1" max="12000" value="${doc.height}"></label>
            </div>
            <label class="fc-wide">背景<select data-fc-doc="backgroundMode">
                <option value="transparent" ${backgroundMode === 'transparent' ? 'selected' : ''}>透明</option>
                <option value="#ffffff" ${backgroundMode === '#ffffff' ? 'selected' : ''}>白色</option>
                <option value="custom" ${backgroundMode === 'custom' ? 'selected' : ''}>自定义</option>
            </select></label>
            <label class="fc-color ${backgroundMode === 'custom' ? '' : 'hidden'}">背景色<input data-fc-doc="backgroundColor" type="color" value="${html(customColor)}"></label>
        </section>${layerFields}`;
    }

    function artboardMarkup(){
        const background = doc.background === 'transparent' ? '' : `background:${html(doc.background)}`;
        const layers = doc.layers.map(layer => `<div class="fc-layer ${layer.id === doc.selectedId ? 'selected' : ''} ${layer.locked ? 'locked' : ''}" data-layer-id="${html(layer.id)}" style="left:${layer.x}px;top:${layer.y}px;width:${layer.width}px;height:${layer.height}px;opacity:${layer.visible ? layer.opacity : 0};transform:rotate(${layer.rotation}deg)">
            <img src="${html(layer.url)}" alt="${html(layer.name)}" draggable="false">
        </div>`).join('');
        const layer = selectedLayer();
        const handles = ['nw','n','ne','e','se','s','sw','w'].map(handle => `<i class="fc-handle fc-${handle}" data-fc-handle="${handle}"></i>`).join('');
        const selection = layer && layer.visible ? `<div class="fc-transform-box ${layer.locked ? 'locked' : ''}" data-layer-id="${html(layer.id)}" style="left:${layer.x}px;top:${layer.y}px;width:${layer.width}px;height:${layer.height}px;transform:rotate(${layer.rotation}deg)">${handles}<i class="fc-rotate-line"></i><i class="fc-rotate-handle" data-fc-handle="rotate"></i></div>` : '';
        const guideHtml = guides.map(guide => `<i class="fc-guide fc-guide-${guide.axis}" style="${guide.axis === 'x' ? `left:${guide.value}px` : `top:${guide.value}px`}"></i>`).join('');
        return `<div class="fc-artboard" style="width:${doc.width}px;height:${doc.height}px;${background}">${layers}${selection}${guideHtml}</div>`;
    }

    function renderWorkspace(){
        host.querySelector('.fc-layer-list').innerHTML = layerListMarkup();
        host.querySelector('.fc-properties-panel').innerHTML = propertiesMarkup();
        const stage = host.querySelector('.fc-stage');
        stage.style.width = `${doc.width * zoom}px`;
        stage.style.height = `${doc.height * zoom}px`;
        stage.innerHTML = artboardMarkup();
        const artboard = stage.querySelector('.fc-artboard');
        artboard.style.transform = `scale(${zoom})`;
        host.querySelector('[data-fc-zoom-label]').textContent = `${Math.round(zoom * 100)}%`;
        host.querySelector('[data-fc-field="zoom"]').value = String(Math.round(zoom * 100));
        const statusTail = host.querySelector('.fc-status span:last-child');
        if(statusTail) statusTail.textContent = `${doc.width} × ${doc.height}px`;
        syncHistoryButtons();
    }

    function renderShell(){
        host.innerHTML = shellMarkup();
        renderWorkspace();
    }

    function setStatus(message, error=false){
        const status = host.querySelector('[data-fc-status]');
        if(status){ status.textContent = message; status.classList.toggle('error', error); }
    }

    function setDropActive(active){
        host.querySelector('.fc-viewport')?.classList.toggle('drop-active', active);
    }

    function importPoint(event){
        const rect = host.querySelector('.fc-artboard')?.getBoundingClientRect();
        if(!rect) return {x:doc.width / 2, y:doc.height / 2};
        return {
            x:core.clamp((event.clientX - rect.left) / zoom, 0, doc.width),
            y:core.clamp((event.clientY - rect.top) / zoom, 0, doc.height),
        };
    }

    function syncHistoryButtons(){
        const undo = host.querySelector('[data-fc-action="undo"]');
        const redo = host.querySelector('[data-fc-action="redo"]');
        if(undo) undo.disabled = !history?.canUndo();
        if(redo) redo.disabled = !history?.canRedo();
    }

    function commit(){
        history.push(doc);
        syncHistoryButtons();
    }

    function fitToWindow(){
        const viewport = host.querySelector('.fc-viewport');
        if(!viewport || !doc) return;
        zoom = Math.max(.1, Math.min(1.5, (viewport.clientWidth - 80) / doc.width, (viewport.clientHeight - 80) / doc.height));
        renderWorkspace();
    }

    function replaceLayer(next){
        doc.layers = doc.layers.map(layer => layer.id === next.id ? next : layer);
    }

    function startMove(event, layer){
        if(layer.locked || event.button !== 0) return;
        event.preventDefault();
        interaction = {type:'move', startX:event.clientX, startY:event.clientY, layer:{...layer}};
    }

    function startHandle(event, handle){
        const layer = selectedLayer();
        if(!layer || layer.locked || event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        interaction = {type:handle === 'rotate' ? 'rotate' : 'resize', handle, startX:event.clientX, startY:event.clientY, layer:{...layer}};
        if(handle === 'rotate'){
            const rect = host.querySelector('.fc-artboard').getBoundingClientRect();
            const cx = rect.left + (layer.x + layer.width / 2) * zoom;
            const cy = rect.top + (layer.y + layer.height / 2) * zoom;
            interaction.center = {x:cx, y:cy};
            interaction.startAngle = Math.atan2(event.clientY - cy, event.clientX - cx) * 180 / Math.PI;
        }
    }

    function onPointerMove(event){
        if(!interaction) return;
        const dx = (event.clientX - interaction.startX) / zoom;
        const dy = (event.clientY - interaction.startY) / zoom;
        let next = interaction.layer;
        if(interaction.type === 'move'){
            next = core.moveLayer(interaction.layer, dx, dy);
            const snapped = core.snapLayer(next, doc, doc.layers, 8 / zoom);
            next = snapped.layer;
            guides = snapped.guides;
        } else if(interaction.type === 'resize'){
            next = core.resizeLayer(interaction.layer, {handle:interaction.handle, dx, dy, freeRatio:event.shiftKey, fromCenter:event.altKey});
        } else if(interaction.type === 'rotate'){
            const angle = Math.atan2(event.clientY - interaction.center.y, event.clientX - interaction.center.x) * 180 / Math.PI;
            let rotation = interaction.layer.rotation + angle - interaction.startAngle;
            if(event.shiftKey) rotation = Math.round(rotation / 15) * 15;
            next = core.rotateLayer(interaction.layer, rotation);
        }
        replaceLayer(next);
        renderWorkspace();
    }

    function finishInteraction(){
        if(!interaction) return;
        interaction = null;
        guides = [];
        commit();
        renderWorkspace();
    }

    function changeLayerProperty(input){
        const layer = selectedLayer();
        if(!layer) return;
        const key = input.dataset.fcProp;
        let value = input.value;
        if(key !== 'name') value = num(value);
        if(key === 'opacity') value = core.clamp(value / 100, 0, 1);
        if(key === 'width' || key === 'height') value = Math.max(core.MIN_SIZE, value);
        replaceLayer(core.normalizeLayer({...layer, [key]:value}));
        commit();
        renderWorkspace();
    }

    function changeDocumentProperty(input){
        const key = input.dataset.fcDoc;
        if(key === 'width' || key === 'height') doc[key] = Math.max(1, Math.min(12000, Math.round(num(input.value, doc[key]))));
        if(key === 'backgroundMode'){
            if(input.value === 'custom') doc.background = host.querySelector('[data-fc-doc="backgroundColor"]')?.value || '#f7dce3';
            else doc.background = input.value;
        }
        if(key === 'backgroundColor') doc.background = input.value;
        commit();
        renderWorkspace();
    }

    function selectLayer(id){
        if(!doc.layers.some(layer => layer.id === id)) return;
        doc.selectedId = id;
        renderWorkspace();
    }

    function layerAction(action, id){
        const layer = doc.layers.find(item => item.id === id);
        if(!layer) return;
        const index = doc.layers.findIndex(item => item.id === id);
        if(action === 'visible') replaceLayer({...layer, visible:!layer.visible});
        if(action === 'lock') replaceLayer({...layer, locked:!layer.locked});
        if(action === 'up') doc.layers = core.reorderLayer(doc.layers, id, index + 1);
        if(action === 'down') doc.layers = core.reorderLayer(doc.layers, id, index - 1);
        commit();
        renderWorkspace();
    }

    function duplicateSelected(){
        const layer = selectedLayer();
        if(!layer) return;
        const id = `${layer.id}-copy-${Date.now().toString(36)}`;
        doc.layers = core.duplicateLayer(doc.layers, layer.id, id);
        doc.selectedId = id;
        commit();
        renderWorkspace();
    }

    function deleteSelected(){
        const layer = selectedLayer();
        if(!layer || doc.layers.length <= 1) return;
        const index = doc.layers.findIndex(item => item.id === layer.id);
        doc.layers = core.deleteLayer(doc.layers, layer.id);
        doc.selectedId = doc.layers[Math.max(0, index - 1)]?.id || '';
        commit();
        renderWorkspace();
    }

    function centerSelected(axis){
        const layer = selectedLayer();
        if(!layer || layer.locked) return;
        const next = {...layer};
        if(axis === 'x') next.x = (doc.width - layer.width) / 2;
        else next.y = (doc.height - layer.height) / 2;
        replaceLayer(next);
        commit();
        renderWorkspace();
    }

    function undo(){
        if(!history.canUndo()) return;
        doc = history.undo();
        renderWorkspace();
    }

    function redo(){
        if(!history.canRedo()) return;
        doc = history.redo();
        renderWorkspace();
    }

    function close(){
        if(exporting) return;
        host.classList.remove('open');
        host.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('free-compositor-open');
        interaction = null;
        guides = [];
        dropController?.cleanup();
    }

    async function exportPng(){
        if(exporting) return;
        if(doc.width * doc.height > 64000000){
            setStatus('画板超过 6400 万像素，请缩小后再导出', true);
            return;
        }
        exporting = true;
        const button = host.querySelector('[data-fc-action="export"]');
        if(button) button.disabled = true;
        setStatus('正在生成高清 PNG…');
        try {
            const canvas = document.createElement('canvas');
            canvas.width = doc.width;
            canvas.height = doc.height;
            const ctx = canvas.getContext('2d');
            if(doc.background !== 'transparent'){
                ctx.fillStyle = doc.background;
                ctx.fillRect(0, 0, doc.width, doc.height);
            }
            for(const layer of core.renderList(doc.layers)){
                const image = await loadImage(layer);
                ctx.save();
                ctx.globalAlpha = layer.opacity;
                ctx.translate(layer.x + layer.width / 2, layer.y + layer.height / 2);
                ctx.rotate(layer.rotation * Math.PI / 180);
                ctx.drawImage(image, -layer.width / 2, -layer.height / 2, layer.width, layer.height);
                ctx.restore();
            }
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
            if(!blob) throw new Error('浏览器未能生成 PNG');
            await adapter.commitPngBlob(blob, {name:`自由合成-${Date.now()}.png`, width:doc.width, height:doc.height});
            exporting = false;
            close();
        } catch(error){
            exporting = false;
            if(button) button.disabled = false;
            setStatus(error?.message || '导出失败', true);
        }
    }

    function action(name){
        if(name === 'close') close();
        if(name === 'fit') fitToWindow();
        if(name === 'undo') undo();
        if(name === 'redo') redo();
        if(name === 'duplicate') duplicateSelected();
        if(name === 'delete') deleteSelected();
        if(name === 'center-x') centerSelected('x');
        if(name === 'center-y') centerSelected('y');
        if(name === 'export') exportPng();
    }

    dropController = createDropController({
        getDocument:() => doc,
        getPoint:importPoint,
        createObjectURL:file => URL.createObjectURL(file),
        revokeObjectURL:url => URL.revokeObjectURL(url),
        deleteCachedUrl:url => imageCache.delete(url),
        decode:async item => {
            const image = await loadImage(item);
            return {naturalWidth:image.naturalWidth, naturalHeight:image.naturalHeight};
        },
        placeImportedLayers:(layers, documentState, point, options) => core.placeImportedLayers(layers, documentState, point, options),
        commit,
        render:renderWorkspace,
        setStatus,
        setActive:setDropActive,
    });

    host.addEventListener('pointerdown', event => {
        const handle = event.target.closest('[data-fc-handle]');
        if(handle){ startHandle(event, handle.dataset.fcHandle); return; }
        const layerEl = event.target.closest('.fc-layer');
        if(layerEl){
            const layer = doc.layers.find(item => item.id === layerEl.dataset.layerId);
            selectLayer(layerEl.dataset.layerId);
            startMove(event, layer);
            return;
        }
        const row = event.target.closest('.fc-layer-row');
        if(row) selectLayer(row.dataset.layerId);
    });

    host.addEventListener('click', event => {
        const layerButton = event.target.closest('[data-fc-layer-action]');
        if(layerButton){
            event.stopPropagation();
            layerAction(layerButton.dataset.fcLayerAction, layerButton.closest('.fc-layer-row')?.dataset.layerId);
            return;
        }
        const button = event.target.closest('[data-fc-action]');
        if(button) action(button.dataset.fcAction);
    });

    host.addEventListener('change', event => {
        if(event.target.dataset.fcProp) changeLayerProperty(event.target);
        if(event.target.dataset.fcDoc) changeDocumentProperty(event.target);
    });

    host.addEventListener('input', event => {
        if(event.target.dataset.fcField === 'zoom'){
            zoom = core.clamp(num(event.target.value, 100) / 100, .1, 2);
            renderWorkspace();
        }
        if(event.target.dataset.fcDoc === 'backgroundColor') changeDocumentProperty(event.target);
    });

    host.addEventListener('dragenter', event => {
        if(!event.target.closest('.fc-viewport')) return;
        dropController.onDragEnter(event);
    });

    host.addEventListener('dragover', event => {
        if(!event.target.closest('.fc-viewport')) return;
        dropController.onDragOver(event);
    });

    host.addEventListener('dragleave', event => {
        if(!event.target.closest('.fc-viewport')) return;
        dropController.onDragLeave(event);
    });

    host.addEventListener('drop', async event => {
        if(!event.target.closest('.fc-viewport')) return;
        try {
            await dropController.onDrop(event);
        } catch(error){
            setStatus(error?.message || '导入图片失败', true);
        }
    });

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', finishInteraction);
    window.addEventListener('keydown', event => {
        if(!host.classList.contains('open')) return;
        const typing = event.target.matches('input,select,textarea,[contenteditable="true"]');
        if(event.key === 'Escape'){ event.preventDefault(); close(); return; }
        if((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z'){
            event.preventDefault();
            event.shiftKey ? redo() : undo();
            return;
        }
        if(typing) return;
        if((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'd'){
            event.preventDefault(); duplicateSelected(); return;
        }
        if(event.key === 'Delete' || event.key === 'Backspace'){
            event.preventDefault(); deleteSelected(); return;
        }
        const delta = event.shiftKey ? 10 : 1;
        const moves = {ArrowLeft:[-delta,0], ArrowRight:[delta,0], ArrowUp:[0,-delta], ArrowDown:[0,delta]};
        if(moves[event.key]){
            const layer = selectedLayer();
            if(layer && !layer.locked){
                event.preventDefault();
                replaceLayer(core.moveLayer(layer, ...moves[event.key]));
                commit();
                renderWorkspace();
            }
        }
    });

    async function open(items, nextAdapter){
        if(!Array.isArray(items) || items.length < 1) throw new Error('至少需要一张图片');
        adapter = nextAdapter;
        const prepared = await prepareItems(items);
        const background = prepared[0];
        doc = core.createDocument({width:background.naturalWidth, height:background.naturalHeight, layers:prepared});
        history = core.createHistory(doc, 50);
        zoom = 1;
        host.classList.add('open');
        host.setAttribute('aria-hidden', 'false');
        document.body.classList.add('free-compositor-open');
        renderShell();
        requestAnimationFrame(fitToWindow);
    }

    root.freeCompositor = {open, close};
    return {createFreeCompositorDropController:createDropController};
});

(function(root, factory){
    const api = factory();
    if(typeof module === 'object' && module.exports) module.exports = api;
    root.FreeCompositorCore = api;
})(typeof window !== 'undefined' ? window : globalThis, function(){
    'use strict';

    const MIN_SIZE = 8;

    function number(value, fallback=0){
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function clamp(value, min, max){
        return Math.max(min, Math.min(max, value));
    }

    function clone(value){
        return JSON.parse(JSON.stringify(value));
    }

    function normalizeLayer(layer={}, index=0){
        const width = Math.max(MIN_SIZE, number(layer.width, number(layer.naturalWidth, 100)));
        const height = Math.max(MIN_SIZE, number(layer.height, number(layer.naturalHeight, 100)));
        return {
            id:String(layer.id || `layer-${index + 1}`),
            name:String(layer.name || layer.id || `图层 ${index + 1}`),
            url:String(layer.url || ''),
            x:number(layer.x, 0),
            y:number(layer.y, 0),
            width,
            height,
            naturalWidth:Math.max(1, number(layer.naturalWidth, width)),
            naturalHeight:Math.max(1, number(layer.naturalHeight, height)),
            rotation:number(layer.rotation, 0),
            opacity:clamp(number(layer.opacity, 1), 0, 1),
            visible:layer.visible !== false,
            locked:layer.locked === true,
        };
    }

    function createDocument(options={}){
        const width = Math.max(1, Math.round(number(options.width, 1080)));
        const height = Math.max(1, Math.round(number(options.height, 1920)));
        const source = Array.isArray(options.layers) ? options.layers : [];
        const layers = source.map((raw, index) => {
            const naturalWidth = Math.max(1, number(raw.naturalWidth, raw.width || width));
            const naturalHeight = Math.max(1, number(raw.naturalHeight, raw.height || height));
            let targetWidth;
            let targetHeight;
            if(index === 0 || raw.role === 'background'){
                targetWidth = width;
                targetHeight = height;
            } else {
                const scale = Math.min(1, width / naturalWidth, height / naturalHeight);
                targetWidth = naturalWidth * scale;
                targetHeight = naturalHeight * scale;
            }
            return normalizeLayer({
                ...raw,
                naturalWidth,
                naturalHeight,
                width:number(raw.width, targetWidth),
                height:number(raw.height, targetHeight),
                x:number(raw.x, (width - number(raw.width, targetWidth)) / 2),
                y:number(raw.y, (height - number(raw.height, targetHeight)) / 2),
            }, index);
        });
        return {
            width,
            height,
            background:String(options.background || 'transparent'),
            layers,
            selectedId:String(options.selectedId || layers.at(-1)?.id || ''),
        };
    }

    function moveLayer(layer, dx, dy){
        const current = normalizeLayer(layer);
        if(current.locked) return current;
        return {...current, x:current.x + number(dx), y:current.y + number(dy)};
    }

    function resizeLayer(layer, options={}){
        const current = normalizeLayer(layer);
        if(current.locked) return current;
        const handle = String(options.handle || 'se');
        const fromCenter = options.fromCenter === true;
        const keepRatio = options.keepRatio === true || /^(nw|ne|sw|se)$/.test(handle);
        const dx = number(options.dx);
        const dy = number(options.dy);
        const horizontal = handle.includes('e') ? dx : handle.includes('w') ? -dx : 0;
        const vertical = handle.includes('s') ? dy : handle.includes('n') ? -dy : 0;
        let width = current.width + horizontal * (fromCenter ? 2 : 1);
        let height = current.height + vertical * (fromCenter ? 2 : 1);
        if(keepRatio){
            const ratio = current.width / current.height;
            if(Math.abs(horizontal) >= Math.abs(vertical * ratio)) height = width / ratio;
            else width = height * ratio;
        }
        width = Math.max(MIN_SIZE, width);
        height = Math.max(MIN_SIZE, height);
        let x = current.x;
        let y = current.y;
        if(fromCenter){
            x = current.x - (width - current.width) / 2;
            y = current.y - (height - current.height) / 2;
        } else {
            if(handle.includes('w')) x = current.x + current.width - width;
            if(handle.includes('n')) y = current.y + current.height - height;
        }
        return {...current, x, y, width, height};
    }

    function rotateLayer(layer, rotation){
        const current = normalizeLayer(layer);
        return current.locked ? current : {...current, rotation:number(rotation, current.rotation)};
    }

    function reorderLayer(layers, id, toIndex){
        const list = (layers || []).map(item => ({...item}));
        const from = list.findIndex(item => item.id === id);
        if(from < 0) return list;
        const [item] = list.splice(from, 1);
        list.splice(clamp(Math.round(number(toIndex)), 0, list.length), 0, item);
        return list;
    }

    function deleteLayer(layers, id){
        return (layers || []).filter(item => item.id !== id).map(item => ({...item}));
    }

    function duplicateLayer(layers, id, nextId){
        const list = (layers || []).map(item => ({...item}));
        const index = list.findIndex(item => item.id === id);
        if(index < 0) return list;
        const source = normalizeLayer(list[index], index);
        const copy = {...source, id:String(nextId || `${source.id}-copy`), name:`${source.name} copy`, x:source.x + 16, y:source.y + 16, locked:false};
        list.splice(index + 1, 0, copy);
        return list;
    }

    function snapshot(value){
        return clone(value);
    }

    function createHistory(initial, limit=50){
        let stack = [snapshot(initial)];
        let index = 0;
        const max = Math.max(2, Math.round(number(limit, 50)));
        return {
            push(value){
                stack = stack.slice(0, index + 1);
                stack.push(snapshot(value));
                if(stack.length > max) stack.shift();
                index = stack.length - 1;
                return this.current();
            },
            undo(){ if(index > 0) index--; return this.current(); },
            redo(){ if(index < stack.length - 1) index++; return this.current(); },
            current(){ return snapshot(stack[index]); },
            canUndo(){ return index > 0; },
            canRedo(){ return index < stack.length - 1; },
        };
    }

    function snapLayer(layer, documentState, others=[], tolerance=6){
        const current = normalizeLayer(layer);
        const xTargets = [0, number(documentState?.width) / 2, number(documentState?.width)];
        const yTargets = [0, number(documentState?.height) / 2, number(documentState?.height)];
        (others || []).filter(item => item.id !== current.id && item.visible !== false).forEach(item => {
            const other = normalizeLayer(item);
            xTargets.push(other.x, other.x + other.width / 2, other.x + other.width);
            yTargets.push(other.y, other.y + other.height / 2, other.y + other.height);
        });
        const xPoints = [current.x, current.x + current.width / 2, current.x + current.width];
        const yPoints = [current.y, current.y + current.height / 2, current.y + current.height];
        let bestX = null;
        let bestY = null;
        xPoints.forEach(point => xTargets.forEach(target => {
            const delta = target - point;
            if(Math.abs(delta) <= tolerance && (!bestX || Math.abs(delta) < Math.abs(bestX.delta))) bestX = {delta, value:target};
        }));
        yPoints.forEach(point => yTargets.forEach(target => {
            const delta = target - point;
            if(Math.abs(delta) <= tolerance && (!bestY || Math.abs(delta) < Math.abs(bestY.delta))) bestY = {delta, value:target};
        }));
        const guides = [];
        if(bestX) guides.push({axis:'x', value:bestX.value});
        if(bestY) guides.push({axis:'y', value:bestY.value});
        return {layer:{...current, x:current.x + (bestX?.delta || 0), y:current.y + (bestY?.delta || 0)}, guides};
    }

    function placeImportedLayer(layer, documentState, point, options={}){
        const source = normalizeLayer(layer);
        const documentWidth = Math.max(1, number(documentState?.width, 1));
        const documentHeight = Math.max(1, number(documentState?.height, 1));
        const maxRatio = clamp(number(options.maxRatio, 0.8), 0.1, 1);
        const scale = Math.min(1, documentWidth * maxRatio / source.naturalWidth, documentHeight * maxRatio / source.naturalHeight);
        const width = source.naturalWidth * scale;
        const height = source.naturalHeight * scale;
        const x = number(point?.x, documentWidth / 2);
        const y = number(point?.y, documentHeight / 2);
        return {...normalizeLayer({...source, width, height, x:x - width / 2, y:y - height / 2}), width, height, x:x - width / 2, y:y - height / 2};
    }

    function placeImportedLayers(layers, documentState, point, options={}){
        const offset = number(options.offset, 24);
        const x = number(point?.x, Math.max(1, number(documentState?.width, 1)) / 2);
        const y = number(point?.y, Math.max(1, number(documentState?.height, 1)) / 2);
        return (layers || []).map((layer, index) => placeImportedLayer(
            layer,
            documentState,
            {x:x + index * offset, y:y + index * offset},
            options,
        ));
    }

    function renderList(layers){
        return (layers || []).filter(item => item.visible !== false).map(item => ({...item}));
    }

    return {
        MIN_SIZE,
        clamp,
        createDocument,
        normalizeLayer,
        moveLayer,
        resizeLayer,
        rotateLayer,
        reorderLayer,
        duplicateLayer,
        deleteLayer,
        snapshot,
        createHistory,
        snapLayer,
        placeImportedLayer,
        placeImportedLayers,
        renderList,
    };
});

(function(root, factory){
    const api = factory();
    if(typeof module === 'object' && module.exports) module.exports = api;
    root.CharacterOverlay = api;
})(typeof window !== 'undefined' ? window : globalThis, function(){
    'use strict';

    function number(value, fallback){
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function clamp(value, min, max){
        return Math.max(min, Math.min(max, value));
    }

    function createDefaultOverlayState(options={}){
        return {
            url: String(options.url || ''),
            name: String(options.name || 'character'),
            visible: options.visible !== false,
            xPct: 0.5,
            bottomPct: 0,
            scalePct: 0.86,
            opacity: 0.72,
        };
    }

    function normalizeOverlayState(state={}){
        return {
            url: String(state.url || ''),
            name: String(state.name || 'character'),
            visible: state.visible !== false,
            xPct: clamp(number(state.xPct, 0.5), -0.5, 1.5),
            bottomPct: clamp(number(state.bottomPct, 0), 0, 1),
            scalePct: clamp(number(state.scalePct, 0.86), 0.2, 1.4),
            opacity: clamp(number(state.opacity, 0.72), 0.2, 1),
            objectUrl: state.objectUrl === true,
        };
    }

    function overlayBoxForFrame(state={}, frame={}){
        const s = normalizeOverlayState(state);
        const frameW = Math.max(1, number(frame.frameW, 1));
        const frameH = Math.max(1, number(frame.frameH, 1));
        const naturalW = Math.max(1, number(frame.naturalW, 1));
        const naturalH = Math.max(1, number(frame.naturalH, 1));
        const height = Math.round(frameH * s.scalePct);
        const width = Math.round(height * naturalW / naturalH);
        const left = Math.round(frameW * s.xPct - width / 2);
        const top = Math.round(frameH * (1 - s.bottomPct) - height);
        return {left, top, width, height, opacity:s.opacity, visible:s.visible};
    }

    function stateFromOverlayBox(state={}, frame={}){
        const s = normalizeOverlayState(state);
        const box = overlayBoxForFrame(s, frame);
        const frameW = Math.max(1, number(frame.frameW, 1));
        const frameH = Math.max(1, number(frame.frameH, 1));
        const left = number(frame.left, box.left);
        const top = number(frame.top, box.top);
        return normalizeOverlayState({
            ...s,
            xPct: (left + box.width / 2) / frameW,
            bottomPct: (frameH - (top + box.height)) / frameH,
        });
    }

    return {
        clamp,
        createDefaultOverlayState,
        normalizeOverlayState,
        overlayBoxForFrame,
        stateFromOverlayBox,
    };
});

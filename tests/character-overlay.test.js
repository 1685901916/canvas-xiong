const assert = require('assert');
const overlay = require('../static/js/character-overlay.js');

function approx(actual, expected, delta = 0.0001) {
  assert.ok(Math.abs(actual - expected) <= delta, `${actual} !== ${expected}`);
}

{
  const state = overlay.createDefaultOverlayState({ url: '/assets/character.png' });
  assert.strictEqual(state.url, '/assets/character.png');
  assert.strictEqual(state.visible, true);
  approx(state.xPct, 0.5);
  approx(state.bottomPct, 0);
  approx(state.scalePct, 0.86);
  approx(state.opacity, 0.72);
}

{
  const state = overlay.normalizeOverlayState({
    url: '/assets/character.png',
    objectUrl: true,
    xPct: 9,
    bottomPct: -4,
    scalePct: 8,
    opacity: 9,
  });
  assert.strictEqual(state.url, '/assets/character.png');
  assert.strictEqual(state.objectUrl, true);
  approx(state.xPct, 1.5);
  approx(state.bottomPct, 0);
  approx(state.scalePct, 1.4);
  approx(state.opacity, 1);
}

{
  const state = overlay.createDefaultOverlayState({ url: '/assets/character.png' });
  const box = overlay.overlayBoxForFrame(state, {
    frameW: 1000,
    frameH: 1600,
    naturalW: 512,
    naturalH: 1024,
  });
  assert.strictEqual(box.width, 688);
  assert.strictEqual(box.height, 1376);
  assert.strictEqual(box.left, 156);
  assert.strictEqual(box.top, 224);
}

{
  const state = overlay.createDefaultOverlayState({ url: '/assets/character.png' });
  const moved = overlay.stateFromOverlayBox(state, {
    frameW: 1000,
    frameH: 1600,
    naturalW: 512,
    naturalH: 1024,
    left: 250,
    top: 200,
  });
  approx(moved.xPct, 0.594);
  approx(moved.bottomPct, 0.015);
}

console.log('character overlay tests passed');

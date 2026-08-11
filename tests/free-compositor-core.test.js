const assert = require('assert');
const core = require('../static/js/free-compositor-core.js');

{
  const doc = core.createDocument({
    width: 1000,
    height: 1600,
    layers: [
      { id: 'bg', name: '背景', url: '/bg.png', naturalWidth: 1000, naturalHeight: 1600, role: 'background' },
      { id: 'girl', name: '人物', url: '/girl.png', naturalWidth: 500, naturalHeight: 1000 },
    ],
  });
  assert.strictEqual(doc.width, 1000);
  assert.strictEqual(doc.height, 1600);
  assert.strictEqual(doc.layers[0].width, 1000);
  assert.strictEqual(doc.layers[0].height, 1600);
  assert.strictEqual(doc.layers[1].width, 500);
  assert.strictEqual(doc.layers[1].height, 1000);
  assert.strictEqual(doc.layers[1].x, 250);
  assert.strictEqual(doc.layers[1].y, 300);
  assert.strictEqual(doc.selectedId, 'girl');
}

{
  const layer = core.normalizeLayer({ id: 'a', width: 200, height: 100, opacity: 8 });
  assert.strictEqual(layer.opacity, 1);
  assert.deepStrictEqual(core.moveLayer(layer, 15, -5), { ...layer, x: 15, y: -5 });
  assert.deepStrictEqual(core.moveLayer({ ...layer, locked: true }, 15, -5), { ...layer, locked: true });
}

{
  const layer = core.normalizeLayer({ id: 'a', x: 100, y: 100, width: 200, height: 100 });
  const resized = core.resizeLayer(layer, { handle: 'se', dx: 100, dy: 2, keepRatio: true });
  assert.strictEqual(resized.width, 300);
  assert.strictEqual(resized.height, 150);
  assert.strictEqual(resized.x, 100);
  assert.strictEqual(resized.y, 100);

  const centered = core.resizeLayer(layer, { handle: 'se', dx: 100, dy: 50, keepRatio: true, fromCenter: true });
  assert.strictEqual(centered.width, 400);
  assert.strictEqual(centered.height, 200);
  assert.strictEqual(centered.x, 0);
  assert.strictEqual(centered.y, 50);

  const minimum = core.resizeLayer(layer, { handle: 'nw', dx: 500, dy: 500 });
  assert.ok(minimum.width >= 8);
  assert.ok(minimum.height >= 8);
}

{
  const layers = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  assert.deepStrictEqual(core.reorderLayer(layers, 'a', 2).map(item => item.id), ['b', 'c', 'a']);
  assert.deepStrictEqual(core.deleteLayer(layers, 'b').map(item => item.id), ['a', 'c']);
  const copy = core.duplicateLayer(layers, 'b', 'b-copy');
  assert.deepStrictEqual(copy.map(item => item.id), ['a', 'b', 'b-copy', 'c']);
  assert.strictEqual(copy[2].name, 'b copy');
}

{
  const history = core.createHistory({ value: 1 }, 3);
  history.push({ value: 2 });
  history.push({ value: 3 });
  assert.deepStrictEqual(history.undo(), { value: 2 });
  assert.deepStrictEqual(history.undo(), { value: 1 });
  assert.deepStrictEqual(history.redo(), { value: 2 });
  history.push({ value: 9 });
  assert.strictEqual(history.canRedo(), false);
  assert.deepStrictEqual(history.current(), { value: 9 });
}

{
  const moving = { id: 'a', x: 442, y: 742, width: 100, height: 100 };
  const result = core.snapLayer(moving, { width: 1000, height: 1600 }, [], 10);
  assert.strictEqual(result.layer.x, 450);
  assert.strictEqual(result.layer.y, 750);
  assert.ok(result.guides.some(guide => guide.axis === 'x' && guide.value === 500));
  assert.ok(result.guides.some(guide => guide.axis === 'y' && guide.value === 800));
}

{
  const layers = [
    { id: 'bottom', visible: true },
    { id: 'hidden', visible: false },
    { id: 'top', visible: true },
  ];
  assert.deepStrictEqual(core.renderList(layers).map(item => item.id), ['bottom', 'top']);
}

{
  const placed = core.placeImportedLayer(
    { id: 'small', naturalWidth: 200, naturalHeight: 100 },
    { width: 1000, height: 1600 },
    { x: 500, y: 800 },
  );
  assert.deepStrictEqual(placed, {
    ...core.normalizeLayer({ id: 'small', naturalWidth: 200, naturalHeight: 100 }),
    x: 400,
    y: 750,
    width: 200,
    height: 100,
  });
}

{
  const placed = core.placeImportedLayer(
    { id: 'large', naturalWidth: 2000, naturalHeight: 1000 },
    { width: 1000, height: 1600 },
    { x: 500, y: 800 },
  );
  assert.strictEqual(placed.x, 100);
  assert.strictEqual(placed.y, 600);
  assert.strictEqual(placed.width, 800);
  assert.strictEqual(placed.height, 400);
}

{
  const placed = core.placeImportedLayers(
    [
      { id: 'one', naturalWidth: 100, naturalHeight: 100 },
      { id: 'two', naturalWidth: 100, naturalHeight: 100 },
    ],
    { width: 1000, height: 1600 },
    { x: 300, y: 400 },
  );
  assert.deepStrictEqual(placed.map(layer => ({ x: layer.x, y: layer.y })), [
    { x: 250, y: 350 },
    { x: 274, y: 374 },
  ]);
}

{
  const placed = core.placeImportedLayer(
    { id: 'pixel', naturalWidth: 1, naturalHeight: 1 },
    { width: 1000, height: 1600 },
    { x: 500, y: 800 },
  );
  assert.strictEqual(placed.width, 1);
  assert.strictEqual(placed.height, 1);
  assert.strictEqual(placed.x, 499.5);
  assert.strictEqual(placed.y, 799.5);
}

{
  const pixel = core.placeImportedLayer(
    { id: 'pixel', naturalWidth: 1, naturalHeight: 1 },
    { width: 1000, height: 1600 },
    { x: 124, y: 457 },
  );
  const moved = core.moveLayer(pixel, 10, -5);
  const rotated = core.rotateLayer(pixel, 45);
  const snapped = core.snapLayer(pixel, { width: 1000, height: 1600 }, [], 0).layer;
  assert.deepStrictEqual(
    [moved, rotated, snapped].map(layer => ({ x: layer.x, y: layer.y, width: layer.width, height: layer.height })),
    [
      { x: 133.5, y: 451.5, width: 1, height: 1 },
      { x: 123.5, y: 456.5, width: 1, height: 1 },
      { x: 123.5, y: 456.5, width: 1, height: 1 },
    ],
  );
}

{
  const placed = core.placeImportedLayers(
    [
      { id: 'one', naturalWidth: 100, naturalHeight: 100 },
      { id: 'two', naturalWidth: 100, naturalHeight: 100 },
    ],
    { width: 1000, height: 1600 },
  );
  assert.deepStrictEqual(placed.map(layer => ({ x: layer.x, y: layer.y })), [
    { x: 450, y: 750 },
    { x: 474, y: 774 },
  ]);
}

console.log('free compositor core tests passed');

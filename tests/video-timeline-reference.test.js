const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const canvas = fs.readFileSync(path.join(root, 'static', 'js', 'canvas.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static', 'css', 'canvas.css'), 'utf8');
const i18n = fs.readFileSync(path.join(root, 'static', 'js', 'i18n', 'canvas.js'), 'utf8');

assert.match(canvas, /data-video-timeline-reference/);
assert.match(canvas, /async function createVideoTimelineReference/);
assert.match(canvas, /fetch\('\/api\/video-timeline-reference'/);
assert.match(canvas, /type:'timelineReference'/);
assert.match(canvas, /timelineSourceId:node\.id/);
assert.match(canvas, /existing\s*=\s*nodes\.find\([^\n]+timelineSourceId/);
assert.doesNotMatch(canvas, /connections\.push\([^\n]+kind:'timelineReference'/);
assert.match(canvas, /timelineStoryboardUrl:String\(result\.storyboard_url/);
assert.match(canvas, /timelineStoryboardLayoutVersion:String\(result\.storyboard_layout_version/);
assert.match(canvas, /data-timeline-storyboard-url/);
assert.match(canvas, /hydrateTimelineReferenceStoryboard/);
assert.match(canvas, /TIMELINE_STORYBOARD_LAYOUT_VERSION\s*=\s*'compact-3'/);
assert.match(canvas, /function renderTimelineReferenceBody/);
assert.match(canvas, /function bindTimelineReferenceMediaDrag/);
assert.match(canvas, /element\.draggable\s*=\s*true/);
assert.match(canvas, /setData\('application\/x-canvas-output-image',\s*url\)/);
assert.match(canvas, /setData\('text\/uri-list',\s*url\)/);
assert.match(canvas, /setData\('text\/plain',\s*url\)/);
assert.match(canvas, /bindTimelineReferenceMediaDrag\(storyboard/);
assert.match(canvas, /bindTimelineReferenceMediaDrag\(button/);
assert.doesNotMatch(canvas, /data-timeline-(?:storyboard|frame)-url[^\n]+draggable="false"/);
assert.match(canvas, /timeline-reference-time/);
assert.match(canvas, /frame\.label/);
assert.match(css, /\.timeline-reference-grid/);
assert.match(css, /\.timeline-reference-storyboard/);
assert.match(css, /object-fit:contain/);
assert.match(css, /\.timeline-reference-(?:storyboard|frame)[^}]*cursor:grab/);
assert.match(css, /\.timeline-reference-(?:storyboard|frame):active[^}]*cursor:grabbing/);

for(const key of [
  'canvas.createTimelineReference',
  'canvas.creatingTimelineReference',
  'canvas.timelineReferenceCreated',
  'canvas.timelineReferenceFailed',
  'canvas.timelineReferenceTitle',
]) assert.ok(i18n.includes(`"${key}"`), `missing i18n key: ${key}`);

console.log('video timeline reference tests passed');

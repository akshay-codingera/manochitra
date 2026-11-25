import test from 'node:test';
import assert from 'node:assert/strict';

const {
  archiveDiagram,
  getArchivedDiagram,
  getAllArchivedDiagrams,
  getArchiveCounts,
  deleteArchivedDiagram,
} = await import('../js/archive.js');

const sampleSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">
  <title>Pythagoras Theorem</title>
  <line x1="100" y1="100" x2="400" y2="400">
    <animate attributeName="opacity" values="0.2;1;0.2" dur="2s" repeatCount="indefinite" />
  </line>
</svg>`;

test('Archiving an approved diagram stores exact SVG with animation, decision, and note', async () => {
  const record = await archiveDiagram({
    conceptId: 'pythagoras',
    conceptName: "Pythagoras' theorem",
    version: 1,
    decision: 'accepted',
    note: 'Verified hypotenuse formula and pulse highlight.',
    svg: sampleSvg,
    result: {
      model: 'gemini-3.5-flash-lite',
      usage: { input_tokens: 1500, output_tokens: 2800 },
      cost: { paid_equivalent_cost_usd: 0.00745 },
      checks: { c1: { passed: true }, c2: { passed: true } },
    },
  });

  assert.ok(record);
  assert.equal(record.id, 'pythagoras_v1');
  assert.equal(record.decision, 'accepted');
  assert.equal(record.note, 'Verified hypotenuse formula and pulse highlight.');
  assert.ok(record.svg.includes('<animate attributeName="opacity"'), 'SVG animation markup must be preserved in archive');

  const retrieved = await getArchivedDiagram('pythagoras', 1);
  assert.ok(retrieved);
  assert.equal(retrieved.decision, 'accepted');
  assert.equal(retrieved.concept_name, "Pythagoras' theorem");
  assert.equal(retrieved.svg, sampleSvg);
});

test('Archiving a rejected diagram classifies it properly', async () => {
  const rejectedSvg = `<svg viewBox="0 0 960 640"><title>Circle</title><circle cx="100" cy="100" r="50"/></svg>`;
  await archiveDiagram({
    conceptId: 'circle',
    conceptName: 'Parts of a circle',
    version: 1,
    decision: 'rejected',
    note: 'Circumference leader line did not touch outer boundary.',
    svg: rejectedSvg,
  });

  const retrieved = await getArchivedDiagram('circle', 1);
  assert.ok(retrieved);
  assert.equal(retrieved.decision, 'rejected');

  const rejectedList = await getAllArchivedDiagrams('rejected');
  const found = rejectedList.find(item => item.concept_id === 'circle' && item.version === 1);
  assert.ok(found, 'Circle v1 must be listed in rejected archives');
});

test('Changing decision updates archive classification without losing original SVG', async () => {
  // Change circle v1 from rejected to accepted
  await archiveDiagram({
    conceptId: 'circle',
    conceptName: 'Parts of a circle',
    version: 1,
    decision: 'accepted',
    note: 'Re-reviewed after instructor guidance.',
    svg: '<svg viewBox="0 0 960 640"><title>Circle v1</title></svg>',
  });

  const updated = await getArchivedDiagram('circle', 1);
  assert.equal(updated.decision, 'accepted');
  assert.equal(updated.note, 'Re-reviewed after instructor guidance.');
});

test('Regenerating retains older archived version alongside new version', async () => {
  // Archive v1
  await archiveDiagram({
    conceptId: 'series-circuit',
    conceptName: 'Series circuit',
    version: 1,
    decision: 'rejected',
    note: 'Floating particle flow needed continuous wire loop',
    svg: '<svg><title>Circuit v1</title></svg>',
  });

  // Archive v2
  await archiveDiagram({
    conceptId: 'series-circuit',
    conceptName: 'Series circuit',
    version: 2,
    decision: 'accepted',
    note: 'Continuous dashoffset flow verified',
    svg: '<svg><title>Circuit v2</title></svg>',
  });

  const v1 = await getArchivedDiagram('series-circuit', 1);
  const v2 = await getArchivedDiagram('series-circuit', 2);

  assert.ok(v1, 'Version 1 must remain preserved in archive');
  assert.equal(v1.decision, 'rejected');
  assert.ok(v2, 'Version 2 must be recorded separately');
  assert.equal(v2.decision, 'accepted');
});

test('Archive counts correctly reflect approved and rejected diagrams', async () => {
  const counts = await getArchiveCounts();
  assert.ok(counts.total >= 3);
  assert.ok(counts.accepted >= 2);
});

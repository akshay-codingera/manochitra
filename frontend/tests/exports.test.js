import test from 'node:test';
import assert from 'node:assert/strict';

const downloads = [];
let activeBlob = null;
let objectUrlCounter = 0;

class MockElement {
  constructor(tag) {
    this.tagName = tag;
    this.style = {};
    this.download = '';
    this.href = '';
  }
  click() {
    downloads.push({ filename: this.download, blob: activeBlob });
  }
  remove() {}
}

globalThis.document = {
  createElement: tag => new MockElement(tag),
  body: { append() {} },
};
globalThis.window = { setTimeout() {} };
globalThis.localStorage = {
  data: {},
  getItem(key) { return this.data[key] ?? null; },
  setItem(key, value) { this.data[key] = value; },
};
URL.createObjectURL = blob => {
  activeBlob = blob;
  return `blob:manochitra-${++objectUrlCounter}`;
};
URL.revokeObjectURL = () => {};

const { downloadSvg, downloadJsonReport, downloadCsvReport, downloadHtmlReport } = await import('../js/exports.js');

const concept = {
  id: 'pythagoras', name: "Pythagoras' theorem", subject: 'Maths', number: 1,
};
const checks = {
  valid_svg: { passed: true, detail: 'SVG parsed.' },
  within_viewbox: { passed: true, detail: 'All shapes fit.' },
  title_and_labels: { passed: true, detail: 'Title and four labels found.' },
  has_animation: { passed: true, detail: 'CSS keyframes found.' },
  scientific_terms: { passed: true, detail: 'Required terms found.' },
  concept_structure: { passed: true, detail: 'Geometry verified.' },
};
const result = {
  trace_id: 'trace-test-001', concept_id: concept.id, concept: concept.name, subject: concept.subject,
  svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><title>Test</title></svg>',
  model: 'fixture-only', status: 'PASS', checks,
  usage: { input_tokens: 100, output_tokens: 250, metadata_available: true },
  cost: { estimated_cost_usd: 0, paid_equivalent_cost_usd: 0.000655 },
  retries: { api_retries: 0, validation_retries: 0, total_retries: 0 },
  latency_ms: 240, timings_ms: { prompt_build_ms: 1, model_request_with_retries_ms: 235, validation_ms: 2 },
  attempt_history: [{ attempt: 1, passed: true, checks }], generated_at: '2026-11-24T00:00:00Z',
};

function lastDownload() {
  assert.ok(downloads.length > 0);
  return downloads.at(-1);
}

test('SVG export creates a named SVG download', async () => {
  const before = downloads.length;
  downloadSvg(result.svg, concept.name);
  const download = lastDownload();
  assert.equal(downloads.length, before + 1);
  assert.equal(download.filename, 'pythagoras-theorem.svg');
  assert.match(await download.blob.text(), /<svg/);
});

test('JSON report contains summary and concept evidence', async () => {
  downloadJsonReport([concept], [result]);
  const download = lastDownload();
  assert.equal(download.filename, 'manochitra-quality-report.json');
  const payload = JSON.parse(await download.blob.text());
  assert.equal(payload.summary.concepts_passed, 1);
  assert.equal(payload.entries[0].result.trace_id, 'trace-test-001');
});

test('CSV export neutralises spreadsheet formulas in reviewer notes', async () => {
  localStorage.setItem('manochitra-review-decisions-v1', JSON.stringify({
    pythagoras: { decision: 'approved', note: '=HYPERLINK("https://bad.example")' },
  }));
  downloadCsvReport([concept], [result]);
  const download = lastDownload();
  assert.equal(download.filename, 'manochitra-quality-summary.csv');
  const csv = await download.blob.text();
  assert.match(csv, /'=HYPERLINK/);
  assert.match(csv, /approved/);
});

test('HTML report escapes reviewer notes and includes validation evidence', async () => {
  localStorage.setItem('manochitra-review-decisions-v1', JSON.stringify({
    pythagoras: { decision: 'rejected', note: '<script>alert(1)</script>' },
  }));
  downloadHtmlReport([concept], [result]);
  const download = lastDownload();
  assert.equal(download.filename, 'manochitra-quality-report.html');
  const html = await download.blob.text();
  assert.match(html, /Generation quality report/);
  assert.match(html, /Validation evidence/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
});

test('reports preserve unavailable token-cost metadata instead of displaying a false zero', async () => {
  const incomplete = {
    ...result,
    usage: { input_tokens: 0, output_tokens: 0, metadata_available: false },
    cost: {
      estimated_cost_usd: null,
      paid_equivalent_cost_usd: null,
      pricing_assumption: 'Unavailable: usage metadata missing.',
    },
  };
  downloadJsonReport([concept], [incomplete]);
  const json = JSON.parse((await lastDownload().blob.text()));
  assert.equal(json.summary.cost_data_complete, false);
  assert.equal(json.summary.estimated_cost_usd, null);

  downloadHtmlReport([concept], [incomplete]);
  const html = await lastDownload().blob.text();
  assert.match(html, /Not available \(incomplete model usage metadata\)/);
  assert.doesNotMatch(html, /Estimated charge: \$0\.000000/);
});

test('empty report does not claim zero spend before any model has run', async () => {
  downloadJsonReport([concept], []);
  const payload = JSON.parse(await lastDownload().blob.text());
  assert.equal(payload.summary.concepts_generated, 0);
  assert.equal(payload.summary.cost_data_complete, false);
  assert.equal(payload.summary.estimated_cost_usd, null);
});

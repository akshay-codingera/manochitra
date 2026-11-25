import test from 'node:test';
import assert from 'node:assert/strict';

// Minimal mock for browser DOM environment
class MockElement {
  constructor(tag = 'div') {
    this.tagName = tag;
    this.style = {};
    this.children = [];
    this.textContent = '';
    this.innerHTML = '';
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  addEventListener() {}
  setAttribute() {}
  removeAttribute() {}
}

globalThis.document = {
  createElement: tag => new MockElement(tag),
  getElementById: () => new MockElement('div'),
  body: new MockElement('body'),
};
globalThis.window = { setTimeout() {} };
globalThis.localStorage = {
  data: {},
  getItem(key) { return this.data[key] ?? null; },
  setItem(key, value) { this.data[key] = value; },
};

const { calculateTelemetry } = await import('../js/dashboard.js');

const concepts = [
  { id: 'pythagoras', name: "Pythagoras' theorem" },
  { id: 'circle', name: 'Parts of a circle' },
  { id: 'series-circuit', name: 'Series circuit' },
  { id: 'photosynthesis', name: 'Photosynthesis' },
  { id: 'states-of-matter', name: 'States of matter' },
];

test('telemetry in zero-state returns all zeroes and dash latency', () => {
  const t = calculateTelemetry(concepts, []);
  assert.equal(t.ready, 0);
  assert.equal(t.totalConcepts, 5);
  assert.equal(t.attemptsCount, 0);
  assert.equal(t.passedCount, 0);
  assert.equal(t.failedCount, 0);
  assert.equal(t.validationRepairs, 0);
  assert.equal(t.apiRetries, 0);
  assert.equal(t.failedValidationRepairs, 0);
  assert.equal(t.failedApiRetries, 0);
  assert.equal(t.passedValidationRepairs, 0);
  assert.equal(t.passedApiRetries, 0);
  assert.equal(t.passedChecks, 0);
  assert.equal(t.totalChecks, 0);
  assert.equal(t.averageLatency, '—');
});

test('diagrams ready only counts valid final PASS with an SVG', () => {
  const results = [
    // 1: PASS with SVG -> counts as ready
    { concept_id: 'pythagoras', status: 'PASS', svg: '<svg>valid</svg>', checks: { c1: { passed: true } } },
    // 2: PASS without SVG -> must NOT count as ready
    { concept_id: 'circle', status: 'PASS', svg: '', checks: { c1: { passed: true } } },
    // 3: FAIL with SVG -> must NOT count as ready
    { concept_id: 'series-circuit', status: 'FAIL', svg: '<svg>failed-checks</svg>', checks: { c1: { passed: false } } },
    // 4: ERROR without SVG -> must NOT count as ready
    { concept_id: 'photosynthesis', status: 'ERROR', svg: null, checks: {} },
    // 5: NOT_GENERATED -> must NOT count as ready
    { concept_id: 'states-of-matter', status: 'NOT_GENERATED', svg: null },
  ];

  const t = calculateTelemetry(concepts, results);
  assert.equal(t.ready, 1, 'Only pythagoras (PASS with SVG) should be counted as ready');
  assert.equal(t.attemptsCount, 4, 'Four concepts were attempted');
  assert.equal(t.passedCount, 2, 'Pythagoras and Circle have status PASS');
  assert.equal(t.failedCount, 2, 'Series-circuit (FAIL) and Photosynthesis (ERROR) are failed requests');
});

test('retries and repairs are counted across genuine attempts without requiring SVG to exist', () => {
  const results = [
    // Passed attempt with 1 validation repair and 0 API retries
    {
      concept_id: 'pythagoras',
      status: 'PASS',
      svg: '<svg>repaired</svg>',
      retries: { api_retries: 0, validation_retries: 1, total_retries: 1 },
      latency_ms: 500,
    },
    // Failed attempt without SVG (e.g. unparseable XML) with 1 repair and 1 API retry
    {
      concept_id: 'circle',
      status: 'FAIL',
      svg: '',
      retries: { api_retries: 1, validation_retries: 1, total_retries: 2 },
      latency_ms: 800,
    },
    // Error attempt without SVG (e.g. 503 transient) with 3 API retries and 0 repairs
    {
      concept_id: 'series-circuit',
      status: 'ERROR',
      svg: null,
      retries: { api_retries: 3, validation_retries: 0, total_retries: 3 },
      latency_ms: 1200,
    },
  ];

  const t = calculateTelemetry(concepts, results);
  // Total repairs and retries must count all genuine attempts, even without SVG!
  assert.equal(t.validationRepairs, 2, 'Total repairs: 1 from pythagoras + 1 from circle (no SVG)');
  assert.equal(t.apiRetries, 4, 'Total retries: 0 + 1 from circle (no SVG) + 3 from series-circuit (no SVG)');

  // Failed requests and their retries/repairs counted separately
  assert.equal(t.failedCount, 2);
  assert.equal(t.failedValidationRepairs, 1, 'Circle failed repair');
  assert.equal(t.failedApiRetries, 4, '1 from circle + 3 from series-circuit');
  assert.equal(t.passedValidationRepairs, 1, 'Pythagoras passed repair');
  assert.equal(t.passedApiRetries, 0);

  // Latency includes all genuine attempts
  assert.equal(t.averageLatency, '833 ms');
});

import test from 'node:test';
import assert from 'node:assert/strict';

// Mock localStorage environment
let storage = {};
globalThis.localStorage = {
  getItem(key) {
    return storage[key] ?? null;
  },
  setItem(key, value) {
    storage[key] = String(value);
  },
  clear() {
    storage = {};
  },
};

const {
  STORAGE_KEY,
  getReview,
  saveDecision,
  saveNote,
  getReviewCounts,
  getAllReviews,
} = await import('../js/reviews.js');

const concepts = [
  { id: 'pythagoras', name: "Pythagoras' theorem" },
  { id: 'circle', name: 'Parts of a circle' },
  { id: 'series-circuit', name: 'Series circuit' },
  { id: 'photosynthesis', name: 'Photosynthesis' },
  { id: 'states-of-matter', name: 'States of matter' },
];

test.beforeEach(() => {
  storage = {};
});

test('Approve stores accepted decision in LocalStorage', () => {
  const result = saveDecision('pythagoras', 'accepted', 1, 'Accurate geometry');
  assert.equal(result.decision, 'accepted');
  assert.equal(result.note, 'Accurate geometry');
  assert.equal(result.version, 1);

  const stored = getReview('pythagoras', 1);
  assert.equal(stored.decision, 'accepted');
  assert.equal(stored.note, 'Accurate geometry');
});

test('Reject stores rejected decision in LocalStorage', () => {
  const result = saveDecision('circle', 'rejected', 1, 'Label collides with border');
  assert.equal(result.decision, 'rejected');
  assert.equal(result.note, 'Label collides with border');

  const stored = getReview('circle', 1);
  assert.equal(stored.decision, 'rejected');
  assert.equal(stored.note, 'Label collides with border');
});

test('Reviewer notes are persisted and updateable independently', () => {
  saveNote('series-circuit', 'Draft note in progress', 1);
  let review = getReview('series-circuit', 1);
  assert.equal(review.note, 'Draft note in progress');
  assert.equal(review.decision, 'pending');

  // Approve preserves the note
  saveDecision('series-circuit', 'accepted', 1);
  review = getReview('series-circuit', 1);
  assert.equal(review.decision, 'accepted');
  assert.equal(review.note, 'Draft note in progress');

  // Updating note preserves decision
  saveNote('series-circuit', 'Approved with battery loop verified', 1);
  review = getReview('series-circuit', 1);
  assert.equal(review.decision, 'accepted');
  assert.equal(review.note, 'Approved with battery loop verified');
});

test('Decisions for all five concepts remain strictly independent', () => {
  saveDecision('pythagoras', 'accepted', 1, 'Pythagoras approved');
  saveDecision('circle', 'rejected', 1, 'Circle rejected');
  saveDecision('series-circuit', 'accepted', 1, 'Circuit approved');
  // photosynthesis and states-of-matter left unreviewed

  assert.equal(getReview('pythagoras', 1).decision, 'accepted');
  assert.equal(getReview('circle', 1).decision, 'rejected');
  assert.equal(getReview('series-circuit', 1).decision, 'accepted');
  assert.equal(getReview('photosynthesis', 1).decision, 'pending');
  assert.equal(getReview('states-of-matter', 1).decision, 'pending');

  const counts = getReviewCounts(concepts, [
    { concept_id: 'pythagoras', version: 1 },
    { concept_id: 'circle', version: 1 },
    { concept_id: 'series-circuit', version: 1 },
    { concept_id: 'photosynthesis', version: 1 },
    { concept_id: 'states-of-matter', version: 1 },
  ]);

  assert.equal(counts.accepted, 2);
  assert.equal(counts.rejected, 1);
  assert.equal(counts.pending, 2);
  assert.equal(counts.total, 5);
});

test('Decisions survive page refresh from LocalStorage JSON', () => {
  saveDecision('photosynthesis', 'accepted', 1, 'Clean photon animation');
  const rawData = storage[STORAGE_KEY];
  assert.ok(rawData, 'LocalStorage should contain json string');

  // Simulate refresh: re-parse from storage
  const parsed = JSON.parse(rawData);
  assert.equal(parsed.photosynthesis['1'].decision, 'accepted');
  assert.equal(parsed.photosynthesis['1'].reviewer_note, 'Clean photon animation');
});

test('Users can change a previous decision later', () => {
  saveDecision('states-of-matter', 'rejected', 1, 'Particle vibration too slow');
  assert.equal(getReview('states-of-matter', 1).decision, 'rejected');

  // Change decision to accepted
  saveDecision('states-of-matter', 'accepted', 1, 'Reviewed again, meets GCSE standards');
  const updated = getReview('states-of-matter', 1);
  assert.equal(updated.decision, 'accepted');
  assert.equal(updated.note, 'Reviewed again, meets GCSE standards');
});

test('Version-specific review: new versions start with Pending Review, old decisions preserved', () => {
  // Version 1 was rejected
  saveDecision('pythagoras', 'rejected', 1, 'Hypotenuse label needed margin');
  assert.equal(getReview('pythagoras', 1).decision, 'rejected');

  // Version 2 generated
  const v2Review = getReview('pythagoras', 2);
  assert.equal(v2Review.decision, 'pending', 'New version must start as Pending Review');
  assert.equal(v2Review.note, '', 'New version note should start fresh or pending');

  // Older version 1 review remains intact in history
  const v1Preserved = getReview('pythagoras', 1);
  assert.equal(v1Preserved.decision, 'rejected');
  assert.equal(v1Preserved.note, 'Hypotenuse label needed margin');
});

test('Malformed LocalStorage data is handled safely without crashing', () => {
  storage[STORAGE_KEY] = 'INVALID_JSON_CORRUPTED{[[[';
  const review = getReview('pythagoras', 1);
  assert.equal(review.decision, 'pending');
  assert.equal(review.note, '');

  // Saving should still work and overwrite corrupted storage with valid JSON
  saveDecision('pythagoras', 'accepted', 1, 'Recovered from corrupt storage');
  assert.equal(getReview('pythagoras', 1).decision, 'accepted');
});

test('Unavailable/restricted localStorage handles gracefully', () => {
  const originalGetItem = localStorage.getItem;
  localStorage.getItem = () => { throw new Error('SecurityError: Access is denied'); };

  // Must not throw
  const review = getReview('pythagoras', 1);
  assert.equal(review.decision, 'pending');

  localStorage.getItem = originalGetItem;
});

const STORAGE_KEY = 'manochitra-review-decisions-v1';

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function writeAll(reviews) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
  } catch {
    // Ignore storage quota errors in restricted environments
  }
}

export function syncServerReviews(serverReviews) {
  if (!serverReviews || typeof serverReviews !== 'object') return;
  const local = readAll();
  const merged = { ...serverReviews, ...local };
  writeAll(merged);
}

export function getReview(conceptId) {
  return readAll()[conceptId] || { decision: 'pending', note: '', version: 1 };
}

export function saveDecision(conceptId, decision, version = null) {
  const reviews = readAll();
  const current = getReview(conceptId);
  reviews[conceptId] = {
    ...current,
    concept_id: conceptId,
    decision,
    version: version !== null ? version : (current.version || 1),
    updated_at: new Date().toISOString(),
  };
  writeAll(reviews);
  return reviews[conceptId];
}

export function saveNote(conceptId, note, version = null) {
  const reviews = readAll();
  const current = getReview(conceptId);
  reviews[conceptId] = {
    ...current,
    concept_id: conceptId,
    note,
    version: version !== null ? version : (current.version || 1),
    updated_at: new Date().toISOString(),
  };
  writeAll(reviews);
  return reviews[conceptId];
}

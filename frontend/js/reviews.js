/**
 * MANOCHITRA — Human Review Persistence
 *
 * Manages human reviewer decisions (accepted, rejected, pending) and reviewer notes
 * in browser LocalStorage.
 *
 * Storage Key: manochitra_reviews_v1
 * Structure: Stored per concept ID and diagram version.
 *
 * Example:
 * {
 *   "pythagoras": {
 *     "1": {
 *       "decision": "accepted",
 *       "reviewer_note": "Correct geometry and readable labels.",
 *       "updated_at": "2026-11-25T14:30:00.000Z"
 *     }
 *   }
 * }
 */

export const STORAGE_KEY = 'manochitra_reviews_v1';
export const LEGACY_STORAGE_KEY = 'manochitra-review-decisions-v1';

let lastSeenLegacyRaw = null;

function readStorage() {
  if (typeof localStorage === 'undefined') return {};

  let primary = null;
  let primaryRaw = null;
  try {
    primaryRaw = localStorage.getItem(STORAGE_KEY);
    if (primaryRaw) primary = JSON.parse(primaryRaw);
  } catch {}

  let legacy = null;
  let legacyRaw = null;
  try {
    legacyRaw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (legacyRaw) legacy = JSON.parse(legacyRaw);
  } catch {}

  // If legacy storage was updated externally (e.g. test harness setting LEGACY_STORAGE_KEY)
  if (legacyRaw && legacyRaw !== lastSeenLegacyRaw) {
    lastSeenLegacyRaw = legacyRaw;
    const migrated = {};
    for (const [cid, val] of Object.entries(legacy || {})) {
      if (val && typeof val === 'object') {
        const ver = String(val.version || 1);
        migrated[cid] = {
          [ver]: {
            decision: val.decision || 'pending',
            reviewer_note: val.note || val.reviewer_note || '',
            updated_at: val.updated_at || new Date().toISOString(),
          },
        };
      }
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
    } catch {}
    return migrated;
  }

  if (primary && typeof primary === 'object' && Object.keys(primary).length > 0) {
    return primary;
  }

  if (legacy && typeof legacy === 'object') {
    const migrated = {};
    for (const [cid, val] of Object.entries(legacy)) {
      if (val && typeof val === 'object') {
        const ver = String(val.version || 1);
        migrated[cid] = {
          [ver]: {
            decision: val.decision || 'pending',
            reviewer_note: val.note || val.reviewer_note || '',
            updated_at: val.updated_at || new Date().toISOString(),
          },
        };
      }
    }
    return migrated;
  }

  return {};
}

function writeStorage(reviews) {
  if (typeof localStorage === 'undefined') return;
  try {
    const serialized = JSON.stringify(reviews);
    localStorage.setItem(STORAGE_KEY, serialized);

    // Also sync flat legacy representation for legacy consumers/tests
    const flatLegacy = {};
    for (const [cid, vers] of Object.entries(reviews)) {
      if (vers && typeof vers === 'object') {
        const latestKey = Object.keys(vers).sort((a, b) => Number(b) - Number(a))[0] || '1';
        const entry = vers[latestKey];
        if (entry) {
          flatLegacy[cid] = {
            decision: entry.decision,
            note: entry.reviewer_note,
            version: Number(latestKey),
            updated_at: entry.updated_at,
          };
        }
      }
    }
    const legSerialized = JSON.stringify(flatLegacy);
    localStorage.setItem(LEGACY_STORAGE_KEY, legSerialized);
    lastSeenLegacyRaw = legSerialized;
  } catch {
    // Ignore storage quota or security restriction errors in sandboxed iframes
  }
}

export function getAllReviews() {
  return readStorage();
}

export function getReview(conceptId, version = 1) {
  if (!conceptId) return { decision: 'pending', note: '', version: 1 };
  const all = readStorage();
  const conceptRecord = all[conceptId];
  const vKey = String(version || 1);

  if (conceptRecord && typeof conceptRecord === 'object') {
    // Versioned lookup
    if (conceptRecord[vKey] && typeof conceptRecord[vKey] === 'object') {
      const entry = conceptRecord[vKey];
      return {
        concept_id: conceptId,
        decision: entry.decision || 'pending',
        note: entry.reviewer_note ?? entry.note ?? '',
        version: Number(vKey),
        updated_at: entry.updated_at || null,
      };
    }
    // Flat fallback if stored flat
    if (typeof conceptRecord.decision === 'string') {
      return {
        concept_id: conceptId,
        decision: conceptRecord.decision,
        note: conceptRecord.reviewer_note ?? conceptRecord.note ?? '',
        version: Number(conceptRecord.version || 1),
        updated_at: conceptRecord.updated_at || null,
      };
    }
  }

  return {
    concept_id: conceptId,
    decision: 'pending',
    note: '',
    version: Number(version || 1),
    updated_at: null,
  };
}

export function saveDecision(conceptId, rawDecision, version = 1, note = null) {
  if (!conceptId) return null;
  const all = readStorage();
  if (!all[conceptId] || typeof all[conceptId] !== 'object') {
    all[conceptId] = {};
  }

  const vKey = String(version || 1);
  const existing = getReview(conceptId, version);

  const updatedEntry = {
    decision: rawDecision || 'pending',
    reviewer_note: note !== null ? String(note) : (existing.note || ''),
    updated_at: new Date().toISOString(),
  };

  all[conceptId][vKey] = updatedEntry;
  writeStorage(all);

  return {
    concept_id: conceptId,
    decision: updatedEntry.decision,
    note: updatedEntry.reviewer_note,
    version: Number(vKey),
    updated_at: updatedEntry.updated_at,
  };
}

export function saveNote(conceptId, note, version = 1) {
  if (!conceptId) return null;
  const all = readStorage();
  if (!all[conceptId] || typeof all[conceptId] !== 'object') {
    all[conceptId] = {};
  }

  const vKey = String(version || 1);
  const existing = getReview(conceptId, version);

  const updatedEntry = {
    decision: existing.decision || 'pending',
    reviewer_note: String(note ?? ''),
    updated_at: new Date().toISOString(),
  };

  all[conceptId][vKey] = updatedEntry;
  writeStorage(all);

  return {
    concept_id: conceptId,
    decision: updatedEntry.decision,
    note: updatedEntry.reviewer_note,
    version: Number(vKey),
    updated_at: updatedEntry.updated_at,
  };
}

export function getReviewCounts(concepts = [], results = []) {
  let accepted = 0;
  let rejected = 0;
  let pending = 0;

  for (const concept of concepts) {
    const result = results.find(r => r.concept_id === concept.id);
    const ver = result?.version || 1;
    const rev = getReview(concept.id, ver);

    if (rev.decision === 'accepted' || rev.decision === 'approved') {
      accepted += 1;
    } else if (rev.decision === 'rejected') {
      rejected += 1;
    } else {
      pending += 1;
    }
  }

  return {
    accepted,
    rejected,
    pending,
    total: concepts.length,
  };
}

export function syncServerReviews(serverReviews) {
  if (!serverReviews || typeof serverReviews !== 'object') return;
  const local = readStorage();

  for (const [cid, sRev] of Object.entries(serverReviews)) {
    if (!sRev || typeof sRev !== 'object') continue;
    const ver = String(sRev.version || 1);
    if (!local[cid]) local[cid] = {};

    // Only apply server review if local has no decision for this version
    if (!local[cid][ver] || !local[cid][ver].decision || local[cid][ver].decision === 'pending') {
      local[cid][ver] = {
        decision: sRev.decision || 'pending',
        reviewer_note: sRev.note || sRev.reviewer_note || '',
        updated_at: sRev.updated_at || new Date().toISOString(),
      };
    }
  }

  writeStorage(local);
}

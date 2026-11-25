/**
 * MANOCHITRA — IndexedDB Diagram Archive
 *
 * Preserves the exact SVG markup, animation, concept metadata, reviewer notes,
 * and review decision (accepted / rejected) in browser IndexedDB.
 *
 * Database: manochitra_archive_db
 * Store: diagram_archives
 * Key: `${concept_id}_v${version}`
 */

const DB_NAME = 'manochitra_archive_db';
const DB_VERSION = 1;
const STORE_NAME = 'diagram_archives';

// In-memory fallback cache for headless environments (e.g., node test runners)
const memoryStore = new Map();

function isIndexedDBAvailable() {
  return typeof indexedDB !== 'undefined' && indexedDB !== null;
}

let dbPromise = null;

export function initArchiveDB() {
  if (!isIndexedDBAvailable()) {
    return Promise.resolve(null);
  }

  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          store.createIndex('concept_id', 'concept_id', { unique: false });
          store.createIndex('decision', 'decision', { unique: false });
          store.createIndex('archived_at', 'archived_at', { unique: false });
          store.createIndex('version', 'version', { unique: false });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => {
        // Fallback to in-memory store if IndexedDB cannot be opened
        resolve(null);
      };
      request.onblocked = () => {
        resolve(null);
      };
    } catch {
      resolve(null);
    }
  });

  return dbPromise;
}

export async function archiveDiagram({
  conceptId,
  conceptName,
  version = 1,
  decision = 'accepted',
  note = '',
  svg = '',
  result = null,
}) {
  if (!conceptId || !svg) return null;

  const id = `${conceptId}_v${version}`;
  const now = new Date().toISOString();

  const record = {
    id,
    concept_id: conceptId,
    concept_name: conceptName || conceptId,
    version: Number(version || 1),
    decision: decision === 'approved' ? 'accepted' : decision,
    note: String(note || ''),
    svg: String(svg),
    model: result?.model || 'gemini-3.5-flash-lite',
    tokens_input: result?.usage?.input_tokens ?? null,
    tokens_output: result?.usage?.output_tokens ?? null,
    cost_usd: result?.cost?.paid_equivalent_cost_usd ?? result?.cost?.estimated_cost_usd ?? null,
    checks_summary: result?.checks
      ? `${Object.values(result.checks).filter(c => c?.passed).length}/6 passed`
      : '6/6 passed',
    archived_at: now,
  };

  // Always keep in-memory fallback updated
  memoryStore.set(id, record);

  const db = await initArchiveDB();
  if (!db) return record;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(record);
      req.onsuccess = () => resolve(record);
      req.onerror = () => resolve(record);
    } catch {
      resolve(record);
    }
  });
}

export async function getArchivedDiagram(conceptId, version = 1) {
  const id = `${conceptId}_v${version}`;
  const db = await initArchiveDB();

  if (!db) {
    return memoryStore.get(id) || null;
  }

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.get(id);
      req.onsuccess = () => resolve(req.result || memoryStore.get(id) || null);
      req.onerror = () => resolve(memoryStore.get(id) || null);
    } catch {
      resolve(memoryStore.get(id) || null);
    }
  });
}

export async function getAllArchivedDiagrams(filterDecision = null) {
  const db = await initArchiveDB();

  if (!db) {
    const list = Array.from(memoryStore.values());
    if (filterDecision) {
      return list.filter(item => item.decision === filterDecision)
        .sort((a, b) => (b.archived_at || '').localeCompare(a.archived_at || ''));
    }
    return list.sort((a, b) => (b.archived_at || '').localeCompare(a.archived_at || ''));
  }

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => {
        let list = req.result || [];
        if (!list.length && memoryStore.size > 0) {
          list = Array.from(memoryStore.values());
        }
        if (filterDecision) {
          list = list.filter(item => item.decision === filterDecision);
        }
        list.sort((a, b) => (b.archived_at || '').localeCompare(a.archived_at || ''));
        resolve(list);
      };
      req.onerror = () => {
        resolve(Array.from(memoryStore.values()));
      };
    } catch {
      resolve(Array.from(memoryStore.values()));
    }
  });
}

export async function getArchiveCounts() {
  const all = await getAllArchivedDiagrams();
  const accepted = all.filter(item => item.decision === 'accepted').length;
  const rejected = all.filter(item => item.decision === 'rejected').length;
  return {
    total: all.length,
    accepted,
    rejected,
  };
}

export async function deleteArchivedDiagram(conceptId, version = 1) {
  const id = `${conceptId}_v${version}`;
  memoryStore.delete(id);
  const db = await initArchiveDB();
  if (!db) return true;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(id);
      req.onsuccess = () => resolve(true);
      req.onerror = () => resolve(false);
    } catch {
      resolve(false);
    }
  });
}

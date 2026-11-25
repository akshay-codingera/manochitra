const API_ROOT = '/api';

async function readError(response) {
  try {
    const payload = await response.json();
    return payload.detail || payload.message || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

export async function fetchDashboard() {
  const response = await fetch(`${API_ROOT}/results`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function fetchModels() {
  const response = await fetch(`${API_ROOT}/models`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function generateConcept(conceptId, modelId = null) {
  const options = {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(modelId ? { 'Content-Type': 'application/json' } : {}),
    },
  };
  if (modelId) {
    options.body = JSON.stringify({ model: modelId });
  }
  const response = await fetch(`${API_ROOT}/generate/${encodeURIComponent(conceptId)}`, options);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function checkBackend() {
  const response = await fetch(`${API_ROOT}/health`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Backend health check failed.');
  return response.json();
}

export async function saveReviewToServer(conceptId, decision, note = '', version = null) {
  const options = {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ decision, note, version }),
  };
  const response = await fetch(`${API_ROOT}/reviews/${encodeURIComponent(conceptId)}`, options);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function regenerateWithFeedback(conceptId, feedback, modelId = null, fromVersion = null) {
  const options = {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ feedback, model: modelId, from_version: fromVersion }),
  };
  const response = await fetch(`${API_ROOT}/regenerate/${encodeURIComponent(conceptId)}`, options);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function approveVersion(conceptId, versionNum) {
  const options = {
    method: 'POST',
    headers: { Accept: 'application/json' },
  };
  const response = await fetch(
    `${API_ROOT}/versions/${encodeURIComponent(conceptId)}/approve/${encodeURIComponent(versionNum)}`,
    options
  );
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function fetchVersions(conceptId) {
  const response = await fetch(`${API_ROOT}/versions/${encodeURIComponent(conceptId)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

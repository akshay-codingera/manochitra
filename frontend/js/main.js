import { generateConcept } from './api.js';
import { renderRows, renderComparisonGrid } from './dashboard.js';
import { downloadCsvReport, downloadHtmlReport, downloadJsonReport } from './exports.js';
import { initialiseTheme } from './theme.js';
import { syncServerReviews } from './reviews.js';

let concepts = [];
let results = [];
let modelRuns = [];
let models = [];
let selectedModelId = 'gemini-3.5-flash-lite';
let defaultModelId = 'gemini-3.5-flash-lite';

const generateButton = document.getElementById('generate-button');
const conceptSelect = document.getElementById('concept-select');
const messageBox = document.getElementById('global-message');

const needleGroup = document.getElementById('gauge-needle-group');
const btnLite = document.getElementById('btn-model-lite');
const btnFlash = document.getElementById('btn-model-flash');

const specName = document.getElementById('spec-name');
const specId = document.getElementById('spec-id');
const specRole = document.getElementById('spec-role');
const specTier = document.getElementById('spec-tier');
const specAccess = document.getElementById('spec-access');
const specPricing = document.getElementById('spec-pricing');

const tabStandard = document.getElementById('tab-standard');
const tabComparison = document.getElementById('tab-comparison');
const standardView = document.getElementById('standard-review-view');
const comparisonView = document.getElementById('comparison-view');

const DEFAULT_MODELS = [
  {
    id: 'gemini-3.5-flash-lite',
    name: 'Gemini 3.5 Flash-Lite',
    short_name: '3.5 Flash-Lite',
    role: 'Efficient, cost-conscious generation.',
    free_tier_listed: true,
    account_access_status: 'UNVERIFIED',
    pricing_text: '$0.30 / 1M input · $2.50 / 1M output',
    gauge_angle: -42,
  },
  {
    id: 'gemini-3.8-flash',
    name: 'Gemini 3.8 Flash',
    short_name: '3.8 Flash',
    role: 'Higher-capability generation.',
    free_tier_listed: true,
    account_access_status: 'UNVERIFIED',
    pricing_text: 'Through 2026-12-31: $0.75 in · $3.75 out / 1M tokens (from 2027-01-01: $1.50 in · $7.50 out)',
    gauge_angle: 42,
  },
];

function showMessage(message, kind = 'info') {
  messageBox.hidden = false;
  messageBox.className = `global-message ${kind}`;
  messageBox.textContent = message;
}

function hideMessage() {
  messageBox.hidden = true;
  messageBox.textContent = '';
  messageBox.className = 'global-message';
}

function setGenerating(isGenerating) {
  generateButton.disabled = isGenerating;
  generateButton.querySelector('span:last-child').textContent = isGenerating ? 'Generating…' : 'Generate SVG';
  generateButton.querySelector('.generate-icon').textContent = isGenerating ? '◌' : '↗';
}

function getModelData(modelId) {
  const found = models.find(m => m.id === modelId);
  if (found) {
    const is38 = modelId.includes('3.8');
    return {
      ...found,
      pricing_text: is38
        ? 'Through 2026-12-31: $0.75 in · $3.75 out / 1M tokens (from 2027-01-01: $1.50 in · $7.50 out)'
        : '$0.30 / 1M input · $2.50 / 1M output',
      gauge_angle: is38 ? 42 : -42,
    };
  }
  return DEFAULT_MODELS.find(m => m.id === modelId) || DEFAULT_MODELS[0];
}

export function selectModel(modelId) {
  selectedModelId = modelId;
  window.__ACTIVE_MODEL__ = modelId;
  const data = getModelData(modelId);
  const isFlash = modelId === 'gemini-3.8-flash';

  // Rotate gauge needle
  if (needleGroup) {
    needleGroup.setAttribute('transform', `rotate(${data.gauge_angle} 90 86)`);
  }

  // Update button active state & ARIA
  if (btnLite && btnFlash) {
    btnLite.classList.toggle('active', !isFlash);
    btnLite.setAttribute('aria-checked', !isFlash ? 'true' : 'false');
    btnFlash.classList.toggle('active', isFlash);
    btnFlash.setAttribute('aria-checked', isFlash ? 'true' : 'false');
  }

  // Update spec readout panel
  if (specName) specName.textContent = data.name;
  if (specId) specId.textContent = data.id;
  if (specRole) specRole.textContent = data.role;
  if (specTier) specTier.textContent = 'Free of charge tier (Google AI Studio)';
  if (specAccess) specAccess.textContent = 'UNVERIFIED';
  if (specPricing) specPricing.textContent = data.pricing_text;

  // Update signal strip
  const statusEl = document.getElementById('model-status');
  if (statusEl) {
    statusEl.textContent = `Instrument target: ${data.name} · Access: UNVERIFIED`;
  }

  // Update comparison grid target highlight if present
  if (document.getElementById('comparison-grid')) {
    const allRuns = [...results];
    for (const run of modelRuns) {
      const idx = allRuns.findIndex(r => r.concept_id === run.concept_id && r.model === run.model);
      if (idx >= 0) allRuns[idx] = run;
      else allRuns.push(run);
    }
    renderComparisonGrid(concepts, allRuns, selectedModelId);
  }
}

function setViewMode(mode) {
  const isComparison = mode === 'comparison';
  if (tabStandard && tabComparison && standardView && comparisonView) {
    tabStandard.classList.toggle('active', !isComparison);
    tabStandard.setAttribute('aria-selected', !isComparison ? 'true' : 'false');
    tabComparison.classList.toggle('active', isComparison);
    tabComparison.setAttribute('aria-selected', isComparison ? 'true' : 'false');

    standardView.hidden = isComparison;
    comparisonView.hidden = !isComparison;
  }
}

function loadDashboardFromInitialHTML() {
  const dataNode = document.getElementById('initial-data');
  if (!dataNode) {
    throw new Error('The saved initial result snapshot was not embedded by the backend.');
  }
  const snapshot = JSON.parse(dataNode.textContent || '{}');
  defaultModelId = snapshot.default_model || 'gemini-3.5-flash-lite';
  concepts = snapshot.concepts || [];
  results = snapshot.results || [];
  modelRuns = snapshot.model_runs || [];
  models = snapshot.models || DEFAULT_MODELS;

  if (snapshot.reviews) {
    syncServerReviews(snapshot.reviews);
  }

  populateConceptSelector(concepts);
  selectModel(defaultModelId);
  renderRows(concepts, results, selectedModelId, modelRuns);

  const statusEl = document.getElementById('model-status');
  if (statusEl) {
    statusEl.textContent = snapshot.model_configured
      ? `Credentials configured · Active: ${snapshot.model || selectedModelId}`
      : 'Backend ready · API key not set';
  }

  if (!snapshot.model_configured) {
    showMessage('The saved dashboard is available. Live generation is disabled until GEMINI_API_KEY is configured on the backend.', 'info');
  } else if (results.length < 5 || results.filter(item => item.status === 'PASS').length < 5) {
    showMessage('This page loaded the saved JSON snapshot without calling Gemini. Run the initial batch script and inspect all five outputs before submitting.', 'info');
  }
}

function populateConceptSelector(items) {
  conceptSelect.replaceChildren();
  for (const concept of items) {
    const option = document.createElement('option');
    option.value = concept.id;
    option.textContent = concept.name;
    conceptSelect.append(option);
  }
}

async function handleGenerate() {
  const conceptId = conceptSelect.value;
  const concept = concepts.find(item => item.id === conceptId);
  if (!concept) {
    showMessage('Choose one of the five assignment concepts.', 'error');
    return;
  }

  hideMessage();
  setGenerating(true);
  const activeModel = getModelData(selectedModelId);
  showMessage(`Generating ${concept.name} using ${activeModel.name} (${selectedModelId}). The backend will call Gemini, validate the SVG and use at most one corrective generation if a check fails.`, 'info');

  try {
    const result = await generateConcept(conceptId, selectedModelId);
    const runModel = result.model || selectedModelId;

    // 1. Update modelRuns by (concept_id, model) so models NEVER overwrite each other
    const existingRunIdx = modelRuns.findIndex(r => r.concept_id === conceptId && (r.model || selectedModelId) === runModel);
    if (existingRunIdx >= 0) {
      modelRuns[existingRunIdx] = result;
    } else {
      modelRuns.push(result);
    }

    // 2. Only update canonical results array if this run was for the canonical model
    if (runModel === defaultModelId) {
      results = [...results.filter(item => item.concept_id !== conceptId), result];
    }

    renderRows(concepts, results, selectedModelId, modelRuns);
    if (result.status === 'PASS') {
      showMessage(`${concept.name} passed all code checks with ${result.model || selectedModelId}. ${result.retries.total_retries} total retry/retries; ${Math.round(result.latency_ms)} ms measured pipeline time.`, 'success');
    } else {
      showMessage(`${concept.name} finished with status ${result.status} on ${result.model || selectedModelId}. ${result.last_error || 'Inspect the failed checks in the review board.'}`, 'error');
    }
  } catch (error) {
    showMessage(`Generation failed: ${error.message}. Your saved diagrams remain available; inspect the backend logs for details.`, 'error');
  } finally {
    setGenerating(false);
  }
}

// Event Listeners
generateButton?.addEventListener('click', handleGenerate);

btnLite?.addEventListener('click', () => selectModel('gemini-3.5-flash-lite'));
btnFlash?.addEventListener('click', () => selectModel('gemini-3.8-flash'));

tabStandard?.addEventListener('click', () => setViewMode('standard'));
tabComparison?.addEventListener('click', () => setViewMode('comparison'));

initialiseTheme();
try {
  loadDashboardFromInitialHTML();
} catch (error) {
  document.getElementById('model-status').textContent = 'Snapshot unavailable';
  showMessage(`Could not load the saved dashboard snapshot: ${error.message}`, 'error');
}

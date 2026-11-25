import { getReview, saveDecision, saveNote } from './reviews.js';
import { downloadPng, downloadSvg } from './exports.js';
import { regenerateWithFeedback, saveReviewToServer, approveVersion } from './api.js';

const CHECKS = [
  ['valid_svg', 'Valid SVG', 'Mandatory'],
  ['within_viewbox', 'Inside viewBox', 'Mandatory'],
  ['title_and_labels', 'Title + labels', 'Mandatory'],
  ['has_animation', 'Animation', 'Mandatory'],
  ['scientific_terms', 'Science terms', 'Custom'],
  ['concept_structure', 'Concept structure', 'Advanced'],
];

let currentConcepts = [];
let currentResults = [];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatCost(result) {
  const cost = result?.cost?.estimated_cost_usd;
  if (typeof cost !== 'number') return '—';
  return `$${cost.toFixed(5)}`;
}

function getCheck(result, key) {
  return result?.checks?.[key] || { passed: false, detail: 'Not generated yet.' };
}

function createConceptCell(concept) {
  const cell = element('td', 'concept-cell');
  cell.append(element('span', 'concept-number', `0${concept.number} / 05`));
  cell.append(element('strong', 'concept-name', concept.name));
  cell.append(element('span', 'subject-tag', concept.subject.toUpperCase()));
  return cell;
}

function createPlaceholder(concept, result) {
  const placeholder = element('div', 'diagram-placeholder');
  const inner = element('div', 'placeholder-inner');
  inner.append(element('div', 'placeholder-symbol', result?.status === 'ERROR' ? '!' : '◌'));
  inner.append(element('strong', '', result?.status === 'ERROR' ? 'Generation needs attention' : 'Awaiting first generation'));
  const note = result?.last_error || 'The initial diagram batch is created with the command in the README.';
  inner.append(element('small', '', note));
  placeholder.append(inner);
  return placeholder;
}

let currentModalConcept = null;
let currentModalResult = null;
let isAnimationPaused = false;
let modalInitialized = false;

function getDefaultReviewRequirements(conceptId) {
  switch (conceptId) {
    case 'circle':
      return [
        'Circumference leader line clearly touches the circle boundary curve.',
        'Diameter is marked passing through center with explicit d = 2r notation.',
        'Labels have minimum 24px margin from canvas borders without overlap.'
      ];
    case 'series-circuit':
      return [
        'Single continuous closed circuit path (no branched or open loops).',
        'DC battery source and two light bulbs connected in direct series.',
        'Continuous wire flow animation (animated stroke-dashoffset, no detached floating particles).'
      ];
    case 'photosynthesis':
      return [
        'Green leaf serves as the central chemical reaction site.',
        'Directed arrow flow: Inputs (CO₂ + H₂O + light) → Leaf → Outputs (Glucose + O₂).',
        'Visible photon animation entering the leaf blade.'
      ];
    case 'states-of-matter':
      return [
        'Three equal-width side-by-side vessels (Solid, Liquid, Gas) clearly labelled.',
        'Gas particle spacing is significantly wider than solid (≥ 2.2× solid spacing).',
        'Smooth thermal vibration in solid and rapid free translation in gas.'
      ];
    case 'pythagoras':
    default:
      return [
        'Right-angled triangle with sides a, b, and hypotenuse c.',
        'Squares constructed on all three sides with clear area formulas a² + b² = c².',
        'Geometric proof animation with all elements staying strictly inside the 960×640 viewBox.'
      ];
  }
}

export function openInspectorModal(concept, result) {
  if (typeof document === 'undefined') return;
  const modal = document.getElementById('svg-inspector-modal');
  if (!modal || !result?.svg) return;

  currentModalConcept = concept;
  currentModalResult = result;
  isAnimationPaused = false;

  const numEl = document.getElementById('modal-concept-num');
  const verSuffix = result.version ? ` · v${result.version}` : '';
  if (numEl) numEl.textContent = `0${concept.number} / 05${verSuffix}`;

  const nameEl = document.getElementById('modal-concept-name');
  if (nameEl) nameEl.textContent = concept.name;

  const tagEl = document.getElementById('modal-subject-tag');
  if (tagEl) tagEl.textContent = (concept.subject || 'SCIENCE').toUpperCase();

  const badgeEl = document.getElementById('modal-model-badge');
  if (badgeEl) {
    const model = result.model || 'gemini-3.5-flash-lite';
    const isFlash = model.includes('3.8');
    badgeEl.textContent = model;
    badgeEl.className = `model-badge ${isFlash ? 'flash' : 'lite'}`;
  }

  const container = document.getElementById('modal-svg-container');
  if (container) {
    container.innerHTML = result.svg;
    if (result.regeneration_metadata?.feedback) {
      const banner = element('div', 'modal-feedback-banner');
      banner.append(element('strong', '', `REVISED WITH HUMAN FEEDBACK (v${result.regeneration_metadata.from_version} → v${result.version})`));
      banner.append(element('span', '', `"${result.regeneration_metadata.feedback}"`));
      container.prepend(banner);
    }
    const svgEl = container.querySelector('svg');
    if (svgEl) {
      svgEl.setAttribute('role', 'img');
      svgEl.setAttribute('aria-label', `${concept.name} animated SVG`);
    }
  }

  const checksGrid = document.getElementById('modal-checks-summary');
  if (checksGrid) {
    checksGrid.replaceChildren();
    for (const [key, label] of CHECKS) {
      const check = getCheck(result, key);
      const pill = element('div', `modal-check-pill ${check.passed ? 'pass' : 'fail'}`);
      pill.append(element('span', '', check.passed ? '✓' : '×'));
      pill.append(element('span', '', label));
      checksGrid.append(pill);
    }
  }

  const reviewList = document.getElementById('modal-review-requirements');
  if (reviewList) {
    reviewList.replaceChildren();
    const requirements = result.visual_quality?.review_requirements || getDefaultReviewRequirements(concept.id);
    for (const req of requirements) {
      const li = element('li', 'modal-req-item', req);
      reviewList.append(li);
    }
  }

  updateAnimationStatus(false);

  if (typeof modal.showModal === 'function') {
    modal.showModal();
  } else {
    modal.setAttribute('open', '');
  }
}

export function setAnimationPaused(paused) {
  isAnimationPaused = paused;
  if (typeof document === 'undefined') return;
  const container = document.getElementById('modal-svg-container');
  if (!container) return;
  const svgEl = container.querySelector('svg');
  if (!svgEl) return;

  if (paused) {
    if (typeof svgEl.pauseAnimations === 'function') {
      try { svgEl.pauseAnimations(); } catch (_) {}
    }
  } else {
    if (typeof svgEl.unpauseAnimations === 'function') {
      try { svgEl.unpauseAnimations(); } catch (_) {}
    }
  }

  const state = paused ? 'paused' : 'running';
  svgEl.style.animationPlayState = state;
  svgEl.querySelectorAll('*').forEach(el => {
    el.style.animationPlayState = state;
  });

  updateAnimationStatus(paused);
}

function updateAnimationStatus(paused) {
  if (typeof document === 'undefined') return;
  const btn = document.getElementById('modal-play-pause');
  if (btn) {
    btn.textContent = paused ? '▶ Play' : '⏸ Pause';
    btn.setAttribute('aria-label', paused ? 'Play animation' : 'Pause animation');
  }

  const pill = document.getElementById('modal-anim-status');
  if (pill) {
    pill.textContent = paused ? '⏸ Paused' : '● Animating';
    pill.className = `anim-status-pill ${paused ? 'paused' : 'running'}`;
  }
}

export function replayAnimation() {
  if (typeof document === 'undefined') return;
  const container = document.getElementById('modal-svg-container');
  if (!container) return;
  const svgEl = container.querySelector('svg');
  if (!svgEl) return;

  const clone = svgEl.cloneNode(true);
  container.replaceChildren(clone);

  if (typeof clone.setCurrentTime === 'function') {
    try { clone.setCurrentTime(0); } catch (_) {}
    try { clone.unpauseAnimations(); } catch (_) {}
  }

  isAnimationPaused = false;
  clone.style.animationPlayState = 'running';
  clone.querySelectorAll('*').forEach(el => {
    el.style.animationPlayState = 'running';
  });

  updateAnimationStatus(false);
}

export function setupInspectorModal() {
  if (modalInitialized || typeof document === 'undefined') return;
  const modal = document.getElementById('svg-inspector-modal');
  if (!modal) return;
  modalInitialized = true;

  const closeBtn = document.getElementById('modal-close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      if (typeof modal.close === 'function') modal.close();
      else modal.removeAttribute('open');
    });
  }

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      if (typeof modal.close === 'function') modal.close();
      else modal.removeAttribute('open');
    }
  });

  const playPauseBtn = document.getElementById('modal-play-pause');
  if (playPauseBtn) {
    playPauseBtn.addEventListener('click', () => {
      setAnimationPaused(!isAnimationPaused);
    });
  }

  const replayBtn = document.getElementById('modal-replay');
  if (replayBtn) {
    replayBtn.addEventListener('click', () => {
      replayAnimation();
    });
  }

  const downloadSvgBtn = document.getElementById('modal-download-svg');
  if (downloadSvgBtn) {
    downloadSvgBtn.addEventListener('click', () => {
      if (currentModalResult?.svg && currentModalConcept) {
        downloadSvg(currentModalResult.svg, currentModalConcept.name);
      }
    });
  }

  const downloadPngBtn = document.getElementById('modal-download-png');
  if (downloadPngBtn) {
    downloadPngBtn.addEventListener('click', async () => {
      if (!currentModalResult?.svg || !currentModalConcept) return;
      downloadPngBtn.disabled = true;
      const old = downloadPngBtn.textContent;
      downloadPngBtn.textContent = 'Preparing…';
      try {
        await downloadPng(currentModalResult.svg, currentModalConcept.name);
      } catch (err) {
        if (typeof window !== 'undefined' && window.alert) {
          window.alert(`PNG export failed: ${err.message}`);
        }
      } finally {
        downloadPngBtn.disabled = false;
        downloadPngBtn.textContent = old;
      }
    });
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', (e) => {
      if (!modal.open && !modal.hasAttribute('open')) return;
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag === 'textarea' || tag === 'input') return;

      if (e.code === 'Space') {
        e.preventDefault();
        setAnimationPaused(!isAnimationPaused);
      } else if (e.code === 'KeyR') {
        e.preventDefault();
        replayAnimation();
      }
    });
  }
}

function createIllustrationCell(concept, result) {
  const cell = element('td', 'illustration-cell');
  const frame = element('div', 'diagram-frame');
  const validSvg = Boolean(result?.svg && getCheck(result, 'valid_svg').passed);

  if (validSvg) {
    frame.setAttribute('tabindex', '0');
    frame.setAttribute('role', 'button');
    frame.setAttribute('aria-label', `Inspect full-size diagram for ${concept.name}`);
    frame.style.cursor = 'pointer';
    frame.addEventListener('click', () => openInspectorModal(concept, result));
    frame.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openInspectorModal(concept, result);
      }
    });

    const iframe = element('iframe', 'diagram-preview');
    iframe.title = `${concept.name} animated SVG preview`;
    iframe.setAttribute('sandbox', '');
    iframe.setAttribute('loading', 'lazy');
    const source = new Blob([result.svg], { type: 'image/svg+xml;charset=utf-8' });
    const sourceUrl = URL.createObjectURL(source);
    iframe.src = sourceUrl;
    iframe.addEventListener('load', () => URL.revokeObjectURL(sourceUrl), { once: true });
    frame.append(iframe);
  } else {
    frame.append(createPlaceholder(concept, result));
  }
  cell.append(frame);

  const footer = element('div', 'preview-footer');
  const status = result?.status || 'NOT_GENERATED';
  const modelId = result?.model;
  if (modelId) {
    const isFlash = modelId.includes('3.8');
    footer.append(element('span', `model-badge ${isFlash ? 'flash' : 'lite'}`, modelId));
  } else {
    footer.append(element('span', '', 'Gemini · pending'));
  }
  if (validSvg) {
    const actions = element('div', 'image-downloads');
    const inspectButton = element('button', 'preview-link', 'INSPECT ⛶');
    inspectButton.type = 'button';
    inspectButton.setAttribute('aria-label', `Inspect ${concept.name}`);
    inspectButton.addEventListener('click', (e) => {
      e.stopPropagation();
      openInspectorModal(concept, result);
    });
    const svgButton = element('button', 'preview-link', 'SVG ↓');
    svgButton.type = 'button';
    svgButton.addEventListener('click', (e) => {
      e.stopPropagation();
      downloadSvg(result.svg, concept.name);
    });
    const pngButton = element('button', 'preview-link', 'PNG ↓');
    pngButton.type = 'button';
    pngButton.addEventListener('click', async (e) => {
      e.stopPropagation();
      pngButton.disabled = true;
      const originalLabel = pngButton.textContent;
      pngButton.textContent = 'Preparing…';
      try {
        await downloadPng(result.svg, concept.name);
      } catch (error) {
        if (typeof window !== 'undefined' && window.alert) {
          window.alert(`PNG export failed: ${error.message}`);
        }
      } finally {
        pngButton.disabled = false;
        pngButton.textContent = originalLabel;
      }
    });
    actions.append(inspectButton, svgButton, pngButton);
    footer.append(actions);
  } else {
    footer.append(element('span', '', status.replaceAll('_', ' ')));
  }
  cell.append(footer);
  return cell;
}

function createChecksCell(result) {
  const cell = element('td', 'checks-cell');
  const list = element('div', 'check-list');
  for (const [key, label, group] of CHECKS) {
    const check = getCheck(result, key);
    const state = !result ? 'wait' : check.passed ? 'pass' : result.status === 'NOT_GENERATED' ? 'wait' : 'fail';
    const row = element('div', `check-item ${state}`);
    row.append(element('span', 'check-mark', state === 'pass' ? '✓' : state === 'fail' ? '×' : '·'));
    const text = element('span', 'check-copy');
    const header = element('div', 'check-header');
    header.append(element('span', 'check-name', label));
    if (group) {
      header.append(element('span', `check-badge ${group.toLowerCase()}`, group));
    }
    text.append(header);
    text.append(element('small', 'check-detail', check.detail || (state === 'wait' ? 'Awaiting result' : 'Check failed')));
    row.append(text);
    list.append(row);
  }
  cell.append(list);
  const status = result?.status || 'WAITING';
  const statusClass = status === 'PASS' ? 'pass' : status === 'FAIL' || status === 'ERROR' ? 'fail' : 'wait';
  cell.append(element('span', `row-status ${statusClass}`, status));
  if (result?.attempt_history?.length) {
    const details = element('details', 'attempt-details');
    details.append(element('summary', '', `${result.attempt_history.length} generation attempt(s)`));
    for (const attempt of result.attempt_history) {
      const attemptLine = element('div', 'attempt-line');
      const failed = Object.entries(attempt.checks || {}).filter(([, check]) => !check.passed);
      attemptLine.append(element('strong', '', `Attempt ${attempt.attempt}: ${attempt.passed ? 'PASS' : 'FAIL'}`));
      if (failed.length) {
        attemptLine.append(element('small', '', failed.map(([key]) => key.replaceAll('_', ' ')).join(' · ')));
      } else {
        attemptLine.append(element('small', '', 'All six checks passed.'));
      }
      details.append(attemptLine);
    }
    cell.append(details);
  }
  return cell;
}

function createUsageCell(result) {
  const cell = element('td', 'usage-cell');
  const versionNum = result?.version || 1;
  const isPass = result?.status === 'PASS';

  // Cost and Version Badge row: flex layout so version appears beside cost without overlap
  const costRow = element('div', 'cost-badge-row');
  costRow.append(element('strong', 'usage-cost', formatCost(result)));
  const verBadge = element('span', 'version-tag', `v${versionNum}`);
  verBadge.classList.add(isPass ? 'approved' : 'pending');
  costRow.append(verBadge);
  cell.append(costRow);

  const input = result?.usage?.input_tokens;
  const output = result?.usage?.output_tokens;
  const usage = input === undefined ? 'Tokens pending' : `${input} in · ${output} out`;
  cell.append(element('span', 'usage-label', usage));
  const retries = result?.retries?.total_retries;
  cell.append(element('span', 'retry-badge', `RETRIES  ${retries ?? '—'}`));
  if (result?.retries) {
    cell.append(element('span', 'usage-label', `API ${result.retries.api_retries} · repair ${result.retries.validation_retries}`));
  }
  if (result?.cost?.billing_tier === 'free') {
    cell.append(element('span', 'usage-label', `Paid eq. ${formatPaidEquivalent(result)}`));
  }
  if (typeof result?.latency_ms === 'number') {
    cell.append(element('span', 'usage-label', `Total ${Math.round(result.latency_ms)} ms`));
  }
  if (result?.timings_ms) {
    const requestMs = Math.round(result.timings_ms.model_request_with_retries_ms || 0);
    const svgMs = Math.round(result.timings_ms.svg_validation_ms || 0);
    const csMs = Math.round(result.timings_ms.concept_structure_ms || 0);
    const checksMs = Math.round(result.timings_ms.validation_ms || (svgMs + csMs));
    cell.append(element('span', 'usage-label', `Model + backoff ${requestMs} ms`));
    if (svgMs || csMs) {
      cell.append(element('span', 'usage-label', `SVG ${svgMs} ms · Structure ${csMs} ms`));
    } else {
      cell.append(element('span', 'usage-label', `Validation ${checksMs} ms`));
    }
  }
  if (result?.trace_id) {
    cell.append(element('span', 'usage-label', `TRACE ${result.trace_id.slice(0, 8)}`));
  }
  return cell;
}

function formatPaidEquivalent(result) {
  const amount = result?.cost?.paid_equivalent_cost_usd;
  return typeof amount === 'number' ? `$${amount.toFixed(5)}` : '—';
}

function createReviewCell(concept, result) {
  const cell = element('td', 'review-cell');
  const versionNum = result?.version || 1;
  const versionsCount = result?.versions_count || (result?.versions?.length || 1);
  const isPass = result?.status === 'PASS';

  if (versionsCount > 1) {
    const verHead = element('div', 'review-version-bar');
    const verCountLabel = element('span', 'version-selector-label', `${versionsCount} versions recorded`);
    verHead.append(verCountLabel);
    cell.append(verHead);
  }

  // Single Primary Action: REGENERATE DIAGRAM
  const regenBtn = element('button', 'regen-feedback-button primary-regen', '↻ REGENERATE DIAGRAM');
  regenBtn.type = 'button';
  regenBtn.id = `regen-btn-${concept.id}`;
  regenBtn.title = `Regenerate ${concept.name} using Gemini 3.5 Flash-Lite`;
  cell.append(regenBtn);

  const statusNote = element('span', 'review-saved', isPass ? `v${versionNum} · VALIDATED` : (result?.status || 'AWAITING GENERATION'));
  cell.append(statusNote);

  regenBtn.addEventListener('click', async () => {
    regenBtn.disabled = true;
    regenBtn.textContent = 'Regenerating…';
    statusNote.textContent = 'Calling Gemini 3.5 Flash-Lite…';

    try {
      const activeModel = 'gemini-3.5-flash-lite';
      const promptFeedback = 'Regenerate diagram ensuring visible, prominent animations and exact geometric accuracy.';
      const res = await regenerateWithFeedback(concept.id, promptFeedback, activeModel, versionNum);
      if (res.result) {
        const idx = currentResults.findIndex(r => r.concept_id === concept.id);
        if (idx >= 0) {
          currentResults[idx] = res.result;
        } else {
          currentResults.push(res.result);
        }
        renderRows(currentConcepts, currentResults);
        openInspectorModal(concept, res.result);
      }
    } catch (err) {
      statusNote.textContent = `Regeneration failed: ${err.message}. Previous diagram preserved.`;
      regenBtn.disabled = false;
      regenBtn.textContent = '↻ REGENERATE DIAGRAM';
    }
  });

  cell.append(regenBtn);
  cell.append(statusNote);

  return cell;
}

export function calculateTelemetry(concepts, results) {
  // 1. Genuine persisted generation attempts: any result where status !== 'NOT_GENERATED' (does NOT require SVG)
  const attempts = results.filter(result => result && result.status && result.status !== 'NOT_GENERATED');

  // 2. Diagrams ready: ONLY valid final PASS result with SVG exists
  const readyResults = results.filter(result => result && result.status === 'PASS' && Boolean(result.svg));
  const ready = readyResults.length;

  // 3. Count passed and failed requests separately
  const passedResults = attempts.filter(result => result.status === 'PASS');
  const failedResults = attempts.filter(result => result.status === 'FAIL' || result.status === 'ERROR');

  // 4. Retries and repairs across ALL genuine attempts (does NOT require SVG)
  const validationRepairs = attempts.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const apiRetries = attempts.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);

  // 5. Retries and repairs for failed requests counted separately
  const failedValidationRepairs = failedResults.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const failedApiRetries = failedResults.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);
  const passedValidationRepairs = passedResults.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const passedApiRetries = passedResults.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);

  // 6. Quality gate checks (from attempted results where checks exist)
  const checks = attempts.flatMap(result => Object.values(result.checks || {}));
  const passedChecks = checks.filter(check => check?.passed).length;

  // 7. Latency
  const latencies = attempts.map(result => result.latency_ms).filter(Number.isFinite);
  const averageLatency = latencies.length
    ? `${Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length)} ms`
    : '—';

  return {
    ready,
    totalConcepts: concepts.length,
    attemptsCount: attempts.length,
    passedCount: passedResults.length,
    failedCount: failedResults.length,
    validationRepairs,
    apiRetries,
    failedValidationRepairs,
    failedApiRetries,
    passedValidationRepairs,
    passedApiRetries,
    passedChecks,
    totalChecks: checks.length,
    averageLatency,
  };
}

export function updateMetrics(concepts, results) {
  const t = calculateTelemetry(concepts, results);

  // Upper signal strip indicators
  const loadedCount = document.getElementById('loaded-count');
  if (loadedCount) loadedCount.innerHTML = `${String(t.ready).padStart(2, '0')}<span>/05</span>`;

  const signalRepairs = document.getElementById('signal-repairs');
  if (signalRepairs) signalRepairs.textContent = String(t.validationRepairs).padStart(2, '0');

  const signalRetries = document.getElementById('signal-retries');
  if (signalRetries) signalRetries.textContent = String(t.apiRetries).padStart(2, '0');

  // Review Board metrics grid
  const metricPass = document.getElementById('metric-pass');
  if (metricPass) metricPass.textContent = `${t.passedCount} / ${t.totalConcepts}`;

  const metricPassSub = document.getElementById('metric-pass-sub');
  if (metricPassSub) {
    metricPassSub.textContent = t.failedCount > 0
      ? `${t.failedCount} failed request${t.failedCount === 1 ? '' : 's'}`
      : 'Only generated results are counted';
  }

  const metricChecks = document.getElementById('metric-checks');
  if (metricChecks) metricChecks.textContent = `${t.passedChecks} / ${t.totalChecks}`;

  const metricRepairs = document.getElementById('metric-repairs');
  if (metricRepairs) metricRepairs.textContent = String(t.validationRepairs);

  const metricRepairsSub = document.getElementById('metric-repairs-sub');
  if (metricRepairsSub) {
    metricRepairsSub.textContent = t.failedValidationRepairs > 0
      ? `${t.passedValidationRepairs} passed · ${t.failedValidationRepairs} in failed`
      : 'Corrective generation repairs';
  }

  const metricRetries = document.getElementById('metric-retries');
  if (metricRetries) metricRetries.textContent = String(t.apiRetries);

  const metricRetriesSub = document.getElementById('metric-retries-sub');
  if (metricRetriesSub) {
    metricRetriesSub.textContent = t.failedApiRetries > 0
      ? `${t.passedApiRetries} passed · ${t.failedApiRetries} in failed`
      : 'Transient 429 / 503 backoff retries';
  }

  const metricLatency = document.getElementById('metric-latency');
  if (metricLatency) metricLatency.textContent = t.averageLatency;
}

function createComparisonColumn(modelId, modelName, role, badgeClass, result, isActiveTarget) {
  const col = element('div', `comparison-col ${isActiveTarget ? 'active-target' : ''}`);

  const header = element('div', 'col-header');
  const tagWrap = element('div', '');
  tagWrap.append(element('span', `col-model-tag ${badgeClass}`, role.toUpperCase()));
  header.append(tagWrap);

  const status = result?.status || 'NOT GENERATED';
  const statusClass = status === 'PASS' ? 'pass' : status === 'FAIL' || status === 'ERROR' ? 'fail' : 'wait';
  header.append(element('span', `row-status ${statusClass}`, status.replaceAll('_', ' ')));
  col.append(header);

  if (!result || result.status === 'NOT_GENERATED') {
    const empty = element('div', 'comparison-empty-note');
    empty.append(element('strong', '', `No ${modelName} telemetry recorded`));
    empty.append(element('span', '', isActiveTarget ? 'Active target in instrument console. Select concept and click Generate SVG above.' : 'Switch instrument dial to this model above to generate comparison data.'));
    col.append(empty);
    return col;
  }

  const checks = Object.values(result.checks || {});
  const passedChecks = checks.filter(c => c?.passed).length;
  const totalChecks = checks.length || 6;

  const stats = element('div', 'col-stats-list');
  
  const box1 = element('div', 'col-stat-box');
  box1.append(element('span', 'col-stat-label', 'CHECKS'));
  box1.append(element('span', 'col-stat-value', `${passedChecks}/${totalChecks}`));
  
  const box2 = element('div', 'col-stat-box');
  box2.append(element('span', 'col-stat-label', 'LATENCY'));
  box2.append(element('span', 'col-stat-value', typeof result.latency_ms === 'number' ? `${Math.round(result.latency_ms)} ms` : '—'));

  const box3 = element('div', 'col-stat-box');
  box3.append(element('span', 'col-stat-label', 'TOKENS'));
  box3.append(element('span', 'col-stat-value mono', result.usage?.metadata_available ? `${result.usage.input_tokens} / ${result.usage.output_tokens}` : '—'));

  const box4 = element('div', 'col-stat-box');
  box4.append(element('span', 'col-stat-label', 'EST. COST'));
  box4.append(element('span', 'col-stat-value', formatCost(result)));

  stats.append(box1, box2, box3, box4);
  col.append(stats);

  if (result.retries) {
    const retryNote = element('span', 'usage-label', `Retries: API ${result.retries.api_retries || 0} · repair ${result.retries.validation_retries || 0}`);
    col.append(retryNote);
  }

  return col;
}

export function renderComparisonGrid(concepts, results, activeModelId = 'gemini-3.5-flash-lite') {
  const container = document.getElementById('comparison-grid');
  if (!container) return;
  container.replaceChildren();

  for (const concept of concepts) {
    const card = element('div', 'comparison-card');

    const head = element('div', 'comparison-concept-head');
    const title = element('div', 'comparison-concept-title');
    title.append(element('span', '', `0${concept.number} / 05`));
    title.append(element('strong', '', concept.name));
    title.append(element('span', 'subject-tag', concept.subject.toUpperCase()));
    head.append(title);
    card.append(head);

    const cols = element('div', 'comparison-cols');

    // Model 1: Gemini 3.5 Flash-Lite
    const liteResult = results.find(item => item.concept_id === concept.id && item.model === 'gemini-3.5-flash-lite')
      || (results.find(item => item.concept_id === concept.id && (!item.model || item.model.includes('3.5'))));
    cols.append(createComparisonColumn('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', 'Efficiency', 'lite', liteResult, activeModelId === 'gemini-3.5-flash-lite'));

    // Model 2: Gemini 3.8 Flash
    const flashResult = results.find(item => item.concept_id === concept.id && item.model === 'gemini-3.8-flash');
    cols.append(createComparisonColumn('gemini-3.8-flash', 'Gemini 3.8 Flash', 'Advanced', 'flash', flashResult, activeModelId === 'gemini-3.8-flash'));

    card.append(cols);
    container.append(card);
  }
}

export function renderRows(concepts, results, activeModelId = 'gemini-3.5-flash-lite', modelRuns = []) {
  currentConcepts = concepts;
  currentResults = results;
  const body = document.getElementById('results-body');
  body.replaceChildren();

  for (const concept of concepts) {
    const result = results.find(item => item.concept_id === concept.id);
    const row = document.createElement('tr');
    row.append(
      createConceptCell(concept),
      createIllustrationCell(concept, result),
      createChecksCell(result),
      createUsageCell(result),
      createReviewCell(concept, result),
    );
    body.append(row);
  }

  updateMetrics(concepts, results);

  // Merge results and modelRuns into comparison set where each (concept_id, model) is distinct
  const comparisonRuns = [...results];
  for (const run of modelRuns) {
    const idx = comparisonRuns.findIndex(r => r.concept_id === run.concept_id && r.model === run.model);
    if (idx >= 0) {
      comparisonRuns[idx] = run;
    } else {
      comparisonRuns.push(run);
    }
  }
  renderComparisonGrid(concepts, comparisonRuns, activeModelId);
  setupInspectorModal();
}

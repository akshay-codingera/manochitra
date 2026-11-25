import { getReview, saveDecision, saveNote, getReviewCounts } from './reviews.js';
import { downloadPng, downloadSvg } from './exports.js';
import { regenerateWithFeedback, saveReviewToServer } from './api.js';
import { archiveDiagram, getAllArchivedDiagrams, getArchiveCounts } from './archive.js';

export const CHECKS = [
  ['valid_svg', 'Valid SVG', 'Mandatory'],
  ['within_viewbox', 'Inside viewBox', 'Mandatory'],
  ['title_and_labels', 'Title + labels', 'Mandatory'],
  ['has_animation', 'Animation', 'Mandatory'],
  ['scientific_terms', 'Science terms', 'Custom'],
  ['concept_structure', 'Concept structure', 'Advanced'],
];

let currentConcepts = [];
let currentResults = [];
let currentArchiveFilter = 'all';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

export function formatStandardCost(result) {
  if (!result || result.status === 'NOT_GENERATED') return 'N/A';
  if (result.usage?.metadata_available === false) return 'N/A';

  const paidEq = result?.cost?.paid_equivalent_cost_usd;
  if (typeof paidEq === 'number' && paidEq > 0) {
    return `$${paidEq.toFixed(5)}`;
  }

  // Calculate from tokens if standard rate exists
  const input = result?.usage?.input_tokens;
  const output = result?.usage?.output_tokens;
  if (typeof input === 'number' && typeof output === 'number' && result?.usage?.metadata_available) {
    const inputRate = result?.cost?.input_rate_per_million ?? 0.3;
    const outputRate = result?.cost?.output_rate_per_million ?? 2.5;
    const calc = (input * inputRate + output * outputRate) / 1_000_000;
    return `$${calc.toFixed(5)}`;
  }

  return 'N/A';
}

export function formatTokensText(result) {
  if (!result || result.status === 'NOT_GENERATED') return 'Tokens: N/A';
  if (result.usage?.metadata_available === false) return 'Tokens: N/A';
  const input = result?.usage?.input_tokens;
  const output = result?.usage?.output_tokens;
  if (typeof input === 'number' && typeof output === 'number') {
    return `${input.toLocaleString()} in · ${output.toLocaleString()} out`;
  }
  return 'Tokens: N/A';
}

function formatCost(result) {
  return formatStandardCost(result);
}

function getCheck(result, key) {
  return result?.checks?.[key] || { passed: false, detail: 'Not generated yet.' };
}

function createNumberCell(concept) {
  const cell = element('td', 'number-cell');
  cell.append(element('span', 'col-number', `0${concept.number}`));
  return cell;
}

function createConceptCell(concept) {
  const cell = element('td', 'concept-cell');
  cell.append(element('span', 'subject-tag', (concept.subject || 'SCIENCE').toUpperCase()));
  cell.append(element('strong', 'concept-name', concept.name));
  const desc = concept.source_text || concept.description || '';
  if (desc) {
    cell.append(element('p', 'concept-description', desc));
  }
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
  const versionNum = result?.version || 1;

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

  const metaGroup = element('div', 'preview-meta-group');
  if (modelId) {
    const isFlash = modelId.includes('3.8');
    metaGroup.append(element('span', `model-badge ${isFlash ? 'flash' : 'lite'}`, modelId));
  } else {
    metaGroup.append(element('span', 'model-badge lite', 'gemini-3.5-flash-lite'));
  }
  metaGroup.append(element('span', 'version-tag', `v${versionNum}`));
  footer.append(metaGroup);

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
    footer.append(element('span', 'row-status wait', status.replaceAll('_', ' ')));
  }
  cell.append(footer);
  return cell;
}

function createChecksCell(result) {
  const cell = element('td', 'checks-cell');
  const list = element('div', 'check-list');

  CHECKS.forEach(([key, label, group], idx) => {
    const check = getCheck(result, key);
    const state = !result ? 'wait' : check.passed ? 'pass' : result.status === 'NOT_GENERATED' ? 'wait' : 'fail';
    const row = element('div', `check-item ${state}`);

    // Check mark with clear text
    const markWrap = element('span', `check-mark ${state}`, state === 'pass' ? '✓' : state === 'fail' ? '×' : '·');
    row.append(markWrap);

    const text = element('div', 'check-copy');
    const header = element('div', 'check-header');
    header.append(element('span', 'check-num', `0${idx + 1}.`));
    header.append(element('span', 'check-name', label));

    const statusPill = element('span', `check-status-pill ${state}`, state === 'pass' ? 'PASS' : state === 'fail' ? 'FAIL' : 'WAIT');
    header.append(statusPill);

    text.append(header);
    text.append(element('small', 'check-detail', check.detail || (state === 'wait' ? 'Awaiting result' : 'Check failed')));
    row.append(text);
    list.append(row);
  });

  cell.append(list);

  const status = result?.status || 'WAITING';
  const statusClass = status === 'PASS' ? 'pass' : status === 'FAIL' || status === 'ERROR' ? 'fail' : 'wait';
  const statusFooter = element('div', 'checks-footer');
  statusFooter.append(element('span', `row-status ${statusClass}`, `${status} (${result?.attempt_history?.length || 1} ATTEMPT)`));
  cell.append(statusFooter);

  return cell;
}

function createUsageCell(result) {
  const cell = element('td', 'usage-cell');

  // Prominent Standard Pricing Estimated Cost
  const costBlock = element('div', 'cost-card-block');
  costBlock.append(element('span', 'cost-eyebrow', 'Estimated API Cost (Standard Pricing)'));

  const costVal = formatStandardCost(result);
  const costRow = element('div', 'cost-amount-row');
  costRow.append(element('strong', 'usage-cost', costVal));
  costBlock.append(costRow);

  // Free-tier charge explicitly noted
  costBlock.append(element('span', 'usage-free-tier', 'Estimated free-tier charge: $0.00'));
  cell.append(costBlock);

  // Compact Tokens & Retries metrics
  const metaGrid = element('div', 'usage-meta-list');
  metaGrid.append(element('div', 'usage-meta-line tokens', formatTokensText(result)));

  const apiRetries = result?.retries?.api_retries ?? 0;
  const valRepairs = result?.retries?.validation_retries ?? 0;

  const retryRow = element('div', 'usage-retries-row');
  retryRow.append(element('span', 'meta-pill', `API RETRIES  ${apiRetries}`));
  retryRow.append(element('span', 'meta-pill', `REPAIRS  ${valRepairs}`));
  metaGrid.append(retryRow);

  if (typeof result?.latency_ms === 'number') {
    metaGrid.append(element('div', 'usage-meta-line latency', `Latency: ${Math.round(result.latency_ms)} ms`));
  }

  cell.append(metaGrid);
  return cell;
}

function createReviewCell(concept, result) {
  const cell = element('td', 'review-cell');
  const versionNum = result?.version || 1;
  const review = getReview(concept.id, versionNum);
  const isPass = result?.status === 'PASS';

  // 1. Header with Version Tag & Current Decision Status
  const headerBar = element('div', 'review-header-bar');
  const verBadge = element('span', 'version-tag', `v${versionNum}`);
  headerBar.append(verBadge);

  const statusBadge = element('span', `review-decision-badge ${review.decision}`);
  if (review.decision === 'accepted') {
    statusBadge.textContent = '✓ ACCEPTED';
  } else if (review.decision === 'rejected') {
    statusBadge.textContent = '✕ REJECTED';
  } else {
    statusBadge.textContent = '◌ PENDING REVIEW';
  }
  headerBar.append(statusBadge);
  cell.append(headerBar);

  // 2. Review Action Buttons (Approve & Reject)
  const actionsRow = element('div', 'review-actions-row');

  const approveBtn = element('button', `review-btn approve ${review.decision === 'accepted' ? 'selected' : ''}`, '✓ APPROVE');
  approveBtn.type = 'button';
  approveBtn.setAttribute('aria-label', `Approve ${concept.name} version ${versionNum}`);

  const rejectBtn = element('button', `review-btn reject ${review.decision === 'rejected' ? 'selected' : ''}`, '✕ REJECT');
  rejectBtn.type = 'button';
  rejectBtn.setAttribute('aria-label', `Reject ${concept.name} version ${versionNum}`);

  actionsRow.append(approveBtn, rejectBtn);
  cell.append(actionsRow);

  // 3. Reviewer Notes Textarea
  const noteWrap = element('div', 'review-note-wrap');
  const noteArea = element('textarea', 'review-note-input');
  noteArea.placeholder = 'Reviewer feedback or notes (persisted locally)…';
  noteArea.value = review.note || '';
  noteArea.rows = 2;
  noteWrap.append(noteArea);

  const noteMeta = element('div', 'review-note-meta');
  const saveIndicator = element('span', 'save-indicator', '● LocalStorage & Archive active');
  noteMeta.append(saveIndicator);
  noteWrap.append(noteMeta);
  cell.append(noteWrap);

  // Event handler: save note on input & blur
  noteArea.addEventListener('input', () => {
    saveNote(concept.id, noteArea.value, versionNum);
    saveIndicator.textContent = '● Saved to LocalStorage';
    // If already in archive, update archive record
    const cur = getReview(concept.id, versionNum);
    if (result?.svg && cur.decision !== 'pending') {
      archiveDiagram({
        conceptId: concept.id,
        conceptName: concept.name,
        version: versionNum,
        decision: cur.decision,
        note: noteArea.value,
        svg: result.svg,
        result,
      }).then(() => renderArchiveSection());
    }
  });

  // Event handler: Approve
  approveBtn.addEventListener('click', async () => {
    const note = noteArea.value.trim();
    saveDecision(concept.id, 'accepted', versionNum, note);

    // UI updates
    approveBtn.classList.add('selected');
    rejectBtn.classList.remove('selected');
    statusBadge.className = 'review-decision-badge accepted';
    statusBadge.textContent = '✓ ACCEPTED';
    saveIndicator.textContent = '● Decision & Diagram Archived';

    // Save to IndexedDB Archive
    if (result?.svg) {
      await archiveDiagram({
        conceptId: concept.id,
        conceptName: concept.name,
        version: versionNum,
        decision: 'accepted',
        note,
        svg: result.svg,
        result,
      });
    }

    updateMetrics(currentConcepts, currentResults);
    renderArchiveSection();

    try {
      saveReviewToServer(concept.id, 'approved', note, versionNum).catch(() => {});
    } catch (_) {}
  });

  // Event handler: Reject
  rejectBtn.addEventListener('click', async () => {
    const note = noteArea.value.trim();
    saveDecision(concept.id, 'rejected', versionNum, note);

    // UI updates
    rejectBtn.classList.add('selected');
    approveBtn.classList.remove('selected');
    statusBadge.className = 'review-decision-badge rejected';
    statusBadge.textContent = '✕ REJECTED';
    saveIndicator.textContent = '● Rejection & Diagram Archived';

    // Save to IndexedDB Archive
    if (result?.svg) {
      await archiveDiagram({
        conceptId: concept.id,
        conceptName: concept.name,
        version: versionNum,
        decision: 'rejected',
        note,
        svg: result.svg,
        result,
      });
    }

    updateMetrics(currentConcepts, currentResults);
    renderArchiveSection();

    try {
      saveReviewToServer(concept.id, 'rejected', note, versionNum).catch(() => {});
    } catch (_) {}
  });

  // 4. Primary Action: REGENERATE DIAGRAM
  const regenBtn = element('button', 'regen-feedback-button primary-regen', '↻ REGENERATE DIAGRAM');
  regenBtn.type = 'button';
  regenBtn.id = `regen-btn-${concept.id}`;
  regenBtn.title = `Regenerate ${concept.name} using Gemini 3.5 Flash-Lite with feedback`;
  cell.append(regenBtn);

  regenBtn.addEventListener('click', async () => {
    regenBtn.disabled = true;
    regenBtn.textContent = 'Regenerating…';
    saveIndicator.textContent = 'Calling Gemini with feedback…';

    try {
      const activeModel = 'gemini-3.5-flash-lite';
      const promptFeedback = noteArea.value.trim() || 'Regenerate diagram ensuring visible, prominent animations and exact geometric accuracy.';
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
      saveIndicator.textContent = `Regeneration failed: ${err.message}. Previous preserved.`;
      regenBtn.disabled = false;
      regenBtn.textContent = '↻ REGENERATE DIAGRAM';
    }
  });

  return cell;
}

export function calculateTelemetry(concepts, results) {
  const attempts = results.filter(result => result && result.status && result.status !== 'NOT_GENERATED');
  const readyResults = results.filter(result => result && result.status === 'PASS' && Boolean(result.svg));
  const ready = readyResults.length;

  const passedResults = attempts.filter(result => result.status === 'PASS');
  const failedResults = attempts.filter(result => result.status === 'FAIL' || result.status === 'ERROR');

  const validationRepairs = attempts.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const apiRetries = attempts.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);

  const failedValidationRepairs = failedResults.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const failedApiRetries = failedResults.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);
  const passedValidationRepairs = passedResults.reduce((sum, result) => sum + (result.retries?.validation_retries || 0), 0);
  const passedApiRetries = passedResults.reduce((sum, result) => sum + (result.retries?.api_retries || 0), 0);

  const checks = attempts.flatMap(result => Object.values(result.checks || {}));
  const passedChecks = checks.filter(check => check?.passed).length;

  const latencies = attempts.map(result => result.latency_ms).filter(Number.isFinite);
  const averageLatency = latencies.length
    ? `${Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length)} ms`
    : '—';

  // Review status counts from LocalStorage
  const reviewCounts = getReviewCounts(concepts, results);

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
    acceptedCount: reviewCounts.accepted,
    rejectedCount: reviewCounts.rejected,
    pendingCount: reviewCounts.pending,
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

  // Review Board 6 Required Metrics
  const metricTotal = document.getElementById('metric-total');
  if (metricTotal) metricTotal.textContent = String(t.totalConcepts).padStart(2, '0');

  const metricPass = document.getElementById('metric-pass');
  if (metricPass) metricPass.textContent = `${t.ready} / ${t.totalConcepts}`;

  const metricChecks = document.getElementById('metric-checks');
  if (metricChecks) metricChecks.textContent = `${t.passedChecks} / ${t.totalChecks}`;

  const metricAccepted = document.getElementById('metric-accepted');
  if (metricAccepted) metricAccepted.textContent = String(t.acceptedCount);

  const metricRejected = document.getElementById('metric-rejected');
  if (metricRejected) metricRejected.textContent = String(t.rejectedCount);

  const metricPending = document.getElementById('metric-pending');
  if (metricPending) metricPending.textContent = String(t.pendingCount);
}

export async function renderArchiveSection() {
  if (typeof document === 'undefined') return;
  const grid = document.getElementById('archive-grid');
  if (!grid) return;

  const counts = await getArchiveCounts();
  const countAll = document.getElementById('archive-count-all');
  if (countAll) countAll.textContent = String(counts.total);
  const countAcc = document.getElementById('archive-count-accepted');
  if (countAcc) countAcc.textContent = String(counts.accepted);
  const countRej = document.getElementById('archive-count-rejected');
  if (countRej) countRej.textContent = String(counts.rejected);

  const filter = currentArchiveFilter === 'all' ? null : currentArchiveFilter;
  const items = await getAllArchivedDiagrams(filter);

  grid.replaceChildren();

  if (items.length === 0) {
    const empty = element('div', 'archive-empty-state');
    empty.append(element('strong', '', 'No archived diagrams in this category.'));
    empty.append(element('p', '', 'Review diagrams above and click Approve or Reject to preserve their animated SVG markup in the local IndexedDB archive.'));
    grid.append(empty);
    return;
  }

  for (const item of items) {
    const card = element('div', 'archive-card');

    const topBar = element('div', 'archive-card-top');
    const titleGroup = element('div', 'archive-card-title');
    titleGroup.append(element('strong', '', item.concept_name));
    titleGroup.append(element('span', 'version-tag', `v${item.version}`));
    topBar.append(titleGroup);

    const badge = element('span', `review-decision-badge ${item.decision}`, item.decision === 'accepted' ? '✓ APPROVED' : '✕ REJECTED');
    topBar.append(badge);
    card.append(topBar);

    // SVG thumbnail / interactive frame
    const frame = element('div', 'archive-thumb-frame');
    const iframe = element('iframe', 'archive-thumb-iframe');
    iframe.title = `${item.concept_name} archived SVG`;
    iframe.setAttribute('sandbox', '');
    iframe.setAttribute('loading', 'lazy');
    const blob = new Blob([item.svg], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    iframe.src = url;
    iframe.addEventListener('load', () => URL.revokeObjectURL(url), { once: true });
    frame.append(iframe);
    card.append(frame);

    // Note and metadata
    const body = element('div', 'archive-card-body');
    if (item.note) {
      body.append(element('p', 'archive-note', `"${item.note}"`));
    } else {
      body.append(element('p', 'archive-note muted', 'No reviewer note entered.'));
    }

    const meta = element('div', 'archive-meta-row');
    const dateStr = item.archived_at ? new Date(item.archived_at).toLocaleString() : 'Recently';
    meta.append(element('span', 'archive-date', `Saved: ${dateStr}`));
    if (item.checks_summary) {
      meta.append(element('span', 'archive-checks', item.checks_summary));
    }
    body.append(meta);
    card.append(body);

    // Actions
    const actions = element('div', 'archive-card-actions');
    const inspectBtn = element('button', 'preview-link', 'INSPECT ⛶');
    inspectBtn.type = 'button';
    inspectBtn.addEventListener('click', () => {
      const concept = currentConcepts.find(c => c.id === item.concept_id) || { id: item.concept_id, name: item.concept_name, number: 1 };
      openInspectorModal(concept, {
        svg: item.svg,
        model: item.model,
        version: item.version,
        checks: {},
      });
    });

    const svgBtn = element('button', 'preview-link', 'SVG ↓');
    svgBtn.type = 'button';
    svgBtn.addEventListener('click', () => {
      downloadSvg(item.svg, `${item.concept_name}_v${item.version}`);
    });

    const pngBtn = element('button', 'preview-link', 'PNG ↓');
    pngBtn.type = 'button';
    pngBtn.addEventListener('click', async () => {
      pngBtn.disabled = true;
      const old = pngBtn.textContent;
      pngBtn.textContent = 'Preparing…';
      try {
        await downloadPng(item.svg, `${item.concept_name}_v${item.version}`);
      } catch (err) {
        if (typeof window !== 'undefined' && window.alert) window.alert(err.message);
      } finally {
        pngBtn.disabled = false;
        pngBtn.textContent = old;
      }
    });

    actions.append(inspectBtn, svgBtn, pngBtn);
    card.append(actions);

    grid.append(card);
  }
}

export function setupArchiveFilterButtons() {
  if (typeof document === 'undefined') return;
  const buttons = document.querySelectorAll('.archive-filter-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentArchiveFilter = btn.getAttribute('data-filter') || 'all';
      renderArchiveSection();
    });
  });
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
  box4.append(element('span', 'col-stat-value', formatStandardCost(result)));

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

    const liteResult = results.find(item => item.concept_id === concept.id && item.model === 'gemini-3.5-flash-lite')
      || (results.find(item => item.concept_id === concept.id && (!item.model || item.model.includes('3.5'))));
    cols.append(createComparisonColumn('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', 'Efficiency', 'lite', liteResult, activeModelId === 'gemini-3.5-flash-lite'));

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
  if (body) {
    body.replaceChildren();

    for (const concept of concepts) {
      const result = results.find(item => item.concept_id === concept.id);
      const row = document.createElement('tr');
      row.append(
        createNumberCell(concept),
        createConceptCell(concept),
        createIllustrationCell(concept, result),
        createChecksCell(result),
        createUsageCell(result),
        createReviewCell(concept, result),
      );
      body.append(row);
    }
  }

  updateMetrics(concepts, results);

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
  setupArchiveFilterButtons();
  renderArchiveSection();
}

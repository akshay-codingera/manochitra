import { getReview } from './reviews.js';

const CHECK_LABELS = {
  valid_svg: 'Valid SVG / XML',
  within_viewbox: 'Drawing inside viewBox',
  title_and_labels: 'Title and explanatory labels',
  has_animation: 'Animation present',
  scientific_terms: 'Concept terminology coverage',
  concept_structure: 'Deterministic concept structure & geometry',
};

function slug(value) {
  return String(value || 'science-diagram-report')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1200);
}

function reportPayload(concepts, results) {
  const byId = new Map(results.map(result => [result.concept_id, result]));
  const entries = concepts.map(concept => {
    const result = byId.get(concept.id) || null;
    return {
      concept,
      result,
      review: getReview(concept.id),
    };
  });
  const generated = entries.filter(entry => entry.result);
  const allChecks = generated.flatMap(entry => Object.values(entry.result.checks || {}));
  const totalInput = generated.reduce((sum, entry) => sum + (entry.result.usage?.input_tokens || 0), 0);
  const totalOutput = generated.reduce((sum, entry) => sum + (entry.result.usage?.output_tokens || 0), 0);
  const totalRetries = generated.reduce((sum, entry) => sum + (entry.result.retries?.total_retries || 0), 0);
  const costDataComplete = generated.length > 0 && generated.every(entry =>
    entry.result.usage?.metadata_available !== false
    && Number.isFinite(entry.result.cost?.estimated_cost_usd)
    && Number.isFinite(entry.result.cost?.paid_equivalent_cost_usd)
  );
  const totalEstimatedCost = generated.reduce((sum, entry) => sum + (entry.result.cost?.estimated_cost_usd ?? 0), 0);
  const totalPaidEquivalent = generated.reduce((sum, entry) => sum + (entry.result.cost?.paid_equivalent_cost_usd ?? 0), 0);
  const latencies = generated.map(entry => entry.result.latency_ms).filter(value => Number.isFinite(value));
  return {
    report_schema: 'manochitra-quality-report/v1',
    exported_at: new Date().toISOString(),
    application: 'MANOCHITRA — Science Diagram Review',
    model: generated.find(entry => entry.result.model)?.result.model || 'Not yet used',
    summary: {
      concepts_total: concepts.length,
      concepts_generated: generated.length,
      concepts_passed: generated.filter(entry => entry.result.status === 'PASS').length,
      concepts_failed: generated.filter(entry => entry.result.status !== 'PASS').length,
      checks_passed: allChecks.filter(check => check?.passed).length,
      checks_total: allChecks.length,
      input_tokens: totalInput,
      output_tokens: totalOutput,
      total_retries: totalRetries,
      cost_data_complete: costDataComplete,
      estimated_cost_usd: costDataComplete ? Number(totalEstimatedCost.toFixed(8)) : null,
      paid_equivalent_cost_usd: costDataComplete ? Number(totalPaidEquivalent.toFixed(8)) : null,
      average_pipeline_latency_ms: latencies.length
        ? Number((latencies.reduce((sum, value) => sum + value, 0) / latencies.length).toFixed(2))
        : null,
    },
    entries: entries.map(({ concept, result, review }) => ({ concept, result, review })),
  };
}

export function downloadSvg(svg, conceptName) {
  if (!svg) throw new Error('There is no SVG available to download.');
  downloadBlob(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }), `${slug(conceptName)}.svg`);
}

export async function downloadPng(svg, conceptName) {
  if (!svg) throw new Error('There is no SVG available to convert.');
  const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
  if (parsed.querySelector('parsererror') || parsed.documentElement.localName !== 'svg') {
    throw new Error('The SVG could not be parsed for PNG export.');
  }
  const viewBox = (parsed.documentElement.getAttribute('viewBox') || '').trim().split(/[ ,]+/).map(Number);
  const widthAttr = Number(parsed.documentElement.getAttribute('width'));
  const heightAttr = Number(parsed.documentElement.getAttribute('height'));
  const width = Math.max(1, Math.min(2400, Math.round(viewBox.length === 4 ? viewBox[2] : widthAttr || 1200)));
  const height = Math.max(1, Math.min(2400, Math.round(viewBox.length === 4 ? viewBox[3] : heightAttr || 800)));
  parsed.documentElement.setAttribute('width', String(width));
  parsed.documentElement.setAttribute('height', String(height));
  const serialised = new XMLSerializer().serializeToString(parsed.documentElement);
  const sourceUrl = URL.createObjectURL(new Blob([serialised], { type: 'image/svg+xml;charset=utf-8' }));
  try {
    const image = new Image();
    image.decoding = 'async';
    image.src = sourceUrl;
    if (typeof image.decode === 'function') await image.decode();
    else await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error('Browser could not render this SVG.'));
    });
    const scale = Math.min(2, 2400 / Math.max(width, height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Canvas is unavailable in this browser.');
    context.fillStyle = '#f7f4e9';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const png = await new Promise((resolve, reject) => canvas.toBlob(blob => {
      if (blob) resolve(blob);
      else reject(new Error('PNG encoding failed.'));
    }, 'image/png'));
    downloadBlob(png, `${slug(conceptName)}.png`);
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

export function downloadJsonReport(concepts, results) {
  const payload = reportPayload(concepts, results);
  downloadBlob(
    new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }),
    'manochitra-quality-report.json',
  );
}

export function downloadCsvReport(concepts, results) {
  const payload = reportPayload(concepts, results);
  const columns = [
    'concept_id', 'concept', 'subject', 'status', 'model', 'valid_svg', 'within_viewbox',
    'title_and_labels', 'has_animation', 'scientific_terms', 'concept_structure', 'input_tokens', 'output_tokens',
    'estimated_cost_usd', 'paid_equivalent_cost_usd', 'api_retries', 'validation_retries',
    'total_retries', 'latency_ms', 'prompt_build_ms', 'model_request_with_retries_ms', 'validation_ms',
    'svg_validation_ms', 'concept_structure_ms', 'trace_id', 'prompt_version', 'review_decision',
    'review_note', 'last_error', 'generated_at',
  ];
  const quote = value => {
    let text = String(value ?? '');
    if (/^[=+@\-\t\r]/.test(text)) text = `'${text}`; // prevent spreadsheet formula execution from exported notes
    return `"${text.replace(/"/g, '""')}"`;
  };
  const rows = payload.entries.map(({ concept, result, review }) => {
    const checks = result?.checks || {};
    const row = {
      concept_id: concept.id,
      concept: concept.name,
      subject: concept.subject,
      status: result?.status || 'NOT_GENERATED',
      model: result?.model || '',
      valid_svg: checks.valid_svg?.passed ?? '',
      within_viewbox: checks.within_viewbox?.passed ?? '',
      title_and_labels: checks.title_and_labels?.passed ?? '',
      has_animation: checks.has_animation?.passed ?? '',
      scientific_terms: checks.scientific_terms?.passed ?? '',
      concept_structure: checks.concept_structure?.passed ?? '',
      input_tokens: result?.usage?.input_tokens ?? '',
      output_tokens: result?.usage?.output_tokens ?? '',
      estimated_cost_usd: result?.usage?.metadata_available === false ? '' : (result?.cost?.estimated_cost_usd ?? ''),
      paid_equivalent_cost_usd: result?.usage?.metadata_available === false ? '' : (result?.cost?.paid_equivalent_cost_usd ?? ''),
      api_retries: result?.retries?.api_retries ?? '',
      validation_retries: result?.retries?.validation_retries ?? '',
      total_retries: result?.retries?.total_retries ?? '',
      latency_ms: result?.latency_ms ?? '',
      prompt_build_ms: result?.timings_ms?.prompt_build_ms ?? '',
      model_request_with_retries_ms: result?.timings_ms?.model_request_with_retries_ms ?? '',
      validation_ms: result?.timings_ms?.validation_ms ?? '',
      svg_validation_ms: result?.timings_ms?.svg_validation_ms ?? '',
      concept_structure_ms: result?.timings_ms?.concept_structure_ms ?? '',
      trace_id: result?.trace_id || '',
      prompt_version: result?.prompt_version || '',
      review_decision: review.decision,
      review_note: review.note,
      last_error: result?.last_error || '',
      generated_at: result?.generated_at || '',
    };
    return columns.map(column => quote(row[column])).join(',');
  });
  const csv = [columns.map(quote).join(','), ...rows].join('\r\n');
  downloadBlob(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }), 'manochitra-quality-summary.csv');
}

export function downloadHtmlReport(concepts, results) {
  const payload = reportPayload(concepts, results);
  const summary = payload.summary;
  const tableRows = payload.entries.map(({ concept, result, review }) => {
    const checks = Object.entries(result?.checks || {}).map(([key, check]) => `
      <li class="${check.passed ? 'pass' : 'fail'}"><b>${escapeHtml(CHECK_LABELS[key] || key)}:</b> ${check.passed ? 'PASS' : 'FAIL'} — ${escapeHtml(check.detail)}</li>`).join('');
    const attempts = (result?.attempt_history || []).map(attempt => {
      const failedChecks = Object.entries(attempt.checks || {}).filter(([, check]) => !check.passed);
      const failedDetail = failedChecks.map(([key, check]) =>
        `<li>${escapeHtml(CHECK_LABELS[key] || key)}: ${escapeHtml(check.detail)}</li>`
      ).join('');
      return `<li>Attempt ${attempt.attempt}: ${attempt.passed ? 'PASS' : 'FAIL'}${failedDetail ? `<ul>${failedDetail}</ul>` : ''}</li>`;
    }).join('');
    return `<tr>
      <td><strong>${escapeHtml(concept.name)}</strong><small>${escapeHtml(concept.subject)}</small><small>${escapeHtml(result?.model || 'No model call')}</small><small>Trace: ${escapeHtml(result?.trace_id || '—')}</small></td>
      <td><b class="status ${result?.status === 'PASS' ? 'pass' : result ? 'fail' : 'wait'}">${escapeHtml(result?.status || 'NOT GENERATED')}</b></td>
      <td>${result?.usage?.input_tokens ?? '—'} / ${result?.usage?.output_tokens ?? '—'}</td>
      <td>${Number.isFinite(result?.cost?.estimated_cost_usd) ? `$${result.cost.estimated_cost_usd.toFixed(6)}` : 'Not available'}<small>Paid equivalent ${Number.isFinite(result?.cost?.paid_equivalent_cost_usd) ? `$${result.cost.paid_equivalent_cost_usd.toFixed(6)}` : 'not available'}</small></td>
      <td>${result?.retries?.total_retries ?? '—'}<small>API ${result?.retries?.api_retries ?? '—'} · repair ${result?.retries?.validation_retries ?? '—'}</small></td>
      <td>${escapeHtml(review.decision)}<small>${escapeHtml(review.note || 'No reviewer note')}</small></td>
    </tr>
    <tr><td colspan="6"><details open><summary>Validation evidence — ${escapeHtml(concept.name)}</summary><ul>${checks || '<li>Not generated; no validation evidence exists.</li>'}</ul>${attempts ? `<p><b>Generation attempts</b></p><ul>${attempts}</ul>` : ''}${result?.last_error ? `<p class="error">${escapeHtml(result.last_error)}</p>` : ''}</details></td></tr>`;
  }).join('');
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MANOCHITRA Quality Report</title>
<style>
:root{color-scheme:light;--ink:#20352b;--muted:#66766b;--paper:#f4f1e6;--card:#fffdf6;--line:#d8d8c8;--lime:#c8d96b;--green:#38674d;--red:#a95143}*{box-sizing:border-box}body{margin:0;padding:36px;background:var(--paper);color:var(--ink);font:14px/1.55 system-ui,Segoe UI,sans-serif}.wrap{max-width:1200px;margin:auto}.kicker{font:11px monospace;letter-spacing:.14em;color:var(--muted)}h1{font:500 clamp(32px,5vw,56px)/1.05 Georgia,serif;margin:10px 0}p{color:var(--muted)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:25px 0}.metric{padding:16px;border:1px solid var(--line);border-radius:12px;background:var(--card)}.metric span{display:block;font:10px monospace;color:var(--muted)}.metric strong{display:block;font:30px Georgia,serif;margin-top:5px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}table{width:100%;border-collapse:collapse;min-width:850px}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{font:10px monospace;letter-spacing:.08em;color:var(--muted);background:#ebe8da}td small{display:block;color:var(--muted);margin-top:4px}.status{font:10px monospace}.pass{color:var(--green)}.fail,.error{color:var(--red)}.wait{color:#7d806d}details{padding:8px 0}summary{cursor:pointer;font-weight:600}ul{margin:10px 0;padding-left:22px}li{margin:5px 0}footer{margin-top:25px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:12px}.actions{display:flex;gap:8px;margin:18px 0}.actions button{border:1px solid var(--line);background:var(--card);padding:9px 13px;border-radius:8px;color:var(--ink)}@media(max-width:700px){body{padding:16px}.metrics{grid-template-columns:repeat(2,1fr)}}@media print{body{padding:0;background:#fff}.actions{display:none}.table-wrap{overflow:visible}table{min-width:0;font-size:10px}details{break-inside:avoid}.metric{background:#fff}}
</style></head><body><main class="wrap"><div class="kicker">MANOCHITRA / SCIENCE DIAGRAM REVIEW</div><h1>Generation quality report</h1><p>Exported ${escapeHtml(payload.exported_at)} · Model: ${escapeHtml(payload.model)}. This report contains recorded application outputs; it does not invent missing results.</p>
<div class="actions"><button onclick="window.print()">Print / Save as PDF</button></div>
<section class="metrics"><div class="metric"><span>DIAGRAMS PASSED</span><strong>${summary.concepts_passed}/${summary.concepts_total}</strong></div><div class="metric"><span>CHECKS PASSED</span><strong>${summary.checks_passed}/${summary.checks_total}</strong></div><div class="metric"><span>TOTAL RETRIES</span><strong>${summary.total_retries}</strong></div><div class="metric"><span>AVG. LATENCY</span><strong>${summary.average_pipeline_latency_ms === null ? '—' : `${summary.average_pipeline_latency_ms} ms`}</strong></div></section>
<p>Tokens: ${summary.input_tokens.toLocaleString()} input / ${summary.output_tokens.toLocaleString()} output · Estimated charge: ${summary.estimated_cost_usd === null ? 'Not available (incomplete model usage metadata)' : `$${summary.estimated_cost_usd.toFixed(6)}`} · Paid-tier equivalent: ${summary.paid_equivalent_cost_usd === null ? 'Not available' : `$${summary.paid_equivalent_cost_usd.toFixed(6)}`}.</p>
<div class="table-wrap"><table><thead><tr><th>CONCEPT</th><th>STATUS</th><th>TOKENS IN / OUT</th><th>COST (USD)</th><th>RETRIES</th><th>HUMAN REVIEW</th></tr></thead><tbody>${tableRows}</tbody></table></div>
<footer>Automated checks verify SVG structure, constrained geometry, required title/labels, animation markup and required concept terminology. The terminology check is not a scientific proof; human review remains necessary. Review decisions are stored in this browser's local storage and included only from the current browser profile.</footer></main></body></html>`;
  downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), 'manochitra-quality-report.html');
}

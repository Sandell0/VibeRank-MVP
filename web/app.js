const $ = (selector) => document.querySelector(selector);

const provider = $("#provider");
const model = $("#model");
const customModel = $("#custom-model");
const runButton = $("#run-evaluation");
const providerNote = $("#provider-note");

let runtimeConfig = null;
let knownElos = null;

const CUSTOM_MODEL_VALUE = "__custom__";
// Catalog entries: [api model id, label, leaderboard display name for ground-truth Elo (null if unknown)]
const modelCatalog = {
  mistral: [
    ["mistral-small-latest", "Mistral Small (latest)", "mistral-small-latest"],
    ["mistral-small-2603", "Mistral Small 2603", null],
    ["mistral-medium-2508", "Mistral Medium 2508", "Mistral Medium 3.1"],
    ["mistral-medium-3.5", "Mistral Medium 3.5", "Mistral Medium 3.5"],
    ["mistral-large-latest", "Mistral Large (latest)", "Mistral Large 3"],
  ],
  openrouter: [
    ["meta-llama/llama-3.2-1b-instruct", "Meta · Llama 3.2 1B Instruct", null],
    ["meta-llama/llama-3.2-3b-instruct", "Meta · Llama 3.2 3B Instruct", null],
    ["meta-llama/llama-3.1-8b-instruct", "Meta · Llama 3.1 8B Instruct", null],
    ["meta-llama/llama-3.3-70b-instruct", "Meta · Llama 3.3 70B Instruct", "Llama 3.3 70B Instruct"],
    ["google/gemma-3-27b-it", "Google · Gemma 3 27B", "Gemma 3 27B (IT)"],
    ["microsoft/phi-4", "Microsoft · Phi 4", "Phi-4"],
    ["deepseek/deepseek-chat-v3.1", "DeepSeek · V3.1", "DeepSeek V3.1"],
    ["moonshotai/kimi-k2-0905", "MoonshotAI · Kimi K2 0905", "Kimi K2 0905"],
    ["moonshotai/kimi-k2.5", "MoonshotAI · Kimi K2.5", "Kimi K2.5"],
    ["openai/gpt-oss-120b", "OpenAI · gpt-oss-120b", "GPT-OSS-120B"],
    ["qwen/qwen3-235b-a22b-2507", "Qwen · Qwen3 235B A22B", "Qwen 3 235B A22B 2507 Instruct"],
  ],
};

const escapeHtml = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed with ${response.status}`);
  return payload;
}

function selectedModelId() {
  return model.value === CUSTOM_MODEL_VALUE ? customModel.value.trim() : model.value;
}

function updateRunButton() {
  const available = provider.value === "mistral"
    ? runtimeConfig?.mistral_available
    : runtimeConfig?.openrouter_available && runtimeConfig?.mistral_available;
  runButton.disabled = !available || !selectedModelId();
}

function updateCustomModel() {
  const isCustom = model.value === CUSTOM_MODEL_VALUE;
  customModel.hidden = !isCustom;
  customModel.required = isCustom;
  updateRunButton();
}

function knownEloFor(truthName) {
  return truthName && knownElos?.has(truthName) ? knownElos.get(truthName) : null;
}

function selectedKnownElo() {
  const id = selectedModelId();
  const entry = (modelCatalog[provider.value] || []).find(([modelId]) => modelId === id);
  return entry ? knownEloFor(entry[2]) : null;
}

async function loadKnownElos() {
  try {
    const data = await request("/api/leaderboard-models?limit=1000");
    knownElos = new Map(data.models.map((entry) => [entry.model, entry.elo]));
    populateModelPicker(provider.value);
  } catch {
    // Ground truth is optional; evaluations work without it.
  }
}

function populateModelPicker(selected) {
  const options = modelCatalog[selected] || [];
  model.replaceChildren(...options.map(([id, label, truthName]) => {
    const option = document.createElement("option");
    option.value = id;
    const elo = knownEloFor(truthName);
    option.textContent = `${label} · ${id}${elo != null ? ` · true Elo ${Math.round(elo)}` : ""}`;
    return option;
  }));
  const customOption = document.createElement("option");
  customOption.value = CUSTOM_MODEL_VALUE;
  customOption.textContent = "Custom model ID…";
  model.append(customOption);
  customModel.value = "";
  updateCustomModel();
}

function updateProvider() {
  const selected = provider.value;
  populateModelPicker(selected);
  if (selected === "mistral") {
    providerNote.textContent = runtimeConfig?.mistral_available
      ? "Five target calls and five grader calls. Estimated API cost is shown after the run."
      : "Set MISTRAL_API_KEY on the server to enable live calls.";
  } else {
    providerNote.textContent = runtimeConfig?.openrouter_available && runtimeConfig?.mistral_available
      ? "Five OpenRouter target calls and five Mistral grader calls. Usage is shown after the run; cost appears when pricing is configured."
      : "Set OPENROUTER_API_KEY and MISTRAL_API_KEY on the server to enable this mode.";
  }
  updateRunButton();
}

function posteriorSvg(series, target) {
  const width = 680;
  const height = 170;
  const padding = { left: 16, right: 16, top: 12, bottom: 25 };
  const minElo = series[0].elo;
  const maxElo = series[series.length - 1].elo;
  const x = (elo) => padding.left + ((elo - minElo) / (maxElo - minElo)) * (width - padding.left - padding.right);
  const y = (density) => height - padding.bottom - density * (height - padding.top - padding.bottom);
  const line = series.map((point) => `${x(point.elo).toFixed(1)},${y(point.density).toFixed(1)}`).join(" ");
  const area = `${padding.left},${height - padding.bottom} ${line} ${width - padding.right},${height - padding.bottom}`;
  const tickStep = (maxElo - minElo) / 4;
  const ticks = Array.from({ length: 5 }, (_, index) => Math.round((minElo + tickStep * index) / 50) * 50);
  const targetMarkup = target == null ? "" : `
    <line class="target-line" x1="${x(target)}" y1="${padding.top}" x2="${x(target)}" y2="${height - padding.bottom}" />
    <text class="chart-label" x="${Math.min(x(target) + 5, width - 78)}" y="22">TRUE ${target}</text>`;
  return `
    <svg class="posterior-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Elo posterior density">
      <line class="chart-axis" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" />
      <line class="chart-grid" x1="${padding.left}" y1="${y(0.5)}" x2="${width - padding.right}" y2="${y(0.5)}" />
      <polygon class="chart-area" points="${area}" />
      <polyline class="chart-line" points="${line}" />
      ${targetMarkup}
      ${ticks.map((tick) => `<text class="chart-label" x="${x(tick)}" y="${height - 6}" text-anchor="middle">${tick}</text>`).join("")}
    </svg>`;
}

function predictionTrajectorySvg(traces, target) {
  if (!traces?.length) return "";
  const width = 680;
  const height = 230;
  const padding = { left: 48, right: 24, top: 22, bottom: 48 };
  const points = traces.map((trace) => ({
    step: trace.step,
    mean: trace.posterior.mean_elo,
    low: trace.posterior.low_elo,
    high: trace.posterior.high_elo,
  }));
  const values = points.flatMap((point) => [point.low, point.high]);
  if (target != null) values.push(target);
  let minElo = Math.floor((Math.min(...values) - 50) / 100) * 100;
  let maxElo = Math.ceil((Math.max(...values) + 50) / 100) * 100;
  if (minElo === maxElo) {
    minElo -= 100;
    maxElo += 100;
  }
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const x = (index) => points.length === 1
    ? padding.left + plotWidth / 2
    : padding.left + (index / (points.length - 1)) * plotWidth;
  const y = (elo) => padding.top + ((maxElo - elo) / (maxElo - minElo)) * plotHeight;
  const meanLine = points.map((point, index) => `${x(index).toFixed(1)},${y(point.mean).toFixed(1)}`).join(" ");
  const tickCount = 5;
  const ticks = Array.from(
    { length: tickCount },
    (_, index) => Math.round(maxElo - ((maxElo - minElo) * index) / (tickCount - 1)),
  );
  const targetMarkup = target == null ? "" : `
    <line class="trajectory-target" x1="${padding.left}" y1="${y(target)}" x2="${width - padding.right}" y2="${y(target)}" />
    <text class="trajectory-label" x="${padding.left + 9}" y="${Math.min(y(target) + 15, height - padding.bottom - 2)}">TRUE ${Math.round(target)}</text>`;
  const intervals = points.map((point, index) => {
    const pointX = x(index);
    const lowY = y(point.low);
    const highY = y(point.high);
    const meanY = y(point.mean);
    const valueX = index === points.length - 1 ? pointX - 9 : pointX + 9;
    const valueAnchor = index === points.length - 1 ? "end" : "start";
    return `
      <line class="trajectory-interval" x1="${pointX}" y1="${highY}" x2="${pointX}" y2="${lowY}" />
      <line class="trajectory-cap" x1="${pointX - 7}" y1="${highY}" x2="${pointX + 7}" y2="${highY}" />
      <line class="trajectory-cap" x1="${pointX - 7}" y1="${lowY}" x2="${pointX + 7}" y2="${lowY}" />
      <circle class="trajectory-point" cx="${pointX}" cy="${meanY}" r="5" />
      <text class="trajectory-value" x="${valueX}" y="${meanY - 7}" text-anchor="${valueAnchor}">${Math.round(point.mean)}</text>
      <text class="trajectory-label" x="${pointX}" y="${height - 25}" text-anchor="middle">Q${point.step}</text>
      <text class="trajectory-label" x="${pointX}" y="${height - 9}" text-anchor="middle">width ${Math.round(point.high - point.low)}</text>`;
  }).join("");
  return `
    <p class="trajectory-heading">Prediction by question <span>mean and 90% interval</span></p>
    <svg class="trajectory-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Predicted Elo and 90 percent interval after each question">
      ${ticks.map((tick) => `
        <line class="trajectory-grid" x1="${padding.left}" y1="${y(tick)}" x2="${width - padding.right}" y2="${y(tick)}" />
        <text class="trajectory-label" x="${padding.left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>`).join("")}
      ${targetMarkup}
      ${intervals}
      <polyline class="trajectory-mean-line" points="${meanLine}" />
    </svg>`;
}

function renderResult(result) {
  const estimate = result.estimate;
  const totalTokens = (result.usage?.author?.total_tokens || 0)
    + (result.usage?.target?.total_tokens || 0)
    + (result.usage?.grader?.total_tokens || 0);
  const targetMetric = result.target_elo == null ? "" : `
    <div class="metric"><span>True Elo</span><strong>${Math.round(result.target_elo)}</strong></div>
    <div class="metric"><span>Absolute error</span><strong>${Math.round(result.absolute_error)}</strong></div>`;
  const tokenMetric = totalTokens > 0 ? `
    <div class="metric"><span>Total tokens</span><strong>${totalTokens.toLocaleString()}</strong></div>` : "";
  const totalCost = result.cost?.total_usd;
  const costMetric = totalCost == null ? "" : `
    <div class="metric"><span>Estimated API cost</span><strong>$${Number(totalCost).toFixed(totalCost < 0.01 ? 4 : 3)}</strong></div>`;
  const direct = result.direct_channel;
  const directMetric = direct?.enabled ? `
    <div class="metric"><span>Texture channel</span><strong>on · τ ${Math.round(direct.tau_elo)} · σ ${Math.round(direct.sigma_w_elo)}</strong></div>` : "";
  const holistic = result.holistic_channel;
  const holisticMetric = holistic?.active ? `
    <div class="metric"><span>Holistic channel</span><strong>calibrated · ${holistic.reference_models} reference models</strong></div>
    <div class="metric"><span>Ordinal diagnostic</span><strong>${Math.round(result.ordinal_estimate.mean_elo)} Elo</strong></div>` : `
    <div class="metric"><span>Holistic channel</span><strong>off — ordinal posterior only</strong></div>`;
  $("#result-content").innerHTML = `
    <div class="result-topline">
      <span class="result-label">${escapeHtml(result.model)} · ${result.questions} answer${result.questions === 1 ? "" : "s"}</span>
      <span class="method-badge">${result.holistic_channel?.active ? "calibrated holistic read" : result.question_mode === "fixed" ? "fixed grader debug" : "adaptive posterior"}</span>
    </div>
    <div class="estimate-grid">
      <div>
        <p class="estimate-number">${Math.round(estimate.mean_elo)}</p>
        <p class="estimate-unit">PREDICTED ELO</p>
      </div>
      <div class="estimate-meta">
        <div class="metric"><span>90% interval</span><strong>${Math.round(estimate.low_elo)}–${Math.round(estimate.high_elo)}</strong></div>
        <div class="metric"><span>Estimate σ</span><strong>${Math.round(estimate.standard_deviation)}</strong></div>
        ${holisticMetric}
        ${directMetric}
        ${costMetric}
        ${tokenMetric}
        ${targetMetric}
      </div>
    </div>
    ${posteriorSvg(result.posterior_series, result.target_elo)}
    ${predictionTrajectorySvg(result.traces, result.target_elo)}
  `;
  $("#result-content").classList.remove("hidden");
}

function renderGraderContext(context) {
  const anchors = Object.entries(context.grade_anchors || {});
  return `
    <details class="grader-context">
      <summary>Exact grader context</summary>
      <div class="grader-context-body">
        <h4>Reference answer</h4>
        <p>${escapeHtml(context.reference_answer)}</p>
        <h4>Rubric</h4>
        <ul>${(context.rubric || []).map((criterion) => `<li>${escapeHtml(criterion)}</li>`).join("")}</ul>
        <h4>Calibration anchors</h4>
        ${anchors.map(([name, answer]) => `
          <div class="anchor-answer"><strong>${escapeHtml(name.replaceAll("_", " "))}</strong>${escapeHtml(answer)}</div>
        `).join("")}
      </div>
    </details>`;
}

function renderTraces(traces) {
  const labels = {
    wrong: "Wrong",
    major_error: "Major error",
    minor_error: "Minor error",
    fully_correct: "Fully correct",
  };
  $("#trace-list").innerHTML = traces.map((trace) => `
    <article class="trace-card">
      <div class="trace-index">
        ${String(trace.step).padStart(2, "0")}
        <small>${escapeHtml(trace.question.domain)}<br />${((trace.usage.target.total_tokens || 0) + (trace.usage.grader.total_tokens || 0)).toLocaleString()} tokens</small>
      </div>
      <div class="trace-question">
        <h3>${escapeHtml(trace.question.title)}</h3>
        <p>${escapeHtml(trace.question.prompt)}</p>
        <div class="answer-box">${escapeHtml(trace.answer)}</div>
        ${renderGraderContext(trace.grader_context)}
      </div>
      <div class="trace-grade">
        <div class="grade-bars">
          ${Object.entries(trace.grade.probabilities).map(([name, probability]) => `
            <div class="grade-row">
              <span>${labels[name]}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${Math.max(1, probability * 100)}%"></div></div>
              <span>${Math.round(probability * 100)}%</span>
            </div>`).join("")}
        </div>
        <p class="grade-explanation">${escapeHtml(trace.grade.explanation)}</p>
        ${trace.grade.satisfied_criteria?.length ? `
          <div class="satisfied-criteria">
            <strong>Satisfied rubric criteria</strong>
            <ul>${trace.grade.satisfied_criteria.map((criterion) => `<li>${escapeHtml(criterion)}</li>`).join("")}</ul>
          </div>` : ""}
        <p class="grade-metadata">
          Error: ${escapeHtml(trace.grade.error_type)} · confidence ${Math.round(trace.grade.confidence * 100)}%<br />
          Estimate: ${Math.round(trace.posterior.mean_elo)} Elo
          ${trace.holistic ? `<br />Holistic: ${Math.round(trace.holistic.raw_mean_elo)} raw → ${Math.round(trace.holistic.mean_elo)} ± ${Math.round(trace.holistic.sigma_elo)}` : ""}
          ${(trace.usage.target.total_tokens || trace.usage.grader.total_tokens) ? `<br />Target: ${(trace.usage.target.total_tokens || 0).toLocaleString()} tokens · grader: ${(trace.usage.grader.total_tokens || 0).toLocaleString()} tokens` : ""}
        </p>
      </div>
    </article>
  `).join("");
}

async function runEvaluation() {
  runButton.disabled = true;
  $("#result-empty").classList.add("hidden");
  $("#result-content").classList.add("hidden");
  $("#result-loading").classList.remove("hidden");
  const payload = {
    provider: provider.value,
    model: selectedModelId(),
    questions: 5,
    seed: 7,
    question_mode: "fixed",
  };
  const knownElo = selectedKnownElo();
  if (knownElo != null) payload.target_elo = knownElo;
  try {
    const result = await request("/api/evaluate", { method: "POST", body: JSON.stringify(payload) });
    renderResult(result);
    renderTraces(result.traces);
  } catch (error) {
    $("#result-content").innerHTML = `<div class="error-box"><strong>Evaluation failed</strong><br />${escapeHtml(error.message)}</div>`;
    $("#result-content").classList.remove("hidden");
  } finally {
    $("#result-loading").classList.add("hidden");
    updateRunButton();
  }
}

async function initialize() {
  try {
    runtimeConfig = await request("/api/config");
    $("#question-count").textContent = `${runtimeConfig.fixed_question_count} fixed`;
    $("#grader-name").textContent = runtimeConfig.grader_model;
    const holisticStatus = runtimeConfig.holistic_channel?.calibrated
      ? ` · holistic calibrated (${runtimeConfig.holistic_channel.reference_models} models)`
      : "";
    $("#runtime-status").textContent = runtimeConfig.mistral_available
      ? `${runtimeConfig.fixed_question_count} fixed questions · ${runtimeConfig.grader_model}${holisticStatus}`
      : "Live API keys unavailable";
    updateProvider();
    loadKnownElos();
  } catch (error) {
    $("#runtime-status").textContent = "Runtime unavailable";
    $("#result-empty").innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
  }
}

provider.addEventListener("change", updateProvider);
model.addEventListener("change", () => {
  updateCustomModel();
  if (!customModel.hidden) customModel.focus();
});
customModel.addEventListener("input", updateRunButton);
runButton.addEventListener("click", runEvaluation);

initialize();

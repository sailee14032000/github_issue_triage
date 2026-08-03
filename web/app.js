const modelASelect = document.getElementById("modelA");
const modelBSelect = document.getElementById("modelB");
const runBtn = document.getElementById("runBtn");
const requestStatusEl = document.getElementById("requestStatus");

function populateModelSelectors(models) {
	modelASelect.innerHTML = "";
	modelBSelect.innerHTML = "";

	models.forEach((model, idx) => {
		const a = document.createElement("option");
		a.value = model;
		a.textContent = model;
		if (idx === 0) a.selected = true;
		modelASelect.appendChild(a);

		const b = document.createElement("option");
		b.value = model;
		b.textContent = model;
		if (idx === 1) b.selected = true;
		modelBSelect.appendChild(b);
	});
}

function syncModelOptions() {
	Array.from(modelASelect.options).forEach((option) => {
		option.disabled = option.value === modelBSelect.value;
	});
	Array.from(modelBSelect.options).forEach((option) => {
		option.disabled = option.value === modelASelect.value;
	});
}

async function loadModels() {
	const res = await fetch("/api/models");
	if (!res.ok) throw new Error("Could not load available models");

	const data = await res.json();
	if (!Array.isArray(data.models) || data.models.length < 2) {
		throw new Error("At least two models are required for comparison");
	}

	populateModelSelectors(data.models);
	syncModelOptions();
}

function setupTabs() {
	const buttons = Array.from(document.querySelectorAll(".tab-btn"));
	buttons.forEach((btn) => {
		btn.addEventListener("click", () => {
			buttons.forEach((x) => x.classList.remove("active"));
			btn.classList.add("active");

			const target = btn.dataset.tab;
			document.querySelectorAll(".tab-content").forEach((p) => p.classList.remove("active"));
			document.getElementById(`tab-${target}`).classList.add("active");
		});
	});
}

const LABELS = ["bug", "enhancement", "question", "documentation", "security", "other"];

function escapeHtml(value) {
	return String(value ?? "")
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#039;");
}

function formatPercent(value) {
	return `${((Number(value) || 0) * 100).toFixed(1)}%`;
}

function renderModelMetrics(modelName, metrics) {
	const rows = LABELS.map((label) => {
		const values = metrics.per_class?.[label] || {};
		return `<tr>
			<td><span class="label-pill">${escapeHtml(label)}</span></td>
			<td>${formatPercent(values.precision)}</td>
			<td>${formatPercent(values.recall)}</td>
			<td>${formatPercent(values.f1)}</td>
			<td>${values.support || 0}</td>
		</tr>`;
	}).join("");

	return `<article class="model-summary">
		<div class="model-summary-header">
			<div><span class="eyebrow">Model</span><h3>${escapeHtml(modelName)}</h3></div>
			<div class="accuracy"><strong>${formatPercent(metrics.overall_accuracy)}</strong><span>accuracy</span></div>
		</div>
		<div class="table-scroll"><table>
			<thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead>
			<tbody>${rows}</tbody>
		</table></div>
	</article>`;
}

function renderConfusionMatrix(modelName, matrix) {
	const rows = LABELS.map((actual) => `<tr>
		<th>${escapeHtml(actual)}</th>
		${LABELS.map((predicted) => `<td>${matrix?.[actual]?.[predicted] || 0}</td>`).join("")}
	</tr>`).join("");

	return `<article class="matrix-card">
		<h3>${escapeHtml(modelName)}</h3>
		<div class="table-scroll"><table class="matrix-table">
			<thead><tr><th>Actual ↓ / Predicted →</th>${LABELS.map((label) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead>
			<tbody>${rows}</tbody>
		</table></div>
	</article>`;
}

function renderIssueRows(rows, includeGroundTruth, modelAName, modelBName) {
	if (!rows.length) return `<div class="empty-state">No issues match this view.</div>`;

	return rows.map((row, index) => {
		const detailId = `${includeGroundTruth ? "scored" : "unscored"}-detail-${index}`;
		return `<tr class="expandable-row" data-detail-id="${detailId}" tabindex="0" aria-expanded="false">
			<td><span class="expand-icon">›</span>${escapeHtml(row.title || `Issue ${row.issue_id}`)}</td>
			<td><span class="label-pill">${escapeHtml(row.model_a_prediction)}</span></td>
			<td><span class="label-pill">${escapeHtml(row.model_b_prediction)}</span></td>
			${includeGroundTruth ? `<td><span class="label-pill truth">${escapeHtml(row.ground_truth_label)}</span></td>` : ""}
		</tr>
		<tr id="${detailId}" class="detail-row" hidden><td colspan="${includeGroundTruth ? 4 : 3}">
			<div class="issue-detail">
				<section><h4>Issue text</h4><p>${escapeHtml(row.body) || "No issue body."}</p></section>
				<section><h4>${escapeHtml(modelAName)} raw output</h4><pre>${escapeHtml(row.model_a_raw_output) || "No raw output."}</pre></section>
				<section><h4>${escapeHtml(modelBName)} raw output</h4><pre>${escapeHtml(row.model_b_raw_output) || "No raw output."}</pre></section>
			</div>
		</td></tr>`;
	}).join("");
}

function setupExpandableRows(container) {
	function toggleRow(row) {
		const detail = document.getElementById(row.dataset.detailId);
		const willOpen = detail.hidden;
		detail.hidden = !willOpen;
		row.setAttribute("aria-expanded", String(willOpen));
		row.classList.toggle("expanded", willOpen);
	}

	container.querySelectorAll(".expandable-row").forEach((row) => {
		row.addEventListener("click", () => toggleRow(row));
		row.addEventListener("keydown", (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				toggleRow(row);
			}
		});
	});
}

function renderScored(payload) {
	const container = document.getElementById("scoredContent");
	const scored = payload.scored;
	if (!scored?.model_a || !scored?.model_b) {
		container.textContent = "No scored results returned.";
		return;
	}

	container.className = "results-content";
	container.innerHTML = `
		<div class="section-heading"><div><span class="eyebrow">Golden subset</span><h3>${scored.match_summary.scored_count} scored issues</h3></div></div>
		<div class="model-grid">
			${renderModelMetrics(payload.request.model_a, scored.model_a)}
			${renderModelMetrics(payload.request.model_b, scored.model_b)}
		</div>
		<div class="section-heading"><h3>Confusion matrices</h3><span>Rows are actual labels; columns are predictions.</span></div>
		<div class="matrix-wrap">
			${renderConfusionMatrix(payload.request.model_a, scored.model_a.confusion_matrix)}
			${renderConfusionMatrix(payload.request.model_b, scored.model_b.confusion_matrix)}
		</div>
		<div class="section-heading"><h3>Model disagreements</h3><span>${scored.disagreements.length} issues</span></div>
		<div class="table-scroll"><table>
			<thead><tr><th>Issue</th><th>${escapeHtml(payload.request.model_a)}</th><th>${escapeHtml(payload.request.model_b)}</th><th>Ground truth</th></tr></thead>
			<tbody>${renderIssueRows(scored.disagreements, true, payload.request.model_a, payload.request.model_b)}</tbody>
		</table></div>`;
	setupExpandableRows(container);
}

function renderDistribution(modelName, distribution) {
	const max = Math.max(1, ...LABELS.map((label) => distribution[label] || 0));
	const bars = LABELS.map((label) => {
		const count = distribution[label] || 0;
		return `<div class="bar-row"><span>${escapeHtml(label)}</span><div class="bar-track"><div class="bar-fill" style="width: ${(count / max) * 100}%"></div></div><strong>${count}</strong></div>`;
	}).join("");
	return `<article class="chart-card"><h3>${escapeHtml(modelName)}</h3>${bars}</article>`;
}

function renderUnscored(payload) {
	const container = document.getElementById("unscoredContent");
	const unscored = payload.unscored;
	if (!unscored?.summary) {
		container.textContent = "No unscored results returned.";
		return;
	}

	container.className = "results-content";
	container.innerHTML = `
		<div class="agreement-banner"><span>Model agreement rate</span><strong>${formatPercent(unscored.summary.agreement_rate)}</strong><small>${unscored.summary.agreement_count} of ${unscored.summary.total_unscored} issues</small></div>
		<div class="section-heading"><h3>Prediction distribution</h3></div>
		<div class="chart-grid">
			${renderDistribution(payload.request.model_a, unscored.model_a_distribution)}
			${renderDistribution(payload.request.model_b, unscored.model_b_distribution)}
		</div>
		<div class="section-heading table-heading"><h3>Issue predictions</h3>
			<label class="toggle-row"><input id="disagreementOnly" type="checkbox" /> Show disagreements only</label>
		</div>
		<div class="table-scroll"><table>
			<thead><tr><th>Issue</th><th>${escapeHtml(payload.request.model_a)}</th><th>${escapeHtml(payload.request.model_b)}</th></tr></thead>
			<tbody id="unscoredRows">${renderIssueRows(unscored.rows, false, payload.request.model_a, payload.request.model_b)}</tbody>
		</table></div>`;

	const rowsContainer = document.getElementById("unscoredRows");
	setupExpandableRows(container);
	document.getElementById("disagreementOnly").addEventListener("change", (event) => {
		const rows = event.target.checked ? unscored.disagreements : unscored.rows;
		rowsContainer.innerHTML = renderIssueRows(rows, false, payload.request.model_a, payload.request.model_b);
		setupExpandableRows(rowsContainer);
	});
}

function formatCurrency(value) {
	return value == null ? "Pricing unavailable" : `$${Number(value).toFixed(6)}`;
}

function formatSeconds(value) {
	return value == null ? "Unavailable" : `${Number(value).toFixed(2)} s`;
}

function renderModelRunSummary(model, wallClockSeconds, maxInFlightCalls) {
	const metrics = [
		["Requests", model.total_requests.toLocaleString()],
		["Total cost", formatCurrency(model.total_cost_usd)],
		["Cost / correct", formatCurrency(model.cost_per_correct_classification_usd)],
		["Wall-clock time", formatSeconds(wallClockSeconds)],
		["Concurrency", `${maxInFlightCalls} calls`],
		["p50 latency", formatSeconds(model.p50_latency_seconds)],
		["p95 latency", formatSeconds(model.p95_latency_seconds)],
		["Throughput", `${Number(model.throughput_requests_per_second).toFixed(2)} req/s`],
		["Rate-limit errors", formatPercent(model.error_rates.rate_limit)],
		["Timeout errors", formatPercent(model.error_rates.timeout)],
		["Other errors", formatPercent(model.error_rates.other)],
		["Input tokens", model.input_tokens.toLocaleString()],
		["Output tokens", model.output_tokens.toLocaleString()],
		["Correct classifications", model.correct_classifications.toLocaleString()],
	];

	return `<article class="model-run-summary">
		<header><span class="eyebrow">Model</span><h3>${escapeHtml(model.model)}</h3></header>
		<dl class="run-metric-list">
			${metrics.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("")}
		</dl>
	</article>`;
}

function renderOperational(payload) {
	const container = document.getElementById("operationalContent");
	const metrics = payload.operational;
	if (!metrics?.models) {
		container.textContent = "No operational metrics returned.";
		return;
	}

	const modelA = metrics.models.model_a;
	const modelB = metrics.models.model_b;
	container.className = "results-content";
	container.innerHTML = `
		<div class="section-heading"><div><span class="eyebrow">Comparison</span><h3>Run summary by model</h3></div></div>
		<div class="model-run-grid">
			${renderModelRunSummary(modelA, metrics.wall_clock_seconds, metrics.max_in_flight_calls)}
			${renderModelRunSummary(modelB, metrics.wall_clock_seconds, metrics.max_in_flight_calls)}
		</div>`;
}

function renderResults(payload) {
	renderScored(payload);
	renderUnscored(payload);
	renderOperational(payload);
}

async function runComparison() {
	const payload = {
		model_a: modelASelect.value,
		model_b: modelBSelect.value,
	};

	runBtn.disabled = true;
	runBtn.textContent = "Running comparison...";
	requestStatusEl.classList.remove("warn");
	requestStatusEl.textContent = "Comparison in progress. This may take several minutes.";

	try {
		const res = await fetch("/api/run-comparison", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		});

		if (!res.ok) {
			const text = await res.text();
			throw new Error(text || "Request failed");
		}

		const data = await res.json();
		renderResults(data);
		const totalErrors = data.summary.model_a_errors + data.summary.model_b_errors;
		const elapsedSeconds = Number(data.operational?.wall_clock_seconds || 0);
		requestStatusEl.textContent =
			`Comparison completed for ${data.summary.total_issues} issues in ` +
			`${elapsedSeconds.toFixed(1)} seconds. ` +
			`${totalErrors} inference errors.`;
		requestStatusEl.classList.toggle("warn", totalErrors > 0);
	} catch (error) {
		requestStatusEl.textContent = `Comparison failed: ${error.message}`;
		requestStatusEl.classList.add("warn");
	} finally {
		runBtn.disabled = false;
		runBtn.textContent = "Run comparison";
	}
}

async function init() {
	setupTabs();
	runBtn.disabled = true;
	modelASelect.disabled = true;
	modelBSelect.disabled = true;

	modelASelect.addEventListener("change", syncModelOptions);
	modelBSelect.addEventListener("change", syncModelOptions);
	runBtn.addEventListener("click", runComparison);

	try {
		await loadModels();
		modelASelect.disabled = false;
		modelBSelect.disabled = false;
		runBtn.disabled = false;
	} catch (error) {
		requestStatusEl.textContent = `Could not initialize: ${error.message}`;
		requestStatusEl.classList.add("warn");
	}
}

init();

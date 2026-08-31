const state = { incidents: [], selected: null, recoveryJobId: null, source: 'all' };
const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const response = await fetch(path, Object.assign({
    headers: { 'Content-Type': 'application/json' }
  }, options));
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || 'Request failed');
  return payload;
}

async function refresh() {
  const values = await Promise.all([
    api('/api/health'), api('/api/incidents'), api('/api/pipelines'), api('/api/jobs')
  ]);
  const health = values[0], incidents = values[1], pipelines = values[2], jobs = values[3];
  $('#health-dot').classList.add('ok');
  $('#health-label').textContent = health.status.toUpperCase();
  $('#mode-badge').textContent = health.mode.toUpperCase();
  state.incidents = incidents.incidents;
  $('#incident-count').textContent = state.incidents.length;
  $('#active-jobs').textContent = jobs.jobs.filter((job) => job.status === 'running').length;
  $('#failed-jobs').textContent = jobs.jobs.filter((job) => job.status === 'failed').length;
  $('#pipeline-health').textContent = pipelines.pipelines.some((item) => item.failed_jobs) ? 'Degraded' : 'Healthy';
  renderIncidents();
  if (state.selected) await selectIncident(state.selected);
}

function renderIncidents() {
  const target = $('#incident-list');
  if (!state.incidents.length) {
    target.innerHTML = '<p class="muted">Inject a scenario to begin.</p>';
    return;
  }
  target.innerHTML = state.incidents.map((incident) =>
    '<button class="incident-card ' + (incident.id === state.selected ? 'active' : '') +
    '" data-id="' + html(incident.id) + '"><strong>' + label(incident.failure_class) +
    '</strong><span>' + html(incident.asset.name) + ' · ' + html(incident.status) +
    '</span></button>'
  ).join('');
  target.querySelectorAll('.incident-card').forEach((button) => {
    button.addEventListener('click', () => selectIncident(button.dataset.id));
  });
}

async function selectIncident(id) {
  state.selected = id;
  const values = await Promise.all([
    api('/api/incidents/' + id), api('/api/incidents/' + id + '/timeline')
  ]);
  const incident = values[0], timeline = values[1];
  const root = $('#incident-detail');
  root.className = 'detail';
  root.innerHTML = '';
  root.append($('#detail-template').content.cloneNode(true));
  $('#incident-title').textContent = label(incident.failure_class);
  $('#incident-meta').textContent = incident.asset.name + ' · ' + incident.job_id;
  $('#incident-status').textContent = incident.status;
  renderHypotheses(incident.hypotheses);
  renderRecovery(incident.selected_recovery);
  renderEvidence(incident.evidence);
  renderTimeline(timeline.timeline);
  renderVerification(incident.verification);
  wireActions(incident);
  renderIncidents();
}

function renderHypotheses(items) {
  const primary = items[0], alternatives = items.slice(1);
  $('#primary-hypothesis').innerHTML = primary ?
    '<h3>' + label(primary.failure_class) + '</h3><p>' + html(primary.explanation) +
    '</p><div class="confidence">' + Math.round(primary.confidence * 100) +
    '%</div><p class="muted">' + primary.evidence_for.length +
    ' supporting evidence items</p>' : '<p>No diagnosis yet.</p>';
  $('#alternative-hypotheses').innerHTML = alternatives.map((item) =>
    '<p><strong>' + label(item.failure_class) + '</strong> · ' +
    Math.round(item.confidence * 100) + '%</p>'
  ).join('');
}

function renderRecovery(plan) {
  $('#recovery-plan').innerHTML = plan ?
    '<h3>' + html(plan.title) + '</h3><p>' + html(plan.predicted_consequence) +
    '</p><p class="muted">Risk ' + html(plan.risk.toUpperCase()) +
    ' · Estimated cost ' + Number(plan.estimated_cost).toFixed(2) +
    ' · Approval required</p>' : '<p>No safe recovery proposed.</p>';
}

function renderEvidence(items) {
  const filtered = state.source === 'all' ? items : items.filter((item) => item.source === state.source);
  $('#evidence-list').innerHTML = filtered.map((item) =>
    '<article class="evidence-item"><strong>' + html(item.summary) + '</strong><small>' +
    html(item.source) + ' · ' + html(item.provenance.provider || 'local') + ' · ' +
    html(item.provenance.query || 'snapshot') + '</small></article>'
  ).join('') || '<p class="muted">No evidence in this view.</p>';
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.source === state.source);
    button.onclick = () => { state.source = button.dataset.source; renderEvidence(items); };
  });
}

function renderTimeline(items) {
  $('#timeline').innerHTML = items.map((item) =>
    '<li><strong>' + label(item.type) + '</strong><span>' + html(item.message) +
    '</span><time>' + new Date(item.created_at).toLocaleTimeString() + '</time></li>'
  ).join('');
}

function renderVerification(result) {
  const word = !result ? 'PENDING' : result.passed ? 'PASSED' : 'FAILED';
  const badge = $('#verification-state');
  badge.textContent = word;
  badge.className = 'verification ' + word.toLowerCase();
  $('#verification-checks').innerHTML = result ? Object.entries(result.checks).map((entry) =>
    '<div class="check"><span>' + label(entry[0]) + '</span><strong>' +
    (entry[1] ? 'PASS' : 'FAIL') + '</strong></div>'
  ).join('') : '<p class="muted">Verification begins only after execution.</p>';
}

function wireActions(incident) {
  const approved = incident.approvals.some((item) => !item.consumed_at);
  const executed = incident.action_attempts.length ? incident.action_attempts[incident.action_attempts.length - 1] : null;
  state.recoveryJobId = executed ? executed.job_id : state.recoveryJobId;
  $('#approve-button').disabled = approved || incident.status !== 'awaiting_approval';
  $('#execute-button').disabled = !approved || incident.status !== 'awaiting_approval';
  $('#verify-button').disabled = !state.recoveryJobId || incident.status !== 'recovering';
  $('#approve-button').onclick = () => act('approve', { actor: $('#actor').value });
  $('#execute-button').onclick = async () => {
    const result = await act('execute', {});
    if (result) state.recoveryJobId = result.recovery_job_id;
  };
  $('#verify-button').onclick = () => act('verify', { recovery_job_id: state.recoveryJobId });
}

async function act(operation, body) {
  try {
    $('#action-message').textContent = label(operation) + ' in progress…';
    const result = await api('/api/incidents/' + state.selected + '/' + operation, {
      method: 'POST', body: JSON.stringify(body)
    });
    await refresh();
    return result;
  } catch (error) {
    $('#action-message').textContent = error.message;
    return null;
  }
}

$('#inject-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const incident = await api('/api/scenarios/' + $('#scenario').value, {
      method: 'POST', body: '{}'
    });
    state.selected = incident.id;
    state.recoveryJobId = null;
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
});
$('#refresh').addEventListener('click', refresh);

function label(value) {
  return String(value || '').split('.').join(' ').split('_').join(' ').replace(
    /(^| )([a-z])/g, (match, space, letter) => space + letter.toUpperCase()
  );
}
function html(value) {
  const node = document.createElement('span');
  node.textContent = String(value);
  return node.innerHTML;
}

refresh().catch((error) => { $('#health-label').textContent = error.message; });

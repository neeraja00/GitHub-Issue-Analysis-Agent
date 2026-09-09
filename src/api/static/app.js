/**
 * GitHub Issue Analysis Agent — Dashboard Application Logic
 */

let currentRunId = null;
let currentReport = null;
let currentIssues = [];
let activeEventSource = null;
let selectedCategoryFilter = 'all';
let selectedPriorityFilter = 'all';
let searchQuery = '';

// DOM Elements
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');
const runModal = document.getElementById('runModal');
const btnOpenModal = document.getElementById('btnOpenModal');
const btnCloseModal = document.getElementById('btnCloseModal');
const btnCancelModal = document.getElementById('btnCancelModal');
const btnStartRun = document.getElementById('btnStartRun');

const trackerCard = document.getElementById('trackerCard');
const runTitle = document.getElementById('runTitle');
const runSubtext = document.getElementById('runSubtext');
const progressPct = document.getElementById('progressPct');
const progressBar = document.getElementById('progressBar');

const kpiAnalyzed = document.getElementById('kpiAnalyzed');
const kpiCritical = document.getElementById('kpiCritical');
const kpiHigh = document.getElementById('kpiHigh');
const kpiDuplicates = document.getElementById('kpiDuplicates');
const kpiCloses = document.getElementById('kpiCloses');

const issuesTableBody = document.getElementById('issuesTableBody');
const duplicateContainer = document.getElementById('duplicateContainer');
const reportPreview = document.getElementById('reportPreview');
const logStream = document.getElementById('logStream');
const searchInput = document.getElementById('searchInput');

// Drawer Elements
const drawerOverlay = document.getElementById('drawerOverlay');
const issueDrawer = document.getElementById('issueDrawer');
const btnCloseDrawer = document.getElementById('btnCloseDrawer');
const btnCopyComment = document.getElementById('btnCopyComment');
const btnCopyReport = document.getElementById('btnCopyReport');
const btnDownloadMd = document.getElementById('btnDownloadMd');
const btnDownloadJson = document.getElementById('btnDownloadJson');
const btnClearLogs = document.getElementById('btnClearLogs');

// Pipeline Step IDs
const STEP_IDS = [
  'step-init', 'step-fetch', 'step-classify', 'step-prioritize',
  'step-deduplicate', 'step-draft_action', 'step-critique', 'step-report'
];

const STEP_ORDER_MAP = {
  'initialize': 0, 'metadata': 0,
  'fetch': 1,
  'classify': 2,
  'prioritize': 3,
  'deduplicate': 4,
  'draft_action': 5,
  'critique': 6,
  'report': 7,
  'apply': 7,
  'complete': 7
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadLatestRun();
});

function setupEventListeners() {
  // Modal handlers
  btnOpenModal.addEventListener('click', () => runModal.classList.add('open'));
  btnCloseModal.addEventListener('click', () => runModal.classList.remove('open'));
  btnCancelModal.addEventListener('click', () => runModal.classList.remove('open'));
  btnStartRun.addEventListener('click', handleStartRun);

  // Drawer handlers
  btnCloseDrawer.addEventListener('click', closeDrawer);
  drawerOverlay.addEventListener('click', closeDrawer);

  // Tab Switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  // Filter Pills
  document.querySelectorAll('#categoryPills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#categoryPills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedCategoryFilter = btn.dataset.filterCat;
      renderIssuesTable();
    });
  });

  document.querySelectorAll('#priorityPills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#priorityPills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedPriorityFilter = btn.dataset.filterPrio;
      renderIssuesTable();
    });
  });

  // Search filter
  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    renderIssuesTable();
  });

  // Copy & Download Handlers
  btnCopyComment.addEventListener('click', () => {
    const text = document.getElementById('drawerCommentBox').innerText;
    navigator.clipboard.writeText(text);
    btnCopyComment.innerText = '✓ Copied!';
    setTimeout(() => { btnCopyComment.innerText = 'Copy Comment'; }, 2000);
  });

  btnCopyReport.addEventListener('click', () => {
    const text = reportPreview.innerText;
    navigator.clipboard.writeText(text);
    btnCopyReport.innerText = '✓ Copied!';
    setTimeout(() => { btnCopyReport.innerText = '📋 Copy Markdown'; }, 2000);
  });

  btnDownloadMd.addEventListener('click', () => {
    if (!currentReport) return;
    const blob = new Blob([reportPreview.innerText], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentReport.repository.replace('/', '_')}_triage_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  });

  btnDownloadJson.addEventListener('click', () => {
    if (!currentReport) return;
    const blob = new Blob([JSON.stringify(currentReport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentReport.repository.replace('/', '_')}_triage_report.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  btnClearLogs.addEventListener('click', () => {
    logStream.innerHTML = '<span style="color: var(--text-muted);">Logs cleared.</span>';
  });
}

function selectRepo(repoName) {
  document.getElementById('repoInput').value = repoName;
}

// Start Analysis Execution
async function handleStartRun() {
  const repo = document.getElementById('repoInput').value.trim();
  const goal = document.getElementById('goalInput').value.trim();
  const limit = parseInt(document.getElementById('limitInput').value, 10) || 10;
  const provider = document.getElementById('providerSelect').value;
  const dryRun = document.getElementById('dryRunCheck').checked;

  if (!repo) {
    alert('Please enter a target repository.');
    return;
  }

  btnStartRun.disabled = true;
  btnStartRun.innerText = 'Launching...';

  try {
    const resp = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo,
        goal,
        limit,
        provider,
        dry_run: dryRun,
        apply: !dryRun,
      }),
    });

    if (!resp.ok) throw new Error(`HTTP error: ${resp.status}`);
    const data = await resp.json();

    runModal.classList.remove('open');
    currentRunId = data.run_id;

    // Reset UI for new run
    resetProgress(repo);
    subscribeToSSE(currentRunId);
    pollForLogs(currentRunId);
  } catch (err) {
    alert(`Failed to launch analysis: ${err.message}`);
  } finally {
    btnStartRun.disabled = false;
    btnStartRun.innerText = '🚀 Start Autonomous Agent';
  }
}

function resetProgress(repo) {
  statusBadge.className = 'status-badge running';
  statusText.innerText = 'Agent Active';
  runTitle.innerText = `Active Run: ${repo}`;
  runSubtext.innerText = 'Initializing triage pipeline...';
  progressBar.style.width = '5%';
  progressPct.innerText = '5%';

  STEP_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'step-node';
  });
  document.getElementById('step-init').classList.add('active');
}

function updateStepper(stepName, percent) {
  progressBar.style.width = `${percent}%`;
  progressPct.innerText = `${percent}%`;

  const targetIdx = STEP_ORDER_MAP[stepName] ?? -1;
  STEP_IDS.forEach((id, idx) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (idx < targetIdx) {
      el.className = 'step-node done';
    } else if (idx === targetIdx) {
      el.className = 'step-node active';
    } else {
      el.className = 'step-node';
    }
  });
}

// Subscribe to SSE
function subscribeToSSE(runId) {
  if (activeEventSource) {
    activeEventSource.close();
  }

  activeEventSource = new EventSource(`/api/runs/${runId}/events`);

  activeEventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.message) {
        runSubtext.innerText = data.message;
      }
      if (data.percent !== undefined) {
        updateStepper(data.step, data.percent);
      }
      if (data.step === 'complete') {
        activeEventSource.close();
        statusBadge.className = 'status-badge';
        statusText.innerText = 'Completed';
        fetchRunDetails(runId);
      } else if (data.step === 'error') {
        activeEventSource.close();
        statusBadge.className = 'status-badge';
        statusBadge.style.color = 'var(--accent-rose)';
        statusText.innerText = 'Failed';
      }
    } catch (err) {
      console.error('SSE parse error', err);
    }
  };

  activeEventSource.onerror = () => {
    // Fallback: poll run details every 2 seconds if SSE is interrupted
    setTimeout(() => fetchRunDetails(runId), 2500);
  };
}

// Fetch Run Details & Report
async function fetchRunDetails(runId) {
  try {
    const resp = await fetch(`/api/runs/${runId}`);
    if (!resp.ok) return;
    const data = await resp.json();

    if (data.report) {
      currentReport = data.report;
      currentIssues = data.report.issues || [];
      renderKPIs(data.report.stats);
      renderIssuesTable();
      renderDuplicates(currentIssues);
      fetchMarkdownReport(runId);
    }
  } catch (err) {
    console.error('Failed to load run details:', err);
  }
}

async function fetchMarkdownReport(runId) {
  try {
    const resp = await fetch(`/api/reports/${runId}`);
    if (resp.ok) {
      const data = await resp.json();
      if (data.markdown) {
        reportPreview.innerText = data.markdown;
      }
    }
  } catch (err) {
    console.error('Report fetch error', err);
  }
}

// Poll Logs for Telemetry Tab
async function pollForLogs(runId) {
  try {
    const resp = await fetch(`/api/runs/${runId}/logs`);
    if (!resp.ok) return;
    const events = await resp.json();

    if (events.length > 0) {
      logStream.innerHTML = events.map(evt => {
        const time = evt.timestamp ? evt.timestamp.split('T')[1].split('.')[0] : '';
        const cls = evt.event_type || '';
        const tokens = evt.tokens ? ` | Tokens: ${evt.tokens}` : '';
        const lat = evt.latency_ms ? ` (${evt.latency_ms}ms)` : '';
        return `<div class="log-entry ${cls}">[${time}][${evt.step?.toUpperCase() || ''}] ${evt.message}${lat}${tokens}</div>`;
      }).join('');
      logStream.scrollTop = logStream.scrollHeight;
    }
  } catch (e) {}

  if (activeEventSource && activeEventSource.readyState !== 2) {
    setTimeout(() => pollForLogs(runId), 3000);
  }
}

// Render KPI Cards
function renderKPIs(stats) {
  if (!stats) return;
  kpiAnalyzed.innerText = stats.total_issues_analyzed || 0;
  kpiCritical.innerText = stats.priorities_breakdown?.critical || 0;
  kpiHigh.innerText = stats.priorities_breakdown?.high || 0;
  kpiDuplicates.innerText = stats.duplicates_detected || 0;
  kpiCloses.innerText = stats.recommended_closes || 0;
}

// Render Issues Table with Search and Filtering
function renderIssuesTable() {
  if (!currentIssues || currentIssues.length === 0) {
    issuesTableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">
          No issues found matching active filters.
        </td>
      </tr>`;
    return;
  }

  const filtered = currentIssues.filter(rec => {
    const issue = rec.issue;
    const cls = rec.classification;
    const prio = rec.priority;

    // Category filter
    if (selectedCategoryFilter !== 'all' && cls?.category !== selectedCategoryFilter) {
      return false;
    }

    // Priority filter
    if (selectedPriorityFilter !== 'all' && prio?.level !== selectedPriorityFilter) {
      return false;
    }

    // Search query
    if (searchQuery) {
      const matchNum = issue.number.toString().includes(searchQuery);
      const matchTitle = issue.title.toLowerCase().includes(searchQuery);
      const matchAuthor = issue.author.toLowerCase().includes(searchQuery);
      if (!matchNum && !matchTitle && !matchAuthor) return false;
    }

    return true;
  });

  if (filtered.length === 0) {
    issuesTableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
          No issues match the selected filter criteria.
        </td>
      </tr>`;
    return;
  }

  issuesTableBody.innerHTML = filtered.map(rec => {
    const issue = rec.issue;
    const cls = rec.classification;
    const prio = rec.priority;
    const act = rec.action;

    const catBadge = getCategoryBadge(cls?.category);
    const prioBadge = getPriorityBadge(prio?.level, prio?.numerical_score);

    return `
      <tr>
        <td>
          <a href="${issue.html_url || '#'}" target="_blank" class="issue-number">#${issue.number}</a>
        </td>
        <td>
          <div class="issue-title">${escapeHtml(issue.title)}</div>
          <div class="issue-meta">Opened by @${escapeHtml(issue.author)} · ${issue.comments_count} comments</div>
        </td>
        <td>${catBadge}</td>
        <td>${prioBadge}</td>
        <td>
          <div style="font-weight: 500; color: var(--text-primary); font-size: 0.85rem;">
            ${escapeHtml(act?.headline || 'Needs triage')}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">
            ${act?.should_close ? '<span style="color: var(--accent-rose)">● Close Recommended</span>' : ''}
          </div>
        </td>
        <td style="text-align: right;">
          <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;" onclick="openIssueDrawer(${issue.number})">
            Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function getCategoryBadge(cat) {
  if (!cat) return '<span class="badge">Unknown</span>';
  const map = {
    bug: 'badge-bug',
    feature_request: 'badge-feature',
    question: 'badge-question',
    documentation: 'badge-docs',
    duplicate: 'badge-dup',
    spam: 'badge-spam',
  };
  const cls = map[cat] || 'badge';
  const label = cat.replace('_', ' ');
  return `<span class="badge ${cls}">${label}</span>`;
}

function getPriorityBadge(level, score) {
  if (!level) return '<span class="prio-pill prio-low">N/A</span>';
  const map = {
    critical: 'prio-critical',
    high: 'prio-high',
    medium: 'prio-medium',
    low: 'prio-low',
  };
  const cls = map[level] || 'prio-low';
  const scoreText = score !== undefined ? ` (${score})` : '';
  return `<span class="prio-pill ${cls}">${level.toUpperCase()}${scoreText}</span>`;
}

// Render Duplicate Graph Cards
function renderDuplicates(issues) {
  const dups = issues.filter(r => r.deduplication && r.deduplication.is_duplicate);

  if (dups.length === 0) {
    duplicateContainer.innerHTML = `
      <div style="color: var(--text-muted); padding: 2rem; grid-column: 1 / -1; text-align: center;">
        No duplicate issues detected in this triage run.
      </div>`;
    return;
  }

  duplicateContainer.innerHTML = dups.map(rec => {
    const issue = rec.issue;
    const dedup = rec.deduplication;
    const match = dedup.best_match;
    const scorePct = Math.round((dedup.confidence || match?.similarity_score || 0.8) * 100);

    return `
      <div class="duplicate-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <span style="font-weight: 700; color: var(--accent-violet);">Duplicate Cluster</span>
          <span class="sim-score-badge">${scorePct}% Semantic Match</span>
        </div>
        <div class="duplicate-pair">
          <div class="duplicate-item">
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.2rem;">Newer Issue</div>
            <strong style="color: var(--accent-cyan);">#${issue.number}</strong>
            <div style="font-size: 0.8rem; margin-top: 0.2rem;">${escapeHtml(issue.title)}</div>
          </div>
          <div class="duplicate-arrow">➔</div>
          <div class="duplicate-item">
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.2rem;">Canonical Original</div>
            <strong style="color: var(--accent-emerald);">#${match?.target_issue_number || '?'}</strong>
            <div style="font-size: 0.8rem; margin-top: 0.2rem;">Canonical Issue</div>
          </div>
        </div>
        <div style="font-size: 0.825rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
          <strong>Rationale:</strong> ${escapeHtml(match?.rationale || 'Shares identical symptoms and root cause.')}
        </div>
        ${match?.matching_aspects?.length ? `
          <div style="font-size: 0.775rem; color: var(--text-muted);">
            Matching: ${match.matching_aspects.map(a => `<code>${escapeHtml(a)}</code>`).join(' ')}
          </div>` : ''}
      </div>
    `;
  }).join('');
}

// Issue Detail Drawer Inspection
function openIssueDrawer(issueNumber) {
  const rec = currentIssues.find(r => r.issue.number === issueNumber);
  if (!rec) return;

  const issue = rec.issue;
  const cls = rec.classification;
  const prio = rec.priority;
  const act = rec.action;

  document.getElementById('drawerIssueNum').innerText = `#${issue.number}`;
  document.getElementById('drawerIssueTitle').innerText = issue.title;

  document.getElementById('drawerCategoryBadge').outerHTML = getCategoryBadge(cls?.category);
  document.getElementById('drawerPriorityBadge').outerHTML = getPriorityBadge(prio?.level, prio?.numerical_score);
  document.getElementById('drawerConfidence').innerText = cls?.confidence ? `${Math.round(cls.confidence * 100)}% confidence` : '';

  document.getElementById('drawerReasoning').innerText = cls?.reasoning || 'No reasoning recorded.';
  document.getElementById('drawerActionHeadline').innerText = act?.headline || 'Standard review';
  document.getElementById('drawerActionReasoning').innerText = act?.reasoning || 'Default maintainer triage.';

  const commentBox = document.getElementById('drawerCommentBox');
  if (act?.draft_comment) {
    commentBox.innerText = act.draft_comment;
    document.getElementById('drawerCommentSection').style.display = 'block';
  } else {
    document.getElementById('drawerCommentSection').style.display = 'none';
  }

  const labelsDiv = document.getElementById('drawerLabels');
  if (act?.labels_to_add?.length) {
    labelsDiv.innerHTML = act.labels_to_add.map(l => `<span class="pill-btn">${escapeHtml(l)}</span>`).join('');
  } else {
    labelsDiv.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">None proposed</span>';
  }

  document.getElementById('drawerIssueBody').innerText = issue.body || '(No issue description provided)';

  drawerOverlay.classList.add('open');
  issueDrawer.classList.add('open');
}

function closeDrawer() {
  drawerOverlay.classList.remove('open');
  issueDrawer.classList.remove('open');
}

// Load Initial / Historical Run
async function loadLatestRun() {
  try {
    const resp = await fetch('/api/runs');
    if (!resp.ok) return;
    const runs = await resp.json();
    if (runs && runs.length > 0) {
      const latest = runs[0];
      currentRunId = latest.run_id;
      runTitle.innerText = `Latest Run: ${latest.repo}`;
      runSubtext.innerText = latest.goal;
      progressBar.style.width = '100%';
      progressPct.innerText = '100%';
      updateStepper('complete', 100);
      fetchRunDetails(latest.run_id);
    }
  } catch (e) {
    console.error('Failed to load runs list', e);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

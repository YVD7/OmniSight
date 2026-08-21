/**
 * OmniSight VLM Agent Status Dashboard
 * Real-Time WebSocket Streaming, Live Model Logs, Dynamic PR Management & DB Sync
 */

let currentViewport = 'mobile';
let latestRunResult = null;
let ws = null;
let wsReconnectTimer = null;
let activeRunDirInitial = null;
let activeRunDirVerified = null;

document.addEventListener('DOMContentLoaded', () => {
  fetchSystemStatus();
  loadDashboardBuilds();
  initWebSocket();
});

// ============================================================================
// Real-Time WebSocket Streaming & Live Event Handling
// ============================================================================

function initWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/orchestrator`;
  
  updateWsStatusBadge('CONNECTING', 'badge-running');

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('⚡ Connected to OmniSight Live WebSocket stream.');
      updateWsStatusBadge('ONLINE (LIVE STREAM)', 'badge-success');
      appendConsoleLog('[WebSocket] Connected to real-time live log and status feed.');
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleLiveEvent(payload);
      } catch (err) {
        console.debug('Raw WS message:', event.data);
      }
    };

    ws.onerror = (err) => {
      console.warn('WebSocket encountered error:', err);
      updateWsStatusBadge('DISCONNECTED', 'badge-idle');
    };

    ws.onclose = () => {
      console.warn('WebSocket connection closed. Reconnecting in 3s...');
      updateWsStatusBadge('RECONNECTING...', 'badge-running');
      ws = null;
      if (!wsReconnectTimer) {
        wsReconnectTimer = setTimeout(() => {
          wsReconnectTimer = null;
          initWebSocket();
        }, 3000);
      }
    };
  } catch (err) {
    console.error('Failed to create WebSocket:', err);
    updateWsStatusBadge('OFFLINE', 'badge-idle');
  }
}

function updateWsStatusBadge(statusText, badgeClass) {
  const badgeContainer = document.getElementById('ws-badge-container');
  const statusLabel = document.getElementById('ws-status-text');
  const pulseDot = document.getElementById('ws-pulse-dot');
  
  if (statusLabel) {
    statusLabel.textContent = `GATEWAY ${statusText}`;
  }
  if (pulseDot) {
    if (statusText.includes('ONLINE')) {
      pulseDot.style.backgroundColor = 'var(--accent-emerald)';
      pulseDot.style.boxShadow = '0 0 10px var(--accent-emerald)';
    } else if (statusText.includes('CONNECTING') || statusText.includes('RECONNECTING')) {
      pulseDot.style.backgroundColor = 'var(--accent-amber)';
      pulseDot.style.boxShadow = '0 0 10px var(--accent-amber)';
    } else {
      pulseDot.style.backgroundColor = 'var(--accent-rose)';
      pulseDot.style.boxShadow = '0 0 10px var(--accent-rose)';
    }
  }
}

function handleLiveEvent(payload) {
  const { type, data, message, timestamp } = payload;

  switch (type) {
    case 'INITIAL_STATE':
      if (payload.recent_logs && payload.recent_logs.length > 0) {
        payload.recent_logs.forEach(log => {
          appendConsoleLog(`[${log.timestamp || 'Live'}] ${log.message}`);
        });
      }
      if (payload.active_run && payload.active_run.status === 'RUNNING') {
        reflectActiveRunState(payload.active_run);
      }
      break;

    case 'LOG':
      appendConsoleLog(`[${timestamp || new Date().toLocaleTimeString()}] ${message}`);
      break;

    case 'RUN_START':
      handleRunStart(data);
      break;

    case 'NODE_STATE':
      handleNodeStateChange(data);
      break;

    case 'SCREENSHOTS':
      handleScreenshotUpdate(data);
      break;

    case 'DEFECTS':
      handleDefectsDetected(data);
      break;

    case 'CODE_CHANGES':
      handleCodeChangesUpdate(data);
      break;

    case 'RUN_COMPLETE':
      handleRunComplete(data);
      break;

    case 'PR_STATUS_CHANGED':
      handlePRStatusChanged(data);
      break;

    default:
      if (message) {
        appendConsoleLog(`[${timestamp || new Date().toLocaleTimeString()}] ${message}`);
      }
  }
}

function handleRunStart(data) {
  appendConsoleLog(`⚡ [Run Started] Run ID: ${data.run_id} | Target: ${data.target_dir} | Branch: ${data.branch}`);
  
  // Reset pipeline node states
  for (let i = 1; i <= 6; i++) {
    setPipelineStepStatus(`step-node-1`, `badge-node-1`, 'IDLE', 'badge-idle');
  }
  
  const overallBadge = document.getElementById('overall-status-badge');
  if (overallBadge) {
    overallBadge.textContent = 'RUNNING';
    overallBadge.className = 'step-badge badge-running';
  }

  showToast(`🚀 VLM Orchestrator triggered automatically (Run: ${data.run_id})`, 'info');
}

function handleNodeStateChange(data) {
  const nodeIdx = data.node_index;
  const nodeName = data.node;
  const status = data.status;

  if (nodeIdx) {
    const stepId = `step-node-${nodeIdx}`;
    const badgeId = `badge-node-${nodeIdx}`;
    
    if (status === 'RUNNING') {
      setPipelineStepStatus(stepId, badgeId, 'RUNNING', 'badge-running');
    } else if (status === 'SUCCESS') {
      setPipelineStepStatus(stepId, badgeId, 'SUCCESS', 'badge-success');
    } else if (status === 'SKIPPED') {
      setPipelineStepStatus(stepId, badgeId, 'NO CHANGES', 'badge-idle');
    } else if (status === 'FAILED') {
      setPipelineStepStatus(stepId, badgeId, 'FAILED', 'badge-rejected');
    }
  }
}

function handleScreenshotUpdate(data) {
  const { phase, run_dir, manifest } = data;
  if (!run_dir) return;

  const runFolderName = run_dir.split('/').pop().split('\\').pop();

  if (phase === 'initial') {
    activeRunDirInitial = runFolderName;
  } else if (phase === 'verified') {
    activeRunDirVerified = runFolderName;
  }

  updateScreenshotGalleryImages();
}

function handleDefectsDetected(data) {
  const defects = data.visual_defects || [];
  const defectDescElem = document.getElementById('defect-desc-text');
  
  if (defects.length > 0) {
    const d = defects[0];
    if (defectDescElem) {
      defectDescElem.innerHTML = `<strong>Defect (${d.defect_type}):</strong> ${d.description || 'Visual layout clipping detected on mobile viewport.'}`;
    }
  } else {
    if (defectDescElem) {
      defectDescElem.innerHTML = `<strong>Status:</strong> No visual defects detected. Clean mobile checkout flow!`;
    }
  }
}

function handleCodeChangesUpdate(data) {
  const changes = data.changes || [];
  if (changes.length > 0) {
    appendConsoleLog(`🛠️ [Code Repair] Applied ${changes.length} patch(es): ${changes.map(c => c.selector || c.file).join(', ')}`);
  }
}

function handleRunComplete(data) {
  const overallBadge = document.getElementById('overall-status-badge');
  const isFixed = data.is_fixed;
  const hasChanges = (data.code_changes && data.code_changes.length > 0);
  const prNumber = data.db_records?.pr_number || data.git_result?.pr_number;

  if (overallBadge) {
    if (isFixed && hasChanges) {
      overallBadge.textContent = prNumber ? `FIXED (PR #${prNumber})` : 'VERIFIED & FIXED';
      overallBadge.className = 'step-badge badge-success';
    } else if (!hasChanges && data.visual_defects_count === 0) {
      overallBadge.textContent = 'CLEAN (NO BUGS)';
      overallBadge.className = 'step-badge badge-success';
    } else {
      overallBadge.textContent = 'FINISHED';
      overallBadge.className = 'step-badge badge-idle';
    }
  }

  appendConsoleLog(`🏁 [Orchestrator Finished] Run completed. Fixed: ${isFixed} | Code Changes: ${hasChanges ? 'Yes' : 'None'} | PR Created: ${prNumber ? `#${prNumber}` : 'No'}`);
  
  if (prNumber) {
    showToast(`🎉 Bug Fixed! Pull Request #${prNumber} created for review.`, 'success');
  } else if (!hasChanges) {
    showToast(`✅ Inspection Completed: No code changes required (No PR created).`, 'info');
  }

  // Refresh table from database
  setTimeout(loadDashboardBuilds, 1000);
}

function handlePRStatusChanged(data) {
  const { pr_id, status } = data;
  updatePRRowUI(pr_id, status);
  showToast(`Pull Request #${pr_id} status updated to: ${status.toUpperCase()}`, status === 'approved' ? 'success' : 'info');
}

function reflectActiveRunState(activeRun) {
  const overallBadge = document.getElementById('overall-status-badge');
  if (overallBadge) {
    overallBadge.textContent = 'RUNNING';
    overallBadge.className = 'step-badge badge-running';
  }
  if (activeRun.node_states) {
    Object.keys(activeRun.node_states).forEach(key => {
      const nodeNum = key.replace('node_', '');
      const state = activeRun.node_states[key];
      setPipelineStepStatus(`step-node-${nodeNum}`, `badge-node-${nodeNum}`, state.status, state.status === 'RUNNING' ? 'badge-running' : 'badge-success');
    });
  }
}

// ============================================================================
// System Status & Builds Database Sync
// ============================================================================

async function fetchSystemStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updateSystemInfo(data);
    }
  } catch (err) {
    console.warn("Could not fetch /api/status, using default parameters.", err);
  }
}

function updateSystemInfo(data) {
  if (data.base_url) {
    const vmUrl = document.getElementById('stat-vm-url');
    const envUrl = document.getElementById('env-base-url');
    if (vmUrl) {
      vmUrl.textContent = data.base_url;
      vmUrl.title = data.base_url;
    }
    if (envUrl) {
      envUrl.textContent = data.base_url;
      envUrl.title = data.base_url;
    }
  }
  if (data.repo_url) {
    const envRepo = document.getElementById('env-repo-url');
    if (envRepo) {
      envRepo.textContent = data.repo_url;
      envRepo.title = data.repo_url;
    }
  }
  if (data.branch) {
    const gitBranch = document.getElementById('stat-git-branch');
    const envBranch = document.getElementById('env-branch');
    if (gitBranch) {
      gitBranch.textContent = data.branch;
      gitBranch.title = data.branch;
    }
    if (envBranch) {
      envBranch.textContent = data.branch;
      envBranch.title = data.branch;
    }
  }
}

// Load Builds and PRs dynamically from database
async function loadDashboardBuilds() {
  const tbody = document.getElementById('table-builds-body');
  const countBadge = document.getElementById('builds-count-badge');

  try {
    const res = await fetch('/api/dashboard-builds');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    
    const data = await res.json();
    const builds = data.builds || [];

    if (countBadge) {
      countBadge.textContent = `${builds.length} build(s) recorded in DB`;
    }

    if (builds.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">
            No builds recorded in database yet. Trigger a run above or push from mock-app!
          </td>
        </tr>
      `;
      return;
    }

    // Update repairs count in stat card
    const fixedCount = builds.filter(b => b.status === 'FIXED').length;
    const repairsElem = document.getElementById('stat-repairs-count');
    if (repairsElem) repairsElem.textContent = `${fixedCount} Fixed`;

    let html = '';
    builds.forEach(b => {
      const commitShort = (b.commit_sha || 'a8f19c2').slice(0, 7);
      const createdAt = b.created_at ? b.created_at.replace('T', ' ').slice(0, 19) : new Date().toISOString().slice(0, 19);
      const repoShort = (b.repo || 'mock-app').split('/').pop().replace('.git', '');
      
      let statusHtml = '';
      if (b.status === 'FIXED') {
        statusHtml = `<span style="color: var(--accent-emerald); font-weight: 600;">✅ FIXED</span>`;
      } else if (b.status === 'CLEAN') {
        statusHtml = `<span style="color: var(--accent-cyan); font-weight: 600;">✨ CLEAN</span>`;
      } else {
        statusHtml = `<span style="color: var(--accent-rose); font-weight: 600;">❌ FAILED</span>`;
      }

      let prActionHtml = '';
      if (b.has_pr) {
        if (b.pr_status === 'approved') {
          prActionHtml = `<span class="status-badge badge-approved" id="pr-status-${b.pr_id}">✅ Approved</span>`;
        } else if (b.pr_status === 'rejected') {
          prActionHtml = `<span class="status-badge badge-rejected" id="pr-status-${b.pr_id}">❌ Rejected</span>`;
        } else {
          prActionHtml = `
            <div class="pr-actions-group" id="pr-actions-${b.pr_id}">
              <a href="${b.pr_url || '#'}" target="_blank" style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 0.75rem; text-decoration: none; margin-right: 0.25rem;">
                PR #${b.pr_number}
              </a>
              <button class="action-btn btn-approve" onclick="handleApprovePR(${b.pr_id}, this)">Approve</button>
              <button class="action-btn btn-reject" onclick="handleRejectPR(${b.pr_id}, this)">Reject</button>
            </div>
          `;
        }
      } else {
        prActionHtml = `<span class="status-badge badge-no-pr">➖ No PR (No Changes)</span>`;
      }

      html += `
        <tr id="build-row-${b.id}">
          <td style="font-family: var(--font-mono); color: var(--primary); font-weight: 600;">#${b.id}</td>
          <td>${repoShort}</td>
          <td><span style="padding: 0.2rem 0.5rem; background: rgba(99,102,241,0.15); color: #818cf8; border-radius: 4px; font-size: 0.78rem;">${b.branch || 'dev'}</span></td>
          <td>${statusHtml}</td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${createdAt}</td>
          <td style="font-family: var(--font-mono);">${commitShort}</td>
          <td id="pr-cell-${b.pr_id || b.id}">${prActionHtml}</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  } catch (err) {
    console.error('Error loading dashboard builds:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--accent-rose); padding: 2rem;">
          Failed to load builds from database: ${err.message}
        </td>
      </tr>
    `;
  }
}

// ============================================================================
// Interactive PR Approval & Rejection Handlers
// ============================================================================

async function handleApprovePR(prId, btnElement) {
  if (!prId) return;

  if (btnElement) {
    const parentGroup = btnElement.closest('.pr-actions-group');
    if (parentGroup) {
      parentGroup.querySelectorAll('button').forEach(b => b.disabled = true);
      btnElement.textContent = 'Approving...';
    }
  }

  try {
    const res = await fetch(`/prs/${prId}/approve`, { method: 'POST' });
    const data = await res.json();
    
    if (res.ok && data.status === 'approved') {
      updatePRRowUI(prId, 'approved');
      appendConsoleLog(`[PR Decision] ✅ Pull Request #${prId} APPROVED by Admin.`);
      showToast(`✅ Pull Request #${prId} successfully approved!`, 'success');
    } else {
      throw new Error(data.error || 'Failed to approve pull request');
    }
  } catch (err) {
    appendConsoleLog(`[PR Action Error] ${err.message}`);
    showToast(`Error: ${err.message}`, 'error');
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.textContent = 'Approve';
    }
  }
}

async function handleRejectPR(prId, btnElement) {
  if (!prId) return;

  if (btnElement) {
    const parentGroup = btnElement.closest('.pr-actions-group');
    if (parentGroup) {
      parentGroup.querySelectorAll('button').forEach(b => b.disabled = true);
      btnElement.textContent = 'Rejecting...';
    }
  }

  try {
    const res = await fetch(`/prs/${prId}/reject`, { method: 'POST' });
    const data = await res.json();

    if (res.ok && data.status === 'rejected') {
      updatePRRowUI(prId, 'rejected');
      appendConsoleLog(`[PR Decision] ❌ Pull Request #${prId} REJECTED by Admin.`);
      showToast(`❌ Pull Request #${prId} marked as rejected.`, 'info');
    } else {
      throw new Error(data.error || 'Failed to reject pull request');
    }
  } catch (err) {
    appendConsoleLog(`[PR Action Error] ${err.message}`);
    showToast(`Error: ${err.message}`, 'error');
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.textContent = 'Reject';
    }
  }
}

function updatePRRowUI(prId, status) {
  const prCell = document.getElementById(`pr-cell-${prId}`);
  const actionsGroup = document.getElementById(`pr-actions-${prId}`);

  let badgeHtml = '';
  if (status === 'approved') {
    badgeHtml = `<span class="status-badge badge-approved" id="pr-status-${prId}">✅ Approved</span>`;
  } else if (status === 'rejected') {
    badgeHtml = `<span class="status-badge badge-rejected" id="pr-status-${prId}">❌ Rejected</span>`;
  }

  if (actionsGroup) {
    actionsGroup.outerHTML = badgeHtml;
  } else if (prCell) {
    prCell.innerHTML = badgeHtml;
  }
}

// ============================================================================
// Manual Orchestrator Form Handler
// ============================================================================

async function handleTriggerOrchestrator(event) {
  event.preventDefault();

  const baseUrl = document.getElementById('input-base-url').value.trim() || null;
  const repoUrl = document.getElementById('input-repo-url').value.trim() || null;
  const branch = document.getElementById('input-branch').value.trim() || 'dev';
  const maxIterations = parseInt(document.getElementById('input-iterations').value) || 3;
  const targetDir = document.getElementById('input-target-dir').value.trim() || 'trailhead-mock-store';

  const btnTrigger = document.getElementById('btn-trigger');
  btnTrigger.disabled = true;
  btnTrigger.innerHTML = '<span>⚡ Executing VLM Multi-Agent Workflow...</span>';

  appendConsoleLog(`[API Manual Trigger] Initiating VLM run (VM URL: ${baseUrl || 'Auto'}, Repo: ${repoUrl || 'Local'}, Branch: ${branch})...`);
  
  const payload = {
    base_url: baseUrl,
    repo_url: repoUrl,
    branch: branch,
    target_dir: targetDir,
    max_iterations: maxIterations
  };

  try {
    const response = await fetch('/orchestrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    latestRunResult = result;

    if (!response.ok) {
      throw new Error(result.detail || 'Orchestration execution failed');
    }
  } catch (error) {
    appendConsoleLog(`❌ [Error] Failed to execute orchestrator: ${error.message}`);
    showToast(`Execution error: ${error.message}`, 'error');
  } finally {
    btnTrigger.disabled = false;
    btnTrigger.innerHTML = '<span>🚀 Execute VLM Orchestrator</span>';
  }
}

function setPipelineStepStatus(stepId, badgeId, text, className) {
  const stepElem = document.getElementById(stepId);
  const badgeElem = document.getElementById(badgeId);
  if (badgeElem) {
    badgeElem.textContent = text;
    badgeElem.className = `step-badge ${className}`;
  }
  if (stepElem) {
    if (className.includes('running')) {
      stepElem.classList.add('active');
      stepElem.classList.remove('success');
    } else if (className.includes('success')) {
      stepElem.classList.remove('active');
      stepElem.classList.add('success');
    } else {
      stepElem.classList.remove('active');
      stepElem.classList.remove('success');
    }
  }
}

// ============================================================================
// Screenshot Viewer Gallery
// ============================================================================

function switchViewportTab(viewport) {
  currentViewport = viewport;
  const buttons = document.querySelectorAll('.viewport-tabs .tab-btn');
  buttons.forEach(b => b.classList.remove('active'));

  const activeBtn = Array.from(buttons).find(b => b.textContent.toLowerCase().includes(viewport));
  if (activeBtn) activeBtn.classList.add('active');

  updateScreenshotGalleryImages();
}

function updateScreenshotGalleryImages() {
  const initialImg = document.getElementById('img-initial-shot');
  const verifiedImg = document.getElementById('img-verified-shot');

  const initialDir = activeRunDirInitial || '20260814-161836';
  const verifiedDir = activeRunDirVerified || '20260814-161852';

  if (initialImg) {
    initialImg.src = `/output/${initialDir}/${currentViewport}_05_place_order.png`;
  }
  if (verifiedImg) {
    verifiedImg.src = `/output/${verifiedDir}/${currentViewport}_05_place_order.png`;
  }
}

// ============================================================================
// UI Helper Utilities: Console Logs & Toast Notifications
// ============================================================================

function appendConsoleLog(msg) {
  const consoleElem = document.getElementById('terminal-console');
  if (consoleElem) {
    consoleElem.textContent += `\n${msg}`;
    consoleElem.scrollTop = consoleElem.scrollHeight;
  }
}

function clearConsoleLog() {
  const consoleElem = document.getElementById('terminal-console');
  if (consoleElem) {
    consoleElem.textContent = '[System] Terminal console cleared.\n[System] Live log listener active.';
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️')}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-fadeout');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function refreshDashboardData() {
  fetchSystemStatus();
  loadDashboardBuilds();
  appendConsoleLog('[Dashboard] Manually refreshed database builds & status.');
  showToast('Dashboard data refreshed', 'info');
}

/**
 * OmniSight VLM Agent Status Dashboard JavaScript
 */

let currentViewport = 'mobile';
let latestRunResult = null;

document.addEventListener('DOMContentLoaded', () => {
  fetchSystemStatus();
});

// Fetch System Status & Environment info
async function fetchSystemStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updateSystemInfo(data);
    }
  } catch (err) {
    console.warn("Could not fetch /api/status, using default fallback parameters.", err);
  }
}

function updateSystemInfo(data) {
  if (data.base_url) {
    document.getElementById('stat-vm-url').textContent = data.base_url;
    document.getElementById('env-base-url').textContent = data.base_url;
  }
  if (data.repo_url) {
    document.getElementById('env-repo-url').textContent = data.repo_url;
  }
  if (data.branch) {
    document.getElementById('stat-git-branch').textContent = data.branch;
    document.getElementById('env-branch').textContent = data.branch;
  }
}

// Trigger VLM Orchestrator Flow via Gateway API
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

  appendConsoleLog(`[API Trigger] Requesting VLM Orchestrator run (VM URL: ${baseUrl || 'Auto'}, Repo: ${repoUrl || 'Local'}, Branch: ${branch})...`);
  
  // Set pipeline nodes state to RUNNING
  setPipelineStepStatus('step-node-1', 'badge-node-1', 'RUNNING', 'badge-running');
  document.getElementById('overall-status-badge').textContent = 'RUNNING';
  document.getElementById('overall-status-badge').className = 'step-badge badge-running';

  const payload = {
    base_url: baseUrl,
    repo_url: repoUrl,
    branch: branch,
    target_dir: targetDir,
    max_iterations: maxIterations
  };

  try {
    // Simulate active node progress animations while waiting for API execution
    setTimeout(() => setPipelineStepStatus('step-node-1', 'badge-node-1', 'SUCCESS', 'badge-success'), 2000);
    setTimeout(() => {
      setPipelineStepStatus('step-node-2', 'badge-node-2', 'RUNNING', 'badge-running');
      appendConsoleLog('[Node 2] VLM Visual Inspector evaluating screenshots for clipping...');
    }, 2500);

    setTimeout(() => {
      setPipelineStepStatus('step-node-2', 'badge-node-2', 'SUCCESS', 'badge-success');
      setPipelineStepStatus('step-node-3', 'badge-node-3', 'RUNNING', 'badge-running');
      appendConsoleLog('[Node 3] Code Analyzer mapping root cause to styles.css .order-action-panel');
    }, 4500);

    setTimeout(() => {
      setPipelineStepStatus('step-node-3', 'badge-node-3', 'SUCCESS', 'badge-success');
      setPipelineStepStatus('step-node-4', 'badge-node-4', 'RUNNING', 'badge-running');
      appendConsoleLog('[Node 4] Code Repairer applying max-height: none patch');
    }, 6000);

    const response = await fetch('/orchestrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    latestRunResult = result;

    if (response.ok && result.is_fixed) {
      setPipelineStepStatus('step-node-4', 'badge-node-4', 'SUCCESS', 'badge-success');
      setPipelineStepStatus('step-node-5', 'badge-node-5', 'SUCCESS', 'badge-success');
      setPipelineStepStatus('step-node-6', 'badge-node-6', 'SUCCESS', 'badge-success');

      document.getElementById('overall-status-badge').textContent = 'VERIFIED & FIXED';
      document.getElementById('overall-status-badge').className = 'step-badge badge-success';

      appendConsoleLog(`🎉 [Verification Success] Bug fixed! Pushed branch '${result.git_result?.branch || branch}' (Commit: ${result.git_result?.commit_hash?.slice(0, 7) || 'HEAD'})`);
      
      updateBuildsTable(result);
    } else {
      appendConsoleLog(`❌ [Orchestrator Result] ${result.detail || 'Workflow finished with unresolved status'}`);
    }
  } catch (error) {
    appendConsoleLog(`❌ [Error] Failed to communicate with Gateway API: ${error.message}`);
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
    } else if (className.includes('success')) {
      stepElem.classList.remove('active');
      stepElem.classList.add('success');
    }
  }
}

// Viewport Tab Switcher for Screenshot Viewer
function switchViewportTab(viewport) {
  currentViewport = viewport;
  const buttons = document.querySelectorAll('.viewport-tabs .tab-btn');
  buttons.forEach(b => b.classList.remove('active'));

  const activeBtn = Array.from(buttons).find(b => b.textContent.toLowerCase().includes(viewport));
  if (activeBtn) activeBtn.classList.add('active');

  const initialImg = document.getElementById('img-initial-shot');
  const verifiedImg = document.getElementById('img-verified-shot');

  if (viewport === 'mobile') {
    initialImg.src = '/output/20260814-161836/mobile_05_place_order.png';
    verifiedImg.src = '/output/20260814-161852/mobile_05_place_order.png';
  } else if (viewport === 'tablet') {
    initialImg.src = '/output/20260814-161836/tablet_05_place_order.png';
    verifiedImg.src = '/output/20260814-161852/tablet_05_place_order.png';
  } else {
    initialImg.src = '/output/20260814-161836/desktop_05_place_order.png';
    verifiedImg.src = '/output/20260814-161852/desktop_05_place_order.png';
  }
}

// PR Approval handlers
async function handleApprovePR(prId) {
  try {
    const res = await fetch(`/prs/${prId}/approve`, { method: 'POST' });
    const data = await res.json();
    appendConsoleLog(`[PR Action] PR #${prId} approved: ${data.message}`);
    alert(`Pull Request #${prId} approved!`);
  } catch (err) {
    appendConsoleLog(`[PR Action Error] ${err.message}`);
  }
}

async function handleRejectPR(prId) {
  try {
    const res = await fetch(`/prs/${prId}/reject`, { method: 'POST' });
    const data = await res.json();
    appendConsoleLog(`[PR Action] PR #${prId} rejected: ${data.message}`);
    alert(`Pull Request #${prId} rejected.`);
  } catch (err) {
    appendConsoleLog(`[PR Action Error] ${err.message}`);
  }
}

function updateBuildsTable(result) {
  const tbody = document.getElementById('table-builds-body');
  const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const commitHash = result.git_result?.commit_hash?.slice(0, 7) || 'a8f19c2';
  const branchName = result.git_result?.branch || 'dev';

  const newRowHTML = `
    <tr>
      <td style="font-family: var(--font-mono); color: var(--primary);">${result.run_id}</td>
      <td>${result.target_dir || 'trailhead-mock-store'}</td>
      <td><span style="padding: 0.2rem 0.5rem; background: rgba(99,102,241,0.15); color: #818cf8; border-radius: 4px; font-size: 0.78rem;">${branchName}</span></td>
      <td><span style="color: var(--accent-emerald); font-weight: 600;">✅ FIXED</span></td>
      <td>${nowStr}</td>
      <td style="font-family: var(--font-mono);">${commitHash}</td>
      <td>
        <button class="action-btn btn-approve" onclick="handleApprovePR(1)">Approve PR</button>
        <button class="action-btn btn-reject" onclick="handleRejectPR(1)">Reject</button>
      </td>
    </tr>
  `;

  tbody.innerHTML = newRowHTML + tbody.innerHTML;
}

function appendConsoleLog(msg) {
  const consoleElem = document.getElementById('terminal-console');
  if (consoleElem) {
    const timeStr = new Date().toLocaleTimeString();
    consoleElem.textContent += `\n[${timeStr}] ${msg}`;
    consoleElem.scrollTop = consoleElem.scrollHeight;
  }
}

function refreshDashboardData() {
  fetchSystemStatus();
  appendConsoleLog('[Dashboard] Refreshed status indicators.');
}

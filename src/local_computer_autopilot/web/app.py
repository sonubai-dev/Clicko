"""Clicko Web UI and REST API application powered by Starlette."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

import anyio.to_thread
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from local_computer_autopilot.agent import AgentMode, AutonomousAgent, WorkflowPlanner
from local_computer_autopilot.audit import export_audit_csv, export_audit_json
from local_computer_autopilot.browser import BrowserManager
from local_computer_autopilot.computer.controller import ComputerController
from local_computer_autopilot.config import AppConfig
from local_computer_autopilot.desktop import WindowManager
from local_computer_autopilot.execution.cancellation import CancellationToken
from local_computer_autopilot.macros import MacroRunner, MacroStorage
from local_computer_autopilot.scheduler import ScheduleDefinition, ScheduleStorage, WorkflowScheduler
from local_computer_autopilot.task import TaskManager

logger = logging.getLogger("local_computer_autopilot.web")

# ── Embedded Modern Single-Page Dashboard HTML ─────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clicko — Local Computer Autopilot Dashboard</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --danger: #ef4444;
      --danger-hover: #dc2626;
      --success: #22c55e;
      --warning: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px; min-height: 100vh; }
    header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand h1 { font-size: 24px; font-weight: 700; color: var(--primary); letter-spacing: -0.5px; }
    .badge { padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
    .badge-success { background: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid var(--success); }
    .badge-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
    .badge-info { background: rgba(56, 189, 248, 0.2); color: var(--primary); border: 1px solid var(--primary); }

    .btn-emergency {
      background: var(--danger);
      color: white;
      border: none;
      padding: 12px 24px;
      font-size: 16px;
      font-weight: 700;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
      transition: all 0.2s ease;
    }
    .btn-emergency:hover { background: var(--danger-hover); transform: scale(1.02); }

    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; }
    .card-title { font-size: 16px; font-weight: 600; color: var(--text-muted); margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }

    .screen-container { position: relative; width: 100%; aspect-ratio: 16 / 9; background: #000; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
    .screen-img { width: 100%; height: 100%; object-fit: contain; }

    .controls-row { display: flex; gap: 10px; margin-top: 14px; }
    .input-goal { flex: 1; background: #0f172a; border: 1px solid var(--border); color: var(--text); padding: 10px 14px; border-radius: 8px; font-size: 14px; }
    .btn { background: var(--primary); color: #0f172a; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: var(--border); color: var(--text); }
    .btn-secondary:hover { background: #475569; }

    .task-list { max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
    .task-item { background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 12px; cursor: pointer; transition: border-color 0.2s; }
    .task-item:hover { border-color: var(--primary); }
    .task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .task-desc { font-weight: 500; font-size: 14px; }
    .task-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 12px; }

    .console-box { background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 14px; font-family: monospace; font-size: 13px; color: #a5f3fc; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }
    .quick-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .quick-btn { background: #334155; border: 1px solid #475569; color: var(--text); padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; }
    .quick-btn:hover { background: #475569; border-color: var(--primary); }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>CLICKO</h1>
      <span class="badge badge-info">Autopilot v0.4 (Phase 4)</span>
      <span id="failsafeBadge" class="badge badge-success">Fail-Safe Active</span>
      <span id="runtimeBadge" class="badge badge-success">Runtime Online</span>
    </div>
    <button class="btn-emergency" onclick="triggerEmergencyStop()">
      🛑 EMERGENCY STOP
    </button>
  </header>

  <!-- Human-in-the-Loop Approval Banner -->
  <div id="approvalBanner" style="display:none; background:#7c2d12; border:1px solid #ea580c; padding:12px 16px; border-radius:8px; margin-bottom:16px; justify-content:space-between; align-items:center;">
    <div>
      <strong style="color:#fdba74;">⚠️ Operator Approval Required:</strong>
      <span id="approvalPrompt" style="margin-left:8px; font-size:14px; color:#fed7aa;">Action needs review</span>
    </div>
    <div style="display:flex; gap:8px;">
      <button class="btn" style="background:#22c55e; color:#0f172a; padding:6px 14px;" onclick="resolveCurrentApproval(true)">Approve</button>
      <button class="btn" style="background:#ef4444; color:#fff; padding:6px 14px;" onclick="resolveCurrentApproval(false)">Reject</button>
    </div>
  </div>

  <div class="grid">
    <!-- Live Screen Viewer -->
    <div class="card">
      <div class="card-title">
        <span>🖥️ Live Desktop Screen</span>
        <div style="display:flex; gap:8px; align-items:center;">
          <select id="monitorSelect" class="quick-btn" onchange="refreshScreenshot()" title="Target Display">
            <option value="">Full Desktop</option>
          </select>
          <button class="btn-secondary quick-btn" onclick="refreshScreenshot()">Refresh Snapshot</button>
        </div>
      </div>
      <div class="screen-container">
        <img id="liveScreen" class="screen-img" src="/api/screenshot" alt="Desktop Screenshot">
      </div>
      <div class="controls-row">
        <span id="screenMeta" class="task-meta">Screen Monitor active</span>
      </div>
    </div>

    <!-- Autonomous Task Planner & Runner -->
    <div class="card">
      <div class="card-title">
        <span>⚡ Autonomous Task Workflow</span>
      </div>
      <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
        Type an objective. Clicko will plan and execute steps safely using local automation and visual verification.
      </p>
      <div class="controls-row">
        <input id="goalInput" class="input-goal" type="text" placeholder="e.g. open edge and search for python" value="open edge and search for python">
        <button class="btn" onclick="runAgentGoal()">Execute Goal</button>
        <button class="btn-secondary" onclick="planAgentGoal()">Plan Only</button>
      </div>
      <div style="margin-top: 14px;">
        <div class="card-title"><span>Execution Log / Output</span></div>
        <div id="consoleLog" class="console-box">Clicko Web Dashboard initialized.\nReady to dispatch commands...</div>
      </div>
    </div>
  </div>

  <div class="grid">
    <!-- Task History -->
    <div class="card">
      <div class="card-title">
        <span>📜 Task History & Audit Log (SQLite)</span>
        <div style="display:flex; gap:6px;">
          <a class="btn-secondary quick-btn" href="/api/audit/export/json" target="_blank" download="clicko_audit.json" style="text-decoration:none;">JSON</a>
          <a class="btn-secondary quick-btn" href="/api/audit/export/csv" target="_blank" download="clicko_audit.csv" style="text-decoration:none;">CSV</a>
          <button class="btn-secondary quick-btn" onclick="loadTasks()">Refresh</button>
        </div>
      </div>
      <div id="taskList" class="task-list">
        <div style="color: var(--text-muted); font-size: 13px;">Loading task history...</div>
      </div>
    </div>

    <!-- Quick Tools Console -->
    <div class="card">
      <div class="card-title">
        <span>🛠️ Quick Action Dispatcher</span>
      </div>
      <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
        Trigger safe individual computer, desktop, and browser tools directly:
      </p>
      <div class="quick-actions">
        <button class="quick-btn" onclick="dispatchAction('computer_get_screen_info')">Screen Info</button>
        <button class="quick-btn" onclick="dispatchAction('computer_get_monitors')">Displays</button>
        <button class="quick-btn" onclick="dispatchAction('desktop_list_windows')">List Windows</button>
        <button class="quick-btn" onclick="dispatchAction('computer_clipboard_get')">Read Clipboard</button>
        <button class="quick-btn" onclick="promptLaunchApp()">Launch App</button>
        <button class="quick-btn" onclick="dispatchAction('computer_get_status')">Runtime Status</button>
        <button class="quick-btn" onclick="dispatchAction('browser_open', {url: 'https://www.bing.com'})">Open Browser (Bing)</button>
        <button class="quick-btn" onclick="dispatchAction('browser_list_tabs')">List Browser Tabs</button>
        <button class="quick-btn" onclick="dispatchAction('browser_close')">Close Browser</button>
      </div>
      <div style="margin-top: 16px;">
        <span class="card-title" style="margin-bottom: 6px;">Safety Guidelines</span>
        <ul style="font-size: 12px; color: var(--text-muted); padding-left: 18px; line-height: 1.6;">
          <li>Move the mouse into any screen corner at any time to trigger PyAutoGUI hardware fail-safe.</li>
          <li>Click the red <strong>Emergency Stop</strong> button above to instantly abort active workflows.</li>
          <li>All executions run 100% locally with zero paid API requirements and unlogged sensitive inputs.</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- Phase 4 Automation Macros Section -->
  <div class="card" style="margin-bottom: 24px;">
    <div class="card-title">
      <span>⚙️ Automation Macros Engine</span>
      <div style="display:flex; gap:8px;">
        <button class="btn-secondary quick-btn" onclick="promptCreateMacro()">+ New Macro</button>
        <button class="btn-secondary quick-btn" onclick="loadMacros()">Refresh Macros</button>
      </div>
    </div>
    <div id="macroList" class="quick-actions" style="min-height:36px;">
      <div style="color:var(--text-muted); font-size:13px;">Loading saved macros...</div>
    </div>
  </div>

  <!-- Phase 5 Scheduled Recurring Workflows Section -->
  <div class="card" style="margin-bottom: 24px;">
    <div class="card-title">
      <span>⏰ Automated Recurring Workflows</span>
      <div style="display:flex; gap:8px;">
        <button class="btn-secondary quick-btn" onclick="promptCreateSchedule()">+ New Schedule</button>
        <button class="btn-secondary quick-btn" onclick="loadSchedules()">Refresh Schedules</button>
      </div>
    </div>
    <div id="scheduleList" class="task-list" style="max-height: 240px;">
      <div style="color:var(--text-muted); font-size:13px;">Loading schedules...</div>
    </div>
  </div>

  <script>
    function log(msg) {
      const box = document.getElementById('consoleLog');
      const time = new Date().toLocaleTimeString();
      box.innerText += `\\n[${time}] ${msg}`;
      box.scrollTop = box.scrollHeight;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    async function refreshScreenshot() {
      const img = document.getElementById('liveScreen');
      const mon = document.getElementById('monitorSelect') ? document.getElementById('monitorSelect').value : '';
      let url = '/api/screenshot?t=' + Date.now();
      if (mon !== '') url += '&monitor=' + encodeURIComponent(mon);
      img.src = url;
      log('Desktop snapshot refreshed' + (mon !== '' ? ` (Display ${mon})` : ''));
    }

    let activeApprovalId = null;

    async function pollApprovals() {
      try {
        const res = await fetch('/api/agent/approvals');
        const list = await res.json();
        const banner = document.getElementById('approvalBanner');
        const prompt = document.getElementById('approvalPrompt');
        if (list && list.length > 0) {
          const req = list[0];
          activeApprovalId = req.approval_id;
          prompt.innerText = `Step ${req.step.step_number}: ${req.step.action_name} — "${req.step.description}"`;
          banner.style.display = 'flex';
        } else {
          activeApprovalId = null;
          banner.style.display = 'none';
        }
      } catch (e) {
        // Silent catch for background polling
      }
    }

    async function resolveCurrentApproval(approved) {
      if (!activeApprovalId) return;
      try {
        log(`Human operator decision: ${approved ? 'APPROVED' : 'REJECTED'} for ${activeApprovalId}`);
        await fetch('/api/agent/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approval_id: activeApprovalId, approved: approved })
        });
        document.getElementById('approvalBanner').style.display = 'none';
        activeApprovalId = null;
      } catch (e) {
        log('Error submitting approval: ' + e);
      }
    }

    async function loadMonitors() {
      try {
        const res = await fetch('/api/monitors');
        const monitors = await res.json();
        const sel = document.getElementById('monitorSelect');
        if (!sel || !monitors) return;
        sel.innerHTML = '<option value="">Full Desktop</option>' + monitors.map(m => `
          <option value="${m.index}">Display ${m.index + 1} (${m.width}x${m.height})${m.is_primary ? ' [Primary]' : ''}</option>
        `).join('');
      } catch (e) {
        console.error('Error loading displays', e);
      }
    }

    async function loadMacros() {
      try {
        const res = await fetch('/api/macros');
        const macros = await res.json();
        const container = document.getElementById('macroList');
        if (!container) return;
        if (!macros || macros.length === 0) {
          container.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">No saved macros yet. Click "+ New Macro" to create one.</div>';
          return;
        }
        container.innerHTML = macros.map(m => `
          <div style="background:#0f172a; border:1px solid var(--border); border-radius:6px; padding:6px 12px; display:flex; align-items:center; gap:8px;">
            <span style="font-weight:600; font-size:13px; color:var(--primary);">${escapeHtml(m.name)}</span>
            <span style="font-size:11px; color:var(--text-muted);">${m.steps.length} steps</span>
            <button class="quick-btn" style="padding:2px 8px; font-size:11px;" onclick="runMacro('${encodeURIComponent(m.id)}')">Run</button>
            <button class="quick-btn" style="padding:2px 8px; font-size:11px; background:#7f1d1d;" onclick="deleteMacro('${encodeURIComponent(m.id)}')">✕</button>
          </div>
        `).join('');
      } catch (e) {
        console.error('Error loading macros', e);
      }
    }

    async function runMacro(macroId) {
      log(`Executing macro ${macroId}...`);
      try {
        const res = await fetch(`/api/macros/${macroId}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: {} })
        });
        const data = await res.json();
        log(`Macro execution completed: success=${data.success}, steps=${data.steps_executed}/${data.total_steps}`);
        loadTasks();
        refreshScreenshot();
      } catch (e) {
        log('Error executing macro: ' + e);
      }
    }

    async function deleteMacro(macroId) {
      if (!confirm('Delete this macro?')) return;
      try {
        await fetch(`/api/macros/${macroId}`, { method: 'DELETE' });
        log(`Deleted macro ${macroId}`);
        loadMacros();
      } catch (e) {
        log('Error deleting macro: ' + e);
      }
    }

    async function promptCreateMacro() {
      const name = prompt('Enter macro name:', 'Check Screen & Displays');
      if (!name) return;
      const steps = [
        { tool: 'computer_get_screen_info', args: {}, description: 'Inspect screen resolution' },
        { tool: 'computer_get_monitors', args: {}, description: 'Enumerate displays' }
      ];
      try {
        await fetch('/api/macros', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, description: 'Created from Web Dashboard', steps: steps })
        });
        log(`Created macro "${name}"`);
        loadMacros();
      } catch (e) {
        log('Error creating macro: ' + e);
      }
    }

    async function promptLaunchApp() {
      const app = prompt('Enter application to launch:', 'notepad.exe');
      if (!app) return;
      log(`Launching desktop application "${app}"...`);
      try {
        const res = await fetch('/api/apps/launch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ app_name: app })
        });
        const data = await res.json();
        log(`Launch result: ` + JSON.stringify(data));
        setTimeout(refreshScreenshot, 1000);
      } catch (e) {
        log('Error launching app: ' + e);
      }
    }

    async function triggerEmergencyStop() {
      try {
        const res = await fetch('/api/emergency-stop', { method: 'POST' });
        const data = await res.json();
        log('🛑 EMERGENCY STOP TRIGGERED: ' + data.message);
        document.getElementById('runtimeBadge').className = 'badge badge-danger';
        document.getElementById('runtimeBadge').innerText = 'Halted';
        loadTasks();
      } catch (e) {
        log('Emergency stop error: ' + e);
      }
    }

    async function runAgentGoal() {
      const goal = document.getElementById('goalInput').value.trim();
      if (!goal) return;
      log(`Starting autonomous execution for goal: "${goal}"...`);
      try {
        const res = await fetch('/api/agent/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal: goal, mode: 'auto' })
        });
        const data = await res.json();
        log(`Execution finished with status [${data.status}]. Steps: ${data.steps_completed}/${data.steps_total} (${data.duration_seconds}s)`);
        if (data.error_message) log(`Error details: ${data.error_message}`);
        loadTasks();
        refreshScreenshot();
      } catch (e) {
        log('Execution error: ' + e);
      }
    }

    async function planAgentGoal() {
      const goal = document.getElementById('goalInput').value.trim();
      if (!goal) return;
      log(`Generating execution plan for: "${goal}"...`);
      try {
        const res = await fetch('/api/agent/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal: goal, mode: 'auto' })
        });
        const data = await res.json();
        log(`Plan generated (${data.mode_used}): ${data.steps.length} steps planned.`);
        data.steps.forEach(s => log(`  Step ${s.step_number}: ${s.action_name} - ${s.description}`));
      } catch (e) {
        log('Plan error: ' + e);
      }
    }

    async function dispatchAction(actionName, params = {}) {
      log(`Dispatching tool '${actionName}'...`);
      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: actionName, parameters: params })
        });
        const data = await res.json();
        log(`Result for ${actionName}:\\n` + JSON.stringify(data, null, 2));
        if (actionName.includes('screenshot') || actionName.includes('browser')) {
          setTimeout(refreshScreenshot, 1000);
        }
      } catch (e) {
        log(`Action '${actionName}' error: ` + e);
      }
    }

    async function loadTasks() {
      try {
        const res = await fetch('/api/tasks');
        const tasks = await res.json();
        const list = document.getElementById('taskList');
        if (!tasks || tasks.length === 0) {
          list.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No tasks recorded yet.</div>';
          return;
        }
        list.innerHTML = tasks.map(t => {
          let badgeClass = 'badge-info';
          if (t.status === 'completed') badgeClass = 'badge-success';
          if (t.status === 'failed' || t.status === 'cancelled') badgeClass = 'badge-danger';
          const safeDesc = escapeHtml(t.description);
          const safeId = encodeURIComponent(t.task_id);
          const safeStatus = escapeHtml(t.status);
          return `
            <div class="task-item" onclick="viewTaskDetails('${safeId}')">
              <div class="task-header">
                <span class="task-desc">${safeDesc}</span>
                <span class="badge ${badgeClass}">${safeStatus}</span>
              </div>
              <div class="task-meta">
                <span>ID: ${safeId}</span>
                <span>Steps: ${Number(t.step_count) || 0}</span>
                <span>Created: ${new Date(t.created_at * 1000).toLocaleTimeString()}</span>
              </div>
            </div>
          `;
        }).join('');
      } catch (e) {
        console.error('Failed to load tasks', e);
      }
    }

    async function viewTaskDetails(taskId) {
      try {
        const res = await fetch('/api/tasks/' + taskId);
        const data = await res.json();
        log(`Task Details for ${taskId}:\\nStatus: ${data.task.status}\\nSteps recorded: ${data.steps.length}`);
        data.steps.forEach(s => {
          log(`  Step ${s.step_number}: ${s.action_name} [${s.status}] ${s.result_summary || ''}`);
        });
      } catch (e) {
        log('Error reading task details: ' + e);
      }
    }

    async function loadSchedules() {
      try {
        const res = await fetch('/api/schedules');
        const schedules = await res.json();
        const list = document.getElementById('scheduleList');
        if (!schedules || schedules.length === 0) {
          list.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No automated schedules configured.</div>';
          return;
        }
        list.innerHTML = schedules.map(s => {
          const badgeClass = s.enabled ? 'badge-success' : 'badge-danger';
          const statusText = s.enabled ? 'Active' : 'Paused';
          const safeName = escapeHtml(s.name);
          const safeId = encodeURIComponent(s.id);
          const safeTarget = escapeHtml(s.target);
          return `
            <div class="task-item" style="cursor:default;">
              <div class="task-header">
                <span class="task-desc"><strong>${safeName}</strong> (Every ${s.interval_seconds}s)</span>
                <div style="display:flex; gap:6px; align-items:center;">
                  <span class="badge ${badgeClass}">${statusText}</span>
                  <button class="btn-secondary quick-btn" onclick="toggleSchedule('${safeId}', ${!s.enabled})">${s.enabled ? 'Pause' : 'Enable'}</button>
                  <button class="btn-secondary quick-btn" style="color:var(--danger);" onclick="deleteSchedule('${safeId}')">Delete</button>
                </div>
              </div>
              <div class="task-meta">
                <span>Target: ${safeTarget}</span>
                <span>Runs: ${s.run_count || 0}</span>
                <span>Next: ${s.next_run ? new Date(s.next_run).toLocaleTimeString() : 'N/A'}</span>
              </div>
            </div>
          `;
        }).join('');
      } catch (e) {
        console.error('Failed to load schedules', e);
      }
    }

    async function promptCreateSchedule() {
      const name = prompt('Schedule name:', 'Daily System Health Check');
      if (!name) return;
      const target = prompt('Workflow goal or macro identifier to run:', 'inspect displays and screen info');
      if (!target) return;
      const secondsStr = prompt('Execution interval in seconds (e.g. 3600 for hourly):', '3600');
      const interval = parseInt(secondsStr, 10) || 3600;

      try {
        await fetch('/api/schedules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, interval_seconds: interval, target: target, is_macro: false })
        });
        log(`Created schedule "${name}" (every ${interval}s)`);
        loadSchedules();
      } catch (e) {
        log('Error creating schedule: ' + e);
      }
    }

    async function toggleSchedule(scheduleId, enabled) {
      try {
        await fetch('/api/schedules/' + scheduleId, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: enabled })
        });
        log(`Schedule ${scheduleId} set to ${enabled ? 'active' : 'paused'}`);
        loadSchedules();
      } catch (e) {
        log('Error toggling schedule: ' + e);
      }
    }

    async function deleteSchedule(scheduleId) {
      if (!confirm('Delete this automated schedule?')) return;
      try {
        await fetch('/api/schedules/' + scheduleId, { method: 'DELETE' });
        log(`Deleted schedule ${scheduleId}`);
        loadSchedules();
      } catch (e) {
        log('Error deleting schedule: ' + e);
      }
    }

    // Initial load
    loadTasks();
    loadMonitors();
    loadMacros();
    loadSchedules();
    setInterval(pollApprovals, 2000);
  </script>
</body>
</html>
"""


class ClickoWebApp:
    """Manages Starlette application state, routes, and API endpoints."""

    def __init__(
        self,
        controller: ComputerController | None = None,
        task_manager: TaskManager | None = None,
        window_manager: WindowManager | None = None,
        browser_manager: BrowserManager | None = None,
        macro_storage: MacroStorage | None = None,
        schedule_storage: ScheduleStorage | None = None,
        cancellation_token: CancellationToken | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.controller = controller or ComputerController(self.config)
        self.task_manager = task_manager or TaskManager()
        self.window_manager = window_manager or WindowManager()
        self.browser_manager = browser_manager or BrowserManager()
        self.macro_storage = macro_storage or MacroStorage()
        self.schedule_storage = schedule_storage or ScheduleStorage()
        self.cancellation_token = cancellation_token or CancellationToken()

        self.planner = WorkflowPlanner()
        self.agent = AutonomousAgent(
            controller=self.controller,
            task_manager=self.task_manager,
            window_manager=self.window_manager,
            browser_manager=self.browser_manager,
            macro_storage=self.macro_storage,
            schedule_storage=self.schedule_storage,
            cancellation_token=self.cancellation_token,
            config=self.config,
        )
        self.scheduler = WorkflowScheduler(
            storage=self.schedule_storage,
            agent=self.agent,
            planner=self.planner,
            macro_runner=MacroRunner(self.macro_storage, self.agent),
        )

        self.app = self._build_app()

    def _build_app(self) -> Starlette:
        routes = [
            Route("/", self.handle_index, methods=["GET"]),
            Route("/api/status", self.handle_status, methods=["GET"]),
            Route("/api/screenshot", self.handle_screenshot, methods=["GET"]),
            Route("/api/tasks", self.handle_list_tasks, methods=["GET"]),
            Route("/api/tasks/{task_id}", self.handle_get_task, methods=["GET"]),
            Route("/api/tasks/{task_id}/cancel", self.handle_cancel_task, methods=["POST"]),
            Route("/api/emergency-stop", self.handle_emergency_stop, methods=["POST"]),
            Route("/api/action", self.handle_dispatch_action, methods=["POST"]),
            Route("/api/agent/plan", self.handle_agent_plan, methods=["POST"]),
            Route("/api/agent/run", self.handle_agent_run, methods=["POST"]),
            Route("/api/windows", self.handle_list_windows, methods=["GET"]),
            Route("/api/monitors", self.handle_list_monitors, methods=["GET"]),
            Route("/api/clipboard", self.handle_get_clipboard, methods=["GET"]),
            Route("/api/clipboard", self.handle_set_clipboard, methods=["POST"]),
            Route("/api/apps/launch", self.handle_launch_app, methods=["POST"]),
            Route("/api/apps/close", self.handle_close_app, methods=["POST"]),
            Route("/api/macros", self.handle_list_macros, methods=["GET"]),
            Route("/api/macros", self.handle_create_macro, methods=["POST"]),
            Route("/api/macros/{macro_id}/execute", self.handle_execute_macro, methods=["POST"]),
            Route("/api/macros/{macro_id}", self.handle_delete_macro, methods=["DELETE"]),
            Route("/api/agent/approvals", self.handle_get_approvals, methods=["GET"]),
            Route("/api/agent/approve", self.handle_resolve_approval, methods=["POST"]),
            Route("/api/schedules", self.handle_list_schedules, methods=["GET"]),
            Route("/api/schedules", self.handle_create_schedule, methods=["POST"]),
            Route("/api/schedules/{schedule_id}", self.handle_delete_schedule, methods=["DELETE"]),
            Route("/api/schedules/{schedule_id}", self.handle_toggle_schedule, methods=["PATCH"]),
            Route("/api/audit/export/json", self.handle_export_audit_json, methods=["GET"]),
            Route("/api/audit/export/csv", self.handle_export_audit_csv, methods=["GET"]),
            Route("/api/diagnostics", self.handle_diagnostics, methods=["GET"]),
        ]
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=[
                    "http://127.0.0.1:8000",
                    "http://localhost:8000",
                    "http://127.0.0.1",
                    "http://localhost",
                ],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
        ]
        return Starlette(routes=routes, middleware=middleware)

    async def handle_index(self, request: Request) -> Response:
        """Serve the modern single-page dashboard."""
        return HTMLResponse(DASHBOARD_HTML)

    async def handle_status(self, request: Request) -> Response:
        """Get runtime health, fail-safe state, and tools inventory."""
        status = self.controller.get_status(["all"]).model_dump()
        status["cancelled"] = self.cancellation_token.is_cancelled
        status["cancel_reason"] = self.cancellation_token.reason
        status["active_task_id"] = self.task_manager.active_task_id
        return JSONResponse(status)

    async def handle_screenshot(self, request: Request) -> Response:
        """Capture real-time screenshot and return as PNG bytes."""
        try:
            monitor_param = request.query_params.get("monitor")
            mon_idx = int(monitor_param) if (monitor_param is not None and monitor_param.isdigit()) else None
            png_bytes = self.controller.take_screenshot(monitor_index=mon_idx)
            return Response(png_bytes, media_type="image/png")
        except Exception as e:
            logger.error("Screenshot capture error: %s", e)
            # Fallback to 1x1 transparent PNG if screenshot unavailable
            fallback = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            return Response(fallback, media_type="image/png")

    async def handle_list_tasks(self, request: Request) -> Response:
        """List recently executed tasks from SQLite."""
        tasks = self.task_manager.list_history(limit=30)
        return JSONResponse(tasks)

    async def handle_get_task(self, request: Request) -> Response:
        """Get task progress and audit step log."""
        task_id = request.path_params["task_id"]
        status = self.task_manager.get_task_status(task_id)
        return JSONResponse(status)

    async def handle_cancel_task(self, request: Request) -> Response:
        """Cancel a specific task."""
        task_id = request.path_params["task_id"]
        self.task_manager.cancel_task(task_id)
        self.cancellation_token.cancel(f"Task {task_id} cancelled via Web UI")
        return JSONResponse({"cancelled": True, "task_id": task_id})

    async def handle_emergency_stop(self, request: Request) -> Response:
        """Emergency Stop button handler."""
        self.cancellation_token.cancel("Emergency Stop triggered by user in Web UI")
        active_id = self.task_manager.active_task_id
        if active_id:
            self.task_manager.cancel_task(active_id)

        # Close any open browser processes
        try:
            if self.browser_manager.is_running:
                self.browser_manager.close()
        except Exception:
            pass

        logger.warning("🛑 Emergency Stop executed successfully")
        return JSONResponse({
            "success": True,
            "message": "Emergency Stop activated. All actions halted and browser closed.",
            "cancellation_reason": self.cancellation_token.reason,
        })

    async def handle_dispatch_action(self, request: Request) -> Response:
        """Execute a tool action directly from web console."""
        try:
            body = await request.json()
            action_name = body.get("action", "")
            parameters = body.get("parameters", {})
            result = self.agent._dispatch_action(action_name, parameters)
            return JSONResponse({"success": True, "action": action_name, "result": result})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def handle_agent_plan(self, request: Request) -> Response:
        """Generate and preview an execution plan for a goal."""
        try:
            body = await request.json()
            goal = body.get("goal", "")
            mode_str = body.get("mode", "auto")
            mode = AgentMode(mode_str) if mode_str in [m.value for m in AgentMode] else AgentMode.AUTO
            plan = self.planner.plan(goal, mode=mode)
            return JSONResponse(plan.model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def handle_agent_run(self, request: Request) -> Response:
        """Run an autonomous workflow for a goal."""
        try:
            body = await request.json()
            goal = body.get("goal", "")
            mode_str = body.get("mode", "auto")
            mode = AgentMode(mode_str) if mode_str in [m.value for m in AgentMode] else AgentMode.AUTO

            # Reset cancellation token before starting new run if previously cancelled
            if self.cancellation_token.is_cancelled:
                self.cancellation_token.reset()

            plan = self.planner.plan(goal, mode=mode)
            # Run blocking plan in thread pool so main event loop remains responsive to Emergency Stop
            result = await anyio.to_thread.run_sync(self.agent.run_plan, plan)
            return JSONResponse(result.model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_list_windows(self, request: Request) -> Response:
        """List open top-level application windows."""
        windows = self.window_manager.list_windows()
        return JSONResponse([w.model_dump() for w in windows])

    async def handle_list_monitors(self, request: Request) -> Response:
        """List connected display monitors."""
        monitors = self.controller.get_monitors()
        return JSONResponse([m.model_dump() for m in monitors])

    async def handle_get_clipboard(self, request: Request) -> Response:
        """Read system clipboard."""
        res = self.controller.get_clipboard_text()
        return JSONResponse(res.model_dump())

    async def handle_set_clipboard(self, request: Request) -> Response:
        """Set system clipboard text."""
        try:
            body = await request.json()
            text = body.get("text", "")
            res = self.controller.set_clipboard_text(text)
            return JSONResponse(res.model_dump())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def handle_launch_app(self, request: Request) -> Response:
        """Launch desktop application."""
        try:
            body = await request.json()
            app_name = body.get("app_name", "")
            args = body.get("args")
            wait_sec = float(body.get("wait_seconds", 2.0))
            res = self.window_manager.launch_app(app_name, args=args, wait_seconds=wait_sec)
            return JSONResponse(res.model_dump())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def handle_close_app(self, request: Request) -> Response:
        """Close desktop application window."""
        try:
            body = await request.json()
            query = body.get("query", "")
            graceful = bool(body.get("graceful", True))
            res = self.window_manager.close_app(query, graceful=graceful)
            return JSONResponse(res.model_dump())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    async def handle_list_macros(self, request: Request) -> Response:
        """List saved automation macros."""
        macros = self.macro_storage.list_macros()
        return JSONResponse([m.model_dump() for m in macros])

    async def handle_create_macro(self, request: Request) -> Response:
        """Save a new macro definition."""
        try:
            body = await request.json()
            name = body.get("name", "")
            description = body.get("description", "")
            steps = body.get("steps", [])
            parameters = body.get("parameters", [])
            macro = self.macro_storage.create_macro(name, description, steps, parameters=parameters)
            return JSONResponse(macro.model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def handle_execute_macro(self, request: Request) -> Response:
        """Execute a saved macro by ID or name."""
        try:
            macro_id = request.path_params["macro_id"]
            body = await request.json()
            params = body.get("parameters", {})
            if self.cancellation_token.is_cancelled:
                self.cancellation_token.reset()
            runner = MacroRunner(self.macro_storage, self.agent)
            result = await anyio.to_thread.run_sync(runner.execute_macro, macro_id, params)
            return JSONResponse(result.model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_delete_macro(self, request: Request) -> Response:
        """Delete a saved macro."""
        macro_id = request.path_params["macro_id"]
        deleted = self.macro_storage.delete_macro(macro_id)
        return JSONResponse({"deleted": deleted, "macro_id": macro_id})

    async def handle_get_approvals(self, request: Request) -> Response:
        """Get pending human approval requests."""
        approvals = self.agent.get_pending_approvals()
        return JSONResponse(approvals)

    async def handle_resolve_approval(self, request: Request) -> Response:
        """Resolve a pending human approval decision."""
        try:
            body = await request.json()
            approval_id = body.get("approval_id", "")
            approved = bool(body.get("approved", False))
            resolved = self.agent.resolve_approval(approval_id, approved)
            return JSONResponse({"resolved": resolved, "approval_id": approval_id, "approved": approved})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    # ── Phase 5: Production Automation Scheduler & Audit Exports ──────────

    async def handle_list_schedules(self, request: Request) -> Response:
        """List all registered automation schedules."""
        schedules = self.schedule_storage.list_schedules()
        return JSONResponse([s.model_dump() for s in schedules])

    async def handle_create_schedule(self, request: Request) -> Response:
        """Create a recurring automation schedule."""
        try:
            body = await request.json()
            name = body.get("name", "").strip()
            interval_seconds = int(body.get("interval_seconds", 60))
            target = body.get("target", "").strip()
            is_macro = bool(body.get("is_macro", False))
            if not name or not target:
                return JSONResponse({"error": "Name and target are required"}, status_code=400)
            if interval_seconds < 5:
                return JSONResponse({"error": "Interval must be at least 5 seconds"}, status_code=400)
            sched = self.schedule_storage.create_schedule(name, interval_seconds, target, is_macro=is_macro)
            return JSONResponse(sched.model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def handle_delete_schedule(self, request: Request) -> Response:
        """Delete an automation schedule."""
        schedule_id = request.path_params["schedule_id"]
        deleted = self.schedule_storage.delete_schedule(schedule_id)
        return JSONResponse({"deleted": deleted, "schedule_id": schedule_id})

    async def handle_toggle_schedule(self, request: Request) -> Response:
        """Enable or disable a schedule."""
        schedule_id = request.path_params["schedule_id"]
        body = await request.json()
        enabled = bool(body.get("enabled", True))
        updated = self.schedule_storage.toggle_schedule(schedule_id, enabled)
        return JSONResponse({"success": updated, "schedule_id": schedule_id, "enabled": enabled})

    async def handle_export_audit_json(self, request: Request) -> Response:
        """Export task audit trail in JSON format."""
        task_id = request.query_params.get("task_id")
        data = export_audit_json(self.task_manager.storage, task_id=task_id)
        return Response(
            data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=clicko_audit.json"},
        )

    async def handle_export_audit_csv(self, request: Request) -> Response:
        """Export task audit trail in CSV format."""
        csv_str = export_audit_csv(self.task_manager.storage)
        return Response(
            csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=clicko_audit.csv"},
        )

    async def handle_diagnostics(self, request: Request) -> Response:
        """Provide detailed system diagnostics."""
        screen = self.controller.get_screen_info().model_dump()
        monitors = [m.model_dump() for m in self.controller.get_monitors()]
        status = self.controller.get_status(["all"]).model_dump()
        local_llm = self.planner.is_local_llm_available()
        schedules_count = len(self.schedule_storage.list_schedules())
        macros_count = len(self.macro_storage.list_macros())
        return JSONResponse({
            "screen": screen,
            "monitors": monitors,
            "status": status,
            "local_llm_available": local_llm,
            "scheduler_running": self.scheduler.is_running,
            "schedules_count": schedules_count,
            "macros_count": macros_count,
        })


def create_app(
    controller: ComputerController | None = None,
    task_manager: TaskManager | None = None,
    window_manager: WindowManager | None = None,
    browser_manager: BrowserManager | None = None,
    macro_storage: MacroStorage | None = None,
    schedule_storage: ScheduleStorage | None = None,
    cancellation_token: CancellationToken | None = None,
    config: AppConfig | None = None,
) -> Starlette:
    """Factory creating configured Starlette app."""
    web_app = ClickoWebApp(
        controller=controller,
        task_manager=task_manager,
        window_manager=window_manager,
        browser_manager=browser_manager,
        macro_storage=macro_storage,
        schedule_storage=schedule_storage,
        cancellation_token=cancellation_token,
        config=config,
    )
    return web_app.app

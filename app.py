"""Flask web dashboard for multicluster-health.

Professional NOC-style dark-themed dashboard with auto-refresh,
utilization bars, and color-coded cluster status cards.

Run with:
    python app.py

Then open http://localhost:5001 in your browser.
"""

import datetime
import json
from pathlib import Path

from flask import Flask, render_template_string, jsonify

from multicluster_health import get_all_clusters_health

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
HEALTH_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


# ── Template ──────────────────────────────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>multicluster-health</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #0b0e14;
    color: #cdd3dc;
    margin: 0; padding: 0; line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  /* ── Top Header ──────────────────────────────────── */
  .top-header {
    background: linear-gradient(135deg, #131822 0%, #18202d 100%);
    border-bottom: 1px solid #1e2937;
    padding: 0 32px;
    display: flex; align-items: center; justify-content: space-between;
    height: 64px;
  }
  .top-header .brand {
    display: flex; align-items: center; gap: 12px;
  }
  .top-header .brand-icon {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, #5291e6, #3fb950);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 700; color: #fff;
  }
  .top-header .brand h1 {
    font-size: 18px; font-weight: 600; color: #e6edf5; margin: 0;
    letter-spacing: -0.3px;
  }
  .top-header .brand h1 small {
    font-weight: 400; font-size: 12px; color: #6a768b; margin-left: 8px;
  }
  .top-header .tagline {
    font-size: 13px; color: #6a768b; display: none;
  }
  @media (min-width: 768px) { .top-header .tagline { display: block; } }

  .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }

  /* ── Summary Banner ──────────────────────────────── */
  .summary-banner {
    background: linear-gradient(135deg, #131822 0%, #18202d 100%);
    border: 1px solid #1e2937; border-radius: 12px;
    padding: 24px 32px; margin-bottom: 28px;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 20px;
  }
  .summary-left { display: flex; align-items: center; gap: 24px; }
  .summary-status-indicator {
    width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0;
  }
  .summary-status-indicator.ok { background: #3fb950; box-shadow: 0 0 12px rgba(63,185,80,0.4); }
  .summary-status-indicator.warn { background: #d29922; box-shadow: 0 0 12px rgba(210,153,34,0.4); }
  .summary-status-indicator.err { background: #f85149; box-shadow: 0 0 12px rgba(248,81,73,0.4); }
  .summary-text { font-size: 16px; font-weight: 600; color: #e6edf5; }
  .summary-text .count { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
  .summary-text .count.ok { color: #3fb950; }
  .summary-text .count.warn { color: #d29922; }
  .summary-text .count.err { color: #f85149; }
  .summary-breakdown { display: flex; gap: 16px; align-items: center; }
  .summary-chip {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 13px; font-weight: 500; padding: 4px 12px;
    border-radius: 20px; background: #0b0e14;
  }
  .summary-chip .dot { width: 8px; height: 8px; border-radius: 50%; }
  .summary-chip .dot.green { background: #3fb950; }
  .summary-chip .dot.yellow { background: #d29922; }
  .summary-chip .dot.red { background: #f85149; }
  .summary-chip .dot.gray { background: #6a768b; }
  .summary-chip .val { color: #e6edf5; font-weight: 600; }
  .summary-right {
    display: flex; align-items: center; gap: 16px;
    font-size: 13px; color: #7a8599;
  }
  .summary-right .pct { font-size: 15px; color: #cdd3dc; }
  .summary-right .pct strong { color: #e6edf5; }

  /* ── Controls ────────────────────────────────────── */
  .controls {
    display: flex; align-items: center; gap: 16px;
  }
  .btn-refresh {
    background: #1e2937; color: #cdd3dc; border: 1px solid #2d3a4c;
    border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 500;
    cursor: pointer; transition: background .15s, border-color .15s;
    font-family: inherit; display: flex; align-items: center; gap: 6px;
  }
  .btn-refresh:hover { background: #263449; border-color: #3d5069; }
  .btn-refresh:disabled { opacity: .5; cursor: not-allowed; }
  .btn-refresh .spin {
    display: inline-block; width: 14px; height: 14px;
    border: 2px solid #6a768b; border-top-color: #cdd3dc;
    border-radius: 50%; animation: rotate .8s linear infinite;
  }
  @keyframes rotate { to { transform: rotate(360deg); } }
  .auto-label {
    font-size: 12px; color: #6a768b;
    display: flex; align-items: center; gap: 6px;
  }
  .auto-label .pulse {
    width: 6px; height: 6px; border-radius: 50%; background: #3fb950;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .4; } }
  .auto-label .pulse.paused { background: #6a768b; animation: none; }

  /* ── Cluster Grid ────────────────────────────────── */
  .cluster-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 20px;
  }

  .card {
    background: #131822; border: 1px solid #1e2937; border-radius: 12px;
    padding: 24px; position: relative; overflow: hidden;
    transition: border-color .2s, box-shadow .2s;
  }
  .card:hover { border-color: #2d3a4c; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }

  .card .accent {
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
  }
  .card.healthy .accent { background: linear-gradient(90deg, #3fb950, #2ea043); }
  .card.degraded .accent { background: linear-gradient(90deg, #d29922, #bb8009); }
  .card.critical .accent { background: linear-gradient(90deg, #f85149, #da3633); }
  .card.unreachable .accent { background: linear-gradient(90deg, #6a768b, #484f58); }

  .card-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 20px;
  }
  .card-header h2 {
    font-size: 17px; margin: 0; color: #e6edf5; font-weight: 600;
    letter-spacing: -0.3px;
  }
  .card-header .context {
    font-size: 12px; color: #6a768b; margin-top: 2px;
  }

  .status-badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 700;
    padding: 4px 14px; border-radius: 20px;
    text-transform: uppercase; letter-spacing: .6px;
    white-space: nowrap;
  }
  .card.healthy .status-badge {
    background: rgba(63,185,80,0.12); color: #3fb950;
    border: 1px solid rgba(63,185,80,0.2);
  }
  .card.degraded .status-badge {
    background: rgba(210,153,34,0.12); color: #d29922;
    border: 1px solid rgba(210,153,34,0.2);
  }
  .card.critical .status-badge {
    background: rgba(248,81,73,0.12); color: #f85149;
    border: 1px solid rgba(248,81,73,0.2);
  }
  .card.unreachable .status-badge {
    background: rgba(106,118,139,0.12); color: #6a768b;
    border: 1px solid rgba(106,118,139,0.2);
  }

  .status-badge .badge-dot {
    width: 7px; height: 7px; border-radius: 50%;
  }
  .card.healthy .badge-dot { background: #3fb950; }
  .card.degraded .badge-dot { background: #d29922; }
  .card.critical .badge-dot { background: #f85149; }
  .card.unreachable .badge-dot { background: #6a768b; }

  /* ── Metrics ─────────────────────────────────────── */
  .metric-group { margin-bottom: 16px; }
  .metric-group:last-child { margin-bottom: 0; }
  .metric-group-label {
    font-size: 11px; font-weight: 600; color: #6a768b;
    text-transform: uppercase; letter-spacing: .6px;
    margin-bottom: 8px;
  }

  .metric-row {
    background: #0b0e14; border-radius: 8px; padding: 12px 16px;
    margin-bottom: 6px;
  }
  .metric-row:last-child { margin-bottom: 0; }

  .metric-top {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 6px;
  }
  .metric-label {
    font-size: 13px; font-weight: 500; color: #7a8599;
  }
  .metric-value {
    font-size: 14px; font-weight: 600; color: #e6edf5;
  }
  .metric-value .sub { font-size: 11px; font-weight: 400; color: #6a768b; }

  /* ── Progress Bars ───────────────────────────────── */
  .bar-track {
    height: 5px; background: #1e2937; border-radius: 3px; overflow: hidden;
  }
  .bar-fill {
    height: 100%; border-radius: 3px;
    transition: width .6s ease;
  }
  .bar-green  { background: #3fb950; }
  .bar-yellow { background: #d29922; }
  .bar-red    { background: #f85149; }
  .bar-blue   { background: #5291e6; }

  /* ── Sub-metric chips ────────────────────────────── */
  .sub-metrics {
    display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;
  }
  .sub-chip {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 600; padding: 2px 10px;
    border-radius: 12px; background: #1e2937;
  }
  .sub-chip.warn { color: #d29922; }
  .sub-chip.err  { color: #f85149; }
  .sub-chip.ok   { color: #3fb950; }

  /* ── Error box ───────────────────────────────────── */
  .error-box {
    background: rgba(248,81,73,0.08);
    border: 1px solid rgba(248,81,73,0.2);
    border-radius: 8px; padding: 12px 14px; margin-top: 8px;
    color: #f85149; font-size: 13px;
    font-family: "SFMono-Regular", Consolas, monospace;
    word-break: break-word;
  }

  .empty-state {
    text-align: center; padding: 80px 20px; color: #6a768b;
  }
  .empty-state .big { font-size: 48px; margin-bottom: 12px; }

  .refresh-toast {
    position: fixed; bottom: 24px; right: 24px;
    background: #1e2937; border: 1px solid #2d3a4c; border-radius: 10px;
    padding: 12px 20px; font-size: 13px; color: #cdd3dc;
    opacity: 0; transition: opacity .3s;
    pointer-events: none; z-index: 100;
  }
  .refresh-toast.show { opacity: 1; }

  @media (max-width: 900px) {
    .cluster-grid { grid-template-columns: 1fr; }
    .summary-banner { flex-direction: column; align-items: stretch; }
    .summary-left { flex-wrap: wrap; }
    .container { padding: 16px; }
    .top-header { padding: 0 16px; }
  }
</style>
</head>
<body>

<!-- Top Header -->
<header class="top-header">
  <div class="brand">
    <div class="brand-icon">&#9670;</div>
    <h1>multicluster-health <small>Kubernetes Cluster Monitor</small></h1>
  </div>
  <div class="tagline">&#9679; Real-time multi-cluster health</div>
</header>

<div class="container">

  <!-- Summary Banner -->
  <div class="summary-banner">
    <div class="summary-left">
      <div class="summary-status-indicator {{ 'ok' if summary.healthy == summary.total else 'warn' if summary.degraded > 0 else 'err' }}"></div>
      <div class="summary-text">
        <span class="count {{ 'ok' if summary.healthy == summary.total else 'warn' if summary.degraded > 0 else 'err' }}">{{ summary.healthy }}</span>
        / {{ summary.total }} clusters healthy
      </div>
      <div class="summary-breakdown">
        {% if summary.healthy %}
        <span class="summary-chip"><span class="dot green"></span><span class="val">{{ summary.healthy }}</span> healthy</span>
        {% endif %}
        {% if summary.degraded %}
        <span class="summary-chip"><span class="dot yellow"></span><span class="val">{{ summary.degraded }}</span> degraded</span>
        {% endif %}
        {% if summary.critical %}
        <span class="summary-chip"><span class="dot red"></span><span class="val">{{ summary.critical }}</span> critical</span>
        {% endif %}
        {% if summary.unreachable %}
        <span class="summary-chip"><span class="dot gray"></span><span class="val">{{ summary.unreachable }}</span> unreachable</span>
        {% endif %}
      </div>
    </div>
    <div class="summary-right">
      {% set pct = (summary.healthy / summary.total * 100)|round(0)|int if summary.total > 0 else 0 %}
      <span class="pct"><strong>{{ pct }}%</strong> operational</span>
      <div class="controls">
        <span class="auto-label">
          <span class="pulse" id="pulse-dot"></span>
          <span id="auto-text">30s auto-refresh</span>
        </span>
        <button class="btn-refresh" id="btn-refresh" onclick="refreshNow()">
          <span id="refresh-icon">&#x21bb;</span>
          <span id="refresh-text">Refresh</span>
        </button>
      </div>
    </div>
  </div>

  <!-- Cluster Cards -->
  <div class="cluster-grid" id="cluster-grid">
  {% for c in clusters %}
    {% set total_pods = c.pods.running + c.pods.pending + c.pods.crashloop + c.pods.failed %}
    {% set total_nodes = c.nodes.ready + c.nodes.not_ready %}
    <div class="card {{ c.status }}" data-cluster="{{ c.name | e }}">
      <div class="accent"></div>
      <div class="card-header">
        <div>
          <h2>{{ c.name }}</h2>
          {% if c.context %}
          <div class="context">{{ c.context }}</div>
          {% endif %}
        </div>
        <div class="status-badge">
          <span class="badge-dot"></span>
          {{ c.status }}
        </div>
      </div>

      {% if c.reachable %}
      <!-- Nodes -->
      <div class="metric-group">
        <div class="metric-group-label">Nodes</div>
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">Ready</span>
            <span class="metric-value">{{ c.nodes.ready }}/{{ total_nodes }} <span class="sub">nodes</span></span>
          </div>
          {% if total_nodes > 0 %}
          <div class="bar-track">
            {% set node_pct = (c.nodes.ready / total_nodes * 100)|round(0)|int %}
            <div class="bar-fill {% if c.nodes.not_ready > 0 %}bar-yellow{% else %}bar-green{% endif %}"
                 style="width: {{ node_pct }}%"></div>
          </div>
          {% endif %}
          {% if c.nodes.not_ready %}
          <div class="sub-metrics">
            <span class="sub-chip err"><strong>{{ c.nodes.not_ready }}</strong> not ready</span>
          </div>
          {% endif %}
        </div>
      </div>

      <!-- Pods -->
      <div class="metric-group">
        <div class="metric-group-label">Pods</div>
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">Running</span>
            <span class="metric-value">{{ c.pods.running }}/{{ total_pods }} <span class="sub">total</span></span>
          </div>
          {% if total_pods > 0 %}
          <div class="bar-track">
            {% set pod_pct = (c.pods.running / total_pods * 100)|round(0)|int %}
            <div class="bar-fill {% if c.pods.crashloop > 0 %}bar-red{% elif c.pods.pending > 0 %}bar-yellow{% else %}bar-green{% endif %}"
                 style="width: {{ pod_pct }}%"></div>
          </div>
          {% endif %}
          <div class="sub-metrics">
            <span class="sub-chip ok"><strong>{{ c.pods.running }}</strong> running</span>
            {% if c.pods.pending %}<span class="sub-chip warn"><strong>{{ c.pods.pending }}</strong> pending</span>{% endif %}
            {% if c.pods.crashloop %}<span class="sub-chip err"><strong>{{ c.pods.crashloop }}</strong> crash looping</span>{% endif %}
            {% if c.pods.failed %}<span class="sub-chip err"><strong>{{ c.pods.failed }}</strong> failed</span>{% endif %}
          </div>
        </div>
      </div>

      <!-- CPU + Memory -->
      <div class="metric-group">
        <div class="metric-group-label">Utilization</div>
        {% set cpu_val = c.cpu_utilization_percent if c.cpu_utilization_percent >= 0 else -1 %}
        {% set mem_val = c.memory_utilization_percent if c.memory_utilization_percent >= 0 else -1 %}
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">CPU</span>
            <span class="metric-value">{{ "%.1f"|format(cpu_val) if cpu_val >= 0 else 'N/A' }}%</span>
          </div>
          {% if cpu_val >= 0 %}
          <div class="bar-track">
            {% set cpu_pct = cpu_val|round(0)|int %}
            <div class="bar-fill {% if cpu_pct >= 90 %}bar-red{% elif cpu_pct >= 75 %}bar-yellow{% else %}bar-blue{% endif %}"
                 style="width: {{ cpu_pct }}%"></div>
          </div>
          {% endif %}
        </div>
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">Memory</span>
            <span class="metric-value">{{ "%.1f"|format(mem_val) if mem_val >= 0 else 'N/A' }}%</span>
          </div>
          {% if mem_val >= 0 %}
          <div class="bar-track">
            {% set mem_pct = mem_val|round(0)|int %}
            <div class="bar-fill {% if mem_pct >= 90 %}bar-red{% elif mem_pct >= 75 %}bar-yellow{% else %}bar-blue{% endif %}"
                 style="width: {{ mem_pct }}%"></div>
          </div>
          {% endif %}
        </div>
      </div>

      {% else %}
      <!-- Unreachable -->
      <div class="metric-group">
        <div class="metric-row">
          <div class="metric-top">
            <span class="metric-label">Status</span>
            <span class="metric-value" style="color:#f85149">Unreachable</span>
          </div>
        </div>
      </div>
      {% if c.error %}
      <div class="error-box">{{ c.error }}</div>
      {% endif %}
      {% endif %}
    </div>
  {% endfor %}
  </div>
</div>

<!-- Toast -->
<div id="refresh-toast" class="refresh-toast"></div>

<script>
(function() {
  var grid = document.getElementById('cluster-grid');
  var btn = document.getElementById('btn-refresh');
  var icon = document.getElementById('refresh-icon');
  var text = document.getElementById('refresh-text');
  var toast = document.getElementById('refresh-toast');
  var pulseDot = document.getElementById('pulse-dot');
  var autoText = document.getElementById('auto-text');
  var autoInterval = 30000;
  var timer = null;
  var loading = false;

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toast._hide);
    toast._hide = setTimeout(function() { toast.classList.remove('show'); }, 2500);
  }

  function setLoading(state) {
    loading = state;
    btn.disabled = state;
    if (state) {
      icon.innerHTML = '<span class="spin"></span>';
      text.textContent = 'Refreshing\u2026';
    } else {
      icon.innerHTML = '\u21bb';
      text.textContent = 'Refresh';
    }
  }

  function refreshNow() {
    if (loading) return;
    setLoading(true);
    var t0 = Date.now();

    var iconEl = icon;
    fetch('/api/health')
      .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function(data) {
        renderClusters(data.clusters || []);
        updateSummary(data.summary || {});
        var elapsed = Date.now() - t0;
        showToast('Updated (' + (elapsed / 1000).toFixed(1) + 's)');
        if (timer) { clearInterval(timer); timer = null; }
        startAutoRefresh();
      })
      .catch(function(err) {
        showToast('Refresh failed: ' + err.message);
      })
      .finally(function() {
        setLoading(false);
      });
  }

  function renderClusters(clusters) {
    if (!clusters || clusters.length === 0) {
      grid.innerHTML = '<div class="empty-state"><div class="big">&#9888;</div>No cluster data available. Check config.yaml.</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < clusters.length; i++) {
      var c = clusters[i];
      var totalPods = (c.pods.running || 0) + (c.pods.pending || 0) + (c.pods.crashloop || 0) + (c.pods.failed || 0);
      var totalNodes = (c.nodes.ready || 0) + (c.nodes.not_ready || 0);

      html += '<div class="card ' + (c.status || 'unreachable') + '">';
      html += '  <div class="accent"></div>';
      html += '  <div class="card-header">';
      html += '    <div><h2>' + esc(c.name) + '</h2>';
      if (c.context) html += '<div class="context">' + esc(c.context) + '</div>';
      html += '    </div>';
      html += '    <div class="status-badge"><span class="badge-dot"></span>' + (c.status || 'unreachable') + '</div>';
      html += '  </div>';

      if (c.reachable) {
        // Nodes
        var nodePct = totalNodes > 0 ? Math.round(c.nodes.ready / totalNodes * 100) : 0;
        html += '  <div class="metric-group"><div class="metric-group-label">Nodes</div><div class="metric-row">';
        html += '    <div class="metric-top"><span class="metric-label">Ready</span><span class="metric-value">' + c.nodes.ready + '/' + totalNodes + ' <span class="sub">nodes</span></span></div>';
        if (totalNodes > 0) {
          html += '    <div class="bar-track"><div class="bar-fill ' + (c.nodes.not_ready > 0 ? 'bar-yellow' : 'bar-green') + '" style="width:' + nodePct + '%"></div></div>';
        }
        if (c.nodes.not_ready > 0) {
          html += '    <div class="sub-metrics"><span class="sub-chip err"><strong>' + c.nodes.not_ready + '</strong> not ready</span></div>';
        }
        html += '  </div></div>';

        // Pods
        var podPct = totalPods > 0 ? Math.round(c.pods.running / totalPods * 100) : 0;
        var podBarClass = 'bar-green';
        if (c.pods.crashloop > 0) podBarClass = 'bar-red';
        else if (c.pods.pending > 0) podBarClass = 'bar-yellow';
        html += '  <div class="metric-group"><div class="metric-group-label">Pods</div><div class="metric-row">';
        html += '    <div class="metric-top"><span class="metric-label">Running</span><span class="metric-value">' + c.pods.running + '/' + totalPods + ' <span class="sub">total</span></span></div>';
        if (totalPods > 0) {
          html += '    <div class="bar-track"><div class="bar-fill ' + podBarClass + '" style="width:' + podPct + '%"></div></div>';
        }
        html += '    <div class="sub-metrics">';
        html += '      <span class="sub-chip ok"><strong>' + c.pods.running + '</strong> running</span>';
        if (c.pods.pending) html += '<span class="sub-chip warn"><strong>' + c.pods.pending + '</strong> pending</span>';
        if (c.pods.crashloop) html += '<span class="sub-chip err"><strong>' + c.pods.crashloop + '</strong> crash looping</span>';
        if (c.pods.failed) html += '<span class="sub-chip err"><strong>' + c.pods.failed + '</strong> failed</span>';
        html += '    </div>';
        html += '  </div></div>';

        // CPU
        var cpuVal = (typeof c.cpu_utilization_percent === 'number' && c.cpu_utilization_percent >= 0) ? c.cpu_utilization_percent : -1;
        html += '  <div class="metric-group"><div class="metric-group-label">Utilization</div><div class="metric-row">';
        html += '    <div class="metric-top"><span class="metric-label">CPU</span><span class="metric-value">' + (cpuVal >= 0 ? cpuVal.toFixed(1) + '%' : 'N/A') + '</span></div>';
        if (cpuVal >= 0) {
          var cpuPct = Math.round(cpuVal);
          html += '    <div class="bar-track"><div class="bar-fill ' + (cpuPct >= 90 ? 'bar-red' : cpuPct >= 75 ? 'bar-yellow' : 'bar-blue') + '" style="width:' + cpuPct + '%"></div></div>';
        }
        html += '  </div>';

        // Memory
        var memVal = (typeof c.memory_utilization_percent === 'number' && c.memory_utilization_percent >= 0) ? c.memory_utilization_percent : -1;
        html += '  <div class="metric-row">';
        html += '    <div class="metric-top"><span class="metric-label">Memory</span><span class="metric-value">' + (memVal >= 0 ? memVal.toFixed(1) + '%' : 'N/A') + '</span></div>';
        if (memVal >= 0) {
          var memPct = Math.round(memVal);
          html += '    <div class="bar-track"><div class="bar-fill ' + (memPct >= 90 ? 'bar-red' : memPct >= 75 ? 'bar-yellow' : 'bar-blue') + '" style="width:' + memPct + '%"></div></div>';
        }
        html += '  </div></div>';
      } else {
        html += '  <div class="metric-group"><div class="metric-row">';
        html += '    <div class="metric-top"><span class="metric-label">Status</span><span class="metric-value" style="color:#f85149">Unreachable</span></div>';
        html += '  </div></div>';
        if (c.error) {
          html += '  <div class="error-box">' + esc(c.error) + '</div>';
        }
      }
      html += '</div>';
    }
    grid.innerHTML = html;
  }

  function updateSummary(s) {
    var els = {
      total: document.querySelector('.summary-text .count'),
      pct: document.querySelector('.pct strong')
    };
    if (els.total) {
      els.total.textContent = s.healthy || 0;
      els.total.className = 'count';
      if (s.healthy === s.total) els.total.classList.add('ok');
      else if (s.degraded > 0) els.total.classList.add('warn');
      else els.total.classList.add('err');
    }
    if (els.pct && s.total > 0) {
      els.pct.textContent = Math.round((s.healthy || 0) / s.total * 100) + '%';
    }
  }

  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  function startAutoRefresh() {
    if (timer) clearInterval(timer);
    timer = setInterval(refreshNow, autoInterval);
  }

  window.refreshNow = refreshNow;
  startAutoRefresh();

  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      if (timer) { clearInterval(timer); timer = null; }
      if (pulseDot) pulseDot.className = 'pulse paused';
      if (autoText) autoText.textContent = 'auto-refresh paused';
    } else {
      startAutoRefresh();
      if (pulseDot) pulseDot.className = 'pulse';
      if (autoText) autoText.textContent = '30s auto-refresh';
    }
  });
})();
</script>
</body>
</html>
"""


# ── Routes ────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Render the health dashboard."""
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        data = get_all_clusters_health(str(HEALTH_CONFIG_PATH))
    except Exception as e:
        return render_template_string(
            TEMPLATE,
            checked_at="error",
            summary={"total": 0, "healthy": 0, "degraded": 0, "critical": 0, "unreachable": 0},
            clusters=[],
            error=str(e),
        )

    return render_template_string(
        TEMPLATE,
        checked_at=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        summary=data["summary"],
        clusters=data["clusters"],
    )


@app.route("/api/health")
def health_api():
    """Return cluster health data as JSON (used by JS auto-refresh)."""
    try:
        data = get_all_clusters_health(str(HEALTH_CONFIG_PATH))
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "clusters": [],
            "summary": {"total": 0, "healthy": 0, "degraded": 0, "critical": 0, "unreachable": 0},
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

"""CLI entry point for multicluster-health.

Usage:
    python -m multicluster_health.cli check --config config.yaml
    multicluster-health check --config config.yaml
"""

import json
import sys
from pathlib import Path

import click

from .aggregator import get_all_clusters_health

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


# ── Report formatter ─────────────────────────────────────────────────────


def _format_health_summary(data: dict) -> str:
    """Render ``get_all_clusters_health()`` output as a Markdown summary."""
    lines: list[str] = [
        "# Multi-Cluster Health Overview\n",
    ]

    summary = data.get("summary", {})
    total = summary.get("total", 0)
    healthy = summary.get("healthy", 0)
    degraded = summary.get("degraded", 0)
    critical = summary.get("critical", 0)
    unreachable = summary.get("unreachable", 0)

    parts = [f"**{healthy} healthy**"]
    if degraded:
        parts.append(f"{degraded} degraded")
    if critical:
        parts.append(f"{critical} critical")
    if unreachable:
        parts.append(f"{unreachable} unreachable")
    else:
        parts.append("all reachable")
    lines.append(f"> {', '.join(parts)}\n")

    for cluster in data.get("clusters", []):
        name = cluster.get("name", cluster.get("context", "?"))
        ctx = cluster.get("context", "?")
        status = cluster.get("status", "unknown")
        reachable = cluster.get("reachable", False)

        if not reachable:
            err = cluster.get("error", "Unknown error")
            lines.append(f"## :red_circle: {name} ({ctx}) — Unreachable")
            lines.append(f"```\n{err}\n```\n")
            continue

        icon = ":large_blue_circle:"
        if status == "degraded":
            icon = ":yellow_circle:"
        elif status == "critical":
            icon = ":red_circle:"

        lines.append(f"## {icon} {name} ({ctx}) — {status}")

        nodes = cluster.get("nodes", {})
        pods = cluster.get("pods", {})
        cpu = cluster.get("cpu_utilization_percent", -1)
        mem = cluster.get("memory_utilization_percent", -1)

        ready = nodes.get("ready", 0)
        not_ready = nodes.get("not_ready", 0)
        total_nodes = ready + not_ready

        lines.append(f"\n**Nodes:** {ready}/{total_nodes} ready")
        if not_ready:
            lines.append(f"  - {not_ready} not ready")

        running = pods.get("running", 0)
        pending = pods.get("pending", 0)
        crashloop = pods.get("crashloop", 0)
        failed = pods.get("failed", 0)
        total_pods = running + pending + crashloop + failed

        lines.append(f"\n**Pods:** {running}/{total_pods} running")
        if pending:
            lines.append(f"  - {pending} pending")
        if crashloop:
            lines.append(f"  - {crashloop} crash looping")
        if failed:
            lines.append(f"  - {failed} failed")

        cpu_str = f"{cpu:.1f}%" if cpu >= 0 else "N/A"
        mem_str = f"{mem:.1f}%" if mem >= 0 else "N/A"
        lines.append(f"\n**Utilization:** CPU {cpu_str}, Memory {mem_str}\n")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────


@click.group()
def cli():
    """Multi-cluster health monitoring for Kubernetes."""


@cli.command()
@click.option("--config", "-c", default=str(DEFAULT_CONFIG),
              type=click.Path(exists=True),
              help="Path to the multi-cluster config YAML.")
@click.option("--output", "-O", type=click.Path(),
              help="Save the report to this file instead of printing to stdout.")
@click.option("--json", "as_json", is_flag=True,
              help="Output raw JSON instead of a Markdown summary.")
def check(config, output, as_json):
    """Check health across all configured Kubernetes clusters in parallel.

    Reads a cluster config YAML and contacts every cluster concurrently
    with a 10-second timeout each. Requires the target kubeconfig contexts
    to be defined in ~/.kube/config.

    \b
    Example:
        multicluster-health check
        multicluster-health check --config my-clusters.yaml --output health.md
        multicluster-health check --json
    """
    click.echo("Probing clusters in parallel ...")
    data = get_all_clusters_health(config)

    if as_json:
        report = json.dumps(data, indent=2, default=str)
    else:
        report = _format_health_summary(data)

    if output:
        Path(output).write_text(report, encoding="utf-8")
        click.echo(f"Health report saved to {output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        click.echo(report)


if __name__ == "__main__":
    cli()

"""Parallel multi-cluster health aggregator.

Runs :func:`~multicluster_health.health.get_cluster_health` across all
configured clusters concurrently and returns a combined result set with
an overall summary.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Dict, List

from .clusters import load_cluster_configs
from .health import get_cluster_health

# Each cluster gets at most this many seconds to respond.
_CLUSTER_TIMEOUT_SECONDS = 10


def get_all_clusters_health(config_path: str) -> Dict[str, Any]:
    """Assess health of every cluster defined in *config_path* in parallel.

    Each cluster is probed in a separate thread with a **10-second timeout**.
    Clusters that time out, raise an unexpected exception, or are already
    returned as unreachable by :func:`get_cluster_health` are all captured
    safely — no single cluster failure propagates to the caller.

    Parameters
    ----------
    config_path:
        Path to the multi-cluster YAML configuration file (see
        :func:`~multicluster_health.clusters.load_cluster_configs`).

    Returns
    -------
    dict with keys:

        **clusters** (*list[dict]*)
            One result per cluster, as returned by
            :func:`get_cluster_health`, with an additional ``"name"`` key
            injected from the config.

        **summary** (*dict*)
            ``{"total": int, "healthy": int, "degraded": int,
              "critical": int, "unreachable": int}``
    """
    cluster_defs = load_cluster_configs(config_path)

    # ── Submit all probes in parallel ────────────────────────────────────
    # Map future -> (name, context) so we can reconstruct results
    # regardless of submission order.
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=len(cluster_defs) or 1) as pool:
        future_to_cluster = {
            pool.submit(get_cluster_health, entry["context"]): entry
            for entry in cluster_defs
        }

        for future in future_to_cluster:
            entry = future_to_cluster[future]
            name: str = entry["name"]
            context: str = entry["context"]

            try:
                result = future.result(timeout=_CLUSTER_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                result = _timeout_result(context)
            except Exception as exc:
                result = _exception_result(context, str(exc))

            # Inject the human-friendly name from the config.
            result["name"] = name
            results.append(result)

    # ── Aggregate summary ────────────────────────────────────────────────
    summary: Dict[str, int] = {
        "total": len(results),
        "healthy": 0,
        "degraded": 0,
        "critical": 0,
        "unreachable": 0,
    }
    for r in results:
        status: str = r.get("status", "unreachable")
        if status in summary:
            summary[status] += 1

    return {
        "clusters": results,
        "summary": summary,
    }


# ── Internal helpers ─────────────────────────────────────────────────────


def _timeout_result(context: str) -> Dict[str, Any]:
    """Build a fallback result for a cluster that did not respond in time."""
    return {
        "name": context,
        "context": context,
        "reachable": False,
        "error": f"Timed out after {_CLUSTER_TIMEOUT_SECONDS}s",
        "status": "unreachable",
    }


def _exception_result(context: str, error: str) -> Dict[str, Any]:
    """Build a fallback result for a cluster whose probe raised unexpectedly."""
    return {
        "name": context,
        "context": context,
        "reachable": False,
        "error": error,
        "status": "unreachable",
    }

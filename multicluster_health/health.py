"""Cluster-level health assessment for Kubernetes.

Provides :func:`get_cluster_health` which collects node health, pod health,
resource utilization, and API server reachability into a single structured
result with an overall status classification.
"""

from typing import Any, Dict, Tuple

from kubernetes.client import CoreV1Api

from .clusters import get_client_for_context

# ── Status thresholds ────────────────────────────────────────────────────

UTILIZATION_CRITICAL_THRESHOLD = 90.0  # CPU or memory % above this → "critical"


# ── Public API ───────────────────────────────────────────────────────────


def get_cluster_health(context_name: str) -> Dict[str, Any]:
    """Assess the overall health of a Kubernetes cluster.

    Connects to the cluster identified by *context_name*, collects node
    readiness, pod status, aggregate resource utilization, and API server
    reachability, then returns a structured dict with a human-friendly
    ``status`` label.

    Parameters
    ----------
    context_name:
        A kubeconfig context name (must exist in ``~/.kube/config``).

    Returns
    -------
    dict with keys:

        **context** (*str*)
            The kubeconfig context that was queried.
        **reachable** (*bool*)
            Whether the API server responded successfully.
        **error** (*str*, optional)
            Set when *reachable* is ``False``.
        **nodes** (*dict*)
            ``{"ready": int, "not_ready": int}``
        **pods** (*dict*)
            ``{"running": int, "pending": int, "crashloop": int, "failed": int}``
        **cpu_utilization_percent** (*float*)
            Approximate cluster-wide CPU request vs. allocatable ratio.
        **memory_utilization_percent** (*float*)
            Approximate cluster-wide memory request vs. allocatable ratio.
        **status** (*str*)
            One of ``"healthy"``, ``"degraded"``, ``"critical"``,
            or ``"unreachable"``.
    """
    result: Dict[str, Any] = {"context": context_name}

    # ── 1. API reachability ──────────────────────────────────────────────
    try:
        v1 = get_client_for_context(context_name)
    except Exception as exc:
        result["reachable"] = False
        result["error"] = str(exc)
        result["status"] = "unreachable"
        return result

    result["reachable"] = True

    # ── 2. Node health ───────────────────────────────────────────────────
    try:
        node_data = _collect_node_data(v1)
        result["nodes"] = {
            "ready": node_data["ready"],
            "not_ready": node_data["not_ready"],
        }
    except Exception as exc:
        result["reachable"] = False
        result["error"] = f"Failed to list nodes: {exc}"
        result["status"] = "unreachable"
        return result

    # ── 3. Pod health (all namespaces) ───────────────────────────────────
    try:
        pod_data = _collect_pod_data(v1)
        result["pods"] = {
            "running": pod_data["running"],
            "pending": pod_data["pending"],
            "crashloop": pod_data["crashloop"],
            "failed": pod_data["failed"],
        }
    except Exception as exc:
        result["reachable"] = False
        result["error"] = f"Failed to list pods: {exc}"
        result["status"] = "unreachable"
        return result

    # ── 4. Resource utilization (best-effort) ────────────────────────────
    try:
        cpu_pct, mem_pct = _compute_utilization(v1)
        result["cpu_utilization_percent"] = cpu_pct
        result["memory_utilization_percent"] = mem_pct
    except Exception:
        result["cpu_utilization_percent"] = -1.0
        result["memory_utilization_percent"] = -1.0

    # ── 5. Status classification ─────────────────────────────────────────
    result["status"] = _classify_status(result)

    return result


# ── Internal helpers ─────────────────────────────────────────────────────


def _collect_node_data(v1: CoreV1Api) -> Dict[str, int]:
    """Count Ready and NotReady nodes across the cluster."""
    nodes = v1.list_node().items
    ready = 0
    not_ready = 0

    for node in nodes:
        conditions = node.status.conditions or []
        is_ready = False
        has_ready_condition = False

        for cond in conditions:
            if cond.type == "Ready":
                has_ready_condition = True
                is_ready = cond.status == "True"
                break

        if is_ready:
            ready += 1
        elif has_ready_condition:
            not_ready += 1
        else:
            # Node has no Ready condition at all — treat as not ready.
            not_ready += 1

    return {"ready": ready, "not_ready": not_ready}


def _collect_pod_data(v1: CoreV1Api) -> Dict[str, int]:
    """Count pods by health status across all namespaces.

    CrashLoopBackOff takes priority over phase — a pod whose *any* container
    (including init containers) is in CrashLoopBackOff is counted as
    ``crashloop`` regardless of its advertised phase.  Remaining pods are
    categorised by their ``.status.phase``.
    """
    pods = v1.list_pod_for_all_namespaces().items
    running = 0
    pending = 0
    failed = 0
    crashloop = 0

    for pod in pods:
        phase = pod.status.phase or "Unknown"

        # Check for CrashLoopBackOff across all containers + init containers.
        in_crashloop = False
        for statuses in (
            pod.status.container_statuses or [],
            pod.status.init_container_statuses or [],
        ):
            for cs in statuses:
                waiting = cs.state.waiting
                if waiting and waiting.reason == "CrashLoopBackOff":
                    in_crashloop = True
                    break
            if in_crashloop:
                break

        if in_crashloop:
            crashloop += 1
        elif phase == "Running":
            running += 1
        elif phase == "Pending":
            pending += 1
        elif phase == "Failed":
            failed += 1
        # Succeeded / Unknown — not explicitly tracked.

    return {
        "running": running,
        "pending": pending,
        "crashloop": crashloop,
        "failed": failed,
    }


def _compute_utilization(v1: CoreV1Api) -> Tuple[float, float]:
    """Compute approximate cluster-wide CPU and memory utilisation.

    Returns ``(cpu_percent, memory_percent)`` where each is the ratio of
    sum(pod resource requests) to sum(node allocatable capacity) across the
    entire cluster, multiplied by 100 and rounded to one decimal place.

    Only pods that are scheduled (assigned to a node) contribute to the
    request totals.  Containers without explicit resource requests contribute
    zero, which means the returned percentages represent a **lower bound** on
    actual utilisation.
    """
    # ── Sum node allocatable capacity ────────────────────────────────────
    nodes = v1.list_node().items
    total_cpu = 0.0    # cores
    total_mem = 0.0    # bytes

    for node in nodes:
        alloc = node.status.allocatable or {}
        total_cpu += _parse_quantity(str(alloc.get("cpu", "0")))
        total_mem += _parse_quantity(str(alloc.get("memory", "0")))

    if total_cpu <= 0 or total_mem <= 0:
        return -1.0, -1.0

    # ── Sum resource requests of scheduled pods ──────────────────────────
    pods = v1.list_pod_for_all_namespaces().items
    requested_cpu = 0.0
    requested_mem = 0.0

    for pod in pods:
        # Only pods assigned to a node consume resources.
        if not pod.spec.node_name:
            continue
        for container in pod.spec.containers:
            requests = container.resources.requests or {}
            if requests:
                requested_cpu += _parse_quantity(str(requests.get("cpu", "0")))
                requested_mem += _parse_quantity(str(requests.get("memory", "0")))

    cpu_pct = _safe_pct(requested_cpu, total_cpu)
    mem_pct = _safe_pct(requested_mem, total_mem)

    return round(cpu_pct, 1), round(mem_pct, 1)


def _parse_quantity(value: str) -> float:
    """Parse a Kubernetes resource quantity into a bare number.

    Handles plain integers, decimals, binary-suffixed (Ki, Mi, Gi, Ti, Pi, Ei),
    and SI-suffixed (m, k, M, G, T, P, E) formats.

    Returns the quantity in its **base unit** (cores for CPU, bytes for
    memory).  Returns ``0.0`` for unparseable values.
    """
    value = value.strip()
    if not value:
        return 0.0

    # Binary suffixes (case-sensitive — Kubernetes uses Ki/Mi/Gi etc.).
    binary_suffixes = {
        "Ki": 2**10,
        "Mi": 2**20,
        "Gi": 2**30,
        "Ti": 2**40,
        "Pi": 2**50,
        "Ei": 2**60,
    }
    for suffix, mult in binary_suffixes.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * mult
            except ValueError:
                return 0.0

    # Decimal SI suffixes (longest first to avoid false match on "m" vs "M").
    decimal_suffixes = {"m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}
    for suffix, mult in sorted(decimal_suffixes.items(), key=lambda x: -len(x[0])):
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * mult
            except ValueError:
                return 0.0

    # Bare number (integer or decimal).
    try:
        return float(value)
    except ValueError:
        return 0.0


def _safe_pct(part: float, total: float) -> float:
    """Return ``part / total * 100``, guarding against division by zero."""
    if total <= 0:
        return -1.0
    return min((part / total) * 100, 100.0)


def _classify_status(result: Dict[str, Any]) -> str:
    """Classify overall cluster health based on observed data.

    Priority order (first match wins):
        1. NotReady nodes or CrashLoopBackOff pods  → ``"degraded"``
        2. CPU or memory utilisation > 90%          → ``"critical"``
        3. Otherwise                                → ``"healthy"``

    ``"unreachable"`` is set before this function is called and is never
    returned here.
    """
    nodes = result.get("nodes", {})
    pods = result.get("pods", {})

    if nodes.get("not_ready", 0) > 0 or pods.get("crashloop", 0) > 0:
        return "degraded"

    cpu = result.get("cpu_utilization_percent", 0)
    mem = result.get("memory_utilization_percent", 0)
    if cpu > UTILIZATION_CRITICAL_THRESHOLD or mem > UTILIZATION_CRITICAL_THRESHOLD:
        return "critical"

    return "healthy"

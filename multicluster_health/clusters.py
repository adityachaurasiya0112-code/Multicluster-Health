"""Multi-cluster client management for Kubernetes health checks.

Provides helpers to load cluster definitions from a shared config file
and build authenticated ``CoreV1Api`` clients for each context.

.. note::

   This module relies on the user's ``~/.kube/config`` containing entries
   for every cluster context referenced in the application config.  Verify
   available contexts with::

       kubectl config get-contexts

   If a context is missing, add it with::

       kubectl config set-context <name> --cluster=<cluster> --user=<user>
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config


# ── Public API ───────────────────────────────────────────────────────────


def load_cluster_configs(config_path: str) -> List[Dict[str, str]]:
    """Read a multi-cluster YAML config and return cluster definitions.

    The YAML file is expected to have the following structure:

    .. code-block:: yaml

        clusters:
          - name: production-us
            context: prod-us-east-1
          - name: production-eu
            context: prod-eu-west-1
          - name: staging
            context: staging-us-east-1

    Each entry maps a human-friendly *name* (used in UI / logging) to a
    *context* that must exist in the user's ``~/.kube/config``.

    Parameters
    ----------
    config_path:
        Absolute or relative path to the YAML configuration file.

    Returns
    -------
    List[Dict[str, str]]
        A list of cluster dicts, each containing ``"name"`` and
        ``"context"`` keys.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    ValueError
        If the config file is malformed or missing required keys.
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Cluster config not found: {config_path}")

    with open(path, "r") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    if not isinstance(raw, dict) or "clusters" not in raw:
        raise ValueError(
            "Config must be a dictionary with a top-level 'clusters' list. "
            f"Got: {type(raw).__name__}"
        )

    clusters: List[Dict[str, Any]] = raw["clusters"]
    if not isinstance(clusters, list):
        raise ValueError(
            f"'clusters' must be a list, got: {type(clusters).__name__}"
        )

    result: List[Dict[str, str]] = []
    for i, entry in enumerate(clusters):
        if not isinstance(entry, dict):
            raise ValueError(f"Cluster entry {i} is not a dict: {entry}")
        if "name" not in entry or "context" not in entry:
            raise ValueError(
                f"Cluster entry {i} must have both 'name' and 'context' keys. "
                f"Got: {list(entry.keys())}"
            )
        result.append({"name": str(entry["name"]), "context": str(entry["context"])})

    return result


def get_client_for_context(context_name: str) -> k8s_client.CoreV1Api:
    """Build a ``CoreV1Api`` client authenticated for the given kubeconfig context.

    This calls ``kubernetes.config.load_kube_config(context=context_name)``
    internally, which:

    1. Reads the user's default kubeconfig (``~/.kube/config``).
    2. Selects the named context (cluster + user + namespace tuple).
    3. Configures a ``kubernetes.client.ApiClient`` with the matching
       credentials.

    .. caution::

       The context **must already exist** in the local kubeconfig.
       See :func:`load_cluster_configs` for how to verify contexts.

    Parameters
    ----------
    context_name:
        The name of a kubeconfig context (e.g. ``"prod-us-east-1"``).

    Returns
    -------
    kubernetes.client.CoreV1Api
        An API client ready to call core Kubernetes APIs (pods, nodes,
        services, etc.) against the target cluster.
    """
    k8s_config.load_kube_config(context=context_name)
    return k8s_client.CoreV1Api()

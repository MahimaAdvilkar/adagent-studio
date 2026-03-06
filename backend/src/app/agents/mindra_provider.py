from __future__ import annotations

from typing import Any

import httpx

from app.agents.executor import execute_graph
from app.agents.orchestration import build_campaign_response
from app.models.agent_graph import AgentGraph
from utils.config import (
    MINDRA_API_KEY,
    MINDRA_API_URL,
    MINDRA_PROVIDER,
    MINDRA_TIMEOUT_SECONDS,
    MINDRA_WORKFLOW_SLUG,
)


class MindraApiError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _build_mindra_view(graph: AgentGraph) -> dict[str, Any]:
    """Build a UI-friendly node tree/events payload from the executed graph."""
    children_map: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes.keys()}
    for node_id, node in graph.nodes.items():
        for dep in node.depends_on:
            if dep in children_map:
                children_map[dep].append(node_id)

    ordered_nodes = sorted(graph.nodes.values(), key=lambda n: (n.level, n.id))
    tree = [
        {
            "id": node.id,
            "name": node.name,
            "depth": node.level,
            "status": node.status.value,
            "depends_on": node.depends_on,
            "children": children_map.get(node.id, []),
            "task": node.description,
        }
        for node in ordered_nodes
    ]

    events = []
    for node in ordered_nodes:
        events.append(
            {
                "type": "node_completed" if node.status.value == "done" else "node_status",
                "node_id": node.id,
                "message": f"{node.name}: {node.status.value}",
            }
        )

    events.append(
        {
            "type": "final_result",
            "node_id": "root",
            "message": "Graph execution finished and returned to UI",
        }
    )

    max_depth = max((n.level for n in graph.nodes.values()), default=0)
    return {
        "max_depth": max_depth,
        "tree": tree,
        "events": events,
    }


def _run_local(brief_payload: dict[str, Any], blueprint) -> dict[str, Any]:
    graph = blueprint.create(brief_payload)
    graph = execute_graph(graph)
    result = build_campaign_response(graph, brief_payload)
    result["mindra"] = _build_mindra_view(graph)
    result["mindra_version"] = "v3-real-graph"
    result["mindra_source"] = "local"
    return result


def _run_api(brief_payload: dict[str, Any]) -> dict[str, Any]:
    if not MINDRA_API_KEY:
        raise RuntimeError("MINDRA_PROVIDER=api but MINDRA_API_KEY is empty.")

    run_url = MINDRA_API_URL
    if not run_url and MINDRA_WORKFLOW_SLUG:
        run_url = f"https://api.mindra.co/v1/workflows/{MINDRA_WORKFLOW_SLUG}/run"
    if not run_url:
        raise RuntimeError(
            "Set MINDRA_API_URL or MINDRA_WORKFLOW_SLUG when MINDRA_PROVIDER=api."
        )

    task = (
        f"Brand: {brief_payload.get('brand', '')}; "
        f"Goal: {brief_payload.get('goal', '')}; "
        f"Audience: {brief_payload.get('audience', '')}; "
        f"Budget: {brief_payload.get('budget', '')}"
    )
    api_payload = {
        "task": task,
        "metadata": brief_payload,
    }

    headers = {"Content-Type": "application/json"}
    headers["x-api-key"] = MINDRA_API_KEY

    with httpx.Client(timeout=MINDRA_TIMEOUT_SECONDS) as client:
        response = client.post(run_url, headers=headers, json=api_payload)

    if response.status_code >= 400:
        raise MindraApiError(
            response.status_code,
            f"Mindra API request failed: {response.status_code} {response.text[:300]}",
        )

    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"Mindra API did not return valid JSON: {str(exc)}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Mindra API response must be a JSON object.")

    execution_id = str(data.get("execution_id", ""))
    status = str(data.get("status", "running"))
    workflow_slug = str(data.get("workflow_slug", MINDRA_WORKFLOW_SLUG or ""))
    workflow_name = str(data.get("workflow_name", workflow_slug or "Mindra Workflow"))
    stream_url = str(data.get("stream_url", ""))

    # API run endpoint is async-by-design; return a normalized snapshot for current UI.
    return {
        "status": status,
        "campaign_id": execution_id or f"mindra-{workflow_slug}",
        "brand": str(brief_payload.get("brand", "")),
        "goal": str(brief_payload.get("goal", "")),
        "strategy": {
            "workflow_slug": workflow_slug,
            "workflow_name": workflow_name,
            "execution_id": execution_id,
            "stream_url": stream_url,
        },
        "vendor_statuses": [],
        "transactions": [],
        "transaction_count": 0,
        "finance": {"total_spend": 0.0, "margin": float(brief_payload.get("budget", 0) or 0)},
        "metrics": {"roi": "-", "clicks": "-", "conversions": "-"},
        "switch_state": "HOLD",
        "switch_note": (
            "Workflow execution started in Mindra API. "
            "Use stream_url to follow live events."
        ),
        "mindra": {
            "max_depth": 0,
            "events": [
                {
                    "type": "workflow_started",
                    "node_id": execution_id or "workflow",
                    "message": (
                        f"{workflow_name} started ({status}). "
                        + (f"stream: {stream_url}" if stream_url else "")
                    ).strip(),
                }
            ],
            "tree": [
                {
                    "id": execution_id or "workflow",
                    "name": workflow_name,
                    "depth": 0,
                    "status": status,
                    "depends_on": [],
                    "children": [],
                    "task": f"Brand={brief_payload.get('brand', '')}; Goal={brief_payload.get('goal', '')}",
                }
            ],
        },
        "mindra_source": "api",
        "mindra_version": "v4-mindra-api",
        "mindra_api_raw": data,
    }


def run_mindra_flow(brief_payload: dict[str, Any], blueprint) -> dict[str, Any]:
    """Graph-first hybrid mode: always execute local graph; Mindra is used by child nodes."""
    result = _run_local(brief_payload, blueprint)
    result["mindra_mode"] = "hybrid-graph-first"
    if MINDRA_PROVIDER == "api":
        result["mindra_note"] = (
            "Full API replacement mode is disabled. Mindra is used as child node only."
        )
    return result

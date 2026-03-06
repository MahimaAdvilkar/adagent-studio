"""
AgentGraph Executor for AdAgent Studio.

Runs the agent graph level by level:
  - Orchestrator nodes  → call Gemini with the node's subgraph_hint to produce a work output
  - Vendor leaf nodes   → call the appropriate VendorClient method (paid via NVM)
  - Internal leaf nodes → call Gemini with node context for analysis/decisions

The executor is synchronous and returns the completed AgentGraph.
"""

import json
from google import genai
from utils.config import GOOGLE_API_KEY
from app.models.agent_graph import AgentGraph, AgentNode, AgentStatus, NodeType
from app.agents.vendor_client import VendorClient

# ── Vendor dispatch table ─────────────────────────────────────────────────────
# Maps agent id fragments → VendorClient method
VENDOR_DISPATCH = {
    "creative_lady":   VendorClient.create_ad_creatives,
    "creative":        VendorClient.create_ad_creatives,
    "website_guy":     VendorClient.build_landing_page,
    "website":         VendorClient.build_landing_page,
    "exa":             VendorClient.research_audience,
    "research":        VendorClient.research_audience,
    "zeroclick":       VendorClient.place_ads,
    "media":           VendorClient.place_ads,
    "ads":             VendorClient.place_ads,
}


def _is_vendor(node: AgentNode) -> bool:
    """True if this node maps to an external vendor call."""
    node_id = node.id.lower()
    return any(key in node_id for key in VENDOR_DISPATCH)


def _get_vendor_fn(node: AgentNode):
    """Return VendorClient method matching the agent id, or None."""
    node_id = node.id.lower()
    for key, fn in VENDOR_DISPATCH.items():
        if key in node_id:
            return fn
    return None


# ── LLM client ───────────────────────────────────────────────────────────────
_gemini = genai.Client(api_key=GOOGLE_API_KEY)
_MODEL  = "gemini-2.5-flash"


def _run_llm_node(node: AgentNode, graph: AgentGraph) -> dict:
    """
    Run a Gemini call for an internal orchestrator or analysis node.
    Context includes: the campaign brief, the node description,
    and outputs from all dependency nodes.
    """
    # Collect dependency outputs to pass as context
    dep_outputs = {}
    for dep_id in node.depends_on:
        dep_node = graph.get_node(dep_id)
        if dep_node and dep_node.output:
            dep_outputs[dep_node.name] = dep_node.output

    prompt = f"""You are the {node.name} agent inside an autonomous advertising agency.

Campaign context:
- Brand: {graph.brand}
- Goal: {graph.goal}
- Budget: ${graph.total_budget}

Your role: {node.description}

{"Inputs from upstream agents:" if dep_outputs else ""}
{json.dumps(dep_outputs, indent=2) if dep_outputs else ""}

{"Special instructions: " + node.subgraph_hint if node.subgraph_hint else ""}

Produce a concise JSON output with your work results. Keys should match your role.
Respond ONLY in valid JSON — no markdown fences, no explanation.
"""

    try:
        response = _gemini.models.generate_content(model=_MODEL, contents=prompt)
        raw = response.text.strip()
        # Strip fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip().rstrip("```")
        return json.loads(raw)
    except Exception as e:
        return {"status": "llm_error", "error": str(e), "raw": getattr(response, "text", "")}


# ── Main executor ─────────────────────────────────────────────────────────────

def execute_graph(graph: AgentGraph) -> AgentGraph:
    """
    Run the full agent graph to completion.
    Returns the same graph with all nodes populated (status + output).
    """
    print(f"[Executor] Starting campaign: {graph.campaign_id} | {graph.brand}")

    max_iterations = 20  # safety limit
    iteration = 0

    while not graph.is_complete() and iteration < max_iterations:
        iteration += 1
        ready_nodes = graph.get_ready_nodes()

        if not ready_nodes:
            print("[Executor] No ready nodes — possible dependency deadlock. Stopping.")
            break

        for node in ready_nodes:
            # Skip if any upstream dep failed
            failed_deps = [
                dep_id for dep_id in node.depends_on
                if graph.get_node(dep_id) and graph.get_node(dep_id).status == AgentStatus.FAILED
            ]
            if failed_deps:
                node.mark_skipped(f"upstream failed: {', '.join(failed_deps)}")
                print(f"[Executor]   ⚠ {node.name} skipped (upstream failed)")
                continue

            print(f"[Executor] Running: {node.icon} {node.name} (level {node.level})")
            node.mark_running()

            try:
                # ── Vendor call ──────────────────────────────────────────────
                vendor_fn = _get_vendor_fn(node)
                if vendor_fn:
                    # Build enriched brief with upstream outputs
                    campaign_brief = dict(node.input or {})
                    campaign_brief["brand"]    = graph.brand
                    campaign_brief["goal"]     = graph.goal
                    campaign_brief["budget"]   = graph.total_budget

                    # Attach upstream outputs (e.g. research → brief enrichment)
                    for dep_id in node.depends_on:
                        dep = graph.get_node(dep_id)
                        if dep and dep.output:
                            campaign_brief.update(dep.output)

                    result = vendor_fn(campaign_brief)
                    node.mark_done(result)
                    print(f"[Executor]   ✓ {node.name} → vendor call: {result.get('status', 'ok')}")

                # ── LLM / internal node ──────────────────────────────────────
                else:
                    result = _run_llm_node(node, graph)
                    node.mark_done(result)
                    print(f"[Executor]   ✓ {node.name} → LLM output keys: {list(result.keys())}")

            except Exception as e:
                error_msg = str(e)
                node.mark_failed(error_msg)
                print(f"[Executor]   ✗ {node.name} FAILED: {error_msg}")

    print(f"[Executor] Done. Summary: {graph.summary()}")
    return graph

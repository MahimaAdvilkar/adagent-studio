from __future__ import annotations

from typing import Any

from app.models.agent_graph import AgentGraph, AgentStatus
from utils.payments import nevermined_wallet_snapshot


VENDOR_COSTS = {
    "website_guy": 3.0,
    "creative_lady": 2.0,
    "exa": 0.5,
    "zeroclick": 2.0,
    "twitter": 0.0,
    "twitter_ad_copy": 0.0,
}


def _review_prompt() -> dict[str, Any]:
    return {
        "title": "Leave a review",
        "message": "Help other users by sharing your experience with this campaign.",
        "cta_label": "Leave Review",
        "endpoint": "/api/trust-net/reviews",
        "method": "POST",
        "required_fields": [
            "agent_id",
            "reviewer_address",
            "verification_tx",
            "score",
            "comment",
        ],
        "optional_fields": [
            "score_accuracy",
            "score_speed",
            "score_value",
            "score_reliability",
        ],
        "notes": [
            "verification_tx must be a real Base Sepolia burn transaction hash.",
            "Reviews are free and do not require an x402 token.",
        ],
    }


def _to_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _find_node(graph: AgentGraph, candidates: list[str]):
    for node_id, node in graph.nodes.items():
        low = node_id.lower()
        if any(key in low for key in candidates):
            return node
    return None


def _vendor_statuses(graph: AgentGraph) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    vendor_map = [
        ("Exa (Research)", ["exa", "research"]),
        ("Website Guy", ["website"]),
        ("Creative Lady", ["creative"]),
        ("Twitter Ad Copy", ["twitter_ad_copy"]),
        ("Twitter Agent", ["mindra_twitter_agent"]),
        ("ZeroClick (Ads)", ["zeroclick", "ads", "media"]),
    ]

    for label, keys in vendor_map:
        node = _find_node(graph, keys)
        if node is None:
            rows.append({"label": label, "status": "Pending"})
            continue
        status = str(node.status.value if isinstance(node.status, AgentStatus) else node.status).capitalize()
        rows.append({"label": label, "status": status})
    return rows


def _transactions(graph: AgentGraph, budget: float) -> tuple[list[dict[str, Any]], float]:
    txs: list[dict[str, Any]] = [
        {"vendor": "Client Payment", "amount": round(float(budget), 2), "status": "Incoming"}
    ]
    spend = 0.0

    vendor_nodes = [
        ("Website Guy", ["website"], VENDOR_COSTS["website_guy"]),
        ("Creative Lady", ["creative"], VENDOR_COSTS["creative_lady"]),
        ("Twitter Ad Copy Agent", ["twitter_ad_copy"], VENDOR_COSTS["twitter_ad_copy"]),
        ("Twitter Agent", ["mindra_twitter_agent"], VENDOR_COSTS["twitter"]),
        ("Exa", ["exa", "research"], VENDOR_COSTS["exa"]),
        ("ZeroClick", ["zeroclick", "ads", "media"], VENDOR_COSTS["zeroclick"]),
    ]

    for name, keys, amount in vendor_nodes:
        node = _find_node(graph, keys)
        if node is None:
            txs.append({"vendor": name, "amount": 0.0, "status": "Not Configured"})
        elif node.status == AgentStatus.DONE:
            txs.append({"vendor": name, "amount": amount, "status": "Paid"})
            spend += amount
        elif node.status == AgentStatus.FAILED:
            txs.append({"vendor": name, "amount": 0.0, "status": "Failed"})
        elif node.status == AgentStatus.SKIPPED:
            txs.append({"vendor": name, "amount": 0.0, "status": "Skipped"})
        else:
            txs.append({"vendor": name, "amount": 0.0, "status": "Pending"})

    return txs, round(spend, 2)


def _strategy_output(graph: AgentGraph, brief: dict[str, Any]) -> dict[str, Any]:
    strategy_node = _find_node(graph, ["strategy"])
    if strategy_node and isinstance(strategy_node.output, dict):
        strategy = dict(strategy_node.output)
    else:
        strategy = {}

    audience = _to_text(strategy.get("audience"), _to_text(brief.get("audience"), "broad audience"))
    messaging = strategy.get("messaging")
    if not isinstance(messaging, list) or not messaging:
        messaging = ["save time", "scale faster", "no-code growth"]

    channels = strategy.get("channels")
    if not isinstance(channels, list) or not channels:
        channels = ["ZeroClick ads", "Landing page"]

    return {
        "goal": _to_text(strategy.get("goal"), _to_text(brief.get("goal"), "drive signups")),
        "audience": audience,
        "needs_website": True,
        "needs_ads": True,
        "messaging": messaging,
        "channels": channels,
        "budget_split": {
            "website": VENDOR_COSTS["website_guy"],
            "creative": VENDOR_COSTS["creative_lady"],
            "twitter_ad_copy": VENDOR_COSTS["twitter_ad_copy"],
            "twitter": VENDOR_COSTS["twitter"],
            "research": VENDOR_COSTS["exa"],
            "ads": VENDOR_COSTS["zeroclick"],
        },
    }


def _switching_signal(graph: AgentGraph) -> tuple[str, str]:
    for node in graph.nodes.values():
        if node.status == AgentStatus.FAILED:
            return "SWITCH", f"{node.name} failed. Switching to internal backup route."
    return "HOLD", "All core agents are healthy."


def _trading_signal(switch_state: str, margin: float) -> tuple[str, str]:
    """
    Hackathon-friendly BUY/SELL signal derived from ROI + switching.
    BUY  -> margin is positive and no failing agent.
    SELL -> margin <= 0 or switching was triggered due to failures.
    """
    if switch_state == "SWITCH" or margin <= 0:
        return "SELL", "Performance or delivery risk detected; reduce spend and reallocate."
    return "BUY", "Positive margin and stable execution; continue investment."


def workflow_preview(brief: dict[str, Any]) -> dict[str, Any]:
    budget = float(brief.get("budget", 15))
    strategy = {
        "goal": _to_text(brief.get("goal"), "drive signups"),
        "audience": _to_text(brief.get("audience"), "tech founders 25-40"),
        "needs_website": True,
        "needs_ads": True,
        "messaging": ["save time", "scale faster", "no-code growth"],
        "channels": ["ZeroClick ads", "Landing page"],
        "budget_split": {
            "website": VENDOR_COSTS["website_guy"],
            "creative": VENDOR_COSTS["creative_lady"],
            "twitter_ad_copy": VENDOR_COSTS["twitter_ad_copy"],
            "twitter": VENDOR_COSTS["twitter"],
            "research": VENDOR_COSTS["exa"],
            "ads": VENDOR_COSTS["zeroclick"],
        },
    }
    spend = sum(strategy["budget_split"].values())
    margin = round(budget - spend, 2)
    roi = f"{(margin / spend):.2f}x" if spend > 0 else "—"
    buy_sell, buy_sell_note = _trading_signal("HOLD", margin)
    wallet = nevermined_wallet_snapshot()
    finance = {"total_spend": round(spend, 2), "margin": margin}
    if wallet.get("available"):
        finance["wallet_value"] = wallet.get("wallet_value")
        finance["wallet_credits"] = wallet.get("wallet_credits")
        finance["price_per_credit"] = wallet.get("price_per_credit")

    return {
        "status": "preview",
        "brand": _to_text(brief.get("brand"), "Unknown brand"),
        "review_prompt": _review_prompt(),
        "strategy": strategy,
        "vendor_statuses": [
            {"label": "Exa (Research)", "status": "Pending"},
            {"label": "Website Guy", "status": "Pending"},
            {"label": "Creative Lady", "status": "Pending"},
            {"label": "Twitter Ad Copy Agent", "status": "Pending"},
            {"label": "Twitter Agent", "status": "Pending"},
            {"label": "ZeroClick (Ads)", "status": "Pending"},
        ],
        "transactions": [
            {"vendor": "Client Payment", "amount": round(budget, 2), "status": "Incoming"},
            {"vendor": "Website Guy", "amount": VENDOR_COSTS["website_guy"], "status": "Planned"},
            {"vendor": "Creative Lady", "amount": VENDOR_COSTS["creative_lady"], "status": "Planned"},
            {"vendor": "Twitter Ad Copy Agent", "amount": VENDOR_COSTS["twitter_ad_copy"], "status": "Planned"},
            {"vendor": "Twitter Agent", "amount": VENDOR_COSTS["twitter"], "status": "Planned"},
            {"vendor": "Exa", "amount": VENDOR_COSTS["exa"], "status": "Planned"},
            {"vendor": "ZeroClick", "amount": VENDOR_COSTS["zeroclick"], "status": "Planned"},
        ],
        "finance": finance,
        "metrics": {"roi": roi, "clicks": "—", "conversions": "—"},
        "buy_sell_signal": buy_sell,
        "buy_sell_note": buy_sell_note,
        "switch_state": "HOLD",
        "switch_note": "Workflow ready. Run campaign to execute agents.",
        "transaction_count": 7,
    }


def build_campaign_response(graph: AgentGraph, brief: dict[str, Any]) -> dict[str, Any]:
    budget = float(brief.get("budget", graph.total_budget))
    transactions, spend = _transactions(graph, budget)
    margin = round(budget - spend, 2)
    roi = f"{(margin / spend):.2f}x" if spend > 0 else "—"

    clicks = "—"
    conversions = "—"
    ads_node = _find_node(graph, ["zeroclick", "ads", "media"])
    if ads_node and isinstance(ads_node.output, dict):
        maybe_clicks = ads_node.output.get("clicks")
        if maybe_clicks is not None:
            clicks = str(maybe_clicks)
    analytics_node = _find_node(graph, ["analytics"])
    if analytics_node and isinstance(analytics_node.output, dict):
        maybe_conv = analytics_node.output.get("conversions")
        if maybe_conv is not None:
            conversions = str(maybe_conv)

    switch_state, switch_note = _switching_signal(graph)
    buy_sell, buy_sell_note = _trading_signal(switch_state, margin)
    wallet = nevermined_wallet_snapshot()
    finance = {"total_spend": spend, "margin": margin}
    if wallet.get("available"):
        finance["wallet_value"] = wallet.get("wallet_value")
        finance["wallet_credits"] = wallet.get("wallet_credits")
        finance["price_per_credit"] = wallet.get("price_per_credit")

    return {
        "status": "complete",
        "campaign_id": graph.campaign_id,
        "brand": graph.brand,
        "goal": graph.goal,
        "review_prompt": _review_prompt(),
        "summary": graph.summary(),
        "strategy": _strategy_output(graph, brief),
        "vendor_statuses": _vendor_statuses(graph),
        "transactions": transactions,
        "transaction_count": len(transactions),
        "finance": finance,
        "metrics": {"roi": roi, "clicks": clicks, "conversions": conversions},
        "buy_sell_signal": buy_sell,
        "buy_sell_note": buy_sell_note,
        "switch_state": switch_state,
        "switch_note": switch_note,
        "agents": {
            node_id: {
                "name": node.name,
                "status": node.status,
                "output": node.output,
                "duration_seconds": node.duration_seconds,
            }
            for node_id, node in graph.nodes.items()
        },
    }

#!/usr/bin/env python3
"""
Autonomous buyer agent — discovers ALL marketplace agents and calls them.

This is CRITICAL for hackathon scoring! Without this, you can only get seller points.

Discovery via Nevermined REST API:
  GET /api/v1/protocol/all-plans        -> all plans
  GET /api/v1/protocol/plans/{id}/agents -> agents for each plan

Scoring multipliers:
  - Plans bought  (x4)
  - Calls made    (x4)  
  - Diversity: unique counterparties (x3, cap 20)

Usage:
    pip install httpx payments-py python-dotenv
    python autonomous_buyer.py
"""

import asyncio
import os
import random
import sys
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from dotenv import load_dotenv
load_dotenv()

import httpx
from payments_py import Payments, PaymentOptions

NVM_API_KEY = os.environ.get("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.environ.get("NVM_ENVIRONMENT", "sandbox")

if not NVM_API_KEY:
    print("ERROR: NVM_API_KEY is required in .env")
    sys.exit(1)

payments = Payments.get_instance(
    PaymentOptions(nvm_api_key=NVM_API_KEY, environment=NVM_ENVIRONMENT)
)

NVM_API_BASE = "https://api.sandbox.nevermined.app/api/v1/protocol"
OWN_AGENT_ID = os.environ.get("NVM_AGENT_ID", "")
OWN_PLAN_ID = os.environ.get("NVM_PLAN_ID", "")

SAMPLE_QUERIES = [
    "Latest AI advertising trends 2026",
    "Autonomous ad campaign optimization",
    "AI-powered creative generation",
    "Programmatic advertising with ML",
    "Multi-channel ad attribution models",
    "Real-time bidding optimization",
    "AI audience segmentation techniques",
    "Creative A/B testing automation",
]


def _extract_post_urls(endpoints: list, base_url: str = "") -> list[str]:
    urls: list[str] = []
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        for method in ("POST", "post", "Post"):
            if method in ep:
                url = ep[method]
                if isinstance(url, str) and url.startswith("http"):
                    urls.append(url)
        url = ep.get("url", "")
        verb = ep.get("verb", ep.get("method", "")).upper()
        if verb == "POST" and isinstance(url, str):
            if url.startswith("http"):
                urls.append(url)
            elif base_url and base_url.startswith("http") and url.startswith("/"):
                urls.append(f"{base_url.rstrip('/')}{url}")
    return list(dict.fromkeys(urls))


async def discover_agents() -> list[dict]:
    discovered: list[dict] = []
    seen_ids: set[str] = set()
    headers = {"Authorization": f"Bearer {NVM_API_KEY}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        all_plans: list[dict] = []
        page = 1
        while True:
            resp = await client.get(
                f"{NVM_API_BASE}/all-plans",
                params={"page": page, "offset": 100},
                headers=headers,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            plans = data.get("plans", [])
            all_plans.extend(plans)
            total = data.get("total", 0)
            print(f"  [Discovery] Page {page}: {len(plans)} plans (total: {total})")
            if len(all_plans) >= total or not plans:
                break
            page += 1

        candidates = [p for p in all_plans if p.get("id") != OWN_PLAN_ID and "DEACTIVATED" not in p.get("metadata", {}).get("main", {}).get("name", "").upper()]
        print(f"  [Discovery] {len(candidates)} candidate plans")

        sem = asyncio.Semaphore(10)

        async def _fetch(plan: dict):
            pid = plan.get("id", "")
            async with sem:
                try:
                    r = await client.get(f"{NVM_API_BASE}/plans/{pid}/agents", headers=headers)
                    if r.status_code != 200:
                        return
                    for agent in r.json().get("agents", []):
                        aid = agent.get("id", "")
                        if not aid or aid == OWN_AGENT_ID or aid in seen_ids:
                            continue
                        meta = agent.get("metadata", {})
                        name = meta.get("main", {}).get("name", "Unknown")
                        if "DEACTIVATED" in name.upper():
                            continue
                        agent_meta = meta.get("agent", {})
                        seen_ids.add(aid)
                        discovered.append({
                            "agent_id": aid,
                            "name": name,
                            "plan_id": pid,
                            "endpoints": agent_meta.get("endpoints", []),
                            "base_url": agent_meta.get("agentDefinitionUrl", ""),
                        })
                except Exception:
                    pass

        await asyncio.gather(*[_fetch(p) for p in candidates], return_exceptions=True)

    print(f"  [Discovery] {len(discovered)} agents found")
    return discovered


async def buy_plan_and_call(agent_info: dict, query: str) -> dict:
    agent_id = agent_info["agent_id"]
    name = agent_info["name"]
    plan_id = agent_info.get("plan_id", "")
    base_url = agent_info.get("base_url", "")

    if not plan_id:
        return {"success": False, "reason": "No plan_id", "agent": name}

    headers = {"Authorization": f"Bearer {NVM_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                await client.post(f"{NVM_API_BASE}/plans/{plan_id}/order", headers=headers)
            except Exception:
                pass

            try:
                token_resp = await client.get(f"{NVM_API_BASE}/token/{plan_id}/{agent_id}", headers=headers)
                if token_resp.status_code != 200:
                    return {"success": False, "reason": f"Token {token_resp.status_code}", "agent": name}
                token = token_resp.json().get("accessToken", token_resp.json().get("token", ""))
            except Exception as e:
                return {"success": False, "reason": str(e)[:100], "agent": name}

            if not token:
                return {"success": False, "reason": "No token", "agent": name}

            urls = _extract_post_urls(agent_info.get("endpoints", []), base_url)
            if not urls and base_url and base_url.startswith("http"):
                for p in ["/ask", "/query", "/search", "/prompt", "/run"]:
                    urls.append(f"{base_url.rstrip('/')}{p}")

            for url in urls:
                try:
                    resp = await client.post(url, json={"query": query}, headers={"Content-Type": "application/json", "payment-signature": token})
                    print(f"  [Call] {name} -> {resp.status_code}")
                    if resp.status_code in (200, 201, 202):
                        return {"success": True, "agent": name}
                except Exception:
                    pass

        return {"success": False, "reason": "Failed", "agent": name}
    except Exception as e:
        return {"success": False, "reason": str(e)[:100], "agent": name}


async def run_buyer(max_rounds=10, delay=30, per_round=40):
    print(f"\n{'='*60}\n  Autonomous Buyer\n{'='*60}\n")

    called: set[str] = set()
    total = ok = 0
    agents: list[dict] = []

    for rnd in range(1, max_rounds + 1):
        print(f"\n--- Round {rnd}/{max_rounds} ---")

        if not agents or rnd % 3 == 1:
            agents = await discover_agents()

        if not agents:
            await asyncio.sleep(delay)
            continue

        batch = ([a for a in agents if a["agent_id"] not in called] + [a for a in agents if a["agent_id"] in called])[:per_round]

        for info in batch:
            result = await buy_plan_and_call(info, random.choice(SAMPLE_QUERIES))
            total += 1
            if result.get("success"):
                ok += 1
            if info["agent_id"] not in called:
                called.add(info["agent_id"])
            await asyncio.sleep(1)

        print(f"[Stats] Total: {total} | OK: {ok} | Unique: {len(called)}")

        if rnd < max_rounds:
            await asyncio.sleep(delay)

    print(f"\n{'='*60}\n  DONE: {total} calls, {ok} ok, {len(called)} unique\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_buyer(
        max_rounds=int(os.environ.get("BUYER_MAX_ROUNDS", "10")),
        delay=int(os.environ.get("BUYER_DELAY", "30")),
        per_round=int(os.environ.get("BUYER_PER_ROUND", "40")),
    ))

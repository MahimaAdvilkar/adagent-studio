"""
Standalone buyer-flow test runner for hackathon transactions.

This file is intentionally separate and does not modify your runtime app logic.
It helps you execute real paid purchases against external seller agents,
including repeat purchases for leaderboard criteria.

Supported services:
  - Creative Lady
  - Website Guy

Usage example:
  export NVM_BUYER_API_KEY='sandbox:...'
  export NVM_ENVIRONMENT='sandbox'
  export CREATIVE_LADY_URL='https://...'
  export CREATIVE_LADY_PLAN_ID='...'
  export WEBSITE_GUY_URL='https://...'
  export WEBSITE_GUY_PLAN_ID='...'

  python backend/src/test_buyer_flow_multi_service.py \
    --service both \
    --repeat-creative 2 \
    --repeat-website 2 \
    --order-first
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from payments_py import PaymentOptions, Payments


@dataclass
class ServiceConfig:
    name: str
    url: str
    plan_id: str
    agent_id: str
    payload: dict[str, Any]
    repeats: int


def load_env() -> None:
    src_dir = Path(__file__).resolve().parent
    backend_dir = src_dir.parent
    repo_dir = backend_dir.parent
    for env_path in [repo_dir / ".ENV", repo_dir / ".env", backend_dir / ".env"]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)


def decode_payment_required(raw: str) -> dict[str, Any]:
    payload = raw.strip()
    missing = len(payload) % 4
    if missing:
        payload += "=" * (4 - missing)
    return json.loads(base64.b64decode(payload).decode("utf-8"))


def extract_plan_agent_from_402(resp: requests.Response) -> tuple[str, str]:
    raw = resp.headers.get("payment-required", "").strip()
    if not raw:
        return "", ""
    try:
        pr = decode_payment_required(raw)
        accepts = pr.get("accepts")
        if not isinstance(accepts, list) or not accepts:
            return "", ""
        first = accepts[0] if isinstance(accepts[0], dict) else {}
        plan_id = str(first.get("planId") or "").strip()
        extra = first.get("extra") if isinstance(first.get("extra"), dict) else {}
        agent_id = str(extra.get("agentId") or "").strip()
        return plan_id, agent_id
    except Exception:
        return "", ""


def get_payments_client(api_key: str, environment: str) -> Payments:
    return Payments.get_instance(
        PaymentOptions(
            nvm_api_key=api_key,
            environment=environment,
        )
    )


def summarize_response(resp: requests.Response) -> str:
    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            return json.dumps(resp.json(), ensure_ascii=True)[:600]
        except Exception:
            return resp.text[:600]
    return resp.text[:600]


def paid_json_call(
    p: Payments,
    cfg: ServiceConfig,
    order_first: bool,
    infer_from_402: bool,
) -> tuple[bool, str]:
    plan_id = cfg.plan_id
    agent_id = cfg.agent_id

    if infer_from_402 and (not plan_id or not agent_id):
        probe = requests.post(
            cfg.url,
            json=cfg.payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        if probe.status_code == 402:
            inferred_plan, inferred_agent = extract_plan_agent_from_402(probe)
            if not plan_id:
                plan_id = inferred_plan
            if not agent_id:
                agent_id = inferred_agent

    if not plan_id:
        return False, f"{cfg.name}: missing plan_id (set env or use seller that returns payment-required header)."

    if order_first:
        try:
            p.plans.order_plan(plan_id=plan_id)
        except Exception as e:
            return False, f"{cfg.name}: order_plan failed: {e}"

    token_kwargs: dict[str, Any] = {"plan_id": plan_id, "redemption_limit": 1}
    if agent_id:
        token_kwargs["agent_id"] = agent_id

    try:
        token_result = p.x402.get_x402_access_token(**token_kwargs)
    except Exception as e:
        return False, f"{cfg.name}: token generation failed: {e}"

    token = str(token_result.get("accessToken") or "").strip()
    if not token:
        return False, f"{cfg.name}: empty access token."

    try:
        resp = requests.post(
            cfg.url,
            json=cfg.payload,
            headers={
                "Content-Type": "application/json",
                "payment-signature": token,
            },
            timeout=90,
        )
    except Exception as e:
        return False, f"{cfg.name}: HTTP request failed: {e}"

    if 200 <= resp.status_code < 300:
        return True, f"{cfg.name}: {resp.status_code} {summarize_response(resp)}"
    return False, f"{cfg.name}: {resp.status_code} {summarize_response(resp)}"


def build_configs(args: argparse.Namespace) -> list[ServiceConfig]:
    creative_payload = {
        "brand": "AdAgent Studio",
        "audience": "SF tech founders 25-40",
        "messaging": ["save time", "scale faster"],
        "formats": ["banner ad", "native ad", "headline"],
        "variations": 3,
    }
    website_payload = {
        "client": "AdAgent Studio",
        "goal": "drive signups",
        "audience": "SF tech founders 25-40",
        "messaging": ["save time", "scale faster"],
        "deadline": "2 hours",
    }

    cfgs: list[ServiceConfig] = []
    if args.service in ("creative", "both"):
        cfgs.append(
            ServiceConfig(
                name="Creative Lady",
                url=(os.getenv("CREATIVE_LADY_URL", "") or "").strip(),
                plan_id=(os.getenv("CREATIVE_LADY_PLAN_ID", "") or "").strip(),
                agent_id=(os.getenv("CREATIVE_LADY_AGENT_ID", "") or "").strip(),
                payload=creative_payload,
                repeats=max(0, args.repeat_creative),
            )
        )
    if args.service in ("website", "both"):
        cfgs.append(
            ServiceConfig(
                name="Website Guy",
                url=(os.getenv("WEBSITE_GUY_URL", "") or "").strip(),
                plan_id=(os.getenv("WEBSITE_GUY_PLAN_ID", "") or "").strip(),
                agent_id=(os.getenv("WEBSITE_GUY_AGENT_ID", "") or "").strip(),
                payload=website_payload,
                repeats=max(0, args.repeat_website),
            )
        )
    return cfgs


def main() -> None:
    load_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("--service", choices=["creative", "website", "both"], default="both")
    parser.add_argument("--repeat-creative", type=int, default=1)
    parser.add_argument("--repeat-website", type=int, default=1)
    parser.add_argument("--order-first", action="store_true")
    parser.add_argument("--infer-from-402", action="store_true")
    args = parser.parse_args()

    api_key = (os.getenv("NVM_BUYER_API_KEY") or os.getenv("NVM_API_KEY") or "").strip()
    nvm_env = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
    if not api_key:
        raise SystemExit("Missing NVM_BUYER_API_KEY (or NVM_API_KEY).")

    p = get_payments_client(api_key, nvm_env)
    cfgs = build_configs(args)
    if not cfgs:
        raise SystemExit("No services selected.")

    success_count = 0
    total_count = 0

    print("=== Buyer Flow Test (Standalone) ===")
    print("environment:", nvm_env)
    print("service_mode:", args.service)
    print("order_first:", args.order_first)
    print("infer_from_402:", args.infer_from_402)
    print()

    for cfg in cfgs:
        if not cfg.url:
            print(f"[SKIP] {cfg.name}: URL not set.")
            continue
        if cfg.repeats <= 0:
            print(f"[SKIP] {cfg.name}: repeats is 0.")
            continue

        for i in range(1, cfg.repeats + 1):
            total_count += 1
            ok, message = paid_json_call(
                p=p,
                cfg=cfg,
                order_first=args.order_first,
                infer_from_402=args.infer_from_402,
            )
            if ok:
                success_count += 1
                print(f"[OK {i}/{cfg.repeats}] {message}")
            else:
                print(f"[FAIL {i}/{cfg.repeats}] {message}")

    print()
    print("=== Summary ===")
    print("attempted:", total_count)
    print("succeeded:", success_count)
    print("failed:", total_count - success_count)


if __name__ == "__main__":
    main()

"""
Buyer script for a paid Nevermined seller endpoint:
  POST https://pod-backend-638060531529.us-central1.run.app/print

It performs a full real payment flow:
1) Probes endpoint without payment-signature to get `payment-required` metadata.
2) Generates x402 token using payments-py.
3) Replays the same request with `payment-signature`.

Usage:
  NVM_BUYER_API_KEY="sandbox:..." \
  python backend/src/buy_print_service.py \
    --pdf "/Users/mahimaadvilkar/Desktop/test.pdf" \
    --email "test@example.com"
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from payments_py import PaymentOptions, Payments

DEFAULT_ENDPOINT = "https://pod-backend-638060531529.us-central1.run.app/print"


def _load_env() -> None:
    src_dir = Path(__file__).resolve().parent
    backend_dir = src_dir.parent
    repo_dir = backend_dir.parent
    for env_path in [repo_dir / ".ENV", repo_dir / ".env", backend_dir / ".env"]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)


def _decode_payment_required(raw_header: str) -> dict[str, Any]:
    payload = raw_header.strip()
    missing = len(payload) % 4
    if missing:
        payload += "=" * (4 - missing)
    decoded = base64.b64decode(payload)
    data = json.loads(decoded.decode("utf-8"))
    return data


def _first_accept(pr: dict[str, Any]) -> dict[str, Any]:
    accepts = pr.get("accepts")
    if not isinstance(accepts, list) or not accepts:
        raise RuntimeError("payment-required header has no accepts entry.")
    first = accepts[0]
    if not isinstance(first, dict):
        raise RuntimeError("payment-required accepts[0] is invalid.")
    return first


def _post_without_payment(endpoint: str, pdf_path: str, email: str) -> requests.Response:
    with open(pdf_path, "rb") as fh:
        files = {"pdf": (Path(pdf_path).name, fh, "application/pdf")}
        data = {"email": email}
        return requests.post(endpoint, files=files, data=data, timeout=60)


def _post_with_payment(endpoint: str, pdf_path: str, email: str, token: str) -> requests.Response:
    with open(pdf_path, "rb") as fh:
        files = {"pdf": (Path(pdf_path).name, fh, "application/pdf")}
        data = {"email": email}
        headers = {"payment-signature": token}
        return requests.post(endpoint, files=files, data=data, headers=headers, timeout=90)


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--order-first", action="store_true")
    args = parser.parse_args()

    buyer_api_key = (os.getenv("NVM_BUYER_API_KEY") or os.getenv("NVM_API_KEY") or "").strip()
    nvm_env = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
    if not buyer_api_key:
        raise SystemExit("Missing NVM_BUYER_API_KEY (or NVM_API_KEY).")

    if not Path(args.pdf).exists():
        raise SystemExit(f"PDF file not found: {args.pdf}")

    first = _post_without_payment(args.endpoint, args.pdf, args.email)
    print("probe_status:", first.status_code)
    if first.status_code != 402:
        print("probe_body:", first.text[:500])
        raise SystemExit("Expected 402 Payment Required from probe request.")

    raw_pr = first.headers.get("payment-required", "")
    if not raw_pr:
        raise SystemExit("Missing payment-required response header.")

    pr = _decode_payment_required(raw_pr)
    accept = _first_accept(pr)
    plan_id = str(accept.get("planId") or "").strip()
    extra = accept.get("extra") if isinstance(accept.get("extra"), dict) else {}
    agent_id = str(extra.get("agentId") or "").strip()

    if not plan_id:
        raise SystemExit("Could not extract planId from payment-required header.")

    print("plan_id:", plan_id)
    print("agent_id:", agent_id or "<none>")
    print("network:", accept.get("network"))

    p = Payments.get_instance(PaymentOptions(nvm_api_key=buyer_api_key, environment=nvm_env))

    if args.order_first:
        try:
            p.plans.order_plan(plan_id=plan_id)
            print("order_plan: ok")
        except Exception as e:
            print("order_plan warning:", e)

    token_kwargs: dict[str, Any] = {"plan_id": plan_id, "redemption_limit": 1}
    if agent_id:
        token_kwargs["agent_id"] = agent_id

    token_result = p.x402.get_x402_access_token(**token_kwargs)
    token = str(token_result.get("accessToken") or "").strip()
    if not token:
        raise SystemExit("Failed to generate x402 access token.")
    print("token_generated:", True)

    paid = _post_with_payment(args.endpoint, args.pdf, args.email, token)
    print("paid_status:", paid.status_code)
    ct = (paid.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            print("paid_json:", json.dumps(paid.json(), indent=2))
            return
        except Exception:
            pass
    print("paid_text:", paid.text[:1000])


if __name__ == "__main__":
    main()

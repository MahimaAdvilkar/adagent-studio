"""
Minimal buyer client for AdAgent Studio.

Generates an x402 token from Nevermined and calls the paid endpoint:
POST /api/run-campaign
"""

import os
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
from payments_py import Payments, PaymentOptions
from payments_py.x402.types import X402PaymentRequired, X402Scheme, X402Resource, X402SchemeExtra


def main() -> None:
    # Load env from common project locations (backend/.env, root .ENV, root .env).
    src_dir = Path(__file__).resolve().parent
    backend_dir = src_dir.parent
    repo_dir = backend_dir.parent
    # Load root env files first, then backend/.env last so backend values win.
    for env_path in [repo_dir / ".ENV", repo_dir / ".env", backend_dir / ".env"]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

    nvm_api_key = (os.getenv("NVM_API_KEY") or "").strip()
    nvm_environment = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
    nvm_plan_id = (os.getenv("NVM_PLAN_ID") or "").strip()
    nvm_agent_id = (os.getenv("NVM_AGENT_ID") or "").strip()
    endpoint = (os.getenv("OUR_ENDPOINT") or "https://adagent-studio-seven.vercel.app/api/run-campaign").strip()

    if not nvm_api_key or not nvm_plan_id:
        raise SystemExit("Missing NVM_API_KEY or NVM_PLAN_ID in backend/.env")

    p = Payments.get_instance(
        PaymentOptions(
            nvm_api_key=nvm_api_key,
            environment=nvm_environment,
        )
    )

    # Try to subscribe this buyer to the seller plan before requesting token.
    # Some sandbox accounts fail here if wallet/address is not configured yet.
    try:
        p.plans.order_plan(plan_id=nvm_plan_id)
    except Exception as e:
        print("order_plan warning:", e)
        print("continuing with token generation...")

    token_result = None
    last_err = None
    for attempt in range(1, 4):
        try:
            token_result = p.x402.get_x402_access_token(
                plan_id=nvm_plan_id,
                agent_id=nvm_agent_id or None,
                redemption_limit=1,
            )
            break
        except Exception as e:
            last_err = e
            print(f"token attempt {attempt}/3 failed:", e)
            if attempt < 3:
                time.sleep(2 * attempt)
    if token_result is None:
        raise SystemExit(f"Failed to generate x402 access token after retries: {last_err}")

    token = token_result.get("accessToken", "")
    if not token:
        raise SystemExit("Failed to generate x402 access token.")
    print("token generated:", bool(token), "len:", len(token))

    # Local diagnostics: verify token against the same plan definition.
    try:
        network = "eip155:84532" if nvm_environment == "sandbox" else "eip155:8453"
        endpoint_url = endpoint
        payment_required = X402PaymentRequired(
            x402_version=2,
            resource=X402Resource(
                url=endpoint_url,
                description="AdAgent Studio paid campaign execution endpoint",
                mime_type="application/json",
            ),
            accepts=[
                X402Scheme(
                    scheme="nvm:erc4337",
                    network=network,
                    plan_id=nvm_plan_id,
                    extra=X402SchemeExtra(
                        version="1",
                        agent_id=nvm_agent_id or None,
                        http_verb="POST",
                    ),
                )
            ],
            extensions={},
        )
        verification = p.facilitator.verify_permissions(
            payment_required=payment_required,
            x402_access_token=token,
        )
        print("verify_permissions.is_valid:", verification.is_valid)
    except Exception as e:
        print("verify_permissions warning:", e)

    payload = {
        "brand": "TechStartup X",
        "goal": "drive signups",
        "audience": "SF tech founders 25-40",
        "budget": 15,
    }
    resp = requests.post(
        endpoint,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "payment-signature": token,
        },
        timeout=60,
    )

    print("status:", resp.status_code)
    try:
        print("response:", resp.json())
    except Exception:
        print("response_text:", resp.text[:500])


if __name__ == "__main__":
    main()

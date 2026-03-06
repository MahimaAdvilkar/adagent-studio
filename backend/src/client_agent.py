"""
Minimal buyer client for AdAgent Studio.

Generates an x402 token from Nevermined and calls the paid endpoint:
POST /api/run-campaign
"""

import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from payments_py import Payments, PaymentOptions


def main() -> None:
    # Load env from common project locations (backend/.env, root .ENV, root .env).
    src_dir = Path(__file__).resolve().parent
    backend_dir = src_dir.parent
    repo_dir = backend_dir.parent
    for env_path in [backend_dir / ".env", repo_dir / ".ENV", repo_dir / ".env"]:
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

    token_result = p.x402.get_x402_access_token(
        plan_id=nvm_plan_id,
        agent_id=nvm_agent_id or None,
        redemption_limit=1,
    )
    token = token_result.get("accessToken", "")
    if not token:
        raise SystemExit("Failed to generate x402 access token.")

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
